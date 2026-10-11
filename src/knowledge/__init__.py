"""
知识管理模块 - 自主进化的AI系统知识处理核心
提供实体识别、关系提取、知识图谱等功能
"""

from .base import *
from .extractors import *
from .utils import *
from .graph import KnowledgeGraph, KnowledgeGraphConfig, GraphNode, GraphEdge
from .manager import KnowledgeManager

# 存储后端为可选导入：不依赖数据库时不影响系统运行
try:
    from .storage import BaseStorage, MemoryStorage, VectorStorage
except Exception:
    BaseStorage = MemoryStorage = VectorStorage = None

__version__ = "2.0.0"
__author__ = "AutoNewsAnalyzer Team"
__all__ = [
    # 基础类
    "KnowledgeExtractionConfig",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractedKnowledge",
    "ExtractionMethod",
    "KnowledgeType",

    # 管理器
    "KnowledgeManager",

    # 提取器
    "BaseKnowledgeExtractor",
    "NERExtractor",
    "RelationExtractor",
    "KnowledgeExtractorFactory",

    # 图谱
    "KnowledgeGraph",
    "KnowledgeGraphConfig",
    "GraphNode",
    "GraphEdge",

    # 存储（可选）
    "BaseStorage",
    "MemoryStorage",
    "VectorStorage",

    # 工具
    "validate_text_input",
    "preprocess_text",
    "calculate_confidence",
]
