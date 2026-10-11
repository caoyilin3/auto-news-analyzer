"""
工作流协调器
负责调度和监控工作流执行
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import queue
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
        self.task_queue = queue.PriorityQueue()
        
        # 工作流存储
        self.workflows = {}  # workflow_id -> List[task_id]
        
        # 执行器
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 10)
        )
        
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
        
        # 将任务加入队列
        for task_id in task_ids:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                # 使用优先级（优先级数字越大越优先，所以用负号）
                self.task_queue.put((-task.priority, task.id))
        
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
        """工作线程主循环"""
        while self.is_running:
            try:
                # 从队列获取任务
                try:
                    priority, task_id = self.task_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                task = self.tasks.get(task_id)
                if not task:
                    self.logger.error(f"任务不存在: {task_id}")
                    continue
                
                # 检查依赖
                if not self._check_dependencies(task):
                    # 依赖未满足，重新放入队列
                    self.task_queue.put((priority, task_id))
                    time.sleep(0.1)
                    continue
                
                # 执行任务
                self._execute_task(task)
                
                # 标记任务完成
                self.task_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"工作线程异常: {e}")
    
    def _check_dependencies(self, task: Task) -> bool:
        """检查任务依赖是否满足"""
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task:
                self.logger.error(f"依赖任务不存在: {dep_id}")
                return False
            
            if dep_task.status != TaskStatus.COMPLETED:
                return False
        
        return True
    
    def _execute_task(self, task: Task):
        """执行单个任务"""
        self.logger.info(f"开始执行任务: {task.name} ({task.id})")
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        # 调用前置回调
        for callback in self.callbacks["task_started"]:
            callback(task)
        
        result = None
        error = None
        
        try:
            # 这里应该根据任务定义调用相应的模块函数
            # 简化实现：模拟执行
            result = self._simulate_task_execution(task)
            
            task.status = TaskStatus.COMPLETED
            task.result = result
            self.stats["completed_tasks"] += 1
            
            # 调用后置回调
            for callback in self.callbacks["task_completed"]:
                callback(task, result)
            
            self.logger.info(f"任务完成: {task.name}")
            
        except Exception as e:
            self.logger.error(f"任务失败: {task.name} - {e}")
            
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self.stats["failed_tasks"] += 1
            
            # 重试逻辑
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                self.logger.info(f"任务重试 {task.retry_count}/{task.max_retries}: {task.name}")
                self.task_queue.put((-task.priority, task.id))
            else:
                # 调用失败回调
                for callback in self.callbacks["task_failed"]:
                    callback(task, e)
        
        finally:
            task.completed_at = datetime.now()
            
            # 检查工作流是否完成
            self._check_workflow_completion(task.workflow_id)
    
    def _simulate_task_execution(self, task: Task) -> Dict[str, Any]:
        """模拟任务执行（占位函数）"""
        # 在实际实现中，这里会根据任务定义调用相应的模块函数
        # 例如：from src.data_acquisition import collect_data
        
        time.sleep(0.5)  # 模拟执行时间
        
        return {
            "status": "success",
            "task_id": task.id,
            "execution_time": 0.5,
            "data": {"sample": "result"},
        }
    
    def _check_workflow_completion(self, workflow_id: str):
        """检查工作流是否完成"""
        if workflow_id not in self.workflows:
            return
        
        task_ids = self.workflows[workflow_id]
        all_completed = True
        any_failed = False
        
        for task_id in task_ids:
            task = self.tasks.get(task_id)
            if not task:
                continue
            
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                all_completed = False
            
            if task.status == TaskStatus.FAILED:
                any_failed = True
        
        if all_completed:
            if any_failed:
                self.stats["failed_workflows"] += 1
                self.logger.warning(f"工作流完成（有失败）: {workflow_id}")
            else:
                self.stats["completed_workflows"] += 1
                self.logger.info(f"工作流完成: {workflow_id}")
            
            # 调用工作流完成回调
            for callback in self.callbacks["workflow_completed"]:
                callback(workflow_id, any_failed)
    
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
        elif any(status == "failed" for status in status_counts.keys()):
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
            "active_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]),
            "pending_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
            "queue_size": self.task_queue.qsize(),
            "total_workflows_active": len([w for w in self.workflows if self.get_workflow_status(w)["status"] == "running"]),
        }
    
    def shutdown(self):
        """关闭协调器"""
        self.stop(wait=True)
        self.executor.shutdown(wait=True)
        self.logger.info("协调器已关闭")