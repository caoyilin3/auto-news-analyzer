"""
知识管理配置模式定义
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator


class StorageType(str, Enum):
    """存储类型枚举"""
    MEMORY = "memory"
    POSTGRES = "postgres"
    NEO4J = "neo4j"
    ELASTICSEARCH = "elasticsearch"
    FAISS = "faiss"
    QDRANT = "qdrant"


class ExtractionMethod(str, Enum):
    """知识提取方法枚举"""
    RULE_BASED = "rule_based"
    MACHINE_LEARNING = "ml"
    DEEP_LEARNING = "dl"
    HYBRID = "hybrid"


class ConflictResolutionStrategy(str, Enum):
    """冲突解决策略枚举"""
    CREDIBILITY = "credibility"
    TIMESTAMP = "timestamp"
    EVIDENCE = "evidence"
    VOTING = "voting"
    HIERARCHICAL = "hierarchical"


class EntityType(BaseModel):
    """实体类型定义"""
    name: str = Field(..., description="实体类型名称")
    description: str = Field("", description="实体类型描述")
    properties: List[str] = Field(default_factory=list, description="属性列表")
    relations: List[str] = Field(default_factory=list, description="关联关系列表")
    weight: float = Field(1.0, ge=0.0, description="类型权重")


class RelationType(BaseModel):
    """关系类型定义"""
    name: str = Field(..., description="关系类型名称")
    description: str = Field("", description="关系类型描述")
    symmetric: bool = Field(False, description="是否对称关系")
    transitive: bool = Field(False, description="是否传递关系")
    reflexive: bool = Field(False, description="是否自反关系")
    domains: List[str] = Field(default_factory=list, description="定义域实体类型")
    ranges: List[str] = Field(default_factory=list, description="值域实体类型")


class ExtractionConfig(BaseModel):
    """知识提取配置"""
    enabled: bool = Field(True, description="是否启用知识提取")
    method: ExtractionMethod = Field(ExtractionMethod.HYBRID, description="提取方法")
    ner_model: str = Field("en_core_web_sm", description="命名实体识别模型")
    relation_model: Optional[str] = Field(None, description="关系提取模型")
    entity_types: List[EntityType] = Field(default_factory=list, description="实体类型定义")
    relation_types: List[RelationType] = Field(default_factory=list, description="关系类型定义")
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0, description="置信度阈值")
    max_entities: int = Field(100, ge=1, description="最大实体数")
    max_relations: int = Field(50, ge=1, description="最大关系数")
    batch_size: int = Field(32, ge=1, description="批量处理大小")
    parallel_processing: bool = Field(True, description="是否并行处理")
    
    @validator('ner_model')
    def validate_ner_model(cls, v):
        """验证NER模型"""
        valid_models = ['en_core_web_sm', 'en_core_web_md', 'en_core_web_lg']
        if v not in valid_models:
            raise ValueError(f'无效的NER模型: {v}，必须是 {valid_models} 之一')
        return v


class StorageConfig(BaseModel):
    """存储配置"""
    graph_storage: StorageType = Field(StorageType.MEMORY, description="知识图谱存储类型")
    vector_storage: StorageType = Field(StorageType.MEMORY, description="向量存储类型")
    embedding_model: str = Field("all-MiniLM-L6-v2", description="嵌入模型")
    embedding_dimension: int = Field(384, ge=1, description="嵌入维度")
    
    # 图存储配置
    graph_config: Dict[str, Any] = Field(default_factory=dict, description="图存储配置")
    
    # 向量存储配置
    vector_config: Dict[str, Any] = Field(default_factory=dict, description="向量存储配置")
    
    # 缓存配置
    cache_enabled: bool = Field(True, description="是否启用缓存")
    cache_size: int = Field(10000, ge=0, description="缓存大小")
    cache_ttl: int = Field(3600, ge=0, description="缓存TTL（秒）")
    
    @validator('embedding_model')
    def validate_embedding_model(cls, v):
        """验证嵌入模型"""
        valid_models = [
            'all-MiniLM-L6-v2',
            'all-mpnet-base-v2',
            'paraphrase-multilingual-MiniLM-L12-v2'
        ]
        if v not in valid_models:
            print(f'警告: 非标准嵌入模型: {v}')
        return v
    
    @validator('embedding_dimension')
    def validate_embedding_dimension(cls, v, values):
        """验证嵌入维度"""
        model = values.get('embedding_model', '')
        
        # 常见模型的嵌入维度
        model_dimensions = {
            'all-MiniLM-L6-v2': 384,
            'all-mpnet-base-v2': 768,
            'paraphrase-multilingual-MiniLM-L12-v2': 384,
        }
        
        expected_dim = model_dimensions.get(model)
        if expected_dim and v != expected_dim:
            print(f'警告: 嵌入模型 {model} 的预期维度是 {expected_dim}，但配置为 {v}')
        
        return v


class KnowledgeSchema(BaseModel):
    """知识管理配置模式"""
    enabled: bool = Field(True, description="是否启用知识管理")
    
    # 提取配置
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig, description="知识提取配置")
    
    # 存储配置
    storage: StorageConfig = Field(default_factory=StorageConfig, description="存储配置")
    
    # 冲突解决
    conflict_resolution: ConflictResolutionStrategy = Field(
        ConflictResolutionStrategy.CREDIBILITY,
        description="冲突解决策略"
    )
    
    # 推理配置
    enable_inference: bool = Field(True, description="是否启用推理")
    inference_depth: int = Field(3, ge=1, le=10, description="推理深度")
    enable_deduction: bool = Field(True, description="是否启用演绎推理")
    enable_induction: bool = Field(False, description="是否启用归纳推理")
    
    # 质量保证
    quality_assurance: bool = Field(True, description="是否启用质量保证")
    validation_enabled: bool = Field(True, description="是否启用验证")
    deduplication_enabled: bool = Field(True, description="是否启用去重")
    
    # 更新策略
    incremental_update: bool = Field(True, description="是否增量更新")
    update_threshold: float = Field(0.8, ge=0.0, le=1.0, description="更新阈值")
    consolidation_frequency: str = Field("daily", description="整合频率")
    
    class Config:
        """Pydantic配置"""
        extra = "forbid"
        validate_assignment = True
    
    @validator('consolidation_frequency')
    def validate_consolidation_frequency(cls, v):
        """验证整合频率"""
        valid_frequencies = ['hourly', 'daily', 'weekly', 'monthly', 'never']
        if v not in valid_frequencies:
            raise ValueError(f'无效的整合频率: {v}，必须是 {valid_frequencies} 之一')
        return v
    
    def get_entity_type(self, name: str) -> Optional[EntityType]:
        """获取实体类型定义"""
        for entity_type in self.extraction.entity_types:
            if entity_type.name == name:
                return entity_type
        return None
    
    def get_relation_type(self, name: str) -> Optional[RelationType]:
        """获取关系类型定义"""
        for relation_type in self.extraction.relation_types:
            if relation_type.name == name:
                return relation_type
        return None
    
    def add_entity_type(self, entity_type: EntityType) -> None:
        """添加实体类型"""
        existing = self.get_entity_type(entity_type.name)
        if existing:
            raise ValueError(f"实体类型 '{entity_type.name}' 已存在")
        self.extraction.entity_types.append(entity_type)
    
    def add_relation_type(self, relation_type: RelationType) -> None:
        """添加关系类型"""
        existing = self.get_relation_type(relation_type.name)
        if existing:
            raise ValueError(f"关系类型 '{relation_type.name}' 已存在")
        self.extraction.relation_types.append(relation_type)
    
    def validate_schema(self) -> List[str]:
        """验证知识模式，返回错误列表"""
        errors = []
        
        # 检查实体类型
        entity_names = set()
        for entity_type in self.extraction.entity_types:
            if entity_type.name in entity_names:
                errors.append(f"重复的实体类型名称: {entity_type.name}")
            entity_names.add(entity_type.name)
        
        # 检查关系类型
        relation_names = set()
        for relation_type in self.extraction.relation_types:
            if relation_type.name in relation_names:
                errors.append(f"重复的关系类型名称: {relation_type.name}")
            relation_names.add(relation_type.name)
            
            # 检查关系定义中的实体类型是否存在
            for domain in relation_type.domains:
                if domain not in entity_names:
                    errors.append(f"关系 '{relation_type.name}' 的定义域实体类型不存在: {domain}")
            
            for range_entity in relation_type.ranges:
                if range_entity not in entity_names:
                    errors.append(f"关系 '{relation_type.name}' 的值域实体类型不存在: {range_entity}")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "extraction": self.extraction.dict(),
            "storage": self.storage.dict(),
            "conflict_resolution": self.conflict_resolution.value,
            "enable_inference": self.enable_inference,
            "inference_depth": self.inference_depth,
            "enable_deduction": self.enable_deduction,
            "enable_induction": self.enable_induction,
            "quality_assurance": self.quality_assurance,
            "validation_enabled": self.validation_enabled,
            "deduplication_enabled": self.deduplication_enabled,
            "incremental_update": self.incremental_update,
            "update_threshold": self.update_threshold,
            "consolidation_frequency": self.consolidation_frequency,
        }