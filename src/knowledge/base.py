"""
基础类和配置定义
为知识管理模块提供统一的数据结构和配置
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
import json
import logging


class ExtractionMethod(Enum):
    """提取方法枚举"""
    RULE_BASED = auto()
    ML_BASED = auto()
    HYBRID = auto()
    LLM_BASED = auto()


class KnowledgeType(Enum):
    """知识类型枚举"""
    ENTITY = auto()
    RELATION = auto()
    EVENT = auto()
    CONCEPT = auto()
    ATTRIBUTE = auto()
    TOPIC = auto()


@dataclass
class KnowledgeExtractionConfig:
    """知识提取配置"""
    method: ExtractionMethod = ExtractionMethod.HYBRID
    confidence_threshold: float = 0.7
    max_entities: int = 100
    max_relations: int = 200
    enable_coreference: bool = True
    enable_abbreviation_expansion: bool = True
    language: str = "zh"
    domain: Optional[str] = None
    custom_rules: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeExtractionConfig':
        """从字典创建"""
        return cls(**data)


@dataclass
class ExtractedEntity:
    """提取的实体"""
    text: str
    label: str
    start_pos: int
    end_pos: int
    confidence: float = 1.0
    normalized_form: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    context: Optional[str] = None
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id or f"entity_{self.start_pos}_{self.end_pos}",
            "text": self.text,
            "label": self.label,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "confidence": round(self.confidence, 3),
            "normalized_form": self.normalized_form,
            "attributes": self.attributes,
            "context": self.context
        }
    
    def __hash__(self):
        return hash((self.text, self.label, self.start_pos, self.end_pos))


@dataclass
class ExtractedRelation:
    """提取的关系"""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    context: Optional[str] = None
    evidence_positions: Optional[Tuple[int, int]] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id or f"rel_{hash(self.subject)}_{hash(self.predicate)}_{hash(self.object)}",
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": round(self.confidence, 3),
            "context": self.context,
            "evidence_positions": self.evidence_positions,
            "attributes": self.attributes
        }
    
    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))


@dataclass
class ExtractedKnowledge:
    """提取的知识集合"""
    text: str
    entities: List[ExtractedEntity]
    relations: List[ExtractedRelation]
    events: List[Dict] = field(default_factory=list)
    concepts: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "text": self.text,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "events": self.events,
            "concepts": self.concepts,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "summary": {
                "entity_count": len(self.entities),
                "relation_count": len(self.relations),
                "event_count": len(self.events),
                "concept_count": len(self.concepts)
            }
        }
    
    def filter_by_confidence(self, threshold: float = 0.5) -> 'ExtractedKnowledge':
        """按置信度过滤"""
        return ExtractedKnowledge(
            text=self.text,
            entities=[e for e in self.entities if e.confidence >= threshold],
            relations=[r for r in self.relations if r.confidence >= threshold],
            events=self.events,
            concepts=self.concepts,
            metadata=self.metadata,
            timestamp=self.timestamp
        )
    
    def save(self, filepath: str) -> bool:
        """保存到文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"保存知识失败: {e}")
            return False
    
    @classmethod
    def load(cls, filepath: str) -> Optional['ExtractedKnowledge']:
        """从文件加载"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            entities = [ExtractedEntity(**e) for e in data['entities']]
            relations = [ExtractedRelation(**r) for r in data['relations']]
            
            return cls(
                text=data['text'],
                entities=entities,
                relations=relations,
                events=data.get('events', []),
                concepts=data.get('concepts', []),
                metadata=data.get('metadata', {}),
                timestamp=data.get('timestamp')
            )
        except Exception as e:
            logging.error(f"加载知识失败: {e}")
            return None