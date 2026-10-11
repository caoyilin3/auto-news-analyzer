"""
知识提取基类
定义统一的知识提取接口
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from ..base import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractedKnowledge,
    KnowledgeExtractionConfig
)


class BaseKnowledgeExtractor(ABC):
    """知识提取器基类"""
    
    def __init__(self, config: Optional[KnowledgeExtractionConfig] = None):
        self.config = config or KnowledgeExtractionConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """提取实体"""
        pass
    
    @abstractmethod
    def extract_relations(self, text: str, 
                         entities: Optional[List[ExtractedEntity]] = None) -> List[ExtractedRelation]:
        """提取关系"""
        pass
    
    def extract_knowledge(self, text: str) -> ExtractedKnowledge:
        """提取完整知识"""
        self.logger.info(f"开始知识提取，文本长度: {len(text)}")
        
        entities = self.extract_entities(text)
        relations = self.extract_relations(text, entities)
        
        return ExtractedKnowledge(
            text=text,
            entities=entities,
            relations=relations,
            metadata={
                "extractor": self.__class__.__name__,
                "method": self.config.method.name,
                "timestamp": datetime.now().isoformat()
            }
        )
