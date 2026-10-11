"""
配置模式定义模块
提供各个模块的配置模式验证
"""

from .crawler import CrawlerConfig, CrawlerSource, CrawlerSchema
from .credibility import CredibilitySchema, CredibilityWeights, CredibilityThresholds
from .knowledge import KnowledgeSchema, ExtractionConfig, StorageConfig

__all__ = [
    "CrawlerConfig",
    "CrawlerSource",
    "CrawlerSchema",
    "CredibilitySchema",
    "CredibilityWeights",
    "CredibilityThresholds",
    "KnowledgeSchema",
    "ExtractionConfig",
    "StorageConfig",
]