"""
工具函数模块
为知识管理提供辅助功能
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime


def validate_text_input(text: str, min_length: int = 10) -> bool:
    """验证文本输入"""
    if not text or not isinstance(text, str):
        return False
    
    text = text.strip()
    if len(text) < min_length:
        return False
    
    # 检查是否包含有效内容（非纯符号或空格）
    if not re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', text):
        return False
    
    return True


def preprocess_text(text: str, 
                   remove_urls: bool = True,
                   remove_emails: bool = True,
                   remove_special_chars: bool = True) -> str:
    """预处理文本"""
    if not text:
        return ""
    
    # 移除URL
    if remove_urls:
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # 移除邮箱
    if remove_emails:
        text = re.sub(r'\S+@\S+', '', text)
    
    # 移除特殊字符
    if remove_special_chars:
        text = re.sub(r'[^\w\u4e00-\u9fa5\s.,!?;:]', '', text)
    
    # 规范化空白字符
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def calculate_confidence(scores: List[float], weights: Optional[List[float]] = None) -> float:
    """计算综合置信度"""
    if not scores:
        return 0.0
    
    if weights is None:
        weights = [1.0] * len(scores)
    
    if len(scores) != len(weights):
        raise ValueError("分数和权重数量不一致")
    
    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    total_weight = sum(weights)
    
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def log_extraction_stats(knowledge, logger: Optional[logging.Logger] = None):
    """记录提取统计"""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    stats = {
        "timestamp": datetime.now().isoformat(),
        "text_length": len(knowledge.text),
        "entity_count": len(knowledge.entities),
        "relation_count": len(knowledge.relations),
        "average_entity_confidence": sum(e.confidence for e in knowledge.entities) / len(knowledge.entities) if knowledge.entities else 0,
        "average_relation_confidence": sum(r.confidence for r in knowledge.relations) / len(knowledge.relations) if knowledge.relations else 0,
    }
    
    logger.info(f"知识提取统计: {stats}")
    return stats


__all__ = [
    "validate_text_input",
    "preprocess_text",
    "calculate_confidence",
    "log_extraction_stats"
]