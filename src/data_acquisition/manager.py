# src/data_acquisition/manager.py
"""
数据采集管理器 - 协调各类爬虫完成多源数据感知

对应研究报告中的"数据感知"环节：从多源自动采集新闻信息。
支持模拟数据与真实数据源，具备自适应抓取能力。
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


class DataAcquisitionManager:
    """数据采集管理器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.crawlers = {}
        self.stats = {
            "total_articles": 0,
            "sources_used": 0,
            "last_collect": None,
            "start_time": datetime.now(),
        }

    def _create_crawler(self, name: str):
        """按需创建爬虫（惰性，避免一次性拉起所有网络连接）"""
        from .mock_crawler import MockCrawler
        from .adaptive_crawler import AdaptiveCrawler

        use_mock = self.config.get("use_mock_data", True)
        if use_mock:
            return MockCrawler(self.config)
        return AdaptiveCrawler(self.config)

    async def collect_data(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行一次数据采集

        Args:
            context: 执行上下文

        Returns:
            采集结果，包含 articles 列表
        """
        context = context or {}
        self.logger.info("开始数据采集...")

        crawler = self._create_crawler("default")
        self.crawlers["default"] = crawler

        try:
            await crawler.initialize()
            limit = self.config.get("mock_data_count", 5) or 5
            articles = await crawler.fetch(limit=limit)
        finally:
            await crawler.close()

        # 统一补齐字段
        for art in articles:
            art.setdefault("id", f"art_{abs(hash(art.get('url',''))):x}")
            art.setdefault("retrieved_at", datetime.now().isoformat())

        self.stats["total_articles"] += len(articles)
        self.stats["sources_used"] = len({a.get("source") for a in articles})
        self.stats["last_collect"] = datetime.now().isoformat()

        # 返回「本周期」统计，避免把累计值写进单周期报告
        cycle_stats = {
            "total_articles": len(articles),
            "sources_used": len({a.get("source") for a in articles}),
            "last_collect": self.stats["last_collect"],
            "lifetime_articles": self.stats["total_articles"],
        }

        self.logger.info(f"数据采集完成，共 {len(articles)} 篇文章")
        return {
            "status": "completed",
            "articles": articles,
            "total": len(articles),
            "stats": cycle_stats,
        }

    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "module": "data_acquisition",
            "stats": self.stats,
            "crawlers": list(self.crawlers.keys()),
        }

    def shutdown(self):
        """关闭采集管理器"""
        self.logger.info("数据采集管理器已关闭")
