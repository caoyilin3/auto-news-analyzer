# src/credibility/base_validator.py
"""
可信度验证器基类
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta


class BaseValidator(ABC):
    """可信度验证器基类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"validator.{name}")
        
        # 阈值配置
        self.min_threshold = config.get('min_threshold', 0.5)
        self.max_threshold = config.get('max_threshold', 0.9)
        
        # 统计信息
        self.stats = {
            'total_validated': 0,
            'passed': 0,
            'rejected': 0,
            'avg_confidence': 0.0,
            'start_time': datetime.now()
        }
        
        # 性能追踪
        self.performance_history = []
        
    @abstractmethod
    async def validate(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证单篇文章
        
        Args:
            article: 待验证的文章
            
        Returns:
            验证结果
        """
        pass
    
    async def validate_batch(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量验证文章
        
        Args:
            articles: 待验证的文章列表
            
        Returns:
            验证结果列表
        """
        self.logger.info(f"开始批量验证 {len(articles)} 篇文章")
        
        results = []
        
        for article in articles:
            try:
                result = await self.validate(article)
                results.append(result)
                
                # 更新统计
                self._update_stats(result)
                
            except Exception as e:
                self.logger.error(f"验证文章失败: {e}")
                # 返回失败结果
                results.append({
                    'passed': False,
                    'confidence': 0.0,
                    'reasons': [f'验证失败: {str(e)[:50]}'],
                    'error': str(e)
                })
        
        self.logger.info(f"批量验证完成，通过: {sum(1 for r in results if r.get('passed', False))}")
        
        return results
    
    def _update_stats(self, result: Dict[str, Any]):
        """更新统计信息"""
        self.stats['total_validated'] += 1
        
        if result.get('passed', False):
            self.stats['passed'] += 1
        else:
            self.stats['rejected'] += 1
        
        # 更新平均置信度（移动平均）
        confidence = result.get('confidence', 0.0)
        n = self.stats['total_validated']
        old_avg = self.stats['avg_confidence']
        self.stats['avg_confidence'] = old_avg * (n-1)/n + confidence/n
        
        # 记录性能历史
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'confidence': confidence,
            'passed': result.get('passed', False),
            'article_id': result.get('article_id', 'unknown')
        })
        
        # 保持历史记录大小
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
    
    def _check_freshness(self, article: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        检查文章新鲜度
        
        Returns:
            (是否通过, 分数, 原因)
        """
        try:
            published_at = article.get('published_at')
            if not published_at:
                return False, 0.0, "缺少发布时间"
            
            # 解析发布时间
            if isinstance(published_at, str):
                if 'T' in published_at:
                    publish_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                else:
                    publish_time = datetime.strptime(published_at, '%Y-%m-%d')
            else:
                publish_time = published_at
            
            # 计算天数差异
            days_old = (datetime.now() - publish_time).days
            
            # 根据配置的最大天数判断
            max_age = self.config.get('max_article_age_days', 30)
            
            if days_old > max_age:
                return False, 0.0, f"文章过时 ({days_old}天前)"
            
            # 计算新鲜度分数（指数衰减）
            freshness_score = max(0.0, 1.0 - (days_old / max_age))
            
            reason = f"新鲜度: {freshness_score:.2f} ({days_old}天前)"
            return True, freshness_score, reason
            
        except Exception as e:
            self.logger.warning(f"新鲜度检查失败: {e}")
            return False, 0.0, f"新鲜度检查失败: {str(e)[:50]}"
    
    def _check_source_reputation(self, source: str) -> Tuple[bool, float, str]:
        """
        检查来源信誉
        
        Returns:
            (是否通过, 分数, 原因)
        """
        # 预定义的信誉评分
        reputation_scores = {
            'techcrunch': 0.85,
            'arxiv': 0.95,
            'github': 0.75,
            'medium': 0.60,
            'mock': 0.50,
            'unknown': 0.30
        }
        
        # 查找最佳匹配
        best_score = 0.3  # 默认分数
        best_source = 'unknown'
        
        for known_source, score in reputation_scores.items():
            if known_source in source.lower():
                if score > best_score:
                    best_score = score
                    best_source = known_source
        
        if best_score >= self.min_threshold:
            return True, best_score, f"来源信誉: {best_source} ({best_score:.2f})"
        else:
            return False, best_score, f"来源信誉低: {best_source} ({best_score:.2f})"
    
    def _check_content_quality(self, article: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        检查内容质量
        
        Returns:
            (是否通过, 分数, 原因)
        """
        content = str(article.get('content', ''))
        title = str(article.get('title', ''))
        
        # 检查内容长度
        content_length = len(content)
        title_length = len(title)
        
        if content_length < 100:
            return False, 0.0, "内容过短"
        
        if title_length < 10:
            return False, 0.0, "标题过短"
        
        # 计算质量分数（基于长度和结构）
        length_score = min(1.0, content_length / 5000)
        
        # 检查段落结构（简单检查换行符数量）
        paragraphs = content.count('\n\n') + content.count('<p>')
        structure_score = min(1.0, paragraphs / 5)
        
        # 综合分数
        quality_score = (length_score * 0.6 + structure_score * 0.4)
        
        reason = f"内容质量: {quality_score:.2f} (长度:{content_length}, 段落:{paragraphs})"
        
        # 使用阈值判断
        min_quality = self.config.get('min_content_quality', 0.3)
        if quality_score >= min_quality:
            return True, quality_score, reason
        else:
            return False, quality_score, f"内容质量低: {quality_score:.2f}"
    
    def _check_author_authority(self, article: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        检查作者权威性
        
        Returns:
            (是否通过, 分数, 原因)
        """
        author = str(article.get('author', '')).strip()
        
        if not author or author.lower() in ['unknown', 'anonymous', '']:
            return False, 0.0, "作者未知"
        
        # 预定义的权威作者名单
        authoritative_authors = {
            'dr.', 'prof.', 'phd', 'university', 'research', 'lab',
            'mit', 'stanford', 'harvard', 'oxford', 'cambridge'
        }
        
        author_lower = author.lower()
        
        # 检查作者名称完整性
        name_parts = author_lower.split()
        if len(name_parts) >= 2:  # 至少有姓和名
            name_completeness = 0.7
        else:
            name_completeness = 0.3
        
        # 检查权威标识
        authority_indicators = 0
        for indicator in authoritative_authors:
            if indicator in author_lower:
                authority_indicators += 1
        
        authority_score = min(1.0, authority_indicators * 0.2 + name_completeness * 0.8)
        
        reason = f"作者权威: {authority_score:.2f} (作者: {author})"
        
        # 使用阈值判断
        min_authority = self.config.get('min_author_authority', 0.4)
        if authority_score >= min_authority:
            return True, authority_score, reason
        else:
            return False, authority_score, f"作者权威性低: {authority_score:.2f}"
    
    def _check_url_quality(self, url: str) -> Tuple[bool, float, str]:
        """
        检查URL质量
        
        Returns:
            (是否通过, 分数, 原因)
        """
        if not url or not isinstance(url, str):
            return False, 0.0, "URL无效"
        
        # 检查可疑路径
        suspicious_paths = ['/promo/', '/ad/', '/sponsored/', '/advertisement/']
        for path in suspicious_paths:
            if path in url.lower():
                return False, 0.0, f"URL包含推广路径: {path}"
        
        # 检查URL长度和结构
        if len(url) < 10:
            return False, 0.0, "URL过短"
        
        # 检查是否包含有效域名
        if '://' not in url:
            return False, 0.0, "URL缺少协议"
        
        # 简单的URL质量评分
        url_score = 0.7  # 基础分数
        
        # 如果是知名域名，提高分数
        trusted_domains = ['.edu', '.gov', '.org', 'arxiv.org', 'github.com']
        for domain in trusted_domains:
            if domain in url:
                url_score = min(1.0, url_score + 0.2)
                break
        
        return True, url_score, f"URL质量: {url_score:.2f}"
    
    def _calculate_confidence(self, check_results: List[Tuple[bool, float, str]]) -> Tuple[float, List[str]]:
        """
        计算综合置信度
        
        Args:
            check_results: 各检查项的结果列表
            
        Returns:
            (置信度分数, 原因列表)
        """
        if not check_results:
            return 0.0, ["无检查项"]
        
        # 分离通过和未通过的检查
        passed_results = [r for r in check_results if r[0]]
        failed_results = [r for r in check_results if not r[0]]
        
        # 计算平均分数（仅使用通过的检查）
        if passed_results:
            avg_score = sum(r[1] for r in passed_results) / len(passed_results)
            # 根据失败检查数量惩罚分数
            penalty = len(failed_results) * 0.15
            final_score = max(0.0, avg_score - penalty)
        else:
            final_score = 0.0
        
        # 收集原因
        reasons = []
        for passed, score, reason in check_results:
            status = "✓" if passed else "✗"
            reasons.append(f"{status} {reason}")
        
        return final_score, reasons
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = datetime.now() - self.stats['start_time']
        
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'pass_rate': (
                self.stats['passed'] / max(1, self.stats['total_validated']) * 100
            ),
            'reject_rate': (
                self.stats['rejected'] / max(1, self.stats['total_validated']) * 100
            ),
            'performance_history_size': len(self.performance_history),
            'config': {
                'min_threshold': self.min_threshold,
                'max_threshold': self.max_threshold,
                'name': self.name
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        if not self.performance_history:
            return {'status': 'no_data'}
        
        # 计算最近100次的统计
        recent_history = self.performance_history[-100:] if len(self.performance_history) > 100 else self.performance_history
        
        confidences = [h['confidence'] for h in recent_history]
        passed_count = sum(1 for h in recent_history if h['passed'])
        
        return {
            'recent_performance': {
                'samples': len(recent_history),
                'avg_confidence': sum(confidences) / len(confidences) if confidences else 0.0,
                'pass_rate': passed_count / len(recent_history) * 100 if recent_history else 0.0,
                'min_confidence': min(confidences) if confidences else 0.0,
                'max_confidence': max(confidences) if confidences else 0.0
            },
            'overall_performance': {
                'total_samples': len(self.performance_history),
                'avg_confidence': self.stats['avg_confidence'],
                'pass_rate': self.stats['passed'] / max(1, self.stats['total_validated']) * 100
            }
        }