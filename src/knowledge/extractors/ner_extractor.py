"""
命名实体识别器
支持多种NLP模型
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

import jieba
import jieba.posseg as pseg

from .base_extractor import BaseKnowledgeExtractor
from ..base import ExtractedEntity, KnowledgeExtractionConfig


@dataclass
class NERConfig:
    """NER配置"""
    model_type: str = "jieba"  # "jieba", "hanlp", "spacy", "bert", "ensemble"
    use_gpu: bool = False
    entity_types: List[str] = field(default_factory=lambda: [
        "PERSON", "ORG", "LOC", "PRODUCT", "TECH", "EVENT"
    ])
    custom_patterns: Dict[str, str] = field(default_factory=dict)
    enable_postprocess: bool = True
    min_confidence: float = 0.5


class NERExtractor(BaseKnowledgeExtractor):
    """命名实体识别器"""
    
    def __init__(self, config: Optional[KnowledgeExtractionConfig] = None, 
                 ner_config: Optional[NERConfig] = None):
        super().__init__(config)
        self.ner_config = ner_config or NERConfig()
        self._init_jieba()
        self._load_patterns()
        self.models = {}
        
        self.logger.info(f"NER提取器初始化完成: {self.ner_config.model_type}")
    
    def _init_jieba(self):
        """初始化jieba"""
        # 添加技术术语
        tech_terms = [
            "人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理",
            "计算机视觉", "大数据", "云计算", "区块链", "物联网"
        ]
        for term in tech_terms:
            jieba.add_word(term, freq=1000, tag='n')
    
    def _load_patterns(self):
        """加载模式"""
        self.patterns = {}
        # 技术实体模式
        self.patterns["TECH"] = re.compile(r'(人工智能|AI|机器学习|ML|深度学习|DL)')
        # 公司名模式
        self.patterns["ORG"] = re.compile(r'([\u4e00-\u9fa5]{2,8}(?:科技|公司|集团))')
    
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """提取实体"""
        entities = []
        
        # 方法1: jieba分词
        if self.ner_config.model_type in ["jieba", "ensemble"]:
            entities.extend(self._extract_with_jieba(text))
        
        # 方法2: 规则匹配
        entities.extend(self._extract_with_patterns(text))
        
        # 后处理
        entities = self._postprocess_entities(entities, text)
        
        # 过滤置信度
        entities = [e for e in entities if e.confidence >= self.ner_config.min_confidence]
        
        self.logger.info(f"提取到 {len(entities)} 个实体")
        return entities
    
    def _extract_with_jieba(self, text: str) -> List[ExtractedEntity]:
        """使用jieba提取"""
        entities = []
        words = pseg.cut(text)
        current_pos = 0
        
        for word, flag in words:
            label = self._jieba_flag_to_label(flag, word)
            if label:
                start_pos = text.find(word, current_pos)
                if start_pos != -1:
                    entities.append(ExtractedEntity(
                        text=word,
                        label=label,
                        start_pos=start_pos,
                        end_pos=start_pos + len(word),
                        confidence=0.8
                    ))
                    current_pos = start_pos + len(word)
        
        return entities
    
    def _jieba_flag_to_label(self, flag: str, word: str) -> Optional[str]:
        """jieba标签转NER标签"""
        mapping = {
            'nr': 'PERSON',
            'nt': 'ORG',
            'ns': 'LOC',
            'nz': 'ORG'
        }
        return mapping.get(flag)
    
    def _extract_with_patterns(self, text: str) -> List[ExtractedEntity]:
        """使用模式匹配提取"""
        entities = []
        
        for label, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                entities.append(ExtractedEntity(
                    text=match.group(),
                    label=label,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=0.7
                ))
        
        return entities
    
    def _postprocess_entities(self, entities: List[ExtractedEntity], text: str) -> List[ExtractedEntity]:
        """后处理实体"""
        if not self.ner_config.enable_postprocess:
            return entities
        
        # 去重（基于位置）
        seen_positions = set()
        processed = []
        
        for entity in entities:
            pos_key = (entity.start_pos, entity.end_pos)
            if pos_key not in seen_positions:
                seen_positions.add(pos_key)
                
                # 添加上下文
                start = max(0, entity.start_pos - 20)
                end = min(len(text), entity.end_pos + 20)
                entity.context = text[start:end]
                
                processed.append(entity)
        
        return processed
    
    def extract_relations(self, text: str, entities: Optional[List[ExtractedEntity]] = None):
        """NER提取器主要提取实体，关系提取简单实现"""
        # 默认实现，子类可重写
        return []