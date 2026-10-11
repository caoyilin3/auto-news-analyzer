# src/data_acquisition/adaptive_crawler.py
"""
自适应爬虫 - 能够根据反馈调整抓取策略
"""
import asyncio
import random
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from .base_crawler import BaseCrawler


class AdaptiveCrawler(BaseCrawler):
    """自适应爬虫"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("adaptive_crawler", config)
        
        # 自适应参数
        self.learning_rate = config.get('learning_rate', 0.1)
        self.exploration_rate = config.get('exploration_rate', 0.2)
        
        # 来源权重（根据历史表现动态调整）
        self.source_weights = {}
        
        # 自适应统计
        self.adaptive_stats = {
            'weight_updates': 0,
            'strategy_changes': 0,
            'exploration_count': 0,
            'exploitation_count': 0
        }
        
    async def fetch(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取数据（自适应版本）
        
        Args:
            limit: 最大获取数量
            
        Returns:
            数据列表
        """
        self.logger.info(f"开始自适应数据获取，目标数量: {limit}")
        
        # 获取数据源配置
        sources = self.config.get('sources', [])
        use_mock_data = self.config.get('use_mock_data', False)
        
        if use_mock_data:
            self.logger.info("使用模拟数据模式")
            return self._generate_mock_data(limit)
        
        # 选择数据源（根据权重）
        selected_sources = self._select_sources(sources, limit)
        
        all_articles = []
        
        for source in selected_sources:
            try:
                self.logger.debug(f"从 {source} 获取数据")
                
                # 根据源类型选择抓取策略
                articles = await self._fetch_from_source(source)
                
                if articles:
                    all_articles.extend(articles)
                    
                    # 记录源表现
                    self._update_source_performance(source, articles)
                    
                    self.logger.debug(f"从 {source} 获取了 {len(articles)} 篇文章")
                    
                    # 如果达到限制，提前返回
                    if len(all_articles) >= limit:
                        all_articles = all_articles[:limit]
                        break
                        
            except Exception as e:
                self.logger.error(f"从 {source} 获取数据失败: {e}")
                # 降低该源的权重
                self._adjust_source_weight(source, success=False)
        
        # 更新统计
        self.stats['total_articles'] += len(all_articles)
        
        self.logger.info(f"自适应数据获取完成，共获取 {len(all_articles)} 篇文章")
        
        return all_articles
    
    def _select_sources(self, sources: List[str], limit: int) -> List[str]:
        """
        选择数据源（基于UCB算法）
        
        Args:
            sources: 可用数据源列表
            limit: 需要的数据量
            
        Returns:
            选择的数据源列表
        """
        if len(sources) == 1:
            return sources
        
        # 初始化权重（如果尚未初始化）
        for source in sources:
            if source not in self.source_weights:
                self.source_weights[source] = {
                    'weight': 1.0,
                    'success_count': 0,
                    'total_count': 0,
                    'last_used': None,
                    'quality_score': 0.0
                }
        
        selected_sources = []
        
        # 计算每个数据源的需求量（基于历史表现）
        source_demands = self._calculate_source_demands(sources, limit)
        
        for source, demand in source_demands.items():
            if demand > 0:
                selected_sources.extend([source] * demand)
        
        # 打乱顺序以避免模式化
        random.shuffle(selected_sources)
        
        return selected_sources
    
    def _calculate_source_demands(self, sources: List[str], limit: int) -> Dict[str, int]:
        """计算每个数据源的需求量"""
        demands = {}
        
        # 计算总权重
        total_weight = sum(self.source_weights[source]['weight'] for source in sources)
        
        if total_weight == 0:
            # 平均分配
            base_demand = limit // len(sources)
            for source in sources:
                demands[source] = base_demand
            return demands
        
        # 根据权重分配需求
        remaining = limit
        
        for source in sources:
            weight = self.source_weights[source]['weight']
            demand = int(limit * weight / total_weight)
            demands[source] = demand
            remaining -= demand
        
        # 分配剩余数量给权重最高的源
        if remaining > 0:
            best_source = max(sources, key=lambda s: self.source_weights[s]['weight'])
            demands[best_source] = demands.get(best_source, 0) + remaining
        
        return demands
    
    async def _fetch_from_source(self, source: str) -> List[Dict[str, Any]]:
        """从特定源获取数据"""
        source_type = self._identify_source_type(source)
        
        try:
            if source_type == 'techcrunch':
                return await self._fetch_techcrunch(source)
            elif source_type == 'arxiv':
                return await self._fetch_arxiv(source)
            elif source_type == 'generic':
                return await self._fetch_generic_website(source)
            else:
                self.logger.warning(f"未知源类型: {source_type}")
                return []
                
        except Exception as e:
            self.logger.error(f"从源 {source} 获取数据失败: {e}")
            return []
    
    def _identify_source_type(self, source: str) -> str:
        """识别源类型"""
        source_lower = source.lower()
        
        if 'techcrunch' in source_lower:
            return 'techcrunch'
        elif 'arxiv' in source_lower:
            return 'arxiv'
        elif 'github' in source_lower:
            return 'github'
        elif 'medium' in source_lower:
            return 'medium'
        else:
            return 'generic'
    
    async def _fetch_techcrunch(self, source: str) -> List[Dict[str, Any]]:
        """获取TechCrunch数据"""
        # 简化的TechCrunch抓取
        url = "https://techcrunch.com/wp-json/wp/v2/posts"
        params = {
            'per_page': 10,
            '_embed': 'true'
        }
        
        try:
            response = await self._fetch_url(url, params=params)
            if response:
                import json
                data = json.loads(response)
                return self._parse_techcrunch_data(data)
        except Exception as e:
            self.logger.error(f"TechCrunch API调用失败: {e}")
        
        # 降级到模拟数据
        return self._generate_mock_techcrunch_data()
    
    async def _fetch_arxiv(self, source: str) -> List[Dict[str, Any]]:
        """获取ArXiv数据"""
        url = "http://export.arxiv.org/api/query"
        params = {
            'search_query': 'cat:cs.AI OR cat:cs.LG OR cat:cs.CL',
            'start': 0,
            'max_results': 10,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        try:
            response = await self._fetch_url(url, params=params)
            if response:
                return self._parse_arxiv_data(response)
        except Exception as e:
            self.logger.error(f"ArXiv API调用失败: {e}")
        
        # 降级到模拟数据
        return self._generate_mock_arxiv_data()
    
    async def _fetch_generic_website(self, source: str) -> List[Dict[str, Any]]:
        """获取通用网站数据"""
        try:
            response = await self._fetch_url(source)
            if response:
                # 生产环境应使用BeautifulSoup等库进行HTML解析
                metadata = self._extract_metadata(response, source)
                
                article = {
                    'title': metadata.get('title', f'Article from {source}'),
                    'content': response[:5000],
                    'url': source,
                    'source': 'generic_website',
                    'published_at': datetime.now().isoformat(),
                    'author': 'Unknown',
                    'category': 'Technology'
                }
                
                return [article]
        except Exception as e:
            self.logger.error(f"通用网站抓取失败: {e}")
        
        return []
    
    def _parse_techcrunch_data(self, data: List[Dict]) -> List[Dict[str, Any]]:
        """解析TechCrunch数据"""
        articles = []
        
        for item in data[:5]:
            try:
                article = {
                    'id': f"techcrunch_{item.get('id', 'unknown')}",
                    'title': item.get('title', {}).get('rendered', 'No Title'),
                    'content': item.get('content', {}).get('rendered', ''),
                    'url': item.get('link', ''),
                    'source': 'techcrunch',
                    'published_at': item.get('date', datetime.now().isoformat()),
                    'author': self._extract_author(item),
                    'category': self._extract_categories(item)
                }
                articles.append(article)
            except Exception as e:
                self.logger.error(f"解析TechCrunch文章失败: {e}")
        
        return articles
    
    def _parse_arxiv_data(self, xml_data: str) -> List[Dict[str, Any]]:
        """解析ArXiv XML数据"""
        articles = []
        
        try:
            import re
            
            # 提取entry部分
            entries = re.findall(r'<entry>(.*?)</entry>', xml_data, re.DOTALL)
            
            for entry in entries[:5]:
                try:
                    # 提取标题
                    title_match = re.search(r'<title>(.*?)</title>', entry)
                    title = title_match.group(1) if title_match else 'No Title'
                    
                    # 提取摘要
                    summary_match = re.search(r'<summary>(.*?)</summary>', entry)
                    summary = summary_match.group(1) if summary_match else ''
                    
                    article = {
                        'id': f"arxiv_{len(articles)+1}",
                        'title': title,
                        'content': summary,
                        'url': f"https://arxiv.org/abs/mock-{len(articles)+1}",
                        'source': 'arxiv',
                        'published_at': datetime.now().isoformat(),
                        'author': 'Unknown Researcher',
                        'category': 'Academic Paper'
                    }
                    articles.append(article)
                    
                except Exception as e:
                    self.logger.error(f"解析ArXiv条目失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"解析ArXiv XML失败: {e}")
        
        return articles
    
    def _extract_author(self, item: Dict) -> str:
        """提取作者信息"""
        try:
            if '_embedded' in item and 'author' in item['_embedded']:
                authors = item['_embedded']['author']
                if authors and len(authors) > 0:
                    return authors[0].get('name', 'Unknown')
        except:
            pass
        return 'Unknown'
    
    def _extract_categories(self, item: Dict) -> str:
        """提取分类信息"""
        try:
            if 'categories' in item:
                for cat in item['categories']:
                    if isinstance(cat, dict) and 'name' in cat:
                        return cat['name']
                    elif isinstance(cat, str):
                        return cat
        except:
            pass
        return 'Technology'
    
    def _update_source_performance(self, source: str, articles: List[Dict[str, Any]]):
        """更新源表现"""
        if source not in self.source_weights:
            self.source_weights[source] = {
                'weight': 1.0,
                'success_count': 0,
                'total_count': 0,
                'last_used': datetime.now(),
                'quality_score': 0.0
            }
        
        stats = self.source_weights[source]
        
        # 更新统计
        stats['success_count'] += 1
        stats['total_count'] += 1
        stats['last_used'] = datetime.now()
        
        # 计算质量分数
        total_length = sum(len(str(article.get('content', ''))) for article in articles)
        avg_length = total_length / max(1, len(articles))
        
        quality = 0.5 + min(0.5, avg_length / 10000)
        
        # 更新权重
        old_weight = stats['weight']
        old_quality = stats.get('quality_score', 0.5)
        
        new_quality = old_quality * 0.9 + quality * 0.1
        stats['quality_score'] = new_quality
        
        weight_change = self.learning_rate * (new_quality - 0.7)
        new_weight = max(0.1, min(2.0, old_weight + weight_change))
        stats['weight'] = new_weight
        
        self.adaptive_stats['weight_updates'] += 1
        
        self.logger.debug(f"源 {source} 权重更新: {old_weight:.3f} -> {new_weight:.3f}")
    
    def _adjust_source_weight(self, source: str, success: bool):
        """调整源权重"""
        if source not in self.source_weights:
            self.source_weights[source] = {
                'weight': 1.0,
                'success_count': 0,
                'total_count': 0,
                'last_used': None,
                'quality_score': 0.5
            }
        
        stats = self.source_weights[source]
        stats['total_count'] += 1
        
        if success:
            stats['success_count'] += 1
            stats['weight'] = min(2.0, stats['weight'] * 1.05)
        else:
            stats['weight'] = max(0.1, stats['weight'] * 0.9)
        
        self.adaptive_stats['weight_updates'] += 1
    
    def _generate_mock_data(self, limit: int) -> List[Dict[str, Any]]:
        """生成模拟数据"""
        self.logger.info(f"生成 {limit} 条模拟数据")
        
        mock_articles = []
        categories = ['AI', 'Quantum Computing', 'Blockchain', 'Cybersecurity', 'Biotech']
        
        for i in range(min(limit, self.config.get('mock_data_count', 5))):
            category = categories[i % len(categories)]
            
            article = {
                'id': f"mock_{datetime.now().strftime('%Y%m%d')}_{i:03d}",
                'title': f"Mock Article {i+1} about {category}",
                'content': f"This is a mock article about {category}. "
                          f"In recent developments, researchers have made significant "
                          f"breakthroughs in {category.lower()} technology.",
                'url': f"https://example.com/mock-article-{i+1}",
                'source': 'mock',
                'published_at': datetime.now().isoformat(),
                'author': f"Researcher {chr(65 + i)}",
                'category': category,
                'is_mock': True
            }
            
            mock_articles.append(article)
        
        return mock_articles
    
    def _generate_mock_techcrunch_data(self) -> List[Dict[str, Any]]:
        """生成模拟TechCrunch数据"""
        articles = []
        
        tech_topics = [
            ('AI Startup Raises $50M', 'AI', 'Sarah Johnson'),
            ('Quantum Computing Breakthrough', 'Quantum', 'Michael Chen'),
            ('Cybersecurity Trends 2024', 'Security', 'Alex Rodriguez'),
        ]
        
        for i, (title, category, author) in enumerate(tech_topics):
            article = {
                'id': f"techcrunch_mock_{i+1}",
                'title': title,
                'content': f"{title}. TechCrunch exclusive report on {category}.",
                'url': f"https://techcrunch.com/mock-article-{i+1}",
                'source': 'techcrunch_mock',
                'published_at': datetime.now().isoformat(),
                'author': author,
                'category': category,
                'is_mock': True
            }
            articles.append(article)
        
        return articles
    
    def _generate_mock_arxiv_data(self) -> List[Dict[str, Any]]:
        """生成模拟ArXiv数据"""
        articles = []
        
        paper_topics = [
            ('Attention Mechanisms in Transformers', 'cs.CL', 'Dr. Zhang et al.'),
            ('Federated Learning Optimization', 'cs.LG', 'Prof. Smith et al.'),
            ('Quantum Neural Networks', 'quant-ph', 'Dr. Gupta et al.'),
        ]
        
        for i, (title, category, author) in enumerate(paper_topics):
            article = {
                'id': f"arxiv_mock_{i+1}",
                'title': title,
                'content': f"Abstract: This paper presents novel findings in {category}.",
                'url': f"https://arxiv.org/abs/mock-{i+1}",
                'source': 'arxiv_mock',
                'published_at': datetime.now().isoformat(),
                'author': author,
                'category': 'Academic Paper',
                'is_mock': True
            }
            articles.append(article)
        
        return articles
    
    def get_adaptive_stats(self) -> Dict[str, Any]:
        """获取自适应统计"""
        source_stats = {}
        for source, stats in self.source_weights.items():
            source_stats[source] = {
                'weight': stats['weight'],
                'success_rate': stats['success_count'] / max(1, stats['total_count']) * 100,
                'quality_score': stats.get('quality_score', 0.0),
                'last_used': stats.get('last_used', None)
            }
        
        return {
            **self.adaptive_stats,
            'source_weights': source_stats,
            'total_sources': len(self.source_weights),
            'exploration_rate': self.exploration_rate,
            'learning_rate': self.learning_rate
        }
    
    def receive_feedback(self, source: str, quality_score: float, 
                        relevance_score: float):
        """
        接收反馈以改进自适应策略
        """
        if source not in self.source_weights:
            return
        
        stats = self.source_weights[source]
        
        # 计算综合分数
        combined_score = (quality_score * 0.6 + relevance_score * 0.4)
        
        # 更新质量分数
        old_quality = stats.get('quality_score', 0.5)
        new_quality = old_quality * 0.8 + combined_score * 0.2
        stats['quality_score'] = new_quality
        
        # 基于反馈调整权重
        weight_adjustment = self.learning_rate * (combined_score - 0.7)
        new_weight = max(0.1, min(2.0, stats['weight'] + weight_adjustment))
        
        self.logger.info(
            f"源 {source} 接收反馈: 质量={quality_score:.2f}, "
            f"权重 {stats['weight']:.3f} -> {new_weight:.3f}"
        )
        
        stats['weight'] = new_weight
        self.adaptive_stats['weight_updates'] += 1
    
    async def reset_weights(self):
        """重置所有源权重"""
        for source in self.source_weights:
            self.source_weights[source]['weight'] = 1.0
            self.source_weights[source]['quality_score'] = 0.5
        
        self.logger.info("所有源权重已重置")
        self.adaptive_stats['strategy_changes'] += 1