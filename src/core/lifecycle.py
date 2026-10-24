"""
系统生命周期管理器
管理系统的启动、运行、维护和关闭
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import concurrent.futures
import traceback


class LifecycleState(Enum):
    """生命周期状态枚举"""
    UNINITIALIZED = "uninitialized"      # 未初始化
    INITIALIZING = "initializing"        # 初始化中
    INITIALIZED = "initialized"          # 已初始化
    STARTING = "starting"                # 启动中
    RUNNING = "running"                  # 运行中
    STOPPING = "stopping"                # 停止中
    STOPPED = "stopped"                  # 已停止
    ERROR = "error"                      # 错误状态
    MAINTENANCE = "maintenance"          # 维护中
    RECOVERING = "recovering"            # 恢复中


class LifecycleEvent(Enum):
    """生命周期事件枚举"""
    BEFORE_INIT = "before_init"          # 初始化前
    AFTER_INIT = "after_init"            # 初始化后
    BEFORE_START = "before_start"        # 启动前
    AFTER_START = "after_start"          # 启动后
    BEFORE_STOP = "before_stop"          # 停止前
    AFTER_STOP = "after_stop"            # 停止后
    BEFORE_SHUTDOWN = "before_shutdown"  # 关闭前
    AFTER_SHUTDOWN = "after_shutdown"    # 关闭后
    ERROR = "error"                      # 错误事件
    RECOVERY = "recovery"                # 恢复事件
    MAINTENANCE_START = "maintenance_start"  # 维护开始
    MAINTENANCE_END = "maintenance_end"  # 维护结束


@dataclass
class LifecycleComponent:
    """生命周期组件定义"""
    name: str
    component: Any
    priority: int = 5  # 1-10，数字越小优先级越高
    auto_initialize: bool = True
    auto_start: bool = True
    auto_stop: bool = True
    dependencies: List[str] = field(default_factory=list)
    initialized: bool = False
    started: bool = False
    error_count: int = 0
    last_error: Optional[str] = None
    last_activity: Optional[datetime] = None


@dataclass
class MaintenanceTask:
    """维护任务定义"""
    name: str
    description: str
    task_func: Callable
    schedule: str  # cron表达式或时间间隔
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True
    concurrent: bool = False  # 是否允许并发执行


class SystemLifecycleManager:
    """系统生命周期管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化生命周期管理器
        
        Args:
            config: 管理器配置
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 系统状态
        self.state = LifecycleState.UNINITIALIZED
        self.state_lock = threading.RLock()
        
        # 组件管理
        self.components: Dict[str, LifecycleComponent] = {}
        self.component_dag = {}  # 依赖关系图
        self.failed_components: List[str] = []
        
        # 维护任务
        self.maintenance_tasks: Dict[str, MaintenanceTask] = {}
        self.maintenance_enabled = self.config.get("maintenance_enabled", True)
        self.maintenance_interval = self.config.get("maintenance_interval", 3600)  # 秒
        
        # 恢复配置
        self.recovery_enabled = self.config.get("recovery_enabled", True)
        self.max_recovery_attempts = self.config.get("max_recovery_attempts", 3)
        self.recovery_delay = self.config.get("recovery_delay", 5)  # 秒
        
        # 健康检查
        self.health_check_enabled = self.config.get("health_check_enabled", True)
        self.health_check_interval = self.config.get("health_check_interval", 60)  # 秒
        
        # 信号处理
        self.signal_handlers_installed = False
        
        # 回调函数
        self.callbacks: Dict[LifecycleEvent, List[Callable]] = {
            LifecycleEvent.BEFORE_INIT: [],
            LifecycleEvent.AFTER_INIT: [],
            LifecycleEvent.BEFORE_START: [],
            LifecycleEvent.AFTER_START: [],
            LifecycleEvent.BEFORE_STOP: [],
            LifecycleEvent.AFTER_STOP: [],
            LifecycleEvent.BEFORE_SHUTDOWN: [],
            LifecycleEvent.AFTER_SHUTDOWN: [],
            LifecycleEvent.ERROR: [],
            LifecycleEvent.RECOVERY: [],
            LifecycleEvent.MAINTENANCE_START: [],
            LifecycleEvent.MAINTENANCE_END: [],
        }
        
        # 统计信息
        self.stats = {
            "start_time": None,
            "uptime": 0,
            "total_initializations": 0,
            "total_starts": 0,
            "total_stops": 0,
            "total_errors": 0,
            "total_recoveries": 0,
            "total_maintenance": 0,
            "component_errors": {},
            "last_event": None,
        }
        
        # 执行器
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 10)
        )
        
        # 后台任务
        self.background_tasks = []
        self.is_running = False
        
        # 初始化信号处理
        self._setup_signal_handlers()
        
        self.logger.info("系统生命周期管理器初始化完成")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        if self.signal_handlers_installed:
            return
        
        try:
            # SIGINT (Ctrl+C)
            signal.signal(signal.SIGINT, self._handle_shutdown_signal)
            
            # SIGTERM (终止信号)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
            
            # SIGUSR1/SIGUSR2 仅在 Unix 上存在，Windows 下跳过（此前会导致整体注册失败）
            if hasattr(signal, "SIGUSR1"):
                signal.signal(signal.SIGUSR1, self._handle_maintenance_signal)
            
            if hasattr(signal, "SIGUSR2"):
                signal.signal(signal.SIGUSR2, self._handle_recovery_signal)
            
            self.signal_handlers_installed = True
            self.logger.debug("信号处理器已设置")
            
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"无法设置信号处理器: {e}")
    
    def _handle_shutdown_signal(self, signum, frame):
        """处理关闭信号"""
        signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        self.logger.info(f"收到关闭信号: {signal_name}")
        
        # 优雅关闭
        self.shutdown()
    
    def _handle_maintenance_signal(self, signum, frame):
        """处理维护信号"""
        self.logger.info("收到维护信号，进入维护模式")
        self.enter_maintenance_mode()
    
    def _handle_recovery_signal(self, signum, frame):
        """处理恢复信号"""
        self.logger.info("收到恢复信号，尝试恢复")
        self.attempt_recovery()
    
    def register_component(self, name: str, component: Any, 
                          priority: int = 5, auto_initialize: bool = True,
                          auto_start: bool = True, auto_stop: bool = True,
                          dependencies: List[str] = None) -> bool:
        """
        注册组件
        
        Args:
            name: 组件名称
            component: 组件对象
            priority: 优先级（1-10，数字越小优先级越高）
            auto_initialize: 是否自动初始化
            auto_start: 是否自动启动
            auto_stop: 是否自动停止
            dependencies: 依赖的组件名称列表
            
        Returns:
            是否成功注册
        """
        with self.state_lock:
            if name in self.components:
                self.logger.warning(f"组件已存在: {name}")
                return False
            
            comp = LifecycleComponent(
                name=name,
                component=component,
                priority=priority,
                auto_initialize=auto_initialize,
                auto_start=auto_start,
                auto_stop=auto_stop,
                dependencies=dependencies or [],
            )
            
            self.components[name] = comp
            
            # 更新依赖关系图
            self.component_dag[name] = dependencies or []
            
            self.logger.info(f"已注册组件: {name} (优先级: {priority})")
            
            # 如果系统已经在运行，且组件配置为自动初始化/启动
            if self.state == LifecycleState.RUNNING:
                if auto_initialize and not comp.initialized:
                    self._initialize_component(name)
                
                if auto_start and comp.initialized and not comp.started:
                    self._start_component(name)
            
            return True
    
    def unregister_component(self, name: str, force: bool = False) -> bool:
        """
        注销组件
        
        Args:
            name: 组件名称
            force: 是否强制注销（即使组件正在运行）
            
        Returns:
            是否成功注销
        """
        with self.state_lock:
            if name not in self.components:
                return False
            
            comp = self.components[name]
            
            # 检查组件状态
            if (comp.started or comp.initialized) and not force:
                self.logger.error(f"组件 {name} 正在运行，无法注销")
                return False
            
            # 停止组件
            if comp.started:
                self._stop_component(name)
            
            # 注销组件
            del self.components[name]
            del self.component_dag[name]
            
            self.logger.info(f"已注销组件: {name}")
            
            return True
    
    def _get_sorted_components(self, operation: str = "initialize") -> List[str]:
        """
        获取排序后的组件列表（基于依赖关系和优先级）
        
        Args:
            operation: 操作类型（initialize, start, stop）
            
        Returns:
            排序后的组件名称列表
        """
        # 根据操作类型过滤组件
        if operation == "initialize":
            components = {name: comp for name, comp in self.components.items() 
                         if comp.auto_initialize and not comp.initialized}
        elif operation == "start":
            components = {name: comp for name, comp in self.components.items() 
                         if comp.auto_start and comp.initialized and not comp.started}
        elif operation == "stop":
            components = {name: comp for name, comp in self.components.items() 
                         if comp.auto_stop and comp.started}
        else:
            components = self.components
        
        # 拓扑排序（考虑依赖关系）
        def topological_sort(graph, nodes):
            result = []
            visited = set()
            temp_visited = set()
            
            def visit(node):
                if node in temp_visited:
                    raise ValueError(f"检测到循环依赖: {node}")
                if node not in visited:
                    temp_visited.add(node)
                    
                    # 获取依赖
                    deps = self.component_dag.get(node, [])
                    for dep in deps:
                        if dep in nodes:  # 只考虑在过滤列表中的依赖
                            visit(dep)
                    
                    temp_visited.remove(node)
                    visited.add(node)
                    result.append(node)
            
            # 按优先级排序节点列表
            sorted_nodes = sorted(nodes.keys(), key=lambda n: (components[n].priority, n))
            
            for node in sorted_nodes:
                if node not in visited:
                    visit(node)
            
            return result
        
        try:
            sorted_components = topological_sort(self.component_dag, components)
            
            # 对于停止操作，需要反转顺序（反向依赖）
            if operation == "stop":
                sorted_components = list(reversed(sorted_components))
            
            return sorted_components
            
        except ValueError as e:
            self.logger.error(f"组件排序失败: {e}")
            # 如果排序失败，按优先级排序
            return sorted(components.keys(), key=lambda n: (components[n].priority, n))
    
    def initialize_system(self) -> bool:
        """
        初始化系统
        
        Returns:
            是否初始化成功
        """
        with self.state_lock:
            if self.state != LifecycleState.UNINITIALIZED:
                self.logger.warning(f"系统不在未初始化状态: {self.state}")
                return False
            
            self.logger.info("开始初始化系统...")
            self.state = LifecycleState.INITIALIZING
            
            # 触发前置回调
            self._trigger_callbacks(LifecycleEvent.BEFORE_INIT)
            
            try:
                # 初始化组件
                sorted_components = self._get_sorted_components("initialize")
                self.logger.info(f"将初始化 {len(sorted_components)} 个组件")
                
                for name in sorted_components:
                    success = self._initialize_component(name)
                    if not success:
                        self.logger.error(f"组件初始化失败: {name}")
                        self._handle_component_error(name, "初始化失败")
                
                # 检查初始化结果
                initialized_components = [c for c in self.components.values() if c.initialized]
                
                if len(initialized_components) == len(self.components):
                    self.state = LifecycleState.INITIALIZED
                    self.logger.info("系统初始化成功")
                else:
                    self.state = LifecycleState.ERROR
                    self.logger.error("系统初始化失败")
                    return False
                
                # 启动后台任务
                self._start_background_tasks()
                
                # 更新统计
                self.stats["total_initializations"] += 1
                
                # 触发后置回调
                self._trigger_callbacks(LifecycleEvent.AFTER_INIT)
                
                return True
                
            except Exception as e:
                self.logger.error(f"系统初始化异常: {e}")
                self.state = LifecycleState.ERROR
                
                # 触发错误回调
                self._trigger_callbacks(LifecycleEvent.ERROR, error=str(e))
                
                return False
    
    def start_system(self) -> bool:
        """
        启动系统
        
        Returns:
            是否启动成功
        """
        with self.state_lock:
            if self.state not in [LifecycleState.INITIALIZED, LifecycleState.STOPPED]:
                self.logger.warning(f"系统不在可启动状态: {self.state}")
                return False
            
            self.logger.info("开始启动系统...")
            self.state = LifecycleState.STARTING
            self.stats["start_time"] = datetime.now()
            
            # 触发前置回调
            self._trigger_callbacks(LifecycleEvent.BEFORE_START)
            
            try:
                # 启动组件
                sorted_components = self._get_sorted_components("start")
                self.logger.info(f"将启动 {len(sorted_components)} 个组件")
                
                for name in sorted_components:
                    success = self._start_component(name)
                    if not success:
                        self.logger.error(f"组件启动失败: {name}")
                        self._handle_component_error(name, "启动失败")
                
                # 检查启动结果
                started_components = [c for c in self.components.values() if c.started]
                
                if started_components:
                    self.state = LifecycleState.RUNNING
                    self.logger.info("系统启动成功")
                    
                    # 启动健康检查
                    if self.health_check_enabled:
                        self._start_health_check()
                    
                    # 启动维护任务
                    if self.maintenance_enabled:
                        self._start_maintenance_scheduler()
                    
                else:
                    self.state = LifecycleState.ERROR
                    self.logger.error("系统启动失败")
                    return False
                
                # 更新统计
                self.stats["total_starts"] += 1
                
                # 触发后置回调
                self._trigger_callbacks(LifecycleEvent.AFTER_START)
                
                return True
                
            except Exception as e:
                self.logger.error(f"系统启动异常: {e}")
                self.state = LifecycleState.ERROR
                
                # 触发错误回调
                self._trigger_callbacks(LifecycleEvent.ERROR, error=str(e))
                
                return False
    
    def stop_system(self, force: bool = False) -> bool:
        """
        停止系统
        
        Args:
            force: 是否强制停止
            
        Returns:
            是否停止成功
        """
        with self.state_lock:
            if self.state not in [LifecycleState.RUNNING, LifecycleState.ERROR]:
                self.logger.warning(f"系统不在可停止状态: {self.state}")
                return False
            
            self.logger.info("开始停止系统...")
            self.state = LifecycleState.STOPPING
            
            # 触发前置回调
            self._trigger_callbacks(LifecycleEvent.BEFORE_STOP)
            
            try:
                # 停止后台任务
                self._stop_background_tasks()
                
                # 停止组件
                sorted_components = self._get_sorted_components("stop")
                self.logger.info(f"将停止 {len(sorted_components)} 个组件")
                
                for name in sorted_components:
                    success = self._stop_component(name, force)
                    if not success and not force:
                        self.logger.warning(f"组件停止失败: {name}")
                
                self.state = LifecycleState.STOPPED
                
                # 更新统计
                self.stats["total_stops"] += 1
                if self.stats["start_time"]:
                    uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
                    self.stats["uptime"] = uptime
                
                # 触发后置回调
                self._trigger_callbacks(LifecycleEvent.AFTER_STOP)
                
                self.logger.info("系统已停止")
                
                return True
                
            except Exception as e:
                self.logger.error(f"系统停止异常: {e}")
                self.state = LifecycleState.ERROR
                
                # 触发错误回调
                self._trigger_callbacks(LifecycleEvent.ERROR, error=str(e))
                
                return False
    
    def shutdown(self) -> bool:
        """
        关闭系统
        
        Returns:
            是否关闭成功
        """
        with self.state_lock:
            self.logger.info("开始关闭系统...")
            
            # 触发前置回调
            self._trigger_callbacks(LifecycleEvent.BEFORE_SHUTDOWN)
            
            try:
                # 停止系统
                if self.state in [LifecycleState.RUNNING, LifecycleState.STARTING]:
                    self.stop_system()
                
                # 关闭组件
                for name, comp in self.components.items():
                    if hasattr(comp.component, 'shutdown'):
                        try:
                            comp.component.shutdown()
                            self.logger.debug(f"已关闭组件: {name}")
                        except Exception as e:
                            self.logger.error(f"关闭组件 {name} 失败: {e}")
                
                # 关闭执行器
                self.executor.shutdown(wait=True)
                
                # 更新状态
                self.state = LifecycleState.STOPPED
                
                # 触发后置回调
                self._trigger_callbacks(LifecycleEvent.AFTER_SHUTDOWN)
                
                self.logger.info("系统已关闭")
                
                return True
                
            except Exception as e:
                self.logger.error(f"系统关闭异常: {e}")
                
                # 触发错误回调
                self._trigger_callbacks(LifecycleEvent.ERROR, error=str(e))
                
                return False
    
    def _initialize_component(self, name: str) -> bool:
        """初始化单个组件"""
        comp = self.components.get(name)
        if not comp:
            return False
        
        if comp.initialized:
            return True
        
        try:
            self.logger.info(f"初始化组件: {name}")
            
            # 检查组件是否有initialize方法
            if hasattr(comp.component, 'initialize'):
                # 异步方法
                if asyncio.iscoroutinefunction(comp.component.initialize):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(comp.component.initialize())
                    finally:
                        loop.close()
                # 同步方法
                else:
                    comp.component.initialize()
            
            comp.initialized = True
            comp.last_activity = datetime.now()
            
            self.logger.info(f"组件初始化成功: {name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"组件初始化失败: {name} - {e}")
            comp.last_error = str(e)
            comp.error_count += 1
            
            return False
    
    def _start_component(self, name: str) -> bool:
        """启动单个组件"""
        comp = self.components.get(name)
        if not comp:
            return False
        
        if comp.started:
            return True
        
        if not comp.initialized:
            self.logger.warning(f"组件未初始化: {name}")
            return False
        
        try:
            self.logger.info(f"启动组件: {name}")
            
            # 检查组件是否有start方法
            if hasattr(comp.component, 'start'):
                # 异步方法
                if asyncio.iscoroutinefunction(comp.component.start):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(comp.component.start())
                    finally:
                        loop.close()
                # 同步方法
                else:
                    comp.component.start()
            
            comp.started = True
            comp.last_activity = datetime.now()
            
            self.logger.info(f"组件启动成功: {name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"组件启动失败: {name} - {e}")
            comp.last_error = str(e)
            comp.error_count += 1
            
            return False
    
    def _stop_component(self, name: str, force: bool = False) -> bool:
        """停止单个组件"""
        comp = self.components.get(name)
        if not comp:
            return False
        
        if not comp.started:
            return True
        
        try:
            self.logger.info(f"停止组件: {name}")
            
            # 检查组件是否有stop方法
            if hasattr(comp.component, 'stop'):
                # 异步方法
                if asyncio.iscoroutinefunction(comp.component.stop):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(comp.component.stop())
                    finally:
                        loop.close()
                # 同步方法
                else:
                    comp.component.stop()
            
            comp.started = False
            comp.last_activity = datetime.now()
            
            self.logger.info(f"组件停止成功: {name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"组件停止失败: {name} - {e}")
            
            if force:
                comp.started = False
                return True
            
            return False
    
    def _handle_component_error(self, component_name: str, error: str):
        """处理组件错误"""
        self.logger.error(f"组件错误: {component_name} - {error}")
        
        # 记录错误
        self.failed_components.append(component_name)
        self.stats["total_errors"] += 1
        
        # 更新组件错误统计
        self.stats["component_errors"][component_name] = self.stats["component_errors"].get(component_name, 0) + 1
        
        # 触发错误回调
        self._trigger_callbacks(LifecycleEvent.ERROR, component=component_name, error=error)
        
        # 如果启用了恢复，尝试恢复
        if self.recovery_enabled:
            self.attempt_recovery()
    
    def _start_background_tasks(self):
        """启动后台任务"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 这里可以启动其他后台任务
        # 例如：监控、日志轮转等
        
        self.logger.debug("后台任务已启动")
    
    def _stop_background_tasks(self):
        """停止后台任务"""
        self.is_running = False
        
        # 停止健康检查
        if hasattr(self, '_health_check_thread'):
            self._health_check_thread.cancel()
        
        # 停止维护调度器
        if hasattr(self, '_maintenance_thread'):
            self._maintenance_thread.cancel()
        
        self.logger.debug("后台任务已停止")
    
    def _start_health_check(self):
        """启动健康检查"""
        if not self.health_check_enabled:
            return
        
        def health_check_worker():
            while self.is_running and self.state == LifecycleState.RUNNING:
                try:
                    self._perform_health_check()
                except Exception as e:
                    self.logger.error(f"健康检查异常: {e}")
                
                time.sleep(self.health_check_interval)
        
        health_thread = threading.Thread(target=health_check_worker, daemon=True, name="HealthCheck")
        health_thread.start()
        
        self.background_tasks.append(health_thread)
        self.logger.info("健康检查已启动")
    
    def _perform_health_check(self):
        """执行健康检查"""
        unhealthy_components = []
        
        for name, comp in self.components.items():
            if comp.started:
                # 检查组件是否有健康检查方法
                if hasattr(comp.component, 'health_check'):
                    try:
                        # 异步方法
                        if asyncio.iscoroutinefunction(comp.component.health_check):
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                health = loop.run_until_complete(comp.component.health_check())
                            finally:
                                loop.close()
                        # 同步方法
                        else:
                            health = comp.component.health_check()
                        
                        if not health.get("healthy", True):
                            unhealthy_components.append(name)
                            self.logger.warning(f"组件健康检查失败: {name}")
                            
                    except Exception as e:
                        unhealthy_components.append(name)
                        self.logger.error(f"组件健康检查异常: {name} - {e}")
        
        # 如果有不健康的组件，尝试恢复
        if unhealthy_components and self.recovery_enabled:
            self.logger.warning(f"发现不健康组件: {unhealthy_components}")
            self.attempt_recovery(target_components=unhealthy_components)
    
    def _start_maintenance_scheduler(self):
        """启动维护任务调度器"""
        if not self.maintenance_enabled:
            return
        
        def maintenance_scheduler():
            while self.is_running and self.state == LifecycleState.RUNNING:
                try:
                    self._run_maintenance_tasks()
                except Exception as e:
                    self.logger.error(f"维护任务调度异常: {e}")
                
                time.sleep(self.maintenance_interval)
        
        maintenance_thread = threading.Thread(target=maintenance_scheduler, daemon=True, name="MaintenanceScheduler")
        maintenance_thread.start()
        
        self.background_tasks.append(maintenance_thread)
        self.logger.info("维护任务调度器已启动")
    
    def _run_maintenance_tasks(self):
        """运行维护任务"""
        current_time = datetime.now()
        
        for task_name, task in self.maintenance_tasks.items():
            if not task.enabled:
                continue
            
            # 检查是否应该运行
            should_run = False
            
            if task.next_run and current_time >= task.next_run:
                should_run = True
            elif not task.last_run:  # 从未运行过
                should_run = True
            
            if should_run:
                self.logger.info(f"执行维护任务: {task_name}")
                
                # 触发前置回调
                self._trigger_callbacks(LifecycleEvent.MAINTENANCE_START, task=task)
                
                try:
                    # 执行任务
                    if task.concurrent:
                        # 并发执行
                        future = self.executor.submit(task.task_func)
                        future.add_done_callback(
                            lambda f: self._on_maintenance_task_complete(task_name, f)
                        )
                    else:
                        # 同步执行
                        result = task.task_func()
                        task.last_run = datetime.now()
                        task.next_run = self._calculate_next_run(task.schedule)
                        
                        self.stats["total_maintenance"] += 1
                        self.logger.info(f"维护任务完成: {task_name}")
                        
                        # 触发后置回调
                        self._trigger_callbacks(LifecycleEvent.MAINTENANCE_END, task=task, result=result)
                
                except Exception as e:
                    self.logger.error(f"维护任务执行失败: {task_name} - {e}")
    
    def _on_maintenance_task_complete(self, task_name: str, future: concurrent.futures.Future):
        """维护任务完成回调"""
        task = self.maintenance_tasks.get(task_name)
        if not task:
            return
        
        try:
            result = future.result()
            task.last_run = datetime.now()
            task.next_run = self._calculate_next_run(task.schedule)
            
            self.stats["total_maintenance"] += 1
            self.logger.info(f"维护任务完成: {task_name}")
            
            # 触发后置回调
            self._trigger_callbacks(LifecycleEvent.MAINTENANCE_END, task=task, result=result)
            
        except Exception as e:
            self.logger.error(f"维护任务执行失败: {task_name} - {e}")
    
    def _calculate_next_run(self, schedule: str) -> datetime:
        """计算下次运行时间"""
        # 简化的实现：假设schedule是秒数
        try:
            interval = int(schedule)
            return datetime.now() + timedelta(seconds=interval)
        except ValueError:
            # 如果是cron表达式，需要解析
            # 这里简化处理，返回1小时后
            return datetime.now() + timedelta(hours=1)
    
    def enter_maintenance_mode(self):
        """进入维护模式"""
        with self.state_lock:
            if self.state != LifecycleState.RUNNING:
                self.logger.warning(f"系统不在运行状态，无法进入维护模式: {self.state}")
                return
            
            self.logger.info("进入维护模式...")
            old_state = self.state
            self.state = LifecycleState.MAINTENANCE
            
            # 暂停非关键组件
            for name, comp in self.components.items():
                if comp.started and comp.priority > 5:  # 低优先级组件
                    self._stop_component(name)
            
            self.logger.info("已进入维护模式")
    
    def exit_maintenance_mode(self):
        """退出维护模式"""
        with self.state_lock:
            if self.state != LifecycleState.MAINTENANCE:
                self.logger.warning(f"系统不在维护模式: {self.state}")
                return
            
            self.logger.info("退出维护模式...")
            self.state = LifecycleState.RUNNING
            
            # 恢复组件
            for name, comp in self.components.items():
                if not comp.started and comp.auto_start:
                    self._start_component(name)
            
            self.logger.info("已退出维护模式")
    
    def attempt_recovery(self, target_components: List[str] = None):
        """尝试恢复"""
        if not self.recovery_enabled:
            return
        
        with self.state_lock:
            if self.state == LifecycleState.RECOVERING:
                self.logger.warning("恢复操作已在执行中")
                return
            
            self.logger.info("开始恢复操作...")
            old_state = self.state
            self.state = LifecycleState.RECOVERING
            
            # 触发恢复回调
            self._trigger_callbacks(LifecycleEvent.RECOVERY)
            
            try:
                # 确定需要恢复的组件
                components_to_recover = target_components or self.failed_components.copy()
                
                if not components_to_recover:
                    self.logger.info("没有需要恢复的组件")
                    self.state = old_state
                    return
                
                self.logger.info(f"尝试恢复组件: {components_to_recover}")
                
                recovered = []
                failed = []
                
                for name in components_to_recover:
                    comp = self.components.get(name)
                    if not comp:
                        continue
                    
                    # 尝试恢复
                    recovery_success = False
                    
                    if comp.started:
                        # 先停止
                        if self._stop_component(name, force=True):
                            # 再启动
                            if self._start_component(name):
                                recovery_success = True
                    else:
                        # 直接启动
                        if self._start_component(name):
                            recovery_success = True
                    
                    if recovery_success:
                        recovered.append(name)
                        if name in self.failed_components:
                            self.failed_components.remove(name)
                    else:
                        failed.append(name)
                        comp.error_count += 1
                        
                        # 如果超过最大重试次数，标记为永久失败
                        if comp.error_count >= self.max_recovery_attempts:
                            self.logger.error(f"组件恢复失败超过最大次数: {name}")
                
                # 更新统计
                self.stats["total_recoveries"] += 1
                
                if recovered:
                    self.logger.info(f"恢复成功组件: {recovered}")
                
                if failed:
                    self.logger.error(f"恢复失败组件: {failed}")
                
                # 恢复原状态
                self.state = old_state
                
                self.logger.info("恢复操作完成")
                
            except Exception as e:
                self.logger.error(f"恢复操作异常: {e}")
                self.state = LifecycleState.ERROR
    
    def _trigger_callbacks(self, event: LifecycleEvent, **kwargs):
        """触发回调函数"""
        self.stats["last_event"] = {
            "event": event.value,
            "timestamp": datetime.now().isoformat(),
            "data": kwargs,
        }
        
        for callback in self.callbacks.get(event, []):
            try:
                callback(event, **kwargs)
            except Exception as e:
                self.logger.error(f"生命周期回调执行失败: {event.value} - {e}")
    
    def register_callback(self, event: LifecycleEvent, callback: Callable):
        """注册回调函数"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"已注册回调函数到事件: {event.value}")
        else:
            self.logger.warning(f"未知的事件类型: {event}")
    
    def register_maintenance_task(self, name: str, description: str, task_func: Callable,
                                schedule: str, enabled: bool = True, concurrent: bool = False):
        """注册维护任务"""
        task = MaintenanceTask(
            name=name,
            description=description,
            task_func=task_func,
            schedule=schedule,
            enabled=enabled,
            concurrent=concurrent,
        )
        
        self.maintenance_tasks[name] = task
        self.logger.info(f"已注册维护任务: {name}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        with self.state_lock:
            # 计算运行时间
            uptime = 0
            if self.stats["start_time"] and self.state == LifecycleState.RUNNING:
                uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
            
            # 统计组件状态
            component_stats = {
                "total": len(self.components),
                "initialized": len([c for c in self.components.values() if c.initialized]),
                "started": len([c for c in self.components.values() if c.started]),
                "failed": len(self.failed_components),
            }
            
            return {
                "state": self.state.value,
                "uptime": uptime,
                "components": component_stats,
                "stats": self.stats,
                "maintenance_tasks": len(self.maintenance_tasks),
                "background_tasks": len(self.background_tasks),
                "timestamp": datetime.now().isoformat(),
            }
    
    def get_component_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取组件状态"""
        comp = self.components.get(name)
        if not comp:
            return None
        
        return {
            "name": comp.name,
            "priority": comp.priority,
            "initialized": comp.initialized,
            "started": comp.started,
            "error_count": comp.error_count,
            "last_error": comp.last_error,
            "last_activity": comp.last_activity.isoformat() if comp.last_activity else None,
            "dependencies": comp.dependencies,
            "auto_initialize": comp.auto_initialize,
            "auto_start": comp.auto_start,
            "auto_stop": comp.auto_stop,
        }