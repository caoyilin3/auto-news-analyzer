# src/credibility/adaptive_validator.py
"""
自适应可信度验证器 - 根据历史表现动态调整验证策略
"""
import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import logging

from .base_validator import BaseValidator


class AdaptiveCredibilityValidator(BaseValidator):
    """自适应可信度验证器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("adaptive_validator", config)
        
        # 自适应参数
        self.learning_rate = config.get('learning_rate', 0.05)
        self.exploration_rate = config.get('exploration_rate', 0.1)
        
        # 维度权重（动态调整）
        self.dimension_weights = {
            'freshness': config.get('freshness_weight', 0.20),
            'source_reputation': config.get('source_weight', 0.35),
            'content_quality': config.get('content_weight', 0.20),
            'author_authority': config.get('author_weight', 0.15),
            'url_quality': config.get('url_weight', 0.10)
        }
        
        # 权重学习历史
        self.weight_history = {dim: [] for dim in self.dimension_weights}
        
        # 反馈追踪
        self.feedback_history = []
        
        # 自适应统计
        self.adaptive_stats = {
            'weight_updates': 0,
            'false_positives': 0,
            'false_negatives': 0,
            'true_positives': 0,
            'true_negatives': 0
        }
        
    async def validate(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证单篇文章（自适应版本）
        
        Args:
            article: 待验证的文章
            
        Returns:
            验证结果
        """
        article_id = article.get('id', 'unknown')
        self.logger.debug(f"开始验证文章: {article_id}")
        
        try:
            # 执行各项检查
            check_results = []
            
            # 1. 新鲜度检查
            freshness_result = self._check_freshness(article)
            check_results.append(('freshness', *freshness_result))
            
            # 2. 来源信誉检查
            source = article.get('source', 'unknown')
            source_result = self._check_source_reputation(source)
            check_results.append(('source_reputation', *source_result))
            
            # 3. 内容质量检查
            content_result = self._check_content_quality(article)
            check_results.append(('content_quality', *content_result))
            
            # 4. 作者权威性检查
            author_result = self._check_author_authority(article)
            check_results.append(('author_authority', *author_result))
            
            # 5. URL质量检查
            url = article.get('url', '')
            url_result = self._check_url_quality(url)
            check_results.append(('url_quality', *url_result))
            
            # 使用当前权重计算综合分数
            confidence, reasons = self._calculate_weighted_confidence(check_results)
            
            # 判断是否通过
            passed = confidence >= self.min_threshold
            
            # 构建结果
            result = {
                'passed': passed,
                'confidence': confidence,
                'reasons': reasons,
                'article_id': article_id,
                'dimension_scores': {
                    dim: score for dim, passed, score, reason in check_results
                },
                'weights_used': self.dimension_weights.copy(),
                'validation_method': 'adaptive'
            }
            
            # 记录本次验证的权重状态
            for dim in self.dimension_weights:
                self.weight_history[dim].append({
                    'timestamp': datetime.now().isoformat(),
                    'weight': self.dimension_weights[dim],
                    'article_id': article_id
                })
                
                # 保持历史记录大小
                if len(self.weight_history[dim]) > 1000:
                    self.weight_history[dim] = self.weight_history[dim][-1000:]
            
            self.logger.debug(f"文章 {article_id} 验证完成: {passed}, 置信度: {confidence:.3f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"验证文章 {article_id} 失败: {e}")
            return {
                'passed': False,
                'confidence': 0.0,
                'reasons': [f'验证过程错误: {str(e)[:50]}'],
                'error': str(e),
                'article_id': article_id
            }
    
    def _calculate_weighted_confidence(self, 
                                     check_results: List[Tuple[str, bool, float, str]]) -> Tuple[float, List[str]]:
        """
        计算加权置信度
        
        Args:
            check_results: 各维度的检查结果
            
        Returns:
            (置信度分数, 原因列表)
        """
        if not check_results:
            return 0.0, ["无检查项"]
        
        total_weight = 0.0
        weighted_sum = 0.0
        reasons = []
        
        for dimension, passed, score, reason in check_results:
            # 获取该维度的权重
            weight = self.dimension_weights.get(dimension, 0.0)
            
            if passed:
                # 通过检查的维度贡献正分
                weighted_sum += score * weight
                total_weight += weight
                reasons.append(f"✓ {dimension}: {score:.2f} (权重: {weight:.2f})")
            else:
                # 未通过检查的维度贡献负分
                weighted_sum -= score * weight * 0.5  # 惩罚系数
                total_weight += weight
                reasons.append(f"✗ {dimension}: {score:.2f} (权重: {weight:.2f})")
        
        # 归一化
        if total_weight > 0:
            final_score = max(0.0, min(1.0, weighted_sum / total_weight))
        else:
            final_score = 0.0
        
        return final_score, reasons
    
    def receive_feedback(self, article_id: str, actual_quality: float, 
                        predicted_confidence: float, dimension_scores: Dict[str, float]):
        """
        接收反馈以改进自适应策略
        
        Args:
            article_id: 文章ID
            actual_quality: 实际质量分数 (0-1)
            predicted_confidence: 预测的置信度分数
            dimension_scores: 各维度的实际分数
        """
        # 计算预测误差
        prediction_error = actual_quality - predicted_confidence
        
        # 记录反馈
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'article_id': article_id,
            'actual_quality': actual_quality,
            'predicted_confidence': predicted_confidence,
            'prediction_error': prediction_error,
            'dimension_scores': dimension_scores,
            'weights_before': self.dimension_weights.copy()
        }
        
        self.feedback_history.append(feedback_entry)
        
        # 保持反馈历史大小
        if len(self.feedback_history) > 1000:
            self.feedback_history = self.feedback_history[-1000:]
        
        # 更新统计
        if prediction_error > 0.2:
            self.adaptive_stats['false_negatives'] += 1  # 低估了质量
        elif prediction_error < -0.2:
            self.adaptive_stats['false_positives'] += 1  # 高估了质量
        elif actual_quality >= 0.7:
            self.adaptive_stats['true_positives'] += 1
        else:
            self.adaptive_stats['true_negatives'] += 1
        
        # 调整权重（如果误差显著）
        if abs(prediction_error) > 0.1:
            self._adjust_weights(prediction_error, dimension_scores)
    
    def _adjust_weights(self, prediction_error: float, dimension_scores: Dict[str, float]):
        """
        根据预测误差调整权重
        
        Args:
            prediction_error: 预测误差（实际 - 预测）
            dimension_scores: 各维度的实际分数
        """
        # 确定需要调整的维度
        adjustments = {}
        
        for dimension, score in dimension_scores.items():
            if dimension in self.dimension_weights:
                # 计算该维度的贡献误差
                weight = self.dimension_weights[dimension]
                dimension_contribution = weight * score
                
                # 如果预测误差为正（低估了质量），增加高分数维度的权重
                if prediction_error > 0:
                    if score > 0.7:  # 高分数维度
                        adjustment = self.learning_rate * prediction_error * (score - 0.5)
                        adjustments[dimension] = adjustment
                # 如果预测误差为负（高估了质量），减少低分数维度的权重
                else:
                    if score < 0.3:  # 低分数维度
                        adjustment = self.learning_rate * prediction_error * (0.5 - score)
                        adjustments[dimension] = adjustment
        
        # 应用调整，确保权重总和为1
        if adjustments:
            # 计算总调整量
            total_adjustment = sum(adjustments.values())
            
            # 应用调整
            for dimension, adjustment in adjustments.items():
                new_weight = max(0.05, min(0.5, 
                    self.dimension_weights[dimension] + adjustment))
                self.dimension_weights[dimension] = new_weight
            
            # 重新归一化
            self._normalize_weights()
            
            self.adaptive_stats['weight_updates'] += 1
            
            self.logger.info(f"权重已调整: {adjustments}")
    
    def _normalize_weights(self):
        """归一化权重，确保总和为1"""
        total = sum(self.dimension_weights.values())
        if total > 0:
            for dimension in self.dimension_weights:
                self.dimension_weights[dimension] /= total
    
    async def explore_new_strategy(self):
        """
        探索新策略（随机调整权重）
        
        用于避免陷入局部最优解
        """
        if np.random.random() < self.exploration_rate:
            # 随机选择一个维度调整
            dimensions = list(self.dimension_weights.keys())
            dim_to_adjust = np.random.choice(dimensions)
            
            # 随机调整量
            adjustment = (np.random.random() - 0.5) * 0.1
            
            old_weight = self.dimension_weights[dim_to_adjust]
            new_weight = max(0.05, min(0.5, old_weight + adjustment))
            self.dimension_weights[dim_to_adjust] = new_weight
            
            # 重新归一化
            self._normalize_weights()
            
            self.logger.info(f"探索性调整: {dim_to_adjust} {old_weight:.3f} -> {new_weight:.3f}")
            
            return True
        
        return False
    
    def get_adaptive_stats(self) -> Dict[str, Any]:
        """获取自适应统计"""
        # 计算准确率
        total_predictions = (
            self.adaptive_stats['true_positives'] +
            self.adaptive_stats['true_negatives'] +
            self.adaptive_stats['false_positives'] +
            self.adaptive_stats['false_negatives']
        )
        
        if total_predictions > 0:
            accuracy = (
                (self.adaptive_stats['true_positives'] + self.adaptive_stats['true_negatives']) /
                total_predictions * 100
            )
        else:
            accuracy = 0.0
        
        # 获取最近的权重趋势
        recent_trends = {}
        for dimension, history in self.weight_history.items():
            if len(history) >= 10:
                recent_weights = [h['weight'] for h in history[-10:]]
                recent_trends[dimension] = {
                    'current': recent_weights[-1],
                    'trend': 'stable',
                    'change_pct': 0.0
                }
                
                if len(recent_weights) >= 2:
                    change = recent_weights[-1] - recent_weights[0]
                    change_pct = change / recent_weights[0] * 100 if recent_weights[0] > 0 else 0.0
                    recent_trends[dimension]['change_pct'] = change_pct
                    
                    if change_pct > 5:
                        recent_trends[dimension]['trend'] = 'increasing'
                    elif change_pct < -5:
                        recent_trends[dimension]['trend'] = 'decreasing'
        
        return {
            **self.adaptive_stats,
            'accuracy_percentage': accuracy,
            'current_weights': self.dimension_weights,
            'weight_trends': recent_trends,
            'feedback_history_size': len(self.feedback_history),
            'learning_rate': self.learning_rate,
            'exploration_rate': self.exploration_rate,
            'performance_metrics': {
                'precision': (
                    self.adaptive_stats['true_positives'] / 
                    max(1, self.adaptive_stats['true_positives'] + self.adaptive_stats['false_positives']) * 100
                ),
                'recall': (
                    self.adaptive_stats['true_positives'] / 
                    max(1, self.adaptive_stats['true_positives'] + self.adaptive_stats['false_negatives']) * 100
                ),
                'f1_score': 0.0  # 待计算
            }
        }
    
    async def reset_weights(self):
        """重置权重到初始配置"""
        config = self.config
        
        self.dimension_weights = {
            'freshness': config.get('freshness_weight', 0.20),
            'source_reputation': config.get('source_weight', 0.35),
            'content_quality': config.get('content_weight', 0.20),
            'author_authority': config.get('author_weight', 0.15),
            'url_quality': config.get('url_weight', 0.10)
        }
        
        # 清空历史
        self.weight_history = {dim: [] for dim in self.dimension_weights}
        
        self.logger.info("权重已重置为初始配置")