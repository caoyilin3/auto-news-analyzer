"""
专利证据模块

提供专利证据收集与证据报告生成能力（可选模块，不参与主工作流）。
依赖 pandas/numpy，缺失时本包仍可安全导入，仅相关类为 None。
"""

try:
    from .collector import PatentEvidenceCollector, get_collector
    from .manager import EvidenceManager, setup_patent_directory
except Exception:  # 可选依赖缺失时不影响主系统导入
    PatentEvidenceCollector = None
    EvidenceManager = None
    get_collector = None
    setup_patent_directory = None

__all__ = [
    "PatentEvidenceCollector",
    "EvidenceManager",
    "get_collector",
    "setup_patent_directory",
]