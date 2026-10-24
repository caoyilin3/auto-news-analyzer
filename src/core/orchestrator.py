"""
工作流协调器
负责调度和监控工作流执行
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import time
import concurrent.futures


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class Task:
    """任务定义"""
    id: str
    name: str
    workflow_id: str
    module: str
    function: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 1  # 1-10，数字越大优先级越高
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timeout: int = 300  # 秒
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID


class Orchestrator:
    """工作流协调器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化协调器
        
        Args:
            config: 协调器配置
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 任务存储
        self.tasks = {}  # task_id -> Task

        # 调度状态：待执行任务（task_id -> 优先级）与在飞任务
        self._waiting: Dict[str, int] = {}
        self._in_flight: Dict[str, concurrent.futures.Future] = {}
        self._in_flight_started: Dict[str, float] = {}
        self._tasks_lock = threading.RLock()
        self._reported_workflows: set = set()

        # 已注册的可执行模块： name -> 模块实例
        self.modules: Dict[str, Any] = {}
        
        # 工作流存储
        self.workflows = {}  # workflow_id -> List[task_id]
        
        # 执行器（并行度 = max_workers）
        self.max_workers = max(1, int(self.config.get("max_workers", 10)))
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        
        # 状态跟踪
        self.is_running = False
        self.worker_thread = None
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "total_workflows": 0,
            "completed_workflows": 0,
            "failed_workflows": 0,
        }
        
        # 回调函数
        self.callbacks = {
            "task_started": [],
            "task_completed": [],
            "task_failed": [],
            "workflow_started": [],
            "workflow_completed": [],
        }
        
        self.logger.info("工作流协调器初始化完成")

    def register_module(self, name: str, module: Any) -> None:
        """注册可被任务调度的模块实例"""
        self.modules[name] = module
        self.logger.info(f"已注册调度模块: {name}")

    def register_modules(self, modules: Dict[str, Any]) -> None:
        """批量注册模块（可直接传入 SystemEngine.modules）"""
        for name, module in modules.items():
            self.register_module(name, module)

    def create_workflow(self, workflow_id: str, tasks: List[Dict[str, Any]]) -> str:
        """
        创建工作流
        
        Args:
            workflow_id: 工作流ID
            tasks: 任务定义列表
            
        Returns:
            工作流ID
        """
        if workflow_id in self.workflows:
            raise ValueError(f"工作流已存在: {workflow_id}")
        
        self.logger.info(f"创建工作流: {workflow_id}")
        
        task_ids = []
        for task_def in tasks:
            task = self._create_task_from_definition(workflow_id, task_def)
            self.tasks[task.id] = task
            task_ids.append(task.id)

        # 任务定义中的 dependencies 写的是任务名，这里统一翻译成任务 ID
        name_to_id = {self.tasks[tid].name: tid for tid in task_ids}
        for tid in task_ids:
            task = self.tasks[tid]
            resolved = []
            for dep in task.dependencies:
                if dep in name_to_id:
                    resolved.append(name_to_id[dep])
                elif dep in self.tasks:
                    resolved.append(dep)
                else:
                    self.logger.warning(f"任务 {task.name} 的依赖不存在: {dep}")
            task.dependencies = resolved
        
        self.workflows[workflow_id] = task_ids
        self.stats["total_workflows"] += 1
        
        # 调用回调
        for callback in self.callbacks["workflow_started"]:
            callback(workflow_id, task_ids)
        
        return workflow_id
    
    def _create_task_from_definition(self, workflow_id: str, task_def: Dict[str, Any]) -> Task:
        """从定义创建任务"""
        task_id = f"{workflow_id}_{task_def['name']}_{int(time.time())}"
        
        return Task(
            id=task_id,
            name=task_def["name"],
            workflow_id=workflow_id,
            module=task_def.get("module", ""),
            function=task_def.get("function", ""),
            parameters=task_def.get("parameters", {}),
            priority=task_def.get("priority", 1),
            timeout=task_def.get("timeout", 300),
            max_retries=task_def.get("max_retries", 3),
            dependencies=task_def.get("dependencies", []),
        )
    
    def submit_workflow(self, workflow_id: str) -> bool:
        """
        提交工作流执行
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            是否成功提交
        """
        if workflow_id not in self.workflows:
            self.logger.error(f"工作流不存在: {workflow_id}")
            return False
        
        task_ids = self.workflows[workflow_id]
        self.logger.info(f"提交工作流 {workflow_id}，包含 {len(task_ids)} 个任务")

        # 任务进入调度池，由工作线程按依赖就绪情况并发派发
        with self._tasks_lock:
            for task_id in task_ids:
                task = self.tasks.get(task_id)
                if task is not None:
                    task.status = TaskStatus.PENDING
                    self._waiting[task_id] = task.priority

        # 启动工作线程（如果还没启动）
        if not self.is_running:
            self.start()
        
        return True
    
    def start(self):
        """启动协调器"""
        if self.is_running:
            self.logger.warning("协调器已经在运行中")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        self.logger.info("协调器已启动")
    
    def _worker_loop(self):
        """调度主循环：按依赖就绪程度并发派发任务"""
        while self.is_running:
            try:
                self._dispatch_ready()
                self._collect_finished()
                if self._in_flight:
                    concurrent.futures.wait(
                        list(self._in_flight.values()),
                        timeout=0.05,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    self._collect_finished()
                else:
                    time.sleep(0.02)
            except Exception as e:
                self.logger.error(f"工作线程异常: {e}")

    def _dispatch_ready(self) -> None:
        """把依赖已满足的等待任务提交到线程池（并行度受 max_workers 限制）"""
        with self._tasks_lock:
            pending = sorted(
                self._waiting.keys(),
                key=lambda tid: (-self._waiting[tid], self.tasks[tid].created_at),
            )

        for task_id in pending:
            task = self.tasks.get(task_id)
            if task is None:
                with self._tasks_lock:
                    self._waiting.pop(task_id, None)
                continue

            ok, reason = self._check_dependencies(task)
            if not ok:
                if reason == "pending":
                    continue
                # 依赖缺失或已失败：判定为失败，避免永久等待
                with self._tasks_lock:
                    self._waiting.pop(task_id, None)
                self._fail_task(task, reason)
                continue

            with self._tasks_lock:
                if len(self._in_flight) >= self.max_workers:
                    return
                if task_id not in self._waiting:
                    continue
                self._waiting.pop(task_id, None)
                self._launch(task)

    def _launch(self, task: Task) -> None:
        """提交单个任务（调用方需持有 _tasks_lock）"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        # 前置回调
        for callback in self.callbacks["task_started"]:
            try:
                callback(task)
            except Exception as e:
                self.logger.warning(f"task_started 回调异常: {e}")

        future = self.executor.submit(self._call_module, task)
        self._in_flight[task.id] = future
        self._in_flight_started[task.id] = time.time()
        self.logger.info(f"开始执行任务: {task.name} ({task.id})")

    def _collect_finished(self) -> None:
        """回收已完成/超时的任务，触发回调并按需重试"""
        now = time.time()
        for task_id, future in list(self._in_flight.items()):
            task = self.tasks.get(task_id)
            if task is None:
                with self._tasks_lock:
                    self._in_flight.pop(task_id, None)
                    self._in_flight_started.pop(task_id, None)
                continue

            if future.done():
                with self._tasks_lock:
                    self._in_flight.pop(task_id, None)
                    self._in_flight_started.pop(task_id, None)
                exc = future.exception()
                if exc is None:
                    self._complete_task(task, future.result())
                else:
                    # 保留异常对象，便于上层（如引擎）取回步骤级结果
                    self._fail_task(task, exc)
                continue

            started = self._in_flight_started.get(task_id, now)
            if task.timeout and now - started > task.timeout:
                with self._tasks_lock:
                    self._in_flight.pop(task_id, None)
                    self._in_flight_started.pop(task_id, None)
                # 线程无法被强制终止，这里只做状态层面的超时处理
                self._fail_task(task, f"任务超时（>{task.timeout}s）", timed_out=True)

    def _complete_task(self, task: Task, result: Dict[str, Any]) -> None:
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now()
        self.stats["completed_tasks"] += 1

        # 回调必须在依赖解锁之前完成：下游任务依赖上游已合并的数据
        for callback in self.callbacks["task_completed"]:
            try:
                callback(task, result)
            except Exception as e:
                self.logger.warning(f"task_completed 回调异常: {e}")

        self.logger.info(f"任务完成: {task.name}")
        self._check_workflow_completion(task.workflow_id)

    def _fail_task(self, task: Task, error: Any, timed_out: bool = False) -> None:
        if self.is_running and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            self.logger.info(f"任务重试 {task.retry_count}/{task.max_retries}: {task.name}")
            with self._tasks_lock:
                self._waiting[task.id] = task.priority
            return

        task.status = TaskStatus.TIMEOUT if timed_out else TaskStatus.FAILED
        task.error = str(error)
        task.completed_at = datetime.now()
        self.stats["failed_tasks"] += 1
        self.logger.error(f"任务失败: {task.name} - {error}")

        for callback in self.callbacks["task_failed"]:
            try:
                callback(task, error)
            except Exception as e:
                self.logger.warning(f"task_failed 回调异常: {e}")

        self._check_workflow_completion(task.workflow_id)

    def _check_dependencies(self, task: Task) -> Tuple[bool, str]:
        """检查任务依赖是否满足

        Returns:
            (是否可执行, 原因)；原因为 "pending" 表示还需等待，其它值为失败原因
        """
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task:
                return False, f"依赖任务不存在: {dep_id}"
            if dep_task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT):
                return False, f"依赖任务失败: {dep_task.name}"
            if dep_task.status != TaskStatus.COMPLETED:
                return False, "pending"
        return True, ""

    def _call_module(self, task: Task) -> Dict[str, Any]:
        """按任务定义调用已注册模块的真实函数（支持同步/异步）"""
        module = self.modules.get(task.module)
        if module is None:
            raise ValueError(f"模块未注册: {task.module}（请先 register_module）")

        func = getattr(module, task.function, None)
        if func is None or not callable(func):
            raise ValueError(f"模块 {task.module} 不存在可调用方法: {task.function}")

        start = time.time()
        if asyncio.iscoroutinefunction(func):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                output = loop.run_until_complete(func(task.parameters))
            finally:
                loop.close()
        else:
            output = func(task.parameters)

        return {
            "status": "success",
            "task_id": task.id,
            "execution_time": round(time.time() - start, 4),
            "data": output if isinstance(output, dict) else {"result": output},
        }
    
    def _check_workflow_completion(self, workflow_id: str):
        """检查工作流是否完成（同一工作流只上报一次）"""
        if workflow_id not in self.workflows:
            return

        task_ids = self.workflows[workflow_id]
        all_completed = True
        any_failed = False
        
        for task_id in task_ids:
            task = self.tasks.get(task_id)
            if not task:
                continue
            
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED,
                                   TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                all_completed = False
            
            if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT):
                any_failed = True
        
        if all_completed and workflow_id not in self._reported_workflows:
            self._reported_workflows.add(workflow_id)
            if any_failed:
                self.stats["failed_workflows"] += 1
                self.logger.warning(f"工作流完成（有失败）: {workflow_id}")
            else:
                self.stats["completed_workflows"] += 1
                self.logger.info(f"工作流完成: {workflow_id}")
            
            # 调用工作流完成回调
            for callback in self.callbacks["workflow_completed"]:
                try:
                    callback(workflow_id, any_failed)
                except Exception as e:
                    self.logger.warning(f"workflow_completed 回调异常: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return {
            "id": task.id,
            "name": task.name,
            "workflow_id": task.workflow_id,
            "status": task.status.value,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error": task.error,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
        }
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        if workflow_id not in self.workflows:
            return None
        
        task_ids = self.workflows[workflow_id]
        tasks_status = []
        
        for task_id in task_ids:
            task_status = self.get_task_status(task_id)
            if task_status:
                tasks_status.append(task_status)
        
        # 计算工作流状态
        status_counts = {}
        for task in tasks_status:
            status = task["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if all(status == "completed" for status in status_counts.keys()):
            workflow_status = "completed"
        elif any(status in ("failed", "timeout", "cancelled") for status in status_counts):
            workflow_status = "failed"
        elif any(status == "running" for status in status_counts.keys()):
            workflow_status = "running"
        else:
            workflow_status = "pending"
        
        return {
            "workflow_id": workflow_id,
            "status": workflow_status,
            "total_tasks": len(tasks_status),
            "task_status": status_counts,
            "tasks": tasks_status,
        }
    
    def register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"已注册回调函数到事件: {event}")
        else:
            self.logger.warning(f"未知的事件类型: {event}")
    
    def stop(self, wait: bool = True):
        """停止协调器"""
        self.logger.info("停止协调器...")
        self.is_running = False
        
        if wait and self.worker_thread:
            self.worker_thread.join(timeout=10)
        
        self.logger.info("协调器已停止")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "max_workers": self.max_workers,
            "active_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]),
            "pending_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
            "queue_size": len(self._waiting),
            "in_flight": len(self._in_flight),
            "total_workflows_active": len([
                w for w in self.workflows
                if (self.get_workflow_status(w) or {}).get("status") == "running"
            ]),
        }
    
    def shutdown(self):
        """关闭协调器"""
        self.stop(wait=True)
        self.executor.shutdown(wait=True)
        self.logger.info("协调器已关闭")