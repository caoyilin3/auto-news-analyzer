"""
关系提取器
提取实体间的语义关系
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .base_extractor import BaseKnowledgeExtractor
from ..base import ExtractedEntity, ExtractedRelation, KnowledgeExtractionConfig


@dataclass
class RelationExtractionConfig:
    """关系提取配置"""
    method: str = "rule"  # "rule", "dependency", "semantic", "hybrid"
    max_distance: int = 100
    min_confidence: float = 0.5
    relation_types: List[str] = field(default_factory=lambda: [
        "位于", "成立于", "专注于", "投资于", "合作于", "收购于"
    ])
    patterns: Dict[str, List[str]] = field(default_factory=dict)


class RelationExtractor(BaseKnowledgeExtractor):
    """关系提取器"""
    
    def __init__(self, config: Optional[KnowledgeExtractionConfig] = None,
                 rel_config: Optional[RelationExtractionConfig] = None):
        super().__init__(config)
        self.rel_config = rel_config or RelationExtractionConfig()
        self._load_patterns()
        self.logger.info("关系提取器初始化完成")
    
    def _load_patterns(self):
        """加载关系模式"""
        self.patterns = defaultdict(list)
        
        # 中文关系模式
        chinese_patterns = {
            "位于": [r'([^，。]*?)(位于|坐落于|地处)([^，。]*?)'],
            "成立于": [r'([^，。]*?)(成立于|创建于|创立于)(\d{4}年)'],
            "专注于": [r'([^，。]*?)(专注于|致力于|专攻于)([^，。]*?)'],
            "投资于": [r'([^，。]*?)(投资|入股|注资)([^，。]*?)'],
            "收购于": [r'([^，。]*?)(收购|并购|兼并)([^，。]*?)'],
        }
        
        for rel_type, patterns in chinese_patterns.items():
            for pattern in patterns:
                self.patterns[rel_type].append(re.compile(pattern))
    
    def extract_entities(self, text: str):
        """关系提取器通常不直接提取实体"""
        return []
    
    def extract_relations(self, text: str, entities: Optional[List[ExtractedEntity]] = None) -> List[ExtractedRelation]:
        """提取关系"""
        if not entities:
            self.logger.warning("未提供实体列表，关系提取效果受限")
            return []
        
        relations = []
        
        # 基于规则的关系提取
        for rel_type, patterns in self.patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    groups = match.groups()
                    if len(groups) >= 3:
                        # 查找匹配的实体
                        entity_pairs = self._find_matching_entities(groups, entities)
                        for subj, obj in entity_pairs:
                            relations.append(ExtractedRelation(
                                subject=subj.text,
                                predicate=rel_type,
                                object=obj.text,
                                confidence=0.7,
                                context=text[max(0, match.start()-20):min(len(text), match.end()+20)],
                                evidence_positions=(match.start(), match.end())
                            ))
        
        # 基于邻近度的关系推断
        relations.extend(self._extract_by_proximity(text, entities))
        
        # 去重和过滤
        relations = self._deduplicate_relations(relations)
        relations = [r for r in relations if r.confidence >= self.rel_config.min_confidence]
        
        self.logger.info(f"提取到 {len(relations)} 个关系")
        return relations
    
    def _find_matching_entities(self, groups: Tuple, entities: List[ExtractedEntity]) -> List[Tuple]:
        """查找匹配的实体对"""
        pairs = []
        
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                group_i, group_j = groups[i], groups[j]
                if not group_i or not group_j:
                    continue
                
                for e1 in entities:
                    if e1.text in group_i or group_i in e1.text:
                        for e2 in entities:
                            if e2 != e1 and (e2.text in group_j or group_j in e2.text):
                                pairs.append((e1, e2))
        
        return pairs
    
    def _extract_by_proximity(self, text: str, entities: List[ExtractedEntity]) -> List[ExtractedRelation]:
        """基于邻近度提取关系"""
        relations = []
        
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                distance = abs(e1.start_pos - e2.start_pos)
                if distance <= self.rel_config.max_distance:
                    rel_type = self._infer_relation_type(e1, e2)
                    if rel_type:
                        confidence = max(0.5, 1.0 - (distance / self.rel_config.max_distance))
                        relations.append(ExtractedRelation(
                            subject=e1.text,
                            predicate=rel_type,
                            object=e2.text,
                            confidence=confidence,
                            context=text[min(e1.start_pos, e2.start_pos):max(e1.end_pos, e2.end_pos)+20]
                        ))
        
        return relations
    
    def _infer_relation_type(self, e1: ExtractedEntity, e2: ExtractedEntity) -> Optional[str]:
        """推断关系类型"""
        type_pairs = {
            ("ORG", "LOC"): "位于",
            ("PERSON", "ORG"): "任职于",
            ("ORG", "TECH"): "专注于",
            ("ORG", "PRODUCT"): "推出了",
        }
        
        key = (e1.label, e2.label)
        if key in type_pairs:
            return type_pairs[key]
        
        key_rev = (e2.label, e1.label)
        if key_rev in type_pairs:
            return type_pairs[key_rev]
        
        return None
    
    def _deduplicate_relations(self, relations: List[ExtractedRelation]) -> List[ExtractedRelation]:
        """去重关系"""
        seen = set()
        unique = []
        
        for rel in relations:
            key = (rel.subject, rel.predicate, rel.object)
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        
        return unique