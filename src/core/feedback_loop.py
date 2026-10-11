"""
反馈循环控制器
实现系统的闭环优化和自适应调整
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
import statistics


class FeedbackType(Enum):
    """反馈类型枚举"""
    PERFORMANCE = "performance"      # 性能反馈
    QUALITY = "quality"              # 质量反馈
    ERROR = "error"                  # 错误反馈
    SUCCESS = "success"              # 成功反馈
    ADAPTATION = "adaptation"        # 自适应反馈
    OPTIMIZATION = "optimization"    # 优化反馈


class FeedbackPriority(Enum):
    """反馈优先级枚举"""
    LOW = "low"      # 低优先级，定期处理
    MEDIUM = "medium"  # 中优先级，尽快处理
    HIGH = "high"    # 高优先级，立即处理
    CRITICAL = "critical"  # 关键优先级，中断处理


@dataclass
class FeedbackItem:
    """反馈项定义"""
    id: str
    type: FeedbackType
    priority: FeedbackPriority
    source: str  # 反馈来源模块
    target: str  # 反馈目标模块
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    processed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "source": self.source,
            "target": self.target,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "result": self.result,
        }


@dataclass
class LearningPattern:
    """学习模式定义"""
    pattern_id: str
    description: str
    conditions: List[Dict[str, Any]]  # 触发条件
    actions: List[Dict[str, Any]]     # 执行动作
    weight: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    last_triggered: Optional[datetime] = None
    
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def should_trigger(self, context: Dict[str, Any]) -> bool:
        """检查是否应该触发"""
        for condition in self.conditions:
            if not self._evaluate_condition(condition, context):
                return False
        return True
    
    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """评估条件"""
        # 简化的条件评估逻辑
        # 实际实现中应该更复杂
        condition_type = condition.get("type", "threshold")
        
        if condition_type == "threshold":
            metric = condition.get("metric")
            operator = condition.get("operator", ">=")
            value = condition.get("value")
            
            if metric in context:
                actual_value = context[metric]
                
                if operator == ">=":
                    return actual_value >= value
                elif operator == "<=":
                    return actual_value <= value
                elif operator == ">":
                    return actual_value > value
                elif operator == "<":
                    return actual_value < value
                elif operator == "==":
                    return actual_value == value
                elif operator == "!=":
                    return actual_value != value
        
        return False


class FeedbackLoopController:
    """反馈循环控制器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化反馈循环控制器
        
        Args:
            config: 控制器配置
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 反馈队列（优先级队列）
        self.feedback_queue = queue.PriorityQueue()
        
        # 反馈存储
        self.feedback_history: List[FeedbackItem] = []
        self.max_history_size = self.config.get("max_history_size", 10000)
        
        # 学习模式
        self.learning_patterns: Dict[str, LearningPattern] = {}
        self._initialize_learning_patterns()
        
        # 适配器注册表
        self.adapters: Dict[str, Callable] = {}
        self._initialize_adapters()
        
        # 控制参数
        self.feedback_window_size = self.config.get("feedback_window_size", 100)
        self.learning_rate = self.config.get("learning_rate", 0.01)
        self.adaptation_threshold = self.config.get("adaptation_threshold", 0.7)
        
        # 统计信息
        self.stats = {
            "total_feedback": 0,
            "processed_feedback": 0,
            "successful_adaptations": 0,
            "failed_adaptations": 0,
            "pattern_triggers": 0,
            "last_adaptation": None,
        }
        
        # 状态
        self.is_running = False
        self.processing_thread = None
        self.adaptation_lock = threading.Lock()
        
        # 回调函数
        self.callbacks = {
            "before_processing": [],
            "after_processing": [],
            "before_adaptation": [],
            "after_adaptation": [],
            "pattern_triggered": [],
        }
        
        self.logger.info("反馈循环控制器初始化完成")
    
    def _initialize_learning_patterns(self):
        """初始化学习模式"""
        # 性能下降模式
        self.learning_patterns["performance_decline"] = LearningPattern(
            pattern_id="performance_decline",
            description="检测到性能下降时调整参数",
            conditions=[
                {
                    "type": "threshold",
                    "metric": "performance_score",
                    "operator": "<=",
                    "value": 0.7
                },
                {
                    "type": "threshold",
                    "metric": "consecutive_failures",
                    "operator": ">=",
                    "value": 3
                }
            ],
            actions=[
                {
                    "type": "parameter_adjustment",
                    "target": "credibility.weights",
                    "adjustment": {"source": -0.05, "content": +0.05}
                },
                {
                    "type": "learning_rate_adjustment",
                    "factor": 0.8
                }
            ]
        )
        
        # 成功模式
        self.learning_patterns["success_pattern"] = LearningPattern(
            pattern_id="success_pattern",
            description="连续成功时优化参数",
            conditions=[
                {
                    "type": "threshold",
                    "metric": "success_rate",
                    "operator": ">=",
                    "value": 0.9
                },
                {
                    "type": "threshold",
                    "metric": "consecutive_successes",
                    "operator": ">=",
                    "value": 5
                }
            ],
            actions=[
                {
                    "type": "reinforce_pattern",
                    "target": "current_parameters",
                    "strength": 0.1
                },
                {
                    "type": "exploration_increase",
                    "factor": 1.2
                }
            ]
        )
        
        # 错误模式
        self.learning_patterns["error_pattern"] = LearningPattern(
            pattern_id="error_pattern",
            description="检测到系统错误时恢复",
            conditions=[
                {
                    "type": "threshold",
                    "metric": "error_rate",
                    "operator": ">=",
                    "value": 0.1
                }
            ],
            actions=[
                {
                    "type": "fallback_configuration",
                    "target": "system"
                },
                {
                    "type": "error_recovery",
                    "strategy": "reset_and_retry"
                }
            ]
        )
    
    def _initialize_adapters(self):
        """初始化适配器"""
        # 注册参数调整适配器
        self.adapters["parameter_adjustment"] = self._adjust_parameters
        self.adapters["learning_rate_adjustment"] = self._adjust_learning_rate
        self.adapters["reinforce_pattern"] = self._reinforce_pattern
        self.adapters["exploration_increase"] = self._increase_exploration
        self.adapters["fallback_configuration"] = self._apply_fallback_config
        self.adapters["error_recovery"] = self._recover_from_error
    
    def submit_feedback(self, feedback_type: FeedbackType, source: str, target: str, 
                       data: Dict[str, Any], priority: FeedbackPriority = FeedbackPriority.MEDIUM) -> str:
        """
        提交反馈
        
        Args:
            feedback_type: 反馈类型
            source: 反馈来源
            target: 反馈目标
            data: 反馈数据
            priority: 反馈优先级
            
        Returns:
            反馈ID
        """
        feedback_id = f"fb_{int(time.time())}_{len(self.feedback_history)}"
        
        feedback = FeedbackItem(
            id=feedback_id,
            type=feedback_type,
            priority=priority,
            source=source,
            target=target,
            data=data,
        )
        
        # 根据优先级计算队列优先级
        # 优先级越高，数字越小（Python的PriorityQueue是最小堆）
        priority_map = {
            FeedbackPriority.LOW: 3,
            FeedbackPriority.MEDIUM: 2,
            FeedbackPriority.HIGH: 1,
            FeedbackPriority.CRITICAL: 0,
        }
        
        queue_priority = priority_map.get(priority, 2)
        self.feedback_queue.put((queue_priority, feedback))
        
        # 保存到历史记录
        self.feedback_history.append(feedback)
        if len(self.feedback_history) > self.max_history_size:
            self.feedback_history = self.feedback_history[-self.max_history_size:]
        
        self.stats["total_feedback"] += 1
        self.logger.debug(f"收到反馈: {feedback_id} ({feedback_type.value}) from {source} to {target}")
        
        # 如果处理线程未运行，启动它
        if not self.is_running:
            self.start_processing()
        
        return feedback_id
    
    def start_processing(self):
        """开始处理反馈"""
        if self.is_running:
            self.logger.warning("反馈处理器已经在运行中")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True,
            name="FeedbackProcessor"
        )
        self.processing_thread.start()
        
        self.logger.info("反馈处理器已启动")
    
    def _processing_loop(self):
        """反馈处理循环"""
        while self.is_running:
            try:
                # 从队列获取反馈
                try:
                    priority, feedback = self.feedback_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                self._process_feedback(feedback)
                
                # 标记任务完成
                self.feedback_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"反馈处理异常: {e}")
    
    def _process_feedback(self, feedback: FeedbackItem):
        """处理单个反馈"""
        self.logger.info(f"处理反馈: {feedback.id} ({feedback.type.value})")
        
        # 调用前置回调
        for callback in self.callbacks["before_processing"]:
            callback(feedback)
        
        try:
            # 根据反馈类型处理
            if feedback.type == FeedbackType.PERFORMANCE:
                result = self._handle_performance_feedback(feedback)
            elif feedback.type == FeedbackType.QUALITY:
                result = self._handle_quality_feedback(feedback)
            elif feedback.type == FeedbackType.ERROR:
                result = self._handle_error_feedback(feedback)
            elif feedback.type == FeedbackType.SUCCESS:
                result = self._handle_success_feedback(feedback)
            elif feedback.type == FeedbackType.ADAPTATION:
                result = self._handle_adaptation_feedback(feedback)
            elif feedback.type == FeedbackType.OPTIMIZATION:
                result = self._handle_optimization_feedback(feedback)
            else:
                result = {"status": "unknown_type", "message": "未知的反馈类型"}
            
            # 更新反馈状态
            feedback.processed = True
            feedback.processed_at = datetime.now()
            feedback.result = result
            
            self.stats["processed_feedback"] += 1
            
            # 检查是否需要自适应调整
            if feedback.type in [FeedbackType.PERFORMANCE, FeedbackType.QUALITY, FeedbackType.ERROR]:
                self._check_for_adaptation(feedback)
            
            # 调用后置回调
            for callback in self.callbacks["after_processing"]:
                callback(feedback, result)
            
            self.logger.debug(f"反馈处理完成: {feedback.id}")
            
        except Exception as e:
            self.logger.error(f"反馈处理失败: {feedback.id} - {e}")
            feedback.result = {"status": "error", "error": str(e)}
    
    def _handle_performance_feedback(self, feedback: FeedbackItem) -> Dict[str, Any]:
        """处理性能反馈"""
        data = feedback.data
        
        # 提取性能指标
        metrics = data.get("metrics", {})
        context = data.get("context", {})
        
        # 分析性能趋势
        performance_score = metrics.get("performance_score", 0.5)
        latency = metrics.get("latency", 0.0)
        throughput = metrics.get("throughput", 0.0)
        
        # 检查是否需要优化
        need_optimization = performance_score < self.adaptation_threshold
        
        return {
            "status": "processed",
            "action": "performance_analysis",
            "performance_score": performance_score,
            "need_optimization": need_optimization,
            "suggested_actions": self._suggest_performance_actions(metrics, context),
        }
    
    def _handle_quality_feedback(self, feedback: FeedbackItem) -> Dict[str, Any]:
        """处理质量反馈"""
        data = feedback.data
        
        quality_score = data.get("quality_score", 0.5)
        dimensions = data.get("dimensions", {})
        
        # 分析质量维度
        source_quality = dimensions.get("source", 0.5)
        content_quality = dimensions.get("content", 0.5)
        freshness = dimensions.get("freshness", 0.5)
        
        # 计算综合质量
        weights = self.config.get("quality_weights", {
            "source": 0.4,
            "content": 0.4,
            "freshness": 0.2,
        })
        
        weighted_score = (
            weights["source"] * source_quality +
            weights["content"] * content_quality +
            weights["freshness"] * freshness
        )
        
        return {
            "status": "processed",
            "action": "quality_analysis",
            "quality_score": quality_score,
            "weighted_score": weighted_score,
            "dimensions": dimensions,
            "suggested_improvements": self._suggest_quality_improvements(dimensions),
        }
    
    def _handle_error_feedback(self, feedback: FeedbackItem) -> Dict[str, Any]:
        """处理错误反馈"""
        data = feedback.data
        
        error_type = data.get("error_type", "unknown")
        error_message = data.get("error_message", "")
        error_context = data.get("context", {})
        
        # 记录错误
        error_rate = self._update_error_statistics(error_type, error_context)
        
        # 检查是否需要紧急处理
        needs_emergency = error_rate > 0.1 or error_type in ["critical", "fatal"]
        
        return {
            "status": "processed",
            "action": "error_handling",
            "error_type": error_type,
            "error_rate": error_rate,
            "needs_emergency": needs_emergency,
            "recovery_actions": self._suggest_error_recovery(error_type, error_context),
        }
    
    def _handle_success_feedback(self, feedback: FeedbackItem) -> Dict[str, Any]:
        """处理成功反馈"""
        data = feedback.data
        
        success_metrics = data.get("metrics", {})
        context = data.get("context", {})
        
        # 记录成功
        success_rate = self._update_success_statistics(success_metrics, context)
        
        # 学习成功模式
        learned_patterns = self._learn_from_success(success_metrics, context)
        
        return {
            "status": "processed",
            "action": "success_analysis",
            "success_rate": success_rate,
            "learned_patterns": learned_patterns,
            "reinforcement_actions": self._suggest_reinforcement_actions(success_metrics),
        }
    
    def _handle_adaptation_feedback(self, feedback: FeedbackItem) -> Dict[str, Any]:
        """处理自适应反馈"""
        data = feedback.data
        
        adaptation_type = data.get("adaptation_type", "parameter")
        parameters = data.get("parameters", {})
        results = data.get("results", {})
        
        # 评估自适应效果
        effectiveness = self._evaluate_adaptation_effectiveness(results)
        
        # 更新自适应策略
        updated_strategy = self._update_adaptation_strategy(adaptation_type, parameters, effectiveness)
        
        return {
            "status": "processed",
            "action": "adaptation_evaluation",
            "adaptation_type": adaptation_type,
            "effectiveness": effectiveness,
            "updated_strategy": updated_strategy,
        }
    
    def _handle_optimization_feedback(self, feedback: FeedbackItem) -> Dict[str, Any]:
        """处理优化反馈"""
        data = feedback.data
        
        optimization_target = data.get("target", "performance")
        parameters = data.get("parameters", {})
        results = data.get("results", {})
        
        # 执行优化
        optimization_result = self._perform_optimization(optimization_target, parameters, results)
        
        # 更新优化策略
        updated_optimization = self._update_optimization_strategy(optimization_target, optimization_result)
        
        return {
            "status": "processed",
            "action": "optimization_execution",
            "optimization_target": optimization_target,
            "optimization_result": optimization_result,
            "updated_strategy": updated_optimization,
        }
    
    def _check_for_adaptation(self, feedback: FeedbackItem):
        """检查是否需要自适应调整"""
        # 获取最近的反馈进行分析
        recent_feedback = self._get_recent_feedback(self.feedback_window_size)
        
        if not recent_feedback:
            return
        
        # 分析反馈模式
        context = self._create_analysis_context(recent_feedback)
        
        # 检查学习模式
        triggered_patterns = []
        for pattern_id, pattern in self.learning_patterns.items():
            if pattern.should_trigger(context):
                triggered_patterns.append(pattern_id)
                
                # 触发模式
                self._trigger_learning_pattern(pattern, context)
                
                # 记录触发
                pattern.last_triggered = datetime.now()
                self.stats["pattern_triggers"] += 1
                
                # 调用回调
                for callback in self.callbacks["pattern_triggered"]:
                    callback(pattern, context)
        
        if triggered_patterns:
            self.logger.info(f"触发的学习模式: {triggered_patterns}")
    
    def _trigger_learning_pattern(self, pattern: LearningPattern, context: Dict[str, Any]):
        """触发学习模式"""
        self.logger.info(f"触发学习模式: {pattern.pattern_id}")
        
        # 调用前置回调
        for callback in self.callbacks["before_adaptation"]:
            callback(pattern, context)
        
        try:
            # 执行模式动作
            for action in pattern.actions:
                action_type = action.get("type")
                adapter = self.adapters.get(action_type)
                
                if adapter:
                    result = adapter(action, context)
                    if result.get("success", False):
                        pattern.success_count += 1
                    else:
                        pattern.failure_count += 1
                else:
                    self.logger.warning(f"未知的动作类型: {action_type}")
            
            self.stats["successful_adaptations"] += 1
            self.stats["last_adaptation"] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.error(f"学习模式执行失败: {pattern.pattern_id} - {e}")
            pattern.failure_count += 1
            self.stats["failed_adaptations"] += 1
        
        finally:
            # 调用后置回调
            for callback in self.callbacks["after_adaptation"]:
                callback(pattern, context)
    
    def _get_recent_feedback(self, window_size: int) -> List[FeedbackItem]:
        """获取最近的反馈"""
        return self.feedback_history[-window_size:] if self.feedback_history else []
    
    def _create_analysis_context(self, feedback_list: List[FeedbackItem]) -> Dict[str, Any]:
        """创建分析上下文"""
        context = {
            "total_feedback": len(feedback_list),
            "performance_scores": [],
            "quality_scores": [],
            "error_types": {},
            "success_count": 0,
            "error_count": 0,
        }
        
        for feedback in feedback_list:
            if feedback.type == FeedbackType.PERFORMANCE:
                score = feedback.data.get("metrics", {}).get("performance_score", 0.5)
                context["performance_scores"].append(score)
            elif feedback.type == FeedbackType.QUALITY:
                score = feedback.data.get("quality_score", 0.5)
                context["quality_scores"].append(score)
            elif feedback.type == FeedbackType.ERROR:
                context["error_count"] += 1
                error_type = feedback.data.get("error_type", "unknown")
                context["error_types"][error_type] = context["error_types"].get(error_type, 0) + 1
            elif feedback.type == FeedbackType.SUCCESS:
                context["success_count"] += 1
        
        # 计算统计数据
        if context["performance_scores"]:
            context["avg_performance"] = statistics.mean(context["performance_scores"])
            context["performance_std"] = statistics.stdev(context["performance_scores"]) if len(context["performance_scores"]) > 1 else 0
        
        if context["quality_scores"]:
            context["avg_quality"] = statistics.mean(context["quality_scores"])
            context["quality_std"] = statistics.stdev(context["quality_scores"]) if len(context["quality_scores"]) > 1 else 0
        
        context["success_rate"] = (
            context["success_count"] / len(feedback_list) if feedback_list else 0
        )
        context["error_rate"] = (
            context["error_count"] / len(feedback_list) if feedback_list else 0
        )
        
        return context
    
    # 适配器方法
    def _adjust_parameters(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """调整参数适配器"""
        target = action.get("target", "")
        adjustment = action.get("adjustment", {})
        
        # 这里应该实现具体的参数调整逻辑
        # 例如，调整可信度权重
        self.logger.info(f"调整参数: {target}，调整值: {adjustment}")
        
        return {"success": True, "message": f"已调整参数: {target}"}
    
    def _adjust_learning_rate(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """调整学习率适配器"""
        factor = action.get("factor", 1.0)
        
        old_rate = self.learning_rate
        self.learning_rate *= factor
        
        self.logger.info(f"调整学习率: {old_rate} -> {self.learning_rate}")
        
        return {"success": True, "old_rate": old_rate, "new_rate": self.learning_rate}
    
    def _reinforce_pattern(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """强化模式适配器"""
        target = action.get("target", "")
        strength = action.get("strength", 0.1)
        
        # 强化当前成功的模式
        self.logger.info(f"强化模式: {target}，强度: {strength}")
        
        return {"success": True, "action": "reinforced_pattern"}
    
    def _increase_exploration(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """增加探索适配器"""
        factor = action.get("factor", 1.2)
        
        # 增加探索率
        self.logger.info(f"增加探索率，因子: {factor}")
        
        return {"success": True, "exploration_increased": True}
    
    def _apply_fallback_config(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """应用回退配置适配器"""
        target = action.get("target", "")
        
        # 应用回退配置
        self.logger.info(f"应用回退配置到: {target}")
        
        return {"success": True, "fallback_applied": True}
    
    def _recover_from_error(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """从错误中恢复适配器"""
        strategy = action.get("strategy", "reset_and_retry")
        
        # 执行恢复策略
        self.logger.info(f"执行错误恢复策略: {strategy}")
        
        return {"success": True, "recovery_strategy": strategy}
    
    # 工具方法（占位实现）
    def _suggest_performance_actions(self, metrics: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """建议性能优化动作"""
        suggestions = []
        
        if metrics.get("latency", 0) > 1000:  # 假设1000ms是阈值
            suggestions.append({
                "action": "optimize_processing",
                "description": "处理延迟过高，优化处理流水线",
                "priority": "high"
            })
        
        return suggestions
    
    def _suggest_quality_improvements(self, dimensions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """建议质量改进动作"""
        improvements = []
        
        if dimensions.get("source", 0.5) < 0.7:
            improvements.append({
                "action": "improve_source_selection",
                "description": "来源质量较低，需要选择更可靠的信源",
                "priority": "medium"
            })
        
        return improvements
    
    def _update_error_statistics(self, error_type: str, context: Dict[str, Any]) -> float:
        """更新错误统计"""
        # 简化的实现
        return 0.05  # 返回错误率
    
    def _suggest_error_recovery(self, error_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """建议错误恢复动作"""
        recovery_actions = []
        
        if error_type in ["connection", "timeout"]:
            recovery_actions.append({
                "action": "retry_with_backoff",
                "description": "使用指数退避策略重试",
                "max_retries": 3
            })
        
        return recovery_actions
    
    def _update_success_statistics(self, metrics: Dict[str, Any], context: Dict[str, Any]) -> float:
        """更新成功统计"""
        # 简化的实现
        return 0.95  # 返回成功率
    
    def _learn_from_success(self, metrics: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """从成功中学习"""
        learned = []
        
        if metrics.get("accuracy", 0) > 0.9:
            learned.append("high_accuracy_pattern")
        
        return learned
    
    def _suggest_reinforcement_actions(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """建议强化动作"""
        reinforcements = []
        
        if metrics.get("consistency", 0) > 0.8:
            reinforcements.append({
                "action": "reinforce_current_strategy",
                "description": "策略一致性高，强化当前策略",
                "strength": 0.1
            })
        
        return reinforcements
    
    def _evaluate_adaptation_effectiveness(self, results: Dict[str, Any]) -> float:
        """评估自适应效果"""
        # 简化的实现
        return results.get("improvement", 0.1)
    
    def _update_adaptation_strategy(self, adaptation_type: str, parameters: Dict[str, Any], 
                                   effectiveness: float) -> Dict[str, Any]:
        """更新自适应策略"""
        return {
            "type": adaptation_type,
            "effectiveness": effectiveness,
            "updated": True
        }
    
    def _perform_optimization(self, target: str, parameters: Dict[str, Any], 
                            results: Dict[str, Any]) -> Dict[str, Any]:
        """执行优化"""
        return {
            "target": target,
            "improvement": 0.05,  # 简化的改进值
            "parameters_updated": True
        }
    
    def _update_optimization_strategy(self, target: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """更新优化策略"""
        return {
            "target": target,
            "strategy_updated": True,
            "improvement": result.get("improvement", 0)
        }
    
    def register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"已注册回调函数到事件: {event}")
        else:
            self.logger.warning(f"未知的事件类型: {event}")
    
    def get_feedback_history(self, limit: int = 100, feedback_type: Optional[FeedbackType] = None) -> List[Dict[str, Any]]:
        """获取反馈历史"""
        history = self.feedback_history[-limit:] if self.feedback_history else []
        
        if feedback_type:
            history = [fb for fb in history if fb.type == feedback_type]
        
        return [fb.to_dict() for fb in history]
    
    def get_learning_patterns(self) -> Dict[str, Dict[str, Any]]:
        """获取学习模式"""
        patterns = {}
        for pattern_id, pattern in self.learning_patterns.items():
            patterns[pattern_id] = {
                "pattern_id": pattern.pattern_id,
                "description": pattern.description,
                "success_rate": pattern.success_rate(),
                "success_count": pattern.success_count,
                "failure_count": pattern.failure_count,
                "last_triggered": pattern.last_triggered.isoformat() if pattern.last_triggered else None,
                "weight": pattern.weight,
            }
        return patterns
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "feedback_queue_size": self.feedback_queue.qsize(),
            "total_history_size": len(self.feedback_history),
            "learning_rate": self.learning_rate,
            "adaptation_threshold": self.adaptation_threshold,
            "is_running": self.is_running,
        }
    
    def stop(self, wait: bool = True):
        """停止反馈处理器"""
        self.logger.info("停止反馈处理器...")
        self.is_running = False
        
        if wait and self.processing_thread:
            self.processing_thread.join(timeout=10)
        
        self.logger.info("反馈处理器已停止")
    
    def shutdown(self):
        """关闭反馈循环控制器"""
        self.stop(wait=True)
        self.logger.info("反馈循环控制器已关闭")