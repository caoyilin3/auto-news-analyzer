# src/data_acquisition/__init__.py
"""
数据获取模块 - 负责从各种来源收集数据
"""

from .base_crawler import BaseCrawler
from .adaptive_crawler import AdaptiveCrawler
from .web_scraper import WebScraper
from .api_client import APIClient
from .mock_crawler import MockCrawler
from .manager import DataAcquisitionManager

__all__ = [
    'BaseCrawler',
    'AdaptiveCrawler',
    'WebScraper',
    'APIClient',
    'MockCrawler',
    'DataAcquisitionManager'
]
