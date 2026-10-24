"""
metrics.py - 指标收集和监控
收集、记录和分析系统性能指标
"""

import logging
import time
import json
import csv
import statistics
import math
from typing import Dict, List, Any, Optional, Union, Callable, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum, auto
import threading
from threading import Lock, RLock
from pathlib import Path
import pickle
import numpy as np
from contextlib import contextmanager
import asyncio

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class MetricType(Enum):
    """指标类型"""
    COUNTER = auto()      # 计数器
    GAUGE = auto()        # 仪表（瞬时值）
    HISTOGRAM = auto()    # 直方图
    SUMMARY = auto()      # 摘要
    RATE = auto()         # 速率


class MetricAggregation(Enum):
    """指标聚合方式"""
    SUM = auto()          # 求和
    AVG = auto()          # 平均值
    MIN = auto()          # 最小值
    MAX = auto()          # 最大值
    COUNT = auto()        # 计数
    P50 = auto()          # 50百分位
    P90 = auto()          # 90百分位
    P95 = auto()          # 95百分位
    P99 = auto()          # 99百分位


@dataclass
class Metric:
    """基础指标"""
    name: str
    metric_type: MetricType
    value: Union[int, float]
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    description: Optional[str] = None
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（枚举值需转成字符串，否则无法 JSON 序列化）"""
        data = asdict(self)
        metric_type = data.get("metric_type")
        if isinstance(metric_type, MetricType):
            data["metric_type"] = metric_type.value
        elif hasattr(metric_type, "value"):
            data["metric_type"] = metric_type.value
        return data
    
    def to_prometheus(self) -> str:
        """转换为Prometheus格式"""
        labels_str = ""
        if self.labels:
            labels_list = [f'{k}="{v}"' for k, v in self.labels.items()]
            labels_str = "{" + ",".join(labels_list) + "}"
        
        return f"{self.name}{labels_str} {self.value}"


@dataclass
class TimeSeriesPoint:
    """时间序列数据点"""
    timestamp: str
    value: Union[int, float]
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricStatistics:
    """指标统计"""
    count: int
    sum: float
    avg: float
    min: float
    max: float
    std: float
    p50: float
    p90: float
    p95: float
    p99: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MetricsCollector:
    """
    指标收集器
    收集和管理系统指标
    """
    
    def __init__(self, collector_name: str = "default", 
                 enable_persistence: bool = True,
                 persistence_path: str = "./data/metrics"):
        """
        初始化指标收集器
        
        Args:
            collector_name: 收集器名称
            enable_persistence: 是否启用持久化
            persistence_path: 持久化路径
        """
        self.collector_name = collector_name
        self.logger = logging.getLogger(f"Metrics.{collector_name}")
        
        # 指标存储
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.time_series: Dict[str, List[TimeSeriesPoint]] = defaultdict(list)
        
        # 聚合数据
        self.aggregations: Dict[str, MetricStatistics] = {}
        
        # 配置
        self.enable_persistence = enable_persistence
        self.persistence_path = Path(persistence_path)
        
        if self.enable_persistence:
            self.persistence_path.mkdir(parents=True, exist_ok=True)
        
        # 线程安全
        self.lock = RLock()
        
        # 系统指标收集
        self.system_metrics_enabled = False
        self.system_metrics_task = None
        
        self.logger.info(f"指标收集器初始化完成: {collector_name}")
    
    def record(self, name: str, value: Union[int, float], 
               metric_type: MetricType = MetricType.GAUGE,
               labels: Optional[Dict[str, str]] = None,
               description: Optional[str] = None,
               unit: Optional[str] = None) -> Metric:
        """
        记录指标
        
        Args:
            name: 指标名称
            value: 指标值
            metric_type: 指标类型
            labels: 标签
            description: 描述
            unit: 单位
            
        Returns:
            记录的指标对象
        """
        with self.lock:
            metric = Metric(
                name=name,
                metric_type=metric_type,
                value=value,
                labels=labels or {},
                description=description,
                unit=unit
            )
            
            self.metrics[name].append(metric)
            
            # 同时记录为时间序列
            ts_point = TimeSeriesPoint(
                timestamp=metric.timestamp,
                value=value,
                labels=labels or {}
            )
            self.time_series[name].append(ts_point)
            
            # 更新聚合统计
            self._update_statistics(name, value)
            
            self.logger.debug(f"记录指标: {name} = {value}")
            return metric
    
    def _update_statistics(self, metric_name: str, value: float):
        """更新统计信息"""
        # 获取最近的值进行统计
        values = [m.value for m in self.metrics[metric_name][-1000:]]
        
        if len(values) < 2:
            return
        
        try:
            stats = MetricStatistics(
                count=len(values),
                sum=sum(values),
                avg=statistics.mean(values),
                min=min(values),
                max=max(values),
                std=statistics.stdev(values) if len(values) > 1 else 0,
                p50=np.percentile(values, 50) if len(values) >= 5 else statistics.median(values),
                p90=np.percentile(values, 90) if len(values) >= 10 else max(values),
                p95=np.percentile(values, 95) if len(values) >= 20 else max(values),
                p99=np.percentile(values, 99) if len(values) >= 100 else max(values)
            )
            
            self.aggregations[metric_name] = stats
            
        except Exception as e:
            self.logger.warning(f"更新统计信息失败: {metric_name} - {e}")
    
    def increment(self, name: str, value: int = 1, 
                  labels: Optional[Dict[str, str]] = None) -> Metric:
        """
        增加计数器
        
        Args:
            name: 计数器名称
            value: 增加值
            labels: 标签
            
        Returns:
            记录的指标对象
        """
        # 查找最近的计数器值
        last_value = 0
        with self.lock:
            if name in self.metrics:
                for metric in reversed(self.metrics[name]):
                    if metric.metric_type == MetricType.COUNTER:
                        last_value = metric.value
                        break
        
        new_value = last_value + value
        return self.record(name, new_value, MetricType.COUNTER, labels)
    
    def decrement(self, name: str, value: int = 1,
                  labels: Optional[Dict[str, str]] = None) -> Metric:
        """
        减少计数器
        
        Args:
            name: 计数器名称
            value: 减少值
            labels: 标签
            
        Returns:
            记录的指标对象
        """
        return self.increment(name, -value, labels)
    
    def gauge(self, name: str, value: Union[int, float],
              labels: Optional[Dict[str, str]] = None) -> Metric:
        """
        记录仪表值
        
        Args:
            name: 仪表名称
            value: 值
            labels: 标签
            
        Returns:
            记录的指标对象
        """
        return self.record(name, value, MetricType.GAUGE, labels)
    
    def histogram(self, name: str, value: Union[int, float],
                  labels: Optional[Dict[str, str]] = None) -> Metric:
        """
        记录直方图值
        
        Args:
            name: 直方图名称
            value: 值
            labels: 标签
            
        Returns:
            记录的指标对象
        """
        return self.record(name, value, MetricType.HISTOGRAM, labels)
    
    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """
        计时器上下文管理器
        
        Args:
            name: 计时器名称
            labels: 标签
        """
        @contextmanager
        def timer_context():
            start_time = time.perf_counter()
            try:
                yield
            finally:
                elapsed = time.perf_counter() - start_time
                self.record(name, elapsed, MetricType.HISTOGRAM, labels,
                          description=f"执行时间: {name}",
                          unit="seconds")
        
        return timer_context()
    
    async def async_timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """
        异步计时器上下文管理器
        
        Args:
            name: 计时器名称
            labels: 标签
        """
        @contextmanager
        async def async_timer_context():
            start_time = time.perf_counter()
            try:
                yield
            finally:
                elapsed = time.perf_counter() - start_time
                self.record(name, elapsed, MetricType.HISTOGRAM, labels,
                          description=f"执行时间: {name}",
                          unit="seconds")
        
        return async_timer_context()
    
    def start_system_metrics_collection(self, interval: float = 60.0):
        """
        开始收集系统指标
        
        Args:
            interval: 收集间隔(秒)
        """
        if not HAS_PSUTIL:
            self.logger.warning("psutil未安装，无法收集系统指标")
            return
        
        self.system_metrics_enabled = True
        
        async def collect_system_metrics():
            while self.system_metrics_enabled:
                try:
                    await self._collect_system_metrics_once()
                    await asyncio.sleep(interval)
                except Exception as e:
                    self.logger.error(f"收集系统指标失败: {e}")
                    await asyncio.sleep(interval)
        
        # 启动后台任务
        self.system_metrics_task = asyncio.create_task(collect_system_metrics())
        self.logger.info(f"系统指标收集已启动，间隔: {interval}秒")
    
    def stop_system_metrics_collection(self):
        """停止收集系统指标"""
        self.system_metrics_enabled = False
        if self.system_metrics_task:
            self.system_metrics_task.cancel()
            self.system_metrics_task = None
        self.logger.info("系统指标收集已停止")
    
    async def _collect_system_metrics_once(self):
        """收集一次系统指标"""
        if not HAS_PSUTIL:
            return
        
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.gauge("system_cpu_percent", cpu_percent,
                  {"type": "total", "collector": self.collector_name})
        
        # 内存使用
        memory = psutil.virtual_memory()
        self.gauge("system_memory_total", memory.total,
                  {"collector": self.collector_name})
        self.gauge("system_memory_available", memory.available,
                  {"collector": self.collector_name})
        self.gauge("system_memory_percent", memory.percent,
                  {"collector": self.collector_name})
        
        # 磁盘使用
        disk = psutil.disk_usage('/')
        self.gauge("system_disk_total", disk.total,
                  {"mount": "/", "collector": self.collector_name})
        self.gauge("system_disk_used", disk.used,
                  {"mount": "/", "collector": self.collector_name})
        self.gauge("system_disk_percent", disk.percent,
                  {"mount": "/", "collector": self.collector_name})
        
        # 网络IO
        net_io = psutil.net_io_counters()
        self.gauge("system_network_bytes_sent", net_io.bytes_sent,
                  {"collector": self.collector_name})
        self.gauge("system_network_bytes_recv", net_io.bytes_recv,
                  {"collector": self.collector_name})
        
        # 进程信息
        process = psutil.Process()
        self.gauge("system_process_cpu_percent", process.cpu_percent(),
                  {"collector": self.collector_name})
        self.gauge("system_process_memory_rss", process.memory_info().rss,
                  {"collector": self.collector_name})
        self.gauge("system_process_memory_percent", process.memory_percent(),
                  {"collector": self.collector_name})
    
    def get_metric(self, name: str, limit: Optional[int] = None) -> List[Metric]:
        """
        获取指标数据
        
        Args:
            name: 指标名称
            limit: 限制返回数量
            
        Returns:
            指标列表
        """
        with self.lock:
            metrics = self.metrics.get(name, [])
            if limit and limit > 0:
                return metrics[-limit:]
            return metrics
    
    def get_time_series(self, name: str, start_time: Optional[str] = None,
                        end_time: Optional[str] = None) -> List[TimeSeriesPoint]:
        """
        获取时间序列数据
        
        Args:
            name: 指标名称
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            时间序列数据点列表
        """
        with self.lock:
            series = self.time_series.get(name, [])
            
            if not start_time and not end_time:
                return series
            
            filtered = []
            for point in series:
                point_time = datetime.fromisoformat(point.timestamp.replace('Z', '+00:00'))
                
                if start_time:
                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    if point_time < start:
                        continue
                
                if end_time:
                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    if point_time > end:
                        continue
                
                filtered.append(point)
            
            return filtered
    
    def get_statistics(self, name: str) -> Optional[MetricStatistics]:
        """
        获取指标统计
        
        Args:
            name: 指标名称
            
        Returns:
            指标统计，不存在则返回None
        """
        with self.lock:
            return self.aggregations.get(name)
    
    def aggregate(self, name: str, 
                  aggregation: MetricAggregation,
                  start_time: Optional[str] = None,
                  end_time: Optional[str] = None) -> Optional[float]:
        """
        聚合指标数据
        
        Args:
            name: 指标名称
            aggregation: 聚合方式
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            聚合值，失败则返回None
        """
        series = self.get_time_series(name, start_time, end_time)
        
        if not series:
            return None
        
        values = [point.value for point in series]
        
        try:
            if aggregation == MetricAggregation.SUM:
                return sum(values)
            elif aggregation == MetricAggregation.AVG:
                return statistics.mean(values)
            elif aggregation == MetricAggregation.MIN:
                return min(values)
            elif aggregation == MetricAggregation.MAX:
                return max(values)
            elif aggregation == MetricAggregation.COUNT:
                return len(values)
            elif aggregation == MetricAggregation.P50:
                return np.percentile(values, 50)
            elif aggregation == MetricAggregation.P90:
                return np.percentile(values, 90)
            elif aggregation == MetricAggregation.P95:
                return np.percentile(values, 95)
            elif aggregation == MetricAggregation.P99:
                return np.percentile(values, 99)
            else:
                return None
                
        except Exception as e:
            self.logger.warning(f"聚合指标失败: {name} - {e}")
            return None
    
    def get_all_metrics(self) -> Dict[str, List[Metric]]:
        """获取所有指标"""
        with self.lock:
            return dict(self.metrics)
    
    def get_all_statistics(self) -> Dict[str, MetricStatistics]:
        """获取所有统计"""
        with self.lock:
            return dict(self.aggregations)
    
    def clear_metrics(self, name: Optional[str] = None):
        """
        清除指标数据
        
        Args:
            name: 指标名称，如果为None则清除所有指标
        """
        with self.lock:
            if name:
                if name in self.metrics:
                    del self.metrics[name]
                if name in self.time_series:
                    del self.time_series[name]
                if name in self.aggregations:
                    del self.aggregations[name]
                self.logger.info(f"清除指标: {name}")
            else:
                self.metrics.clear()
                self.time_series.clear()
                self.aggregations.clear()
                self.logger.info("清除所有指标")
    
    def export_to_json(self, filepath: Optional[str] = None) -> str:
        """
        导出为JSON
        
        Args:
            filepath: 文件路径，如果为None则返回JSON字符串
            
        Returns:
            JSON字符串（如果filepath为None）
        """
        export_data = {
            "collector_name": self.collector_name,
            "export_time": datetime.now().isoformat(),
            "metrics": {},
            "statistics": {}
        }
        
        with self.lock:
            for name, metrics in self.metrics.items():
                export_data["metrics"][name] = [m.to_dict() for m in metrics]
            
            for name, stats in self.aggregations.items():
                export_data["statistics"][name] = asdict(stats)
        
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2, default=str)
        
        if filepath:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)
            
            self.logger.info(f"指标已导出到JSON: {filepath}")
        
        return json_str
    
    def export_to_csv(self, filepath: str, metric_names: Optional[List[str]] = None):
        """
        导出为CSV
        
        Args:
            filepath: 文件路径
            metric_names: 要导出的指标名称列表，如果为None则导出所有
        """
        with self.lock:
            if metric_names is None:
                metric_names = list(self.metrics.keys())
            
            if not metric_names:
                self.logger.warning("没有指标可导出")
                return
            
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                
                # 写入标题
                headers = ['timestamp', 'metric_name', 'value', 'labels', 'type']
                writer.writerow(headers)
                
                # 写入数据
                for name in metric_names:
                    metrics = self.metrics.get(name, [])
                    for metric in metrics:
                        row = [
                            metric.timestamp,
                            metric.name,
                            metric.value,
                            json.dumps(metric.labels, ensure_ascii=False),
                            metric.metric_type.name
                        ]
                        writer.writerow(row)
            
            self.logger.info(f"指标已导出到CSV: {filepath}")
    
    def save_state(self, filepath: Optional[str] = None) -> bool:
        """
        保存状态到文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否成功
        """
        if not self.enable_persistence:
            self.logger.warning("持久化功能已禁用")
            return False
        
        try:
            if filepath is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = self.persistence_path / f"metrics_{self.collector_name}_{timestamp}.pkl"
            else:
                filepath = Path(filepath)
            
            state_data = {
                "collector_name": self.collector_name,
                "metrics": dict(self.metrics),
                "time_series": dict(self.time_series),
                "aggregations": dict(self.aggregations),
                "saved_at": datetime.now().isoformat()
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(state_data, f)
            
            self.logger.info(f"指标状态已保存: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存指标状态失败: {e}")
            return False
    
    def load_state(self, filepath: str) -> bool:
        """
        从文件加载状态
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否成功
        """
        try:
            with open(filepath, 'rb') as f:
                state_data = pickle.load(f)
            
            self.metrics = defaultdict(list, state_data.get("metrics", {}))
            self.time_series = defaultdict(list, state_data.get("time_series", {}))
            self.aggregations = state_data.get("aggregations", {})
            
            self.logger.info(f"指标状态已加载: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"加载指标状态失败: {e}")
            return False
    
    def generate_report(self, 
                        metric_names: Optional[List[str]] = None,
                        start_time: Optional[str] = None,
                        end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        生成指标报告
        
        Args:
            metric_names: 指标名称列表，如果为None则包含所有
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            指标报告
        """
        with self.lock:
            if metric_names is None:
                metric_names = list(self.metrics.keys())
            
            report = {
                "collector_name": self.collector_name,
                "report_time": datetime.now().isoformat(),
                "time_range": {
                    "start": start_time,
                    "end": end_time
                },
                "metrics_summary": {},
                "overall_statistics": {}
            }
            
            total_metrics = 0
            total_points = 0
            
            for name in metric_names:
                metrics = self.get_metric(name)
                series = self.get_time_series(name, start_time, end_time)
                
                if not metrics:
                    continue
                
                # 统计信息
                values = [point.value for point in series]
                
                if values:
                    stats = {
                        "count": len(values),
                        "sum": sum(values),
                        "avg": statistics.mean(values),
                        "min": min(values),
                        "max": max(values),
                        "latest": metrics[-1].value if metrics else 0
                    }
                    
                    report["metrics_summary"][name] = stats
                    
                    total_metrics += 1
                    total_points += len(values)
            
            # 总体统计
            report["overall_statistics"] = {
                "total_metrics": total_metrics,
                "total_data_points": total_points,
                "time_span": self._calculate_time_span(start_time, end_time)
            }
            
            return report
    
    def _calculate_time_span(self, start_time: Optional[str], end_time: Optional[str]) -> str:
        """计算时间跨度"""
        if not start_time or not end_time:
            return "unknown"
        
        try:
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            delta = end - start
            
            if delta.days > 0:
                return f"{delta.days}天{delta.seconds // 3600}小时"
            elif delta.seconds >= 3600:
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                return f"{hours}小时{minutes}分钟"
            elif delta.seconds >= 60:
                minutes = delta.seconds // 60
                seconds = delta.seconds % 60
                return f"{minutes}分钟{seconds}秒"
            else:
                return f"{delta.seconds}秒"
        except:
            return "unknown"


class MetricsRegistry:
    """
    指标注册表
    管理多个指标收集器
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.collectors: Dict[str, MetricsCollector] = {}
        self.default_collector: Optional[MetricsCollector] = None
        self.lock = Lock()
        
        # 创建默认收集器
        self.create_collector("default", set_as_default=True)
        
        self._initialized = True
    
    def create_collector(self, name: str, set_as_default: bool = False) -> MetricsCollector:
        """
        创建指标收集器
        
        Args:
            name: 收集器名称
            set_as_default: 是否设置为默认收集器
            
        Returns:
            创建的收集器
        """
        with self.lock:
            if name in self.collectors:
                raise ValueError(f"收集器已存在: {name}")
            
            collector = MetricsCollector(name)
            self.collectors[name] = collector
            
            if set_as_default or self.default_collector is None:
                self.default_collector = collector
            
            return collector
    
    def get_collector(self, name: Optional[str] = None) -> MetricsCollector:
        """
        获取指标收集器
        
        Args:
            name: 收集器名称，如果为None则返回默认收集器
            
        Returns:
            指标收集器
        """
        with self.lock:
            if name is None:
                if self.default_collector is None:
                    self.default_collector = self.create_collector("default")
                return self.default_collector
            
            if name not in self.collectors:
                raise ValueError(f"收集器不存在: {name}")
            
            return self.collectors[name]
    
    def set_default_collector(self, name: str):
        """
        设置默认收集器
        
        Args:
            name: 收集器名称
        """
        with self.lock:
            if name not in self.collectors:
                raise ValueError(f"收集器不存在: {name}")
            
            self.default_collector = self.collectors[name]
    
    def remove_collector(self, name: str):
        """
        移除指标收集器
        
        Args:
            name: 收集器名称
        """
        with self.lock:
            if name not in self.collectors:
                return
            
            if self.default_collector == self.collectors[name]:
                self.default_collector = None
            
            del self.collectors[name]
            
            # 如果默认收集器被移除，设置另一个为默认
            if self.default_collector is None and self.collectors:
                self.default_collector = next(iter(self.collectors.values()))
    
    def get_all_collectors(self) -> Dict[str, MetricsCollector]:
        """获取所有收集器"""
        with self.lock:
            return dict(self.collectors)
    
    def export_all(self, base_path: str):
        """
        导出所有收集器的数据
        
        Args:
            base_path: 基础路径
        """
        base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)
        
        with self.lock:
            for name, collector in self.collectors.items():
                collector_path = base_path / name
                collector_path.mkdir(exist_ok=True)
                
                # 导出JSON
                json_file = collector_path / f"{name}_metrics.json"
                collector.export_to_json(str(json_file))
                
                # 导出CSV
                csv_file = collector_path / f"{name}_metrics.csv"
                collector.export_to_csv(str(csv_file))
    
    def generate_global_report(self) -> Dict[str, Any]:
        """
        生成全局报告
        
        Returns:
            全局报告
        """
        with self.lock:
            report = {
                "report_time": datetime.now().isoformat(),
                "total_collectors": len(self.collectors),
                "collectors": [],
                "global_statistics": {
                    "total_metrics": 0,
                    "total_data_points": 0
                }
            }
            
            for name, collector in self.collectors.items():
                collector_report = collector.generate_report()
                
                report["collectors"].append({
                    "name": name,
                    "is_default": collector == self.default_collector,
                    "metrics_count": len(collector.metrics),
                    "data_points": sum(len(metrics) for metrics in collector.metrics.values())
                })
                
                report["global_statistics"]["total_metrics"] += len(collector.metrics)
                report["global_statistics"]["total_data_points"] += sum(
                    len(metrics) for metrics in collector.metrics.values()
                )
            
            return report


# 全局指标注册表实例
_metrics_registry = None

def get_metrics_registry() -> MetricsRegistry:
    """获取全局指标注册表"""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


def record_metric(name: str, value: Union[int, float], 
                  collector_name: Optional[str] = None, **kwargs) -> Metric:
    """
    记录指标（快捷函数）
    
    Args:
        name: 指标名称
        value: 指标值
        collector_name: 收集器名称
        **kwargs: 其他参数
        
    Returns:
        记录的指标对象
    """
    registry = get_metrics_registry()
    collector = registry.get_collector(collector_name)
    return collector.record(name, value, **kwargs)


def increment_counter(name: str, value: int = 1,
                      collector_name: Optional[str] = None, **kwargs) -> Metric:
    """
    增加计数器（快捷函数）
    
    Args:
        name: 计数器名称
        value: 增加值
        collector_name: 收集器名称
        **kwargs: 其他参数
        
    Returns:
        记录的指标对象
    """
    registry = get_metrics_registry()
    collector = registry.get_collector(collector_name)
    return collector.increment(name, value, **kwargs)


def timer_decorator(name: str, collector_name: Optional[str] = None):
    """
    计时器装饰器
    
    Args:
        name: 计时器名称
        collector_name: 收集器名称
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            registry = get_metrics_registry()
            collector = registry.get_collector(collector_name)
            
            with collector.timer(name):
                return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            registry = get_metrics_registry()
            collector = registry.get_collector(collector_name)
            
            async with collector.async_timer(name):
                return await func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
    return decorator


# 导出主要类和函数
__all__ = [
    "MetricType",
    "MetricAggregation",
    "Metric",
    "TimeSeriesPoint",
    "MetricStatistics",
    "MetricsCollector",
    "MetricsRegistry",
    "get_metrics_registry",
    "record_metric",
    "increment_counter",
    "timer_decorator"
]