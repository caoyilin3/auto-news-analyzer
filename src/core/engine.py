"""
系统核心引擎
负责协调所有模块的工作流
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import concurrent.futures


class EngineState(Enum):
    """引擎状态枚举"""
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class WorkflowStep:
    """工作流步骤定义"""
    name: str
    module: str
    function: str
    enabled: bool = True
    timeout: int = 300  # 秒
    retry_count: int = 3
    dependencies: List[str] = field(default_factory=list)


class SystemEngine:
    """系统核心引擎"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化系统引擎
        
        Args:
            config: 系统配置
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.state = EngineState.INITIALIZED
        
        # 工作流定义
        self.workflow_steps = self._define_workflow_steps()
        
        # 模块实例
        self.modules = {}
        
        # 执行器
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
        # 统计信息
        self.metrics = {
            "total_cycles": 0,
            "successful_cycles": 0,
            "failed_cycles": 0,
            "total_processing_time": 0.0,
            "last_run_time": None,
        }
        
        # 回调函数
        self.callbacks = {
            "before_step": [],
            "after_step": [],
            "before_cycle": [],
            "after_cycle": [],
            "on_error": [],
        }
        
        self.logger.info("系统引擎初始化完成")
    
    def _define_workflow_steps(self) -> List[WorkflowStep]:
        """定义工作流步骤"""
        return [
            WorkflowStep(
                name="data_acquisition",
                module="data_acquisition",
                function="collect_data",
                enabled=True,
                timeout=600,
                retry_count=3,
                dependencies=[],
            ),
            WorkflowStep(
                name="credibility_assessment",
                module="credibility",
                function="assess_credibility",
                enabled=True,
                timeout=300,
                retry_count=2,
                dependencies=["data_acquisition"],
            ),
            WorkflowStep(
                name="knowledge_extraction",
                module="knowledge",
                function="extract_knowledge",
                enabled=True,
                timeout=600,
                retry_count=2,
                dependencies=["credibility_assessment"],
            ),
            WorkflowStep(
                name="evolution_learning",
                module="evolution",
                function="learn_and_adapt",
                enabled=self.config.get("evolution", {}).get("enabled", True),
                timeout=300,
                retry_count=1,
                dependencies=["knowledge_extraction"],
            ),
            WorkflowStep(
                name="memory_management",
                module="memory",
                function="manage_memory",
                enabled=self.config.get("memory", {}).get("enabled", True),
                timeout=300,
                retry_count=2,
                dependencies=["knowledge_extraction"],
            ),
            WorkflowStep(
                name="report_generation",
                module="interfaces",
                function="generate_report",
                enabled=True,
                timeout=180,
                retry_count=1,
                dependencies=["knowledge_extraction", "memory_management"],
            ),
        ]
    
    def initialize_modules(self) -> bool:
        """初始化所有模块"""
        self.logger.info("初始化系统模块...")
        
        try:
            # 数据采集模块
            from ..data_acquisition.manager import DataAcquisitionManager
            self.modules["data_acquisition"] = DataAcquisitionManager(
                self.config.get("crawler", {})
            )
            
            # 可信度评估模块
            from ..credibility.evaluator import CredibilityEvaluator
            self.modules["credibility"] = CredibilityEvaluator(
                self.config.get("credibility", {})
            )
            
            # 知识管理模块
            from ..knowledge.manager import KnowledgeManager
            self.modules["knowledge"] = KnowledgeManager(
                self.config.get("knowledge", {})
            )
            
            # 进化学习模块
            from ..evolution.manager import EvolutionManager
            self.modules["evolution"] = EvolutionManager(
                self.config.get("evolution", {})
            )
            
            # 记忆管理模块
            from ..memory.manager import MemoryManager
            self.modules["memory"] = MemoryManager(
                self.config.get("memory", {})
            )
            
            # 接口模块
            from ..interfaces.reporter import ReportGenerator
            self.modules["interfaces"] = ReportGenerator(
                self.config.get("reporting", {})
            )
            
            self.logger.info("所有模块初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"模块初始化失败: {e}")
            self.state = EngineState.ERROR
            return False
    
    def register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"已注册回调函数到事件: {event}")
        else:
            self.logger.warning(f"未知的事件类型: {event}")
    
    def execute_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个工作流步骤
        
        Args:
            step: 工作流步骤
            context: 执行上下文
            
        Returns:
            执行结果
        """
        if not step.enabled:
            self.logger.debug(f"跳过禁用的步骤: {step.name}")
            return {"status": "skipped", "step": step.name}
        
        self.logger.info(f"执行步骤: {step.name}")
        
        # 调用前置回调
        for callback in self.callbacks["before_step"]:
            callback(step, context)
        
        result = {
            "step": step.name,
            "start_time": datetime.now().isoformat(),
            "status": "unknown",
            "error": None,
            "duration": 0.0,
            "data": {},
        }
        
        try:
            # 检查依赖是否满足
            for dep in step.dependencies:
                if dep not in context.get("completed_steps", []):
                    raise Exception(f"依赖步骤未完成: {dep}")
            
            # 获取模块和函数
            module = self.modules.get(step.module)
            if not module:
                raise Exception(f"模块未找到: {step.module}")
            
            func = getattr(module, step.function, None)
            if not func:
                raise Exception(f"函数未找到: {step.function}")
            
            # 执行函数
            start_time = time.time()
            
            # 根据函数类型决定执行方式
            if asyncio.iscoroutinefunction(func):
                # 异步函数
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    step_result = loop.run_until_complete(func(context.get("data", {})))
                finally:
                    loop.close()
            else:
                # 同步函数
                step_result = func(context.get("data", {}))
            
            execution_time = time.time() - start_time
            result["duration"] = execution_time
            
            # 处理结果
            if isinstance(step_result, dict):
                result["data"] = step_result
                result["status"] = step_result.get("status", "completed")
            else:
                result["data"] = {"result": step_result}
                result["status"] = "completed"
            
            self.logger.info(f"步骤完成: {step.name} (耗时: {execution_time:.2f}秒)")
            
        except Exception as e:
            self.logger.error(f"步骤执行失败: {step.name} - {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            
            # 调用错误回调
            for callback in self.callbacks["on_error"]:
                callback(step, context, e)
        
        # 调用后置回调
        for callback in self.callbacks["after_step"]:
            callback(step, context, result)
        
        result["end_time"] = datetime.now().isoformat()
        return result
    
    def run_workflow(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行完整的工作流
        
        Args:
            input_data: 输入数据
            
        Returns:
            工作流执行结果
        """
        if self.state == EngineState.RUNNING:
            raise Exception("引擎已经在运行中")
        
        self.state = EngineState.RUNNING
        self.logger.info("开始执行工作流")
        
        # 初始化上下文
        context = {
            "start_time": datetime.now().isoformat(),
            "data": input_data or {},
            "completed_steps": [],
            "step_results": [],
            "errors": [],
        }
        
        # 调用前置回调
        for callback in self.callbacks["before_cycle"]:
            callback(context)
        
        overall_result = {
            "workflow_id": f"wf_{int(time.time())}",
            "status": "running",
            "context": context,
            "metrics": {},
        }
        
        try:
            # 按顺序执行工作流步骤
            for step in self.workflow_steps:
                if self.state != EngineState.RUNNING:
                    self.logger.warning("工作流被中断")
                    break
                
                # 执行步骤（带重试机制）
                step_result = None
                for attempt in range(step.retry_count + 1):
                    step_result = self.execute_step(step, context)
                    
                    if step_result["status"] in ["completed", "skipped"]:
                        break
                    elif attempt < step.retry_count:
                        self.logger.warning(f"步骤 {step.name} 失败，重试 {attempt + 1}/{step.retry_count}")
                        time.sleep(2 ** attempt)  # 指数退避
                
                # 记录步骤结果
                context["step_results"].append(step_result)
                
                if step_result["status"] == "completed":
                    context["completed_steps"].append(step.name)
                    # 合并步骤数据到上下文
                    if "data" in step_result:
                        context["data"].update(step_result["data"])
                elif step_result["status"] == "failed":
                    context["errors"].append({
                        "step": step.name,
                        "error": step_result["error"]
                    })
                    
                    # 根据配置决定是否继续
                    if self.config.get("workflow", {}).get("continue_on_error", False):
                        self.logger.warning(f"步骤 {step.name} 失败，继续执行后续步骤")
                    else:
                        self.logger.error(f"步骤 {step.name} 失败，停止工作流")
                        overall_result["status"] = "failed"
                        break
            
            # 更新总体状态
            if overall_result["status"] != "failed":
                if context["errors"]:
                    overall_result["status"] = "completed_with_errors"
                else:
                    overall_result["status"] = "completed"
            
            # 计算指标
            overall_result["metrics"] = self._calculate_metrics(context)
            
            # 更新引擎统计
            self.metrics["total_cycles"] += 1
            if overall_result["status"] == "completed":
                self.metrics["successful_cycles"] += 1
            else:
                self.metrics["failed_cycles"] += 1
            self.metrics["last_run_time"] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.error(f"工作流执行异常: {e}")
            overall_result["status"] = "failed"
            overall_result["error"] = str(e)
            self.state = EngineState.ERROR
        
        finally:
            context["end_time"] = datetime.now().isoformat()
            overall_result["context"] = context
            
            # 调用后置回调
            for callback in self.callbacks["after_cycle"]:
                callback(context, overall_result)
            
            if self.state != EngineState.ERROR:
                self.state = EngineState.STOPPED
            
            self.logger.info(f"工作流执行完成，状态: {overall_result['status']}")
        
        return overall_result
    
    def _calculate_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """计算工作流指标"""
        metrics = {
            "total_steps": len(context["step_results"]),
            "completed_steps": len([r for r in context["step_results"] if r["status"] == "completed"]),
            "skipped_steps": len([r for r in context["step_results"] if r["status"] == "skipped"]),
            "failed_steps": len([r for r in context["step_results"] if r["status"] == "failed"]),
            "total_duration": 0.0,
            "step_durations": {},
        }
        
        # 计算总耗时
        if context.get("start_time") and context.get("end_time"):
            start = datetime.fromisoformat(context["start_time"])
            end = datetime.fromisoformat(context["end_time"])
            metrics["total_duration"] = (end - start).total_seconds()
        
        # 收集各步骤耗时
        for result in context["step_results"]:
            step_name = result["step"]
            duration = result.get("duration", 0.0)
            metrics["step_durations"][step_name] = duration
            metrics["total_duration"] += duration
        
        return metrics
    
    def run_continuous(self, interval: int = 3600, max_cycles: int = None):
        """
        连续运行工作流
        
        Args:
            interval: 运行间隔（秒）
            max_cycles: 最大运行次数
        """
        self.logger.info(f"开始连续运行，间隔: {interval}秒，最大次数: {max_cycles or '无限'}")
        
        cycle_count = 0
        self.state = EngineState.RUNNING
        
        try:
            while self.state == EngineState.RUNNING:
                if max_cycles and cycle_count >= max_cycles:
                    self.logger.info(f"达到最大运行次数: {max_cycles}")
                    break
                
                cycle_count += 1
                self.logger.info(f"开始第 {cycle_count} 个周期")
                
                # 运行工作流
                result = self.run_workflow()
                
                # 检查结果
                if result["status"] == "failed":
                    self.logger.error("工作流失败，停止连续运行")
                    break
                
                # 等待下一个周期
                if self.state == EngineState.RUNNING and cycle_count < (max_cycles or float('inf')):
                    self.logger.info(f"等待 {interval} 秒后开始下一个周期...")
                    
                    # 分段等待，以便能够响应停止请求
                    for _ in range(interval):
                        if self.state != EngineState.RUNNING:
                            break
                        time.sleep(1)
                        
        except KeyboardInterrupt:
            self.logger.info("用户中断连续运行")
        except Exception as e:
            self.logger.error(f"连续运行异常: {e}")
        finally:
            self.state = EngineState.STOPPED
            self.logger.info(f"连续运行结束，共执行 {cycle_count} 个周期")
    
    def stop(self):
        """停止引擎"""
        self.logger.info("停止系统引擎...")
        self.state = EngineState.STOPPING
        
        # 等待当前工作流完成
        time.sleep(1)
        
        self.state = EngineState.STOPPED
        self.logger.info("系统引擎已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        return {
            "state": self.state.value,
            "metrics": self.metrics,
            "modules": {name: module.get_status() if hasattr(module, 'get_status') else "unknown" 
                    for name, module in self.modules.items()},
            "workflow_steps": [step.name for step in self.workflow_steps if step.enabled],
            "timestamp": datetime.now().isoformat(),
        }
    
    def shutdown(self):
        """关闭引擎，释放资源"""
        self.logger.info("关闭系统引擎...")
        
        self.stop()
        
        # 关闭执行器
        self.executor.shutdown(wait=True)
        
        # 关闭所有模块
        for name, module in self.modules.items():
            if hasattr(module, 'shutdown'):
                try:
                    module.shutdown()
                    self.logger.debug(f"已关闭模块: {name}")
                except Exception as e:
                    self.logger.error(f"关闭模块 {name} 失败: {e}")
        
        self.logger.info("系统引擎已关闭")