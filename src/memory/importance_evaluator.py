"""
重要性评估器
评估记忆的重要性，用于决定保留优先级
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib

@dataclass
class ImportanceScore:
    """重要性评分"""
    overall: float = 0.5
    components: Dict[str, float] = None
    
    def __post_init__(self):
        if self.components is None:
            self.components = {}
    
    def add_component(self, name: str, score: float, weight: float = 1.0):
        """添加评分组件"""
        self.components[name] = score * weight
    
    def calculate_overall(self, weights: Dict[str, float] = None):
        """计算总体评分"""
        if not self.components:
            self.overall = 0.5
            return
        
        if weights is None:
            # 默认权重
            weights = {
                "relevance": 0.3,
                "novelty": 0.2,
                "utility": 0.25,
                "confidence": 0.15,
                "emotional_value": 0.1
            }
        
        weighted_sum = 0
        total_weight = 0
        
        for name, score in self.components.items():
            weight = weights.get(name, 1.0)
            weighted_sum += score * weight
            total_weight += weight
        
        self.overall = weighted_sum / total_weight if total_weight > 0 else 0.5


class ImportanceEvaluator:
    """重要性评估器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 预定义的评估规则
        self.rules = {
            "factual_consistency": self._evaluate_factual_consistency,
            "source_credibility": self._evaluate_source_credibility,
            "temporal_relevance": self._evaluate_temporal_relevance,
            "domain_specific": self._evaluate_domain_specific,
            "emotional_impact": self._evaluate_emotional_impact
        }
        
        # 领域特定权重
        self.domain_weights = {
            "finance": {"market_impact": 0.4, "regulatory": 0.3, "innovation": 0.3},
            "technology": {"innovation": 0.5, "adoption": 0.3, "security": 0.2},
            "politics": {"policy_impact": 0.4, "public_interest": 0.3, "geopolitical": 0.3},
            "health": {"public_health": 0.5, "innovation": 0.3, "regulatory": 0.2}
        }
    
    def evaluate(self, 
                 memory_content: Any,
                 metadata: Dict[str, Any],
                 context: Dict[str, Any] = None) -> ImportanceScore:
        """
        评估记忆的重要性
        
        Args:
            memory_content: 记忆内容
            metadata: 记忆元数据
            context: 评估上下文
            
        Returns:
            ImportanceScore对象
        """
        score = ImportanceScore()
        context = context or {}
        
        # 1. 相关性评估
        relevance_score = self._evaluate_relevance(memory_content, context)
        score.add_component("relevance", relevance_score, 0.3)
        
        # 2. 新颖性评估
        novelty_score = self._evaluate_novelty(memory_content, metadata)
        score.add_component("novelty", novelty_score, 0.2)
        
        # 3. 实用性评估
        utility_score = self._evaluate_utility(memory_content, metadata, context)
        score.add_component("utility", utility_score, 0.25)
        
        # 4. 置信度评估
        confidence_score = metadata.get("confidence", 0.5)
        score.add_component("confidence", confidence_score, 0.15)
        
        # 5. 情感价值评估
        emotional_score = self._evaluate_emotional_value(memory_content)
        score.add_component("emotional_value", emotional_score, 0.1)
        
        # 6. 应用预定义规则
        for rule_name, rule_func in self.rules.items():
            if rule_name in self.config.get("enabled_rules", self.rules.keys()):
                rule_score = rule_func(memory_content, metadata, context)
                score.add_component(rule_name, rule_score, 0.05)
        
        # 7. 领域特定评估
        domain = metadata.get("domain", "general")
        if domain in self.domain_weights:
            domain_score = self._evaluate_domain_specific(memory_content, metadata, domain)
            score.add_component(f"domain_{domain}", domain_score, 0.1)
        
        # 计算总体评分
        score.calculate_overall()
        
        return score
    
    def _evaluate_relevance(self, content: Any, context: Dict[str, Any]) -> float:
        """评估相关性"""
        # 简单实现：基于关键词匹配
        if isinstance(content, str):
            content_lower = content.lower()
            
            # 从上下文中获取相关主题
            topics = context.get("topics", [])
            current_focus = context.get("current_focus", "")
            
            relevance = 0.0
            
            # 检查是否包含当前焦点
            if current_focus and current_focus.lower() in content_lower:
                relevance += 0.4
            
            # 检查是否包含相关主题
            for topic in topics:
                if topic.lower() in content_lower:
                    relevance += 0.6 / len(topics) if topics else 0
            
            return min(1.0, relevance)
        
        return 0.5  # 默认值
    
    def _evaluate_novelty(self, content: Any, metadata: Dict[str, Any]) -> float:
        """评估新颖性"""
        # 基于时间的新颖性
        created_at = metadata.get("created_at")
        if isinstance(created_at, datetime):
            age_days = (datetime.now() - created_at).days
            
            # 指数衰减：越新得分越高
            novelty = np.exp(-age_days / 30)  # 30天半衰期
            return float(novelty)
        
        # 基于内容重复率的新颖性
        if isinstance(content, str):
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # 这里可以添加查重逻辑
            # 简单实现：假设内容唯一
            return 0.8
        
        return 0.5
    
    def _evaluate_utility(self, 
                         content: Any, 
                         metadata: Dict[str, Any],
                         context: Dict[str, Any]) -> float:
        """评估实用性"""
        utility = 0.5
        
        # 基于记忆类型
        memory_type = metadata.get("memory_type", "fact")
        type_utilities = {
            "skill": 0.9,
            "pattern": 0.8,
            "relationship": 0.7,
            "fact": 0.6,
            "event": 0.5
        }
        
        utility += type_utilities.get(memory_type, 0.5) * 0.3
        
        # 基于访问频率预测
        predicted_access = metadata.get("predicted_access_frequency", 0)
        if predicted_access > 0:
            utility += min(0.3, predicted_access * 0.1)
        
        # 基于实际效用记录
        past_utility = metadata.get("past_utility_score", 0)
        utility += past_utility * 0.2
        
        return min(1.0, utility)
    
    def _evaluate_emotional_value(self, content: Any) -> float:
        """评估情感价值"""
        # 简单实现：基于情感词检测
        if isinstance(content, str):
            content_lower = content.lower()
            
            # 积极情感词
            positive_words = {
                "success", "achievement", "breakthrough", "innovation",
                "progress", "improvement", "growth", "positive"
            }
            
            # 消极情感词
            negative_words = {
                "failure", "crisis", "problem", "issue", "challenge",
                "negative", "decline", "loss", "risk"
            }
            
            # 统计情感词
            positive_count = sum(1 for word in positive_words if word in content_lower)
            negative_count = sum(1 for word in negative_words if word in content_lower)
            
            # 计算情感强度
            if positive_count > 0 or negative_count > 0:
                emotional_intensity = (positive_count + negative_count) / 10  # 归一化
                emotional_intensity = min(1.0, emotional_intensity)
                
                # 积极情感得高分，消极情感得低分
                if positive_count > negative_count:
                    return 0.5 + emotional_intensity * 0.5
                else:
                    return 0.5 - emotional_intensity * 0.5
        
        return 0.5
    
    def _evaluate_factual_consistency(self, 
                                     content: Any, 
                                     metadata: Dict[str, Any],
                                     context: Dict[str, Any]) -> float:
        """评估事实一致性"""
        # 基于来源可信度
        source_credibility = metadata.get("source_credibility", 0.5)
        
        # 基于与其他记忆的一致性
        consistency_score = metadata.get("consistency_score", 0.5)
        
        # 综合评分
        return (source_credibility * 0.6 + consistency_score * 0.4)
    
    def _evaluate_source_credibility(self, 
                                    content: Any, 
                                    metadata: Dict[str, Any],
                                    context: Dict[str, Any]) -> float:
        """评估来源可信度"""
        source = metadata.get("source", "")
        
        # 可信来源列表（简化的实现）
        credible_sources = {
            "official_report": 0.9,
            "peer_reviewed": 0.9,
            "verified_expert": 0.8,
            "mainstream_media": 0.7,
            "social_media": 0.3,
            "anonymous": 0.2
        }
        
        # 查找匹配的源类型
        for source_type, credibility in credible_sources.items():
            if source_type in source.lower():
                return credibility
        
        return 0.5
    
    def _evaluate_temporal_relevance(self, 
                                    content: Any, 
                                    metadata: Dict[str, Any],
                                    context: Dict[str, Any]) -> float:
        """评估时间相关性"""
        # 检查是否有时间信息
        time_info = metadata.get("time_reference", {})
        
        if not time_info:
            return 0.5
        
        # 检查是否为当前事件
        is_current = time_info.get("is_current", False)
        if is_current:
            return 0.9
        
        # 检查时间范围
        time_range = time_info.get("time_range", {})
        if "start" in time_range and "end" in time_range:
            start_time = time_range["start"]
            end_time = time_range["end"]
            now = datetime.now()
            
            # 如果包含当前时间，相关性高
            if start_time <= now <= end_time:
                return 0.8
            
            # 如果即将发生，相关性中等
            if now < start_time and (start_time - now).days < 7:
                return 0.7
        
        return 0.5
    
    def _evaluate_domain_specific(self, 
                                 content: Any, 
                                 metadata: Dict[str, Any],
                                 domain: str) -> float:
        """评估领域特定重要性"""
        if domain not in self.domain_weights:
            return 0.5
        
        domain_score = 0.5
        
        # 领域特定关键词
        domain_keywords = {
            "finance": ["stock", "market", "investment", "revenue", "profit"],
            "technology": ["ai", "algorithm", "software", "hardware", "innovation"],
            "politics": ["policy", "government", "election", "law", "regulation"],
            "health": ["medical", "healthcare", "treatment", "vaccine", "research"]
        }
        
        # 统计关键词出现次数
        if isinstance(content, str):
            content_lower = content.lower()
            keywords = domain_keywords.get(domain, [])
            
            keyword_count = sum(1 for keyword in keywords if keyword in content_lower)
            
            # 归一化
            if keywords:
                domain_score += min(0.4, keyword_count / len(keywords))
        
        return min(1.0, domain_score)
    
    def _evaluate_emotional_impact(self, 
                                  content: Any, 
                                  metadata: Dict[str, Any],
                                  context: Dict[str, Any]) -> float:
        """评估情感影响"""
        # 检查是否有情感标签
        emotional_tags = metadata.get("emotional_tags", [])
        
        if not emotional_tags:
            return 0.5
        
        # 情感强度映射
        emotion_strength = {
            "high_impact": 0.9,
            "controversial": 0.8,
            "inspiring": 0.7,
            "sad": 0.6,
            "neutral": 0.5
        }
        
        # 计算平均情感强度
        total_strength = 0
        count = 0
        
        for tag in emotional_tags:
            for emotion, strength in emotion_strength.items():
                if emotion in tag.lower():
                    total_strength += strength
                    count += 1
        
        if count > 0:
            return total_strength / count
        
        return 0.5
    
    def batch_evaluate(self, 
                    memories_data: List[Dict[str, Any]],
                    context: Dict[str, Any] = None) -> List[ImportanceScore]:
        """批量评估重要性"""
        scores = []
        
        for memory_data in memories_data:
            content = memory_data.get("content", "")
            metadata = memory_data.get("metadata", {})
            
            score = self.evaluate(content, metadata, context)
            scores.append(score)
        
        return scores
    
    def update_weights(self, 
                    feedback_data: Dict[str, Any]):
        """根据反馈更新评估权重"""
        # 这里可以实现基于反馈的学习逻辑
        # 例如：如果某个记忆被频繁访问，提高相关特征的权重
        
        success_feedback = feedback_data.get("successful_recalls", 0)
        failure_feedback = feedback_data.get("failed_recalls", 0)
        
        # 简单调整：增加成功回忆的记忆类型的权重
        if success_feedback > failure_feedback:
            # 可以在这里实现更复杂的权重调整逻辑
            pass