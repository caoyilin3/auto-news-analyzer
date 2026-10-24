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


class _StepFailure(Exception):
    """步骤失败：携带原始步骤结果，便于调度器重试与失败上报"""

    def __init__(self, step_result: Dict[str, Any]):
        message = step_result.get("error") or f"步骤失败: {step_result.get('step')}"
        super().__init__(message)
        self.step_result = step_result


class _WorkflowAdapter:
    """把引擎的工作流步骤暴露为 Orchestrator 可调度的任务函数"""

    def __init__(self, engine: "SystemEngine"):
        self._engine = engine
        for step in engine.workflow_steps:
            setattr(self, step.name, self._make(step))

    def _make(self, step: WorkflowStep):
        def run(context: Dict[str, Any]) -> Dict[str, Any]:
            # 报告步骤执行前先汇总反馈与进化结果
            if step.name == "report_generation":
                self._engine._attach_cycle_summary(context)
            result = self._engine.execute_step(step, context, check_dependencies=False)
            if result.get("status") == "failed":
                raise _StepFailure(result)
            return result

        run.__name__ = step.name
        return run


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

        # 是否正在执行周期（与展示用的 state 解耦，避免与生命周期管理器冲突）
        self._executing = False
        self._stop_requested = False
        # 并行调度时各任务回调会并发合并结果，需要加锁
        self._context_lock = threading.RLock()

        # 工作流定义
        self.workflow_steps = self._define_workflow_steps()
        
        # 模块实例
        self.modules = {}

        # 基础设施组件（initialize_modules 中创建）
        self.state_manager = None
        self.feedback_loop = None
        self.evidence = None
        self.evaluator = None
        self.export_evaluation_csv = True
        self.metrics_collector = None
        self.metrics_export_path = "data/metrics/engine_metrics.json"
        
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
        # 本次进程内的统计（不从状态文件恢复），用于命令行汇总
        self.run_metrics = {
            "total_cycles": 0,
            "successful_cycles": 0,
            "failed_cycles": 0,
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
                # 报告需要进化与记忆的结果，显式声明依赖（并行调度时据此排序）
                dependencies=["knowledge_extraction", "evolution_learning", "memory_management"],
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
            
            # 基础设施：状态管理 / 反馈循环 / 专利证据 / 进化调参接口
            self._init_infrastructure()
            
            self.logger.info("所有模块初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"模块初始化失败: {e}")
            self.state = EngineState.ERROR
            return False

    # ------------------------------------------------------------------ 基础设施
    def _init_infrastructure(self) -> None:
        """初始化状态管理、反馈循环、专利证据与进化调参接口"""
        state_cfg = self.config.get("state", {}) or {}
        try:
            from .state_manager import SystemStateManager

            self.state_manager = SystemStateManager({
                "persistence_enabled": state_cfg.get("persistence_enabled", True),
                "persistence_path": state_cfg.get(
                    "persistence_path", "data/state/engine_state.pkl"
                ),
                "autosave_interval": state_cfg.get("autosave_interval", 300),
            })
            # 恢复上一次运行累计的指标（若存在）
            restored = self.state_manager.get_state("engine.metrics")
            if isinstance(restored, dict):
                self.metrics.update({k: v for k, v in restored.items() if k in self.metrics})
                self.logger.info("已从状态文件恢复引擎指标")
        except Exception as e:
            self.logger.warning(f"状态管理器初始化失败（降级为无状态）: {e}")
            self.state_manager = None

        feedback_cfg = self.config.get("feedback", {}) or {}
        try:
            from .feedback_loop import FeedbackLoopController

            self.feedback_loop = FeedbackLoopController({
                "max_history_size": feedback_cfg.get("max_history_size", 500),
            })
        except Exception as e:
            self.logger.warning(f"反馈循环初始化失败（降级为无反馈）: {e}")
            self.feedback_loop = None

        evolution = self.modules.get("evolution")
        if evolution is not None:
            self._register_tunables(evolution)
            self._restore_tunables(evolution)
            self._attach_evaluator(evolution)

        evidence_cfg = self.config.get("patent_evidence", {}) or {}
        if evidence_cfg.get("enabled", True):
            try:
                from ..patent_evidence import get_collector

                system_name = self.config.get("system", {}).get("name", "AutoNewsAnalyzer")
                self.evidence = get_collector(system_name)
            except Exception as e:
                self.logger.warning(f"专利证据收集器初始化失败: {e}")
                self.evidence = None

    def _attach_evaluator(self, evolution) -> None:
        """创建并接入长期学习效果评估器（周期数据集）"""
        eval_cfg = self.config.get("evaluation", {}) or {}
        try:
            from ..evolution.effectiveness import LearningEffectivenessEvaluator

            self.evaluator = LearningEffectivenessEvaluator(
                dataset_path=eval_cfg.get("dataset_path", "data/cycle_metrics.jsonl")
            )
            self.export_evaluation_csv = bool(eval_cfg.get("export_csv", True))
            evolution.attach_evaluator(self.evaluator)
        except Exception as e:
            self.logger.warning(f"长期效果评估器初始化失败: {e}")
            self.evaluator = None

        # 通用指标收集器（utils.metrics），用于周期级指标留存与导出
        try:
            from ..utils.metrics import MetricsCollector

            self.metrics_collector = MetricsCollector(
                collector_name="engine", enable_persistence=False
            )
            self.metrics_export_path = (self.config.get("monitoring", {}) or {}).get(
                "metrics_path", "data/metrics/engine_metrics.json"
            )
        except Exception as e:
            self.logger.warning(f"指标收集器初始化失败: {e}")
            self.metrics_collector = None

    def _register_tunables(self, evolution) -> None:
        """把各模块中允许进化调整的参数暴露给进化管理器"""
        credibility = self.modules.get("credibility")
        if credibility is not None:
            evolution.register_tunable(
                "credibility.theta_high",
                lambda: credibility.theta_high,
                lambda v: setattr(credibility, "theta_high", float(v)),
                0.60, 0.95, 0.02,
            )
            evolution.register_tunable(
                "credibility.theta_low",
                lambda: credibility.theta_low,
                lambda v: setattr(credibility, "theta_low", float(v)),
                0.30, 0.70, 0.02,
            )

        knowledge = self.modules.get("knowledge")
        relation_extractor = getattr(knowledge, "relation_extractor", None)
        if relation_extractor is not None and hasattr(relation_extractor, "rel_config"):
            evolution.register_tunable(
                "extraction.relation_min_confidence",
                lambda: relation_extractor.rel_config.min_confidence,
                lambda v: setattr(relation_extractor.rel_config, "min_confidence", float(v)),
                0.30, 0.90, 0.05,
            )

    def _restore_tunables(self, evolution) -> None:
        """恢复上次运行进化得到的参数，使进化成果跨进程累积"""
        if self.state_manager is None:
            return
        saved = self.state_manager.get_state("evolution.tunables")
        if not isinstance(saved, dict):
            return
        restored = []
        for name, value in saved.items():
            spec = evolution.tunables.get(name)
            if spec is None or not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            try:
                spec["set"](float(value))
                restored.append(f"{name}={value}")
            except Exception as e:
                self.logger.warning(f"恢复参数 {name} 失败: {e}")
        if restored:
            self.logger.info(f"已恢复进化参数: {', '.join(restored)}")

    def initialize(self) -> bool:
        """生命周期管理器调用入口"""
        return self.initialize_modules()

    def start(self) -> bool:
        """生命周期管理器调用入口：标记引擎进入运行状态"""
        self.state = EngineState.RUNNING
        self._stop_requested = False
        return True

    def health_check(self) -> Dict[str, Any]:
        """健康检查（生命周期管理器会定期调用）"""
        initialized = len(self.modules) == 6
        healthy = initialized and self.state != EngineState.ERROR
        return {
            "healthy": healthy,
            "state": self.state.value,
            "modules": len(self.modules),
            "executing": self._executing,
        }
    
    def register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"已注册回调函数到事件: {event}")
        else:
            self.logger.warning(f"未知的事件类型: {event}")
    
    def execute_step(self, step: WorkflowStep, context: Dict[str, Any],
                     check_dependencies: bool = True) -> Dict[str, Any]:
        """
        执行单个工作流步骤
        
        Args:
            step: 工作流步骤
            context: 执行上下文
            check_dependencies: 是否在步骤内校验依赖（由 Orchestrator 调度时置 False）
            
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
            # 检查依赖是否满足（调度器模式下由 DAG 保证顺序）
            if check_dependencies:
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
            
            # 根据函数类型决定执行方式（按 step.timeout 强制超时）
            if asyncio.iscoroutinefunction(func):
                # 异步函数
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    step_result = loop.run_until_complete(
                        asyncio.wait_for(func(context.get("data", {})), timeout=step.timeout)
                    )
                finally:
                    loop.close()
            else:
                # 同步函数：交给线程池执行，以便真正落实超时控制
                future = self.executor.submit(func, context.get("data", {}))
                step_result = future.result(timeout=step.timeout)
            
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
        if self._executing:
            raise Exception("引擎已经在运行中")

        self._executing = True
        self.state = EngineState.RUNNING
        self.logger.info("开始执行工作流")
        
        # 初始化上下文
        context = {
            "start_time": datetime.now().isoformat(),
            "data": input_data or {},
            "completed_steps": [],
            "step_results": [],
            "step_data": {},   # 每个步骤的原始产出，避免平铺合并时互相覆盖
            "errors": [],
        }
        
        # 调用前置回调
        for callback in self.callbacks["before_cycle"]:
            callback(context)

        # 记录周期开始前的参数值（用于准确计算参数漂移）
        evolution = self.modules.get("evolution")
        tunables_before = (
            evolution.get_tunable_values()
            if evolution is not None and hasattr(evolution, "get_tunable_values")
            else {}
        )
        
        overall_result = {
            "workflow_id": f"wf_{int(time.time())}",
            "status": "running",
            "context": context,
            "tunables_before": tunables_before,
            "metrics": {},
        }
        
        try:
            executor_kind = self.config.get("workflow", {}).get("executor", "orchestrator")
            if executor_kind == "sequential":
                self._run_sequential(context, overall_result)
            else:
                self._run_orchestrated(context, overall_result)
            
            # 更新总体状态
            if overall_result["status"] != "failed":
                if context["errors"]:
                    overall_result["status"] = "completed_with_errors"
                else:
                    overall_result["status"] = "completed"
            
            # 计算指标
            overall_result["metrics"] = self._calculate_metrics(context)
            
            # 更新引擎统计（self.metrics 会从状态文件恢复，是跨进程累计值）
            self.metrics["total_cycles"] += 1
            self.run_metrics["total_cycles"] += 1
            if overall_result["status"] == "completed":
                self.metrics["successful_cycles"] += 1
                self.run_metrics["successful_cycles"] += 1
            else:
                self.metrics["failed_cycles"] += 1
                self.run_metrics["failed_cycles"] += 1
            self.metrics["last_run_time"] = datetime.now().isoformat()
            self.metrics["total_processing_time"] += overall_result["metrics"].get(
                "total_duration", 0.0
            )
            
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
            
            self._executing = False
            if self.state != EngineState.ERROR:
                self.state = EngineState.STOPPED

            # 状态持久化（失败不影响主流程）
            self._persist_state(overall_result)
            
            self.logger.info(f"工作流执行完成，状态: {overall_result['status']}")
        
        return overall_result

    # ------------------------------------------------------------------ 执行器
    def _run_sequential(self, context: Dict[str, Any], overall_result: Dict[str, Any]) -> None:
        """顺序执行工作流（回退模式）"""
        for step in self.workflow_steps:
            if self._stop_requested:
                self.logger.warning("工作流被中断")
                break

            if step.name == "report_generation":
                self._attach_cycle_summary(context)

            self._update_workflow_stats(context)

            step_result = None
            for attempt in range(step.retry_count + 1):
                step_result = self.execute_step(step, context)
                if step_result["status"] in ["completed", "skipped"]:
                    break
                if attempt < step.retry_count:
                    self.logger.warning(
                        f"步骤 {step.name} 失败，重试 {attempt + 1}/{step.retry_count}"
                    )
                    time.sleep(2 ** attempt)

            self._record_step_result(context, step_result)

            if step_result["status"] == "failed" and not self.config.get(
                "workflow", {}
            ).get("continue_on_error", False):
                self.logger.error(f"步骤 {step.name} 失败，停止工作流")
                overall_result["status"] = "failed"
                break

    def _run_orchestrated(self, context: Dict[str, Any],
                          overall_result: Dict[str, Any]) -> None:
        """通过 Orchestrator 的 DAG 调度执行工作流（独立步骤可并行）"""
        from .orchestrator import Orchestrator

        enabled_steps = [s for s in self.workflow_steps if s.enabled]
        enabled_names = {s.name for s in enabled_steps}
        workflow_cfg = self.config.get("workflow", {}) or {}
        max_workers = max(1, int(workflow_cfg.get("max_workers", 2)))

        orchestrator = Orchestrator({"max_workers": max_workers})
        adapter = _WorkflowAdapter(self)
        orchestrator.register_module("_workflow", adapter)

        def on_completed(task, result):
            step_result = (result or {}).get("data") or {}
            step_result.setdefault("step", task.name)
            step_result.setdefault("status", "completed")
            step_result["duration"] = (result or {}).get("execution_time", 0.0)
            context.setdefault("step_durations", {})[task.name] = step_result["duration"]
            self._record_step_result(context, step_result, append=False)

        def on_failed(task, error):
            step_result = getattr(error, "step_result", None)
            if not step_result:
                step_result = {
                    "step": task.name,
                    "status": "failed",
                    "error": str(error),
                }
            self._record_step_result(context, step_result, append=False)

        orchestrator.register_callback("task_completed", on_completed)
        orchestrator.register_callback("task_failed", on_failed)

        tasks = []
        for index, step in enumerate(enabled_steps):
            tasks.append({
                "name": step.name,
                "module": "_workflow",
                "function": step.name,
                "parameters": context,
                "dependencies": [d for d in step.dependencies if d in enabled_names],
                "timeout": step.timeout,
                "max_retries": step.retry_count,
                "priority": 10 - index,
            })

        workflow_id = orchestrator.create_workflow(str(context["start_time"]), tasks)
        orchestrator.submit_workflow(workflow_id)

        deadline = time.time() + sum(s.timeout for s in enabled_steps) + 5
        status = None
        try:
            while time.time() < deadline:
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] in ("completed", "failed"):
                    break
                if self._stop_requested:
                    self.logger.warning("工作流被中断")
                    break
                time.sleep(0.02)
        finally:
            orchestrator.shutdown()

        # 按步骤定义顺序重建 step_results（回调中的合并顺序是完成顺序）
        task_by_name = {t["name"]: t for t in (status or {}).get("tasks", [])}
        context["step_results"] = []
        for step in self.workflow_steps:
            if not step.enabled:
                context["step_results"].append({"step": step.name, "status": "skipped"})
                continue
            info = task_by_name.get(step.name, {})
            if info.get("status") == "completed":
                context["step_results"].append({
                    "step": step.name,
                    "status": "completed",
                    "duration": (context.get("step_durations") or {}).get(step.name, 0.0),
                    "data": context["step_data"].get(step.name, {}),
                })
            else:
                context["step_results"].append({
                    "step": step.name,
                    "status": "failed",
                    "error": info.get("error") or "未执行完成",
                })
                context["errors"].append({
                    "step": step.name,
                    "error": info.get("error") or "未执行完成",
                })

        failed = [r for r in context["step_results"] if r["status"] == "failed"]
        if failed and not workflow_cfg.get("continue_on_error", False):
            overall_result["status"] = "failed"

    def _update_workflow_stats(self, context: Dict[str, Any]) -> None:
        """把“至今的执行进度”写入上下文，供进化等下游步骤评估"""
        context["data"]["_workflow_stats"] = {
            "attempted": len(context["step_data"]),
            "failed": len(context["errors"]),
            "total_steps": len(self.workflow_steps),
        }

    def _record_step_result(self, context: Dict[str, Any], step_result: Dict[str, Any],
                            append: bool = True) -> None:
        """合并单个步骤的产出到上下文（stats/status 等通用键加步骤前缀）"""
        if not step_result:
            return

        with self._context_lock:
            if append:
                context["step_results"].append(step_result)

            status = step_result.get("status")
            step_name = step_result.get("step")

            if status in ("completed", "skipped"):
                # 跳过的步骤同样视为“已解决”，否则依赖它的步骤会被误判为依赖缺失
                if step_name not in context["completed_steps"]:
                    context["completed_steps"].append(step_name)

            if status == "completed":
                step_data = dict(step_result.get("data") or {})
                context["step_data"][step_name] = step_data
                for key, value in step_data.items():
                    if key in ("stats", "status", "articles_processed"):
                        context["data"][f"{step_name}_{key}"] = value
                    else:
                        context["data"][key] = value
                context["data"]["_step_data"] = context["step_data"]
            elif status == "failed":
                error = step_result.get("error", "未知错误")
                if not any(e.get("step") == step_name for e in context["errors"]):
                    context["errors"].append({"step": step_name, "error": error})

            self._update_workflow_stats(context)

    # ------------------------------------------------------------------ 周期汇总
    def _attach_cycle_summary(self, context: Dict[str, Any]) -> None:
        """把反馈与进化状态挂到上下文，供报告生成"""
        data = context["data"]
        data["feedback_summary"] = self._submit_cycle_feedback(context)
        evolution = self.modules.get("evolution")
        if evolution is not None and hasattr(evolution, "get_status"):
            try:
                data["evolution_summary"] = evolution.get_status()
            except Exception as e:
                self.logger.warning(f"进化状态汇总失败: {e}")

    def _submit_cycle_feedback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """把本周期实测指标提交到反馈循环"""
        summary: Dict[str, Any] = {"total": 0, "queue": 0, "recent": []}
        if self.feedback_loop is None:
            return summary

        from .feedback_loop import FeedbackPriority, FeedbackType

        data = context.get("data", {})
        articles = data.get("articles") or []
        payload = {
            "articles": data.get("total", 0),
            "passed": len(articles),
            "rejected": data.get("rejected_count", 0),
            "entities": data.get("total_entities", 0),
            "relations": data.get("total_relations", 0),
            "evolved": bool(data.get("evolved")),
            "errors": len(context.get("errors") or []),
        }
        priority = (
            FeedbackPriority.HIGH if payload["errors"] else FeedbackPriority.MEDIUM
        )
        try:
            self.feedback_loop.submit_feedback(
                FeedbackType.PERFORMANCE, "engine", "evolution", payload, priority
            )
            if payload["errors"]:
                self.feedback_loop.submit_feedback(
                    FeedbackType.ERROR,
                    "engine",
                    "evolution",
                    {"errors": context.get("errors")[:3]},
                    FeedbackPriority.HIGH,
                )
            stats = self.feedback_loop.get_stats()
            summary.update({
                "total": stats.get("total_feedback", 0),
                "queue": stats.get("feedback_queue_size", 0),
                "recent": self.feedback_loop.get_feedback_history(limit=3),
            })
        except Exception as e:
            self.logger.warning(f"提交反馈失败: {e}")
        return summary

    def _persist_state(self, overall_result: Dict[str, Any]) -> None:
        """把引擎指标与本周期的进化结果写入状态管理器，并记录专利证据"""
        if self.state_manager is not None:
            try:
                from .state_manager import StateType

                self.state_manager.set_state(
                    "engine.metrics", dict(self.metrics), StateType.SYSTEM
                )
                self.state_manager.set_state(
                    "engine.last_cycle",
                    {
                        "status": overall_result.get("status"),
                        "workflow_id": overall_result.get("workflow_id"),
                        "finished_at": datetime.now().isoformat(),
                        "duration": overall_result.get("metrics", {}).get("total_duration", 0.0),
                    },
                    StateType.SYSTEM,
                )
                evolution = self.modules.get("evolution")
                if evolution is not None and hasattr(evolution, "get_tunable_values"):
                    self.state_manager.set_state(
                        "evolution.tunables",
                        evolution.get_tunable_values(),
                        StateType.CONFIG,
                    )
                self.state_manager.save_state()
            except Exception as e:
                self.logger.warning(f"状态持久化失败: {e}")

        self._record_evidence(overall_result)
        self._record_cycle_dataset(overall_result)
        self._record_metrics(overall_result)

    def _record_metrics(self, overall_result: Dict[str, Any]) -> None:
        """用 utils.metrics.MetricsCollector 记录周期级指标"""
        collector = self.metrics_collector
        if collector is None:
            return
        try:
            from ..utils.metrics import MetricType

            data = overall_result.get("context", {}).get("data", {})
            duration = overall_result.get("metrics", {}).get("total_duration", 0.0)
            collector.record("articles_collected", data.get("total", 0),
                             MetricType.GAUGE, unit="articles")
            collector.record("articles_passed", len(data.get("articles") or []),
                             MetricType.GAUGE, unit="articles")
            collector.record("articles_rejected", data.get("rejected_count", 0),
                             MetricType.GAUGE, unit="articles")
            collector.record("entities_extracted", data.get("total_entities", 0),
                             MetricType.GAUGE, unit="entities")
            collector.record("relations_extracted", data.get("total_relations", 0),
                             MetricType.GAUGE, unit="relations")
            collector.record("cycle_duration", duration,
                             MetricType.HISTOGRAM, unit="seconds")

            evolution = self.modules.get("evolution")
            for key in ("learn_rate", "reject_rate", "accuracy_rate"):
                if evolution is not None and key in (evolution.last_metrics or {}):
                    collector.record(key, evolution.last_metrics[key], MetricType.GAUGE)
            if evolution is not None:
                for name, value in (evolution.get_tunable_values() or {}).items():
                    collector.record(f"tunable_{name.split('.')[-1]}", value, MetricType.GAUGE)
        except Exception as e:
            self.logger.warning(f"记录周期指标失败: {e}")

    def _record_cycle_dataset(self, overall_result: Dict[str, Any]) -> None:
        """把本周期指标写入长期效果评估数据集（data/cycle_metrics.jsonl）"""
        if self.evaluator is None:
            return
        try:
            data = overall_result.get("context", {}).get("data", {})
            evolution = self.modules.get("evolution")
            metrics = dict(getattr(evolution, "last_metrics", {}) or {})
            metrics.update({
                "articles": data.get("total", 0),
                "passed": len(data.get("articles") or []),
                "rejected": data.get("rejected_count", 0),
                "duration": overall_result.get("metrics", {}).get("total_duration", 0.0),
            })
            tunables = (
                evolution.get_tunable_values()
                if evolution is not None and hasattr(evolution, "get_tunable_values")
                else {}
            )
            self.evaluator.record_cycle(
                metrics=metrics,
                tunables=tunables,
                changes=data.get("changes") or [],
                cycle_id=overall_result.get("workflow_id"),
                tunables_before=overall_result.get("tunables_before") or {},
            )
        except Exception as e:
            self.logger.warning(f"写入周期数据集失败: {e}")

    def _record_evidence(self, overall_result: Dict[str, Any]) -> None:
        """把本轮的参数调整写入专利证据（JSONL），形成可追溯的创新证据链"""
        if self.evidence is None:
            return
        data = overall_result.get("context", {}).get("data", {})
        changes = data.get("changes") or []
        if not changes:
            return
        try:
            for change in changes:
                self.evidence.log_evolution(
                    module="credibility",
                    decision=f"adjust {change['parameter']}",
                    reason=change.get("reason", ""),
                    before_state={"value": change.get("before")},
                    after_state={"value": change.get("after")},
                    impact_score=float(abs(change.get("delta", 0.0))),
                )
        except Exception as e:
            self.logger.warning(f"写入专利证据失败: {e}")
    
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
            max_cycles: 最大运行次数（None 表示不限制）
        """
        self.logger.info(f"开始连续运行，间隔: {interval}秒，最大次数: {max_cycles or '无限'}")

        cycle_count = 0
        self._stop_requested = False
        self.state = EngineState.RUNNING

        try:
            while not self._stop_requested:
                if max_cycles and cycle_count >= max_cycles:
                    self.logger.info(f"达到最大运行次数: {max_cycles}")
                    break

                cycle_count += 1
                self.logger.info(f"开始第 {cycle_count} 个周期")

                # 运行工作流（run_workflow 内部会临时占用 _executing 标记）
                result = self.run_workflow()

                # 检查结果
                if result["status"] == "failed":
                    self.logger.error("工作流失败，停止连续运行")
                    break

                if self._stop_requested or (max_cycles and cycle_count >= max_cycles):
                    break

                self.logger.info(f"等待 {interval} 秒后开始下一个周期...")
                # 分段等待，以便及时响应停止请求
                for _ in range(max(1, int(interval))):
                    if self._stop_requested:
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
        self._stop_requested = True
        
        # 等待当前工作流完成
        time.sleep(0.2)
        
        self.state = EngineState.STOPPED
        self.logger.info("系统引擎已停止")
    
    def metrics_snapshot(self) -> Dict[str, float]:
        """供 Prometheus 端点采集的扁平指标"""
        snapshot = {
            "autonews_cycles_total": self.metrics.get("total_cycles", 0),
            "autonews_cycles_success_total": self.metrics.get("successful_cycles", 0),
            "autonews_cycles_failed_total": self.metrics.get("failed_cycles", 0),
            "autonews_processing_seconds_total": self.metrics.get("total_processing_time", 0.0),
        }

        credibility = self.modules.get("credibility")
        if credibility is not None:
            snapshot["autonews_theta_high"] = getattr(credibility, "theta_high", 0.0)
            snapshot["autonews_theta_low"] = getattr(credibility, "theta_low", 0.0)
            stats = getattr(credibility, "stats", {}) or {}
            snapshot["autonews_reject_total"] = stats.get("reject", 0)
            snapshot["autonews_learn_total"] = stats.get("learn", 0)

        knowledge = self.modules.get("knowledge")
        if knowledge is not None:
            stats = getattr(knowledge, "stats", {}) or {}
            snapshot["autonews_entities_total"] = stats.get("entities_extracted", 0)
            snapshot["autonews_relations_total"] = stats.get("relations_extracted", 0)

        evolution = self.modules.get("evolution")
        last_metrics = getattr(evolution, "last_metrics", {}) if evolution else {}
        for key in ("learn_rate", "reject_rate", "accuracy_rate",
                    "extraction_yield", "relation_yield"):
            if key in last_metrics:
                snapshot[f"autonews_{key}"] = last_metrics[key]

        return snapshot

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        status = {
            "state": self.state.value,
            "metrics": self.metrics,
            "run_metrics": self.run_metrics,
            "modules": {name: module.get_status() if hasattr(module, 'get_status') else "unknown" 
                    for name, module in self.modules.items()},
            "workflow_steps": [step.name for step in self.workflow_steps if step.enabled],
            "timestamp": datetime.now().isoformat(),
        }
        if self.state_manager is not None:
            try:
                status["state_manager"] = self.state_manager.get_stats()
            except Exception:
                pass
        if self.feedback_loop is not None:
            try:
                status["feedback"] = self.feedback_loop.get_stats()
            except Exception:
                pass
        if self.metrics_collector is not None:
            try:
                status["metrics_collector"] = {
                    "name": self.metrics_collector.collector_name,
                    "series": len(self.metrics_collector.metrics),
                }
            except Exception:
                pass
        if self.evaluator is not None:
            try:
                status["evaluation"] = self.evaluator.evaluate()
            except Exception:
                pass
        return status
    
    def shutdown(self):
        """关闭引擎，释放资源"""
        self.logger.info("关闭系统引擎...")
        
        self.stop()

        # 先停掉后台组件，避免线程在关闭模块时仍在访问它们
        if self.feedback_loop is not None:
            try:
                self.feedback_loop.shutdown()
            except Exception as e:
                self.logger.warning(f"关闭反馈循环失败: {e}")
            self.feedback_loop = None

        if self.state_manager is not None:
            try:
                self.state_manager.save_state()
            except Exception as e:
                self.logger.warning(f"保存状态失败: {e}")
            try:
                self.state_manager.shutdown()
            except Exception as e:
                self.logger.warning(f"关闭状态管理器失败: {e}")
            self.state_manager = None

        # 导出长期效果评估数据集（CSV，便于用 Excel/pandas 出图）
        if self.evaluator is not None and self.export_evaluation_csv:
            try:
                exported = self.evaluator.export_csv()
                if exported:
                    self.logger.info(f"周期数据集已导出: {exported}")
            except Exception as e:
                self.logger.warning(f"导出周期数据集失败: {e}")

        # 导出指标快照（utils.metrics）
        if self.metrics_collector is not None:
            try:
                self.metrics_collector.export_to_json(self.metrics_export_path)
            except Exception as e:
                self.logger.warning(f"导出指标失败: {e}")

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