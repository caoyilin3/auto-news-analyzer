"""
可信度评估配置模式定义
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator, root_validator


class CredibilityWeights(BaseModel):
    """可信度权重配置"""
    source: float = Field(0.35, ge=0.0, le=1.0, description="来源可信度权重")
    freshness: float = Field(0.20, ge=0.0, le=1.0, description="信息新鲜度权重")
    author: float = Field(0.15, ge=0.0, le=1.0, description="作者权威性权重")
    content: float = Field(0.20, ge=0.0, le=1.0, description="内容质量权重")
    url: float = Field(0.10, ge=0.0, le=1.0, description="URL规范性权重")
    
    @root_validator
    def validate_weight_sum(cls, values):
        """验证权重总和是否为1"""
        weights = [values.get('source', 0), values.get('freshness', 0), 
                  values.get('author', 0), values.get('content', 0), 
                  values.get('url', 0)]
        total = sum(weights)
        
        # 允许微小误差
        if abs(total - 1.0) > 0.001:
            raise ValueError(f'可信度权重总和必须为1.0，当前总和为: {total}')
        
        return values


class CredibilityThresholds(BaseModel):
    """可信度阈值配置"""
    high: float = Field(0.8, ge=0.0, le=1.0, description="高可信度阈值")
    medium: float = Field(0.5, ge=0.0, le=1.0, description="中等可信度阈值")
    low: float = Field(0.0, ge=0.0, le=1.0, description="低可信度阈值")
    
    @root_validator
    def validate_threshold_order(cls, values):
        """验证阈值顺序"""
        high = values.get('high', 0.8)
        medium = values.get('medium', 0.5)
        low = values.get('low', 0.0)
        
        if not (low <= medium <= high):
            raise ValueError(f'阈值必须满足: low <= medium <= high，当前: {low}, {medium}, {high}')
        
        return values


class SourceReputation(BaseModel):
    """来源信誉配置"""
    domain: str = Field(..., description="域名")
    reputation_score: float = Field(..., ge=0.0, le=1.0, description="信誉分数")
    category: Optional[str] = Field(None, description="分类：news, academic, blog, etc.")
    last_updated: Optional[str] = Field(None, description="最后更新时间")
    trust_level: str = Field("medium", description="信任级别：high, medium, low")


class CredibilitySchema(BaseModel):
    """可信度评估配置模式"""
    enabled: bool = Field(True, description="是否启用可信度评估")
    min_score: float = Field(0.7, ge=0.0, le=1.0, description="最小接受分数")
    auto_learn: bool = Field(True, description="是否自动学习调整权重")
    weights: CredibilityWeights = Field(default_factory=CredibilityWeights, description="权重配置")
    thresholds: CredibilityThresholds = Field(default_factory=CredibilityThresholds, description="阈值配置")
    source_reputation: Dict[str, float] = Field(
        default_factory=dict, 
        description="来源信誉分数映射"
    )
    freshness_decay_rate: float = Field(0.1, ge=0.0, le=1.0, description="新鲜度衰减率")
    author_verification: bool = Field(True, description="是否验证作者")
    content_analysis: bool = Field(True, description="是否分析内容质量")
    url_analysis: bool = Field(True, description="是否分析URL")
    cross_validation: bool = Field(False, description="是否进行交叉验证")
    validation_sources: List[str] = Field(default_factory=list, description="验证来源列表")
    
    class Config:
        """Pydantic配置"""
        extra = "forbid"
        validate_assignment = True
    
    @validator('source_reputation')
    def validate_source_reputation_scores(cls, v):
        """验证来源信誉分数"""
        for domain, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f'来源信誉分数必须在0-1之间: {domain}={score}')
        return v
    
    @validator('validation_sources')
    def validate_validation_sources(cls, v, values):
        """验证验证来源"""
        if values.get('cross_validation', False) and not v:
            raise ValueError('启用交叉验证时必须提供 validation_sources')
        return v
    
    def calculate_score(self, scores: Dict[str, float]) -> float:
        """
        计算综合可信度分数
        
        Args:
            scores: 各维度分数字典
            
        Returns:
            综合可信度分数
        """
        weight_dict = self.weights.dict()
        total_score = 0.0
        
        for dimension, weight in weight_dict.items():
            if dimension in scores:
                total_score += weight * scores[dimension]
            else:
                # 如果某个维度没有分数，使用默认值（比如0.5）
                total_score += weight * 0.5
        
        return total_score
    
    def get_credibility_level(self, score: float) -> str:
        """
        根据分数获取可信度级别
        
        Args:
            score: 可信度分数
            
        Returns:
            可信度级别：high, medium, low
        """
        if score >= self.thresholds.high:
            return "high"
        elif score >= self.thresholds.medium:
            return "medium"
        else:
            return "low"
    
    def get_source_reputation(self, domain: str) -> float:
        """
        获取来源信誉分数
        
        Args:
            domain: 域名
            
        Returns:
            信誉分数，如果不存在则返回默认值0.5
        """
        return self.source_reputation.get(domain, 0.5)
    
    def add_source_reputation(self, domain: str, score: float, category: str = None):
        """
        添加或更新来源信誉
        
        Args:
            domain: 域名
            score: 信誉分数
            category: 分类
        """
        if not 0.0 <= score <= 1.0:
            raise ValueError(f'信誉分数必须在0-1之间: {score}')
        
        self.source_reputation[domain] = score
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "min_score": self.min_score,
            "auto_learn": self.auto_learn,
            "weights": self.weights.dict(),
            "thresholds": self.thresholds.dict(),
            "source_reputation": self.source_reputation,
            "freshness_decay_rate": self.freshness_decay_rate,
            "author_verification": self.author_verification,
            "content_analysis": self.content_analysis,
            "url_analysis": self.url_analysis,
            "cross_validation": self.cross_validation,
            "validation_sources": self.validation_sources,
        }