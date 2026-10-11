"""
保留策略
根据重要性、时间等因素决定记忆的保留策略
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
import numpy as np
from dataclasses import dataclass

class RetentionStrategy(Enum):
    """保留策略枚举"""
    AGGRESSIVE = "aggressive"      # 积极保留：保留大多数记忆
    BALANCED = "balanced"          # 平衡保留：权衡重要性和空间
    CONSERVATIVE = "conservative"  # 保守保留：只保留重要记忆
    ADAPTIVE = "adaptive"          # 自适应保留：根据系统状态调整

@dataclass
class RetentionRule:
    """保留规则"""
    name: str
    condition: Any  # 条件判断函数或表达式
    priority: int = 1
    action: str = "retain"  # retain, review, forget
    
    def evaluate(self, memory_data: Dict[str, Any]) -> Tuple[bool, float]:
        """评估规则是否满足"""
        # 这里可以根据实际条件判断
        # 简化实现：总是返回False
        return False, 0.0

@dataclass
class RetentionDecision:
    """保留决策"""
    memory_id: str
    action: str  # retain, forget, review
    confidence: float
    reason: str
    suggested_priority: int = 1
    expiration_date: Optional[datetime] = None

class RetentionPolicy:
    """保留策略管理器"""
    
    def __init__(self, 
                 strategy: RetentionStrategy = RetentionStrategy.BALANCED,
                 config: Dict[str, Any] = None):
        self.strategy = strategy
        self.config = config or {}
        
        # 策略参数
        self.strategy_params = {
            RetentionStrategy.AGGRESSIVE: {
                "min_importance_threshold": 0.1,
                "max_age_days": 365,
                "retention_rate_target": 0.9
            },
            RetentionStrategy.BALANCED: {
                "min_importance_threshold": 0.3,
                "max_age_days": 180,
                "retention_rate_target": 0.7
            },
            RetentionStrategy.CONSERVATIVE: {
                "min_importance_threshold": 0.6,
                "max_age_days": 90,
                "retention_rate_target": 0.5
            },
            RetentionStrategy.ADAPTIVE: {
                "min_importance_threshold": 0.4,
                "max_age_days": 365,
                "retention_rate_target": 0.8
            }
        }
        
        # 预定义规则
        self.rules: List[RetentionRule] = self._initialize_rules()
        
        # 决策历史
        self.decision_history: List[RetentionDecision] = []
        
        # 自适应参数
        self.adaptive_params = self.strategy_params[RetentionStrategy.ADAPTIVE].copy()
    
    def _initialize_rules(self) -> List[RetentionRule]:
        """初始化保留规则"""
        rules = [
            RetentionRule(
                name="high_importance_retain",
                condition=lambda m: m.get("importance_score", 0) > 0.8,
                priority=1,
                action="retain"
            ),
            RetentionRule(
                name="recent_access_retain",
                condition=lambda m: m.get("last_accessed_days", 999) < 7,
                priority=2,
                action="retain"
            ),
            RetentionRule(
                name="low_importance_forget",
                condition=lambda m: m.get("importance_score", 0) < 0.2,
                priority=3,
                action="forget"
            ),
            RetentionRule(
                name="old_memory_review",
                condition=lambda m: m.get("age_days", 0) > 180,
                priority=4,
                action="review"
            ),
            RetentionRule(
                name="frequently_accessed_retain",
                condition=lambda m: m.get("access_count", 0) > 10,
                priority=1,
                action="retain"
            ),
            RetentionRule(
                name="system_critical_retain",
                condition=lambda m: m.get("is_critical", False),
                priority=0,  # 最高优先级
                action="retain"
            )
        ]
        
        return rules
    
    def evaluate_memory(self, 
                       memory_data: Dict[str, Any]) -> RetentionDecision:
        """
        评估单个记忆的保留决策
        
        Args:
            memory_data: 记忆数据
            
        Returns:
            保留决策
        """
        # 获取策略参数
        params = self._get_current_params()
        
        # 基础评估
        base_decision = self._base_evaluation(memory_data, params)
        
        # 应用规则
        rule_decisions = self._apply_rules(memory_data)
        
        # 合并决策
        final_decision = self._merge_decisions(base_decision, rule_decisions)
        
        # 记录决策
        self.decision_history.append(final_decision)
        
        return final_decision
    
    def _get_current_params(self) -> Dict[str, Any]:
        """获取当前策略参数"""
        if self.strategy == RetentionStrategy.ADAPTIVE:
            return self.adaptive_params
        else:
            return self.strategy_params.get(self.strategy, {})
    
    def _base_evaluation(self, 
                        memory_data: Dict[str, Any],
                        params: Dict[str, Any]) -> RetentionDecision:
        """基础评估"""
        memory_id = memory_data.get("id", "unknown")
        
        # 提取关键指标
        importance = memory_data.get("importance_score", 0.5)
        age_days = memory_data.get("age_days", 0)
        access_count = memory_data.get("access_count", 0)
        last_accessed_days = memory_data.get("last_accessed_days", 999)
        
        # 根据策略计算决策
        action = "review"
        confidence = 0.5
        reason = "base_evaluation"
        
        # 重要性阈值检查
        min_importance = params.get("min_importance_threshold", 0.3)
        if importance < min_importance:
            action = "forget"
            confidence = 0.7
            reason = f"importance_below_threshold ({importance:.2f} < {min_importance})"
        elif importance > min_importance + 0.3:
            action = "retain"
            confidence = 0.8
            reason = f"importance_above_threshold ({importance:.2f})"
        
        # 时间阈值检查
        max_age = params.get("max_age_days", 180)
        if age_days > max_age and action != "retain":
            action = "forget"
            confidence = max(confidence, 0.6)
            reason = f"memory_too_old ({age_days} days > {max_age})"
        
        # 访问频率检查
        if access_count > 5 and last_accessed_days < 30:
            if action == "forget":
                action = "review"
                confidence = 0.6
                reason = f"frequently_accessed_review ({access_count} accesses)"
            elif action == "review":
                action = "retain"
                confidence = 0.7
                reason = f"frequently_accessed_retain ({access_count} accesses)"
        
        # 创建决策
        decision = RetentionDecision(
            memory_id=memory_id,
            action=action,
            confidence=confidence,
            reason=reason,
            suggested_priority=self._calculate_priority(memory_data)
        )
        
        # 如果有过期时间，计算过期日期
        if action == "retain":
            expiration_days = self._calculate_expiration_days(memory_data, params)
            if expiration_days:
                decision.expiration_date = datetime.now() + timedelta(days=expiration_days)
        
        return decision
    
    def _apply_rules(self, memory_data: Dict[str, Any]) -> List[RetentionDecision]:
        """应用所有规则"""
        decisions = []
        
        for rule in self.rules:
            try:
                # 评估条件
                if callable(rule.condition):
                    condition_met = rule.condition(memory_data)
                else:
                    # 这里可以实现更复杂的条件解析
                    condition_met = False
                
                if condition_met:
                    decision = RetentionDecision(
                        memory_id=memory_data.get("id", "unknown"),
                        action=rule.action,
                        confidence=0.8,
                        reason=f"rule_triggered: {rule.name}",
                        suggested_priority=rule.priority
                    )
                    decisions.append(decision)
            except Exception as e:
                # 规则执行出错，跳过
                continue
        
        return decisions
    
    def _merge_decisions(self, 
                        base_decision: RetentionDecision,
                        rule_decisions: List[RetentionDecision]) -> RetentionDecision:
        """合并多个决策"""
        if not rule_decisions:
            return base_decision
        
        # 按优先级排序
        rule_decisions.sort(key=lambda d: d.suggested_priority)
        
        # 获取最高优先级的规则决策
        primary_rule_decision = rule_decisions[0]
        
        # 检查冲突
        if (primary_rule_decision.action != base_decision.action and 
            primary_rule_decision.suggested_priority < 2):  # 高优先级规则
            
            # 使用规则决策，但降低置信度
            final_decision = RetentionDecision(
                memory_id=primary_rule_decision.memory_id,
                action=primary_rule_decision.action,
                confidence=primary_rule_decision.confidence * 0.8,
                reason=f"{primary_rule_decision.reason} (overrides base: {base_decision.action})",
                suggested_priority=primary_rule_decision.suggested_priority
            )
        else:
            # 使用基础决策
            final_decision = base_decision
        
        return final_decision
    
    def _calculate_priority(self, memory_data: Dict[str, Any]) -> int:
        """计算保留优先级"""
        priority = 5  # 默认优先级
        
        importance = memory_data.get("importance_score", 0.5)
        access_count = memory_data.get("access_count", 0)
        is_critical = memory_data.get("is_critical", False)
        
        if is_critical:
            priority = 1
        elif importance > 0.8:
            priority = 2
        elif importance > 0.6:
            priority = 3
        elif access_count > 10:
            priority = 3
        elif importance < 0.3:
            priority = 7
        
        return priority
    
    def _calculate_expiration_days(self, 
                                  memory_data: Dict[str, Any],
                                  params: Dict[str, Any]) -> Optional[int]:
        """计算过期天数"""
        importance = memory_data.get("importance_score", 0.5)
        age_days = memory_data.get("age_days", 0)
        
        # 根据重要性计算过期时间
        if importance > 0.8:
            # 重要记忆：长期保留
            return 365
        elif importance > 0.6:
            # 中等重要性：中期保留
            return 180
        elif importance > 0.4:
            # 一般记忆：短期保留
            return 90
        else:
            # 低重要性：近期评估
            return 30
    
    def batch_evaluate(self, 
                      memories_data: List[Dict[str, Any]]) -> Dict[str, RetentionDecision]:
        """批量评估记忆保留"""
        decisions = {}
        
        for memory_data in memories_data:
            memory_id = memory_data.get("id")
            if memory_id:
                decision = self.evaluate_memory(memory_data)
                decisions[memory_id] = decision
        
        return decisions
    
    def adjust_strategy(self, 
                       system_stats: Dict[str, Any],
                       feedback: Dict[str, Any] = None):
        """调整保留策略"""
        if self.strategy != RetentionStrategy.ADAPTIVE:
            return
        
        # 获取当前状态
        memory_usage = system_stats.get("memory_usage_ratio", 0)
        retention_rate = system_stats.get("retention_rate", 0.7)
        avg_importance = system_stats.get("avg_importance", 0.5)
        
        # 根据状态调整参数
        target_params = self.strategy_params[RetentionStrategy.ADAPTIVE].copy()
        
        # 内存使用率过高，收紧策略
        if memory_usage > 0.8:
            target_params["min_importance_threshold"] = min(
                0.6, target_params["min_importance_threshold"] + 0.1
            )
            target_params["max_age_days"] = max(
                30, target_params["max_age_days"] * 0.8
            )
        
        # 内存使用率过低，放宽策略
        elif memory_usage < 0.3:
            target_params["min_importance_threshold"] = max(
                0.2, target_params["min_importance_threshold"] - 0.1
            )
            target_params["max_age_days"] = min(
                365, int(target_params["max_age_days"] * 1.2)
            )
        
        # 根据反馈调整
        if feedback:
            recall_success_rate = feedback.get("recall_success_rate", 0.8)
            
            if recall_success_rate < 0.6:
                # 回忆成功率低，放宽策略
                target_params["min_importance_threshold"] = max(
                    0.2, target_params["min_importance_threshold"] - 0.1
                )
            elif recall_success_rate > 0.9:
                # 回忆成功率高，收紧策略
                target_params["min_importance_threshold"] = min(
                    0.7, target_params["min_importance_threshold"] + 0.05
                )
        
        # 平滑更新
        for key in target_params:
            if key in self.adaptive_params:
                old_value = self.adaptive_params[key]
                new_value = target_params[key]
                
                # 线性插值
                self.adaptive_params[key] = old_value * 0.7 + new_value * 0.3
    
    def add_custom_rule(self, rule: RetentionRule):
        """添加自定义规则"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
    
    def remove_rule(self, rule_name: str):
        """移除规则"""
        self.rules = [r for r in self.rules if r.name != rule_name]
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """获取策略摘要"""
        params = self._get_current_params()
        
        return {
            "strategy": self.strategy.value,
            "parameters": params,
            "rule_count": len(self.rules),
            "decision_history_count": len(self.decision_history),
            "recent_decisions": self._get_recent_decisions_summary()
        }
    
    def _get_recent_decisions_summary(self) -> Dict[str, int]:
        """获取最近决策摘要"""
        if not self.decision_history:
            return {}
        
        recent = self.decision_history[-100:]  # 最近100个决策
        summary = {"retain": 0, "forget": 0, "review": 0}
        
        for decision in recent:
            summary[decision.action] += 1
        
        return summary