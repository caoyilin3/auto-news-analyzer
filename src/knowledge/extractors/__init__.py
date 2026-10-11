"""
知识提取器模块
包括实体识别、关系提取等
"""

from .base_extractor import BaseKnowledgeExtractor
from .ner_extractor import NERExtractor, NERConfig
from .relation_extractor import RelationExtractor, RelationExtractionConfig

__all__ = [
    "BaseKnowledgeExtractor",
    "NERExtractor",
    "NERConfig",
    "RelationExtractor",
    "RelationExtractionConfig",
    "KnowledgeExtractorFactory",
]


class KnowledgeExtractorFactory:
    """知识提取器工厂"""
    
    @staticmethod
    def create_extractor(extractor_type: str, **kwargs):
        """
        创建提取器
        
        Args:
            extractor_type: "ner", "relation", 或 "hybrid"
            **kwargs: 配置参数
        """
        from ..base import KnowledgeExtractionConfig
        
        config = kwargs.get('config', KnowledgeExtractionConfig())
        
        if extractor_type.lower() == 'ner':
            ner_config = kwargs.get('ner_config', NERConfig())
            return NERExtractor(config, ner_config)
        
        elif extractor_type.lower() == 'relation':
            rel_config = kwargs.get('rel_config', RelationExtractionConfig())
            return RelationExtractor(config, rel_config)
        
        elif extractor_type.lower() == 'hybrid':
            # 创建组合提取器
            class HybridExtractor(BaseKnowledgeExtractor):
                def __init__(self, config):
                    super().__init__(config)
                    self.ner_extractor = NERExtractor(config)
                    self.rel_extractor = RelationExtractor(config)
                
                def extract_entities(self, text):
                    return self.ner_extractor.extract_entities(text)
                
                def extract_relations(self, text, entities=None):
                    if entities is None:
                        entities = self.extract_entities(text)
                    return self.rel_extractor.extract_relations(text, entities)
            
            return HybridExtractor(config)
        
        else:
            raise ValueError(f"未知的提取器类型: {extractor_type}")