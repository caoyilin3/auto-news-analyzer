# src/data_acquisition/mock_crawler.py
"""
模拟爬虫 - 生成模拟新闻数据，用于开发/测试环境
无需网络访问，保证系统开箱即用
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from .base_crawler import BaseCrawler


class MockCrawler(BaseCrawler):
    """模拟爬虫"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("mock_crawler", config)
        self.mock_data_count = config.get('mock_data_count', 5)

    async def fetch(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取模拟数据

        Args:
            limit: 最大获取数量

        Returns:
            模拟文章列表
        """
        self.logger.info(f"生成模拟数据，目标数量: {limit}")
        articles = self._generate_mock_data(min(limit, self.mock_data_count))
        self.stats['total_articles'] += len(articles)
        self.logger.info(f"模拟数据获取完成，共 {len(articles)} 篇文章")
        return articles

    def _generate_mock_data(self, limit: int) -> List[Dict[str, Any]]:
        """生成模拟文章"""
        mock_articles = []

        templates = [
            {
                'title': 'AI 初创公司推出新一代深度学习平台',
                'content': (
                    '这家专注于人工智能的初创公司今天宣布推出新一代深度学习平台。'
                    '该平台整合了自研的大规模语言模型与高效训练框架，'
                    '据称推理速度较上一代提升约 40%。公司表示，'
                    '新平台将首先面向金融与医疗领域开放。'
                ),
                'source': 'techcrunch_mock',
                'author': 'Sarah Johnson',
                'category': 'Technology',
                'url': 'https://techcrunch.com/mock/ai-platform-1',
                'published_days_ago': 0,
            },
            {
                'title': '量子计算在材料科学领域取得突破',
                'content': (
                    '研究团队在量子计算领域取得重要进展，'
                    '利用量子模拟方法成功预测了一种新型超导材料的结构。'
                    '这项工作结合了量子神经网络与经典分子动力学，'
                    '为未来高性能电池的研发提供了理论基础。'
                ),
                'source': 'arxiv_mock',
                'author': 'Dr. Zhang et al.',
                'category': 'Academic Paper',
                'url': 'https://arxiv.org/abs/mock-quantum-2',
                'published_days_ago': 2,
            },
            {
                'title': '开源社区发布新一代网络安全框架',
                'content': (
                    '一个由社区驱动的开源项目发布了全新一代网络安全框架。'
                    '该框架内置了流量异常检测、零信任访问控制等能力，'
                    '并提供了与主流云平台的即插即用集成。'
                ),
                'source': 'github_mock',
                'author': 'Alex Rodriguez',
                'category': 'Security',
                'url': 'https://github.com/mock/security-framework-3',
                'published_days_ago': 5,
            },
            {
                'title': '低质量推广文章：点击领取免费大奖',
                'content': (
                    '点击链接立即领取您的专属大奖！限时优惠，'
                    '错过再等一年。立即订阅我们的广告邮件。'
                ),
                'source': 'ad_source',
                'author': '未知',
                'category': 'Promotion',
                'url': 'https://ads.example.com/sponsored/click-4',
                'published_days_ago': 1,
            },
            {
                'title': '生物科技公司获新一轮融资',
                'content': (
                    '这家生物科技公司宣布完成新一轮融资，'
                    '本轮融资将用于推进其 mRNA 疫苗管线的临床研究。'
                    '多家知名投资机构参与了本轮投资。'
                ),
                'source': 'techcrunch_mock',
                'author': 'Michael Chen',
                'category': 'Biotech',
                'url': 'https://techcrunch.com/mock/biotech-5',
                'published_days_ago': 8,
            },
            {
                'title': 'OpenAI 收购一家专注模型的初创公司',
                'content': (
                    '据多方消息，OpenAI 已收购一家专注于大模型优化的初创公司。'
                    '此次收购将补充其在模型压缩与推理加速方面的技术积累，'
                    '预计将进一步降低部署成本。'
                ),
                'source': 'techcrunch_mock',
                'author': 'Sarah Johnson',
                'category': 'Technology',
                'url': 'https://techcrunch.com/mock/openai-6',
                'published_days_ago': 0,
            },
        ]

        for i in range(min(limit, len(templates))):
            tpl = templates[i % len(templates)]
            published_at = (datetime.now() - timedelta(days=tpl['published_days_ago'])).isoformat()

            article = {
                'id': f"mock_{datetime.now().strftime('%Y%m%d')}_{i:03d}",
                'title': tpl['title'],
                'content': tpl['content'],
                'url': tpl['url'],
                'source': tpl['source'],
                'published_at': published_at,
                'author': tpl['author'],
                'category': tpl['category'],
                'is_mock': True,
            }
            mock_articles.append(article)

        return mock_articles
