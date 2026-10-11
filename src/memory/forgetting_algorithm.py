"""
遗忘算法
根据保留策略执行记忆遗忘
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
import random
from dataclasses import dataclass
from enum import Enum

class ForgettingStrategy(Enum):
    """遗忘策略枚举"""
    GRADUAL = "gradual"          # 渐进式遗忘
    THRESHOLD = "threshold"      # 阈值式遗忘
    COMPETITIVE = "competitive"  # 竞争式遗忘
    INTERFERENCE = "interference"  # 干扰式遗忘

@dataclass
class ForgettingCandidate:
    """遗忘候选"""
    memory_id: str
    forget_score: float
    reasons: List[str]
    metadata: Dict[str, Any]
    
    def __lt__(self, other):
        # 用于排序：遗忘分数越高，优先级越高
        return self.forget_score > other.forget_score

class ForgettingAlgorithm:
    """遗忘算法"""
    
    def __init__(self, 
                 strategy: ForgettingStrategy = ForgettingStrategy.GRADUAL,
                 config: Dict[str, Any] = None):
        self.strategy = strategy
        self.config = config or {}
        
        # 策略特定参数
        self.strategy_params = {
            ForgettingStrategy.GRADUAL: {
                "decay_rate": 0.01,
                "retention_threshold": 0.1,
                "batch_size": 10
            },
            ForgettingStrategy.THRESHOLD: {
                "importance_threshold": 0.3,
                "age_threshold_days": 180,
                "retention_threshold": 0.2
            },
            ForgettingStrategy.COMPETITIVE: {
                "competition_factor": 0.5,
                "similarity_threshold": 0.7,
                "batch_size": 20
            },
            ForgettingStrategy.INTERFERENCE: {
                "interference_strength": 0.3,
                "similarity_threshold": 0.8,
                "batch_size": 15
            }
        }
        
        # 遗忘历史
        self.forgetting_history: List[Dict[str, Any]] = []
        
        # 学习到的参数
        self.learned_params = self.strategy_params[strategy].copy()
    
    def select_memories_to_forget(self,
                                 memories: List[Any],
                                 target_count: int = 10,
                                 context: Dict[str, Any] = None) -> List[Any]:
        """
        选择要遗忘的记忆
        
        Args:
            memories: 记忆对象列表
            target_count: 目标遗忘数量
            context: 上下文信息
            
        Returns:
            要遗忘的记忆列表
        """
        context = context or {}
        
        # 根据策略选择记忆
        if self.strategy == ForgettingStrategy.GRADUAL:
            candidates = self._gradual_forgetting(memories, target_count, context)
        elif self.strategy == ForgettingStrategy.THRESHOLD:
            candidates = self._threshold_forgetting(memories, target_count, context)
        elif self.strategy == ForgettingStrategy.COMPETITIVE:
            candidates = self._competitive_forgetting(memories, target_count, context)
        elif self.strategy == ForgettingStrategy.INTERFERENCE:
            candidates = self._interference_forgetting(memories, target_count, context)
        else:
            candidates = self._default_forgetting(memories, target_count, context)
        
        # 限制数量
        candidates = candidates[:target_count]
        
        # 记录遗忘决策
        self._record_forgetting_decision(candidates, context)
        
        return candidates
    
    def _gradual_forgetting(self,
                           memories: List[Any],
                           target_count: int,
                           context: Dict[str, Any]) -> List[Any]:
        """渐进式遗忘算法"""
        params = self.learned_params
        
        # 计算每个记忆的遗忘分数
        candidates = []
        
        for memory in memories:
            # 获取记忆属性
            memory_data = self._extract_memory_data(memory)
            
            # 计算遗忘分数
            forget_score = self._calculate_gradual_forget_score(memory_data, params)
            
            # 收集遗忘原因
            reasons = self._identify_forgetting_reasons(memory_data, params)
            
            if forget_score > 0:
                candidate = ForgettingCandidate(
                    memory_id=memory_data.get("id", str(id(memory))),
                    forget_score=forget_score,
                    reasons=reasons,
                    metadata=memory_data
                )
                candidates.append(candidate)
        
        # 按遗忘分数排序
        candidates.sort()
        
        return [self._get_memory_by_id(c.memory_id, memories) for c in candidates]
    
    def _threshold_forgetting(self,
                            memories: List[Any],
                            target_count: int,
                            context: Dict[str, Any]) -> List[Any]:
        """阈值式遗忘算法"""
        params = self.learned_params
        
        candidates = []
        
        for memory in memories:
            memory_data = self._extract_memory_data(memory)
            
            # 检查是否满足遗忘阈值条件
            should_forget, forget_score, reasons = self._check_threshold_conditions(
                memory_data, params
            )
            
            if should_forget:
                candidate = ForgettingCandidate(
                    memory_id=memory_data.get("id", str(id(memory))),
                    forget_score=forget_score,
                    reasons=reasons,
                    metadata=memory_data
                )
                candidates.append(candidate)
        
        # 按遗忘分数排序
        candidates.sort()
        
        return [self._get_memory_by_id(c.memory_id, memories) for c in candidates]
    
    def _competitive_forgetting(self,
                              memories: List[Any],
                              target_count: int,
                              context: Dict[str, Any]) -> List[Any]:
        """竞争式遗忘算法"""
        params = self.learned_params
        
        # 首先按重要性分组
        memories_by_importance = {}
        for memory in memories:
            memory_data = self._extract_memory_data(memory)
            importance = memory_data.get("importance_score", 0.5)
            
            # 离散化重要性
            importance_level = int(importance * 10)  # 0-10
            
            if importance_level not in memories_by_importance:
                memories_by_importance[importance_level] = []
            memories_by_importance[importance_level].append(memory)
        
        # 在每个重要性级别内进行竞争
        all_candidates = []
        
        for importance_level, level_memories in memories_by_importance.items():
            if len(level_memories) <= 1:
                continue
            
            # 计算相似度矩阵
            similarity_matrix = self._calculate_similarity_matrix(level_memories)
            
            # 应用竞争机制
            level_candidates = self._apply_competition(
                level_memories, similarity_matrix, params
            )
            
            all_candidates.extend(level_candidates)
        
        # 全局排序
        all_candidates.sort()
        
        return [self._get_memory_by_id(c.memory_id, memories) for c in all_candidates]
    
    def _interference_forgetting(self,
                               memories: List[Any],
                               target_count: int,
                               context: Dict[str, Any]) -> List[Any]:
        """干扰式遗忘算法"""
        params = self.learned_params
        
        # 识别相互干扰的记忆对
        interference_pairs = self._identify_interference_pairs(memories, params)
        
        # 为每对选择要遗忘的记忆
        candidates = []
        processed_memories = set()
        
        for memory1, memory2, interference_strength in interference_pairs:
            if (memory1 in processed_memories or 
                memory2 in processed_memories):
                continue
            
            # 选择较弱的记忆遗忘
            memory1_data = self._extract_memory_data(memory1)
            memory2_data = self._extract_memory_data(memory2)
            
            memory1_strength = self._calculate_memory_strength(memory1_data)
            memory2_strength = self._calculate_memory_strength(memory2_data)
            
            if memory1_strength < memory2_strength:
                forget_memory = memory1
                forget_data = memory1_data
                keep_memory = memory2
            else:
                forget_memory = memory2
                forget_data = memory2_data
                keep_memory = memory1
            
            forget_score = interference_strength * (1.0 - min(memory1_strength, memory2_strength))
            
            candidate = ForgettingCandidate(
                memory_id=forget_data.get("id", str(id(forget_memory))),
                forget_score=forget_score,
                reasons=[f"interference_with_{forget_data.get('id', 'other_memory')}"],
                metadata=forget_data
            )
            candidates.append(candidate)
            
            processed_memories.add(forget_memory)
            processed_memories.add(keep_memory)
        
        # 补充遗忘（如果需要更多）
        if len(candidates) < target_count:
            remaining_memories = [m for m in memories if m not in processed_memories]
            if remaining_memories:
                additional_candidates = self._gradual_forgetting(
                    remaining_memories,
                    target_count - len(candidates),
                    context
                )
                candidates.extend(additional_candidates)
        
        # 排序
        candidates.sort()
        
        return [self._get_memory_by_id(c.memory_id, memories) for c in candidates]
    
    def _default_forgetting(self,
                           memories: List[Any],
                           target_count: int,
                           context: Dict[str, Any]) -> List[Any]:
        """默认遗忘算法"""
        # 基于综合分数的简单遗忘
        candidates = []
        
        for memory in memories:
            memory_data = self._extract_memory_data(memory)
            
            # 计算综合遗忘分数
            forget_score = self._calculate_composite_forget_score(memory_data)
            
            if forget_score > 0:
                candidate = ForgettingCandidate(
                    memory_id=memory_data.get("id", str(id(memory))),
                    forget_score=forget_score,
                    reasons=["composite_score_based"],
                    metadata=memory_data
                )
                candidates.append(candidate)
        
        candidates.sort()
        
        return [self._get_memory_by_id(c.memory_id, memories) for c in candidates]
    
    def _extract_memory_data(self, memory) -> Dict[str, Any]:
        """从记忆对象中提取数据"""
        if hasattr(memory, 'to_dict'):
            return memory.to_dict()
        elif hasattr(memory, '__dict__'):
            return memory.__dict__
        elif isinstance(memory, dict):
            return memory
        else:
            return {"id": str(id(memory))}
    
    def _get_memory_by_id(self, memory_id: str, memories: List[Any]) -> Any:
        """根据ID获取记忆对象"""
        for memory in memories:
            memory_data = self._extract_memory_data(memory)
            if memory_data.get("id") == memory_id:
                return memory
        
        # 如果找不到，返回第一个记忆
        return memories[0] if memories else None
    
    def _calculate_gradual_forget_score(self,
                                       memory_data: Dict[str, Any],
                                       params: Dict[str, Any]) -> float:
        """计算渐进式遗忘分数"""
        # 基础遗忘分数
        forget_score = 0.0
        
        # 1. 基于保留分数
        retention_score = memory_data.get("retention_score", 1.0)
        retention_threshold = params.get("retention_threshold", 0.1)
        
        if retention_score < retention_threshold:
            forget_score += (1.0 - retention_score) * 0.4
        
        # 2. 基于时间衰减
        age_days = memory_data.get("age_days", 0)
        decay_rate = params.get("decay_rate", 0.01)
        
        age_factor = min(1.0, age_days * decay_rate)
        forget_score += age_factor * 0.3
        
        # 3. 基于重要性
        importance = memory_data.get("importance_score", 0.5)
        forget_score += (1.0 - importance) * 0.3
        
        # 归一化
        forget_score = min(1.0, forget_score)
        
        return forget_score
    
    def _check_threshold_conditions(self,
                                   memory_data: Dict[str, Any],
                                   params: Dict[str, Any]) -> Tuple[bool, float, List[str]]:
        """检查阈值条件"""
        reasons = []
        forget_score = 0.0
        
        # 重要性阈值
        importance_threshold = params.get("importance_threshold", 0.3)
        importance = memory_data.get("importance_score", 0.5)
        
        if importance < importance_threshold:
            reasons.append(f"importance_below_threshold ({importance:.2f} < {importance_threshold})")
            forget_score += 0.4
        
        # 年龄阈值
        age_threshold = params.get("age_threshold_days", 180)
        age_days = memory_data.get("age_days", 0)
        
        if age_days > age_threshold:
            reasons.append(f"age_exceeds_threshold ({age_days} > {age_threshold})")
            forget_score += 0.3
        
        # 保留分数阈值
        retention_threshold = params.get("retention_threshold", 0.2)
        retention_score = memory_data.get("retention_score", 1.0)
        
        if retention_score < retention_threshold:
            reasons.append(f"retention_below_threshold ({retention_score:.2f} < {retention_threshold})")
            forget_score += 0.3
        
        # 判断是否需要遗忘
        should_forget = len(reasons) > 0
        
        return should_forget, forget_score, reasons
    
    def _calculate_similarity_matrix(self, memories: List[Any]) -> np.ndarray:
        """计算相似度矩阵"""
        n = len(memories)
        similarity_matrix = np.eye(n)  # 对角线为1
        
        # 简单实现：随机相似度
        for i in range(n):
            for j in range(i+1, n):
                # 这里应该实现实际的内容相似度计算
                similarity = random.uniform(0.1, 0.9)
                similarity_matrix[i][j] = similarity
                similarity_matrix[j][i] = similarity
        
        return similarity_matrix
    
    def _apply_competition(self,
                          memories: List[Any],
                          similarity_matrix: np.ndarray,
                          params: Dict[str, Any]) -> List[ForgettingCandidate]:
        """应用竞争机制"""
        n = len(memories)
        competition_factor = params.get("competition_factor", 0.5)
        similarity_threshold = params.get("similarity_threshold", 0.7)
        
        # 计算每个记忆的竞争分数
        competition_scores = np.zeros(n)
        
        for i in range(n):
            memory_data = self._extract_memory_data(memories[i])
            base_strength = self._calculate_memory_strength(memory_data)
            
            # 与相似记忆竞争
            for j in range(n):
                if i != j and similarity_matrix[i][j] > similarity_threshold:
                    other_data = self._extract_memory_data(memories[j])
                    other_strength = self._calculate_memory_strength(other_data)
                    
                    # 竞争损失
                    competition_loss = competition_factor * (
                        other_strength - base_strength
                    ) * similarity_matrix[i][j]
                    
                    competition_scores[i] += max(0, competition_loss)
        
        # 创建遗忘候选
        candidates = []
        
        for i, score in enumerate(competition_scores):
            if score > 0:
                memory_data = self._extract_memory_data(memories[i])
                
                candidate = ForgettingCandidate(
                    memory_id=memory_data.get("id", str(i)),
                    forget_score=score,
                    reasons=[f"competition_loss_score_{score:.2f}"],
                    metadata=memory_data
                )
                candidates.append(candidate)
        
        candidates.sort()
        return candidates
    
    def _identify_interference_pairs(self,
                                    memories: List[Any],
                                    params: Dict[str, Any]) -> List[Tuple[Any, Any, float]]:
        """识别干扰记忆对"""
        interference_strength = params.get("interference_strength", 0.3)
        similarity_threshold = params.get("similarity_threshold", 0.8)
        
        pairs = []
        n = len(memories)
        
        # 简单实现：随机配对
        for i in range(min(n, 10)):  # 限制检查数量
            for j in range(i+1, min(n, 10)):
                # 这里应该实现实际的干扰检测
                similarity = random.uniform(0.5, 1.0)
                
                if similarity > similarity_threshold:
                    pairs.append((
                        memories[i],
                        memories[j],
                        interference_strength * similarity
                    ))
        
        return pairs
    
    def _calculate_memory_strength(self, memory_data: Dict[str, Any]) -> float:
        """计算记忆强度"""
        importance = memory_data.get("importance_score", 0.5)
        retention = memory_data.get("retention_score", 1.0)
        activation = memory_data.get("activation_level", 0.0)
        access_count = memory_data.get("access_count", 0)
        
        # 综合强度计算
        strength = (
            importance * 0.3 +
            retention * 0.3 +
            activation * 0.2 +
            min(1.0, access_count / 20) * 0.2
        )
        
        return strength
    
    def _calculate_composite_forget_score(self, memory_data: Dict[str, Any]) -> float:
        """计算综合遗忘分数"""
        # 多种因素加权
        factors = {
            "importance_inverse": 1.0 - memory_data.get("importance_score", 0.5),
            "retention_inverse": 1.0 - memory_data.get("retention_score", 1.0),
            "age_factor": min(1.0, memory_data.get("age_days", 0) / 365),
            "low_access": 1.0 - min(1.0, memory_data.get("access_count", 0) / 10)
        }
        
        weights = {
            "importance_inverse": 0.4,
            "retention_inverse": 0.3,
            "age_factor": 0.2,
            "low_access": 0.1
        }
        
        forget_score = 0.0
        for factor, value in factors.items():
            forget_score += value * weights.get(factor, 0)
        
        return min(1.0, forget_score)
    
    def _identify_forgetting_reasons(self,
                                    memory_data: Dict[str, Any],
                                    params: Dict[str, Any]) -> List[str]:
        """识别遗忘原因"""
        reasons = []
        
        # 检查各种条件
        importance = memory_data.get("importance_score", 0.5)
        if importance < 0.3:
            reasons.append(f"low_importance ({importance:.2f})")
        
        retention = memory_data.get("retention_score", 1.0)
        if retention < 0.3:
            reasons.append(f"low_retention ({retention:.2f})")
        
        age_days = memory_data.get("age_days", 0)
        if age_days > 180:
            reasons.append(f"old_memory ({age_days} days)")
        
        last_accessed_days = memory_data.get("last_accessed_days", 999)
        if last_accessed_days > 30:
            reasons.append(f"not_recently_accessed ({last_accessed_days} days)")
        
        if not reasons:
            reasons.append("no_specific_reason")
        
        return reasons
    
    def _record_forgetting_decision(self,
                                   candidates: List[ForgettingCandidate],
                                   context: Dict[str, Any]):
        """记录遗忘决策"""
        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "strategy": self.strategy.value,
            "candidate_count": len(candidates),
            "context": context,
            "candidates": [
                {
                    "memory_id": c.memory_id,
                    "forget_score": c.forget_score,
                    "reasons": c.reasons
                }
                for c in candidates[:10]  # 只记录前10个
            ]
        }
        
        self.forgetting_history.append(decision_record)
        
        # 限制历史记录长度
        if len(self.forgetting_history) > 100:
            self.forgetting_history = self.forgetting_history[-100:]
    
    def learn_from_feedback(self, feedback: Dict[str, Any]):
        """从反馈中学习"""
        if self.strategy != ForgettingStrategy.ADAPTIVE:
            return
        
        # 分析反馈数据
        recall_success_rate = feedback.get("recall_success_rate", 0.8)
        forgetting_regret_rate = feedback.get("forgetting_regret_rate", 0.1)
        
        # 调整参数
        if recall_success_rate < 0.6:
            # 回忆成功率低，说明遗忘过多，减少遗忘
            self.learned_params["retention_threshold"] = max(
                0.05, self.learned_params["retention_threshold"] * 0.9
            )
        elif recall_success_rate > 0.9:
            # 回忆成功率高，可以增加遗忘
            self.learned_params["retention_threshold"] = min(
                0.3, self.learned_params["retention_threshold"] * 1.1
            )
        
        if forgetting_regret_rate > 0.2:
            # 遗忘后悔率高，减少遗忘
            self.learned_params["importance_threshold"] = max(
                0.2, self.learned_params["importance_threshold"] * 0.9
            )
    
    def get_forgetting_statistics(self) -> Dict[str, Any]:
        """获取遗忘统计"""
        if not self.forgetting_history:
            return {}
        
        recent_decisions = self.forgetting_history[-50:]
        
        # 计算统计
        total_candidates = sum(d["candidate_count"] for d in recent_decisions)
        avg_candidates = total_candidates / len(recent_decisions) if recent_decisions else 0
        
        # 分析遗忘原因分布
        reason_distribution = {}
        for decision in recent_decisions:
            for candidate in decision["candidates"]:
                for reason in candidate["reasons"]:
                    reason_key = reason.split("(")[0].strip()
                    reason_distribution[reason_key] = reason_distribution.get(reason_key, 0) + 1
        
        return {
            "strategy": self.strategy.value,
            "total_decisions_recorded": len(self.forgetting_history),
            "recent_avg_candidates_per_decision": avg_candidates,
            "reason_distribution": reason_distribution,
            "learned_parameters": self.learned_params
        }
    
    def change_strategy(self, new_strategy: ForgettingStrategy):
        """改变遗忘策略"""
        self.strategy = new_strategy
        
        if new_strategy in self.strategy_params:
            self.learned_params = self.strategy_params[new_strategy].copy()
        else:
            self.learned_params = {}