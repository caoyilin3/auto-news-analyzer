# src/credibility/rule_based_validator.py
"""
规则基础验证器 - 使用预定义规则进行可信度评估
"""
import asyncio
import re
from datetime import datetime
from typing import Dict, Any, List
import logging

from .base_validator import BaseValidator


class RuleBasedValidator(BaseValidator):
    """规则基础验证器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("rule_based_validator", config)
        
        # 规则配置
        self.rules = config.get('rules', [])
        
        # 信誉数据库
        self.source_reputation_db = config.get('source_reputation_db', {})
        self.authority_authors = config.get('authority_authors', [])
        
        # 规则权重
        self.rule_weights = config.get('rule_weights', {
            'freshness': 0.25,
            'source': 0.30,
            'content': 0.25,
            'author': 0.15,
            'url': 0.05
        })
        
        # 预编译正则表达式
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式模式"""
        self.patterns = {
            'url_ad_pattern': re.compile(r'/(promo|ad|sponsored|advertisement)/', re.I),
            'authority_pattern': re.compile(r'(dr\.|prof\.|phd|university|research|lab)', re.I),
            'suspicious_words': re.compile(r'(click here|sign up|subscribe now|limited time)', re.I)
        }
    
    async def validate(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用规则验证文章
        
        Args:
            article: 待验证的文章
            
        Returns:
            验证结果
        """
        article_id = article.get('id', 'unknown')
        self.logger.debug(f"开始规则验证: {article_id}")
        
        try:
            # 执行所有规则检查
            rule_results = []
            
            # 规则1: 新鲜度检查
            freshness_result = self._apply_freshness_rule(article)
            rule_results.append(('freshness', *freshness_result))
            
            # 规则2: 来源检查
            source_result = self._apply_source_rule(article)
            rule_results.append(('source', *source_result))
            
            # 规则3: 内容检查
            content_result = self._apply_content_rule(article)
            rule_results.append(('content', *content_result))
            
            # 规则4: 作者检查
            author_result = self._apply_author_rule(article)
            rule_results.append(('author', *author_result))
            
            # 规则5: URL检查
            url_result = self._apply_url_rule(article)
            rule_results.append(('url', *url_result))
            
            # 计算加权分数
            confidence, reasons = self._calculate_rule_based_confidence(rule_results)
            
            # 判断是否通过
            passed = confidence >= self.min_threshold
            
            # 构建结果
            result = {
                'passed': passed,
                'confidence': confidence,
                'reasons': reasons,
                'article_id': article_id,
                'rule_results': {
                    rule: {'passed': passed, 'score': score, 'reason': reason}
                    for rule, passed, score, reason in rule_results
                },
                'validation_method': 'rule_based'
            }
            
            self.logger.debug(f"规则验证完成: {article_id}, 置信度: {confidence:.3f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"规则验证失败: {e}")
            return {
                'passed': False,
                'confidence': 0.0,
                'reasons': [f'规则验证错误: {str(e)[:50]}'],
                'error': str(e),
                'article_id': article_id
            }
    
    def _apply_freshness_rule(self, article: Dict[str, Any]) -> tuple:
        """应用新鲜度规则"""
        try:
            published_at = article.get('published_at')
            if not published_at:
                return False, 0.0, "缺少发布时间"
            
            # 解析时间
            if isinstance(published_at, str):
                if 'T' in published_at:
                    publish_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                else:
                    publish_time = datetime.strptime(published_at, '%Y-%m-%d')
            else:
                publish_time = published_at
            
            # 计算天数
            days_old = (datetime.now() - publish_time).days
            
            # 根据规则判断
            max_age_rules = {
                'news': 7,      # 新闻：7天
                'academic': 365,  # 学术：1年
                'general': 30    # 一般：30天
            }
            
            article_type = self._determine_article_type(article)
            max_age = max_age_rules.get(article_type, 30)
            
            if days_old > max_age:
                return False, 0.0, f"文章过时: {days_old}天前（类型: {article_type}）"
            
            # 计算分数
            freshness_score = max(0.0, 1.0 - (days_old / max_age))
            
            return True, freshness_score, f"新鲜度: {freshness_score:.2f} ({days_old}天前)"
            
        except Exception as e:
            return False, 0.0, f"新鲜度检查失败: {str(e)[:30]}"
    
    def _apply_source_rule(self, article: Dict[str, Any]) -> tuple:
        """应用来源规则"""
        source = article.get('source', 'unknown').lower()
        
        # 检查信誉数据库
        source_reputation = self.source_reputation_db.get(source, 0.5)
        
        # 应用规则
        if source_reputation >= 0.8:
            return True, source_reputation, f"高信誉来源: {source} ({source_reputation:.2f})"
        elif source_reputation >= 0.6:
            return True, source_reputation, f"中等信誉来源: {source} ({source_reputation:.2f})"
        elif source_reputation >= 0.4:
            return False, source_reputation, f"低信誉来源: {source} ({source_reputation:.2f})"
        else:
            return False, source_reputation, f"未知或不可信来源: {source}"
    
    def _apply_content_rule(self, article: Dict[str, Any]) -> tuple:
        """应用内容规则"""
        content = str(article.get('content', ''))
        title = str(article.get('title', ''))
        
        # 规则1: 内容长度
        content_length = len(content)
        title_length = len(title)
        
        if content_length < 200:
            return False, 0.0, f"内容过短: {content_length}字符"
        
        if title_length < 10:
            return False, 0.0, f"标题过短: {title_length}字符"
        
        # 规则2: 段落结构
        paragraphs = content.count('\n\n')
        if paragraphs < 2:
            return False, 0.0, f"段落不足: {paragraphs}段"
        
        # 规则3: 检查可疑词汇
        suspicious_count = len(self.patterns['suspicious_words'].findall(content))
        if suspicious_count > 3:
            return False, 0.0, f"包含过多可疑词汇: {suspicious_count}个"
        
        # 计算内容质量分数
        length_score = min(1.0, content_length / 3000)
        structure_score = min(1.0, paragraphs / 10)
        
        quality_score = (length_score * 0.6 + structure_score * 0.4)
        
        return True, quality_score, f"内容质量: {quality_score:.2f}"
    
    def _apply_author_rule(self, article: Dict[str, Any]) -> tuple:
        """应用作者规则"""
        author = str(article.get('author', '')).strip()
        
        if not author or author.lower() == 'unknown':
            return False, 0.0, "作者未知"
        
        # 规则1: 检查作者名称完整性
        name_parts = author.split()
        if len(name_parts) < 2:
            return False, 0.0, f"作者名称不完整: {author}"
        
        # 规则2: 检查权威标识
        authority_match = self.patterns['authority_pattern'].search(author)
        if authority_match:
            return True, 0.8, f"权威作者: {author}"
        
        # 规则3: 检查预定义权威作者列表
        author_lower = author.lower()
        for auth in self.authority_authors:
            if auth.lower() in author_lower:
                return True, 0.9, f"已知权威作者: {author}"
        
        # 规则4: 检查机构邮箱
        if '@' in author:
            domain = author.split('@')[-1]
            if any(edu in domain for edu in ['.edu', '.ac.', '.univ.']):
                return True, 0.7, f"机构作者: {author}"
        
        # 默认：中等可信度
        return True, 0.5, f"普通作者: {author}"
    
    def _apply_url_rule(self, article: Dict[str, Any]) -> tuple:
        """应用URL规则"""
        url = article.get('url', '')
        
        if not url:
            return False, 0.0, "缺少URL"
        
        # 规则1: 检查URL长度
        if len(url) < 10:
            return False, 0.0, f"URL过短: {len(url)}字符"
        
        # 规则2: 检查协议
        if not url.startswith(('http://', 'https://')):
            return False, 0.0, "URL缺少有效协议"
        
        # 规则3: 检查广告路径
        if self.patterns['url_ad_pattern'].search(url):
            return False, 0.0, "URL包含广告路径"
        
        # 规则4: 检查可信域名
        trusted_domains = ['.edu', '.gov', '.org', 'arxiv.org', 'github.com']
        for domain in trusted_domains:
            if domain in url:
                return True, 0.9, f"可信域名: {domain}"
        
        # 规则5: 检查顶级域名
        tlds = ['.com', '.net', '.io', '.ai']
        for tld in tlds:
            if url.endswith(tld) or f'.{tld}/' in url:
                return True, 0.7, f"商业域名: {tld}"
        
        # 默认分数
        return True, 0.5, "普通URL"
    
    def _determine_article_type(self, article: Dict[str, Any]) -> str:
        """确定文章类型"""
        source = article.get('source', '').lower()
        category = article.get('category', '').lower()
        content = article.get('content', '').lower()
        
        # 根据来源判断
        if 'arxiv' in source:
            return 'academic'
        elif 'news' in source or 'crunch' in source:
            return 'news'
        
        # 根据分类判断
        if any(word in category for word in ['paper', 'research', 'academic']):
            return 'academic'
        elif any(word in category for word in ['news', 'update', 'announcement']):
            return 'news'
        
        # 根据内容关键词判断
        academic_words = ['study', 'research', 'experiment', 'data', 'results', 'conclusion']
        news_words = ['today', 'yesterday', 'breaking', 'reports', 'announced']
        
        academic_count = sum(1 for word in academic_words if word in content)
        news_count = sum(1 for word in news_words if word in content)
        
        if academic_count > news_count:
            return 'academic'
        elif news_count > academic_count:
            return 'news'
        
        return 'general'
    
    def _calculate_rule_based_confidence(self, rule_results: List[tuple]) -> tuple:
        """计算基于规则的置信度"""
        if not rule_results:
            return 0.0, ["无规则检查结果"]
        
        total_weight = 0.0
        weighted_sum = 0.0
        reasons = []
        
        for rule_name, passed, score, reason in rule_results:
            weight = self.rule_weights.get(rule_name, 0.0)
            
            if passed:
                weighted_sum += score * weight
                total_weight += weight
                reasons.append(f"✓ {rule_name}: {score:.2f}")
            else:
                # 未通过的规则严重惩罚
                weighted_sum -= score * weight
                total_weight += weight
                reasons.append(f"✗ {rule_name}: {reason}")
        
        # 归一化
        if total_weight > 0:
            final_score = max(0.0, min(1.0, weighted_sum / total_weight))
        else:
            final_score = 0.0
        
        return final_score, reasons
    
    def add_rule(self, rule_name: str, rule_func: callable, weight: float = 0.0):
        """
        添加自定义规则
        
        Args:
            rule_name: 规则名称
            rule_func: 规则函数，返回 (passed, score, reason)
            weight: 规则权重
        """
        # 在实际实现中，需要将规则添加到规则列表中
        # 这里简化为更新规则权重
        if rule_name not in self.rule_weights:
            self.rule_weights[rule_name] = weight
            self.logger.info(f"添加新规则: {rule_name}, 权重: {weight}")
    
    def update_source_reputation(self, source: str, reputation: float):
        """
        更新来源信誉
        
        Args:
            source: 来源名称
            reputation: 信誉分数 (0-1)
        """
        self.source_reputation_db[source] = max(0.0, min(1.0, reputation))
        self.logger.info(f"更新来源信誉: {source} -> {reputation:.2f}")
    
    def get_rule_stats(self) -> Dict[str, Any]:
        """获取规则统计"""
        return {
            'total_rules': len(self.rule_weights),
            'rule_weights': self.rule_weights,
            'source_reputation_db_size': len(self.source_reputation_db),
            'authority_authors_count': len(self.authority_authors),
            'config': {
                'min_threshold': self.min_threshold,
                'max_threshold': self.max_threshold
            }
        }