"""
爬虫配置模式定义
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import timedelta
import re
from pydantic import BaseModel, Field, validator, root_validator


class CrawlerSource(BaseModel):
    """数据源配置"""
    name: str = Field(..., description="数据源名称")
    type: str = Field(..., description="数据源类型：rss, api, mock, file")
    url: Optional[str] = Field(None, description="数据源URL")
    enabled: bool = Field(True, description="是否启用")
    weight: float = Field(1.0, ge=0.0, le=1.0, description="数据源权重")
    update_frequency: str = Field("daily", description="更新频率：hourly, daily, weekly")
    rate_limit: Optional[int] = Field(None, ge=1, description="速率限制（请求/分钟）")
    timeout: int = Field(30, ge=1, le=300, description="请求超时时间（秒）")
    retry_count: int = Field(3, ge=0, le=10, description="重试次数")
    headers: Dict[str, str] = Field(default_factory=dict, description="请求头")
    params: Dict[str, Any] = Field(default_factory=dict, description="请求参数")
    description: Optional[str] = Field(None, description="数据源描述")
    
    @validator('type')
    def validate_type(cls, v):
        valid_types = ['rss', 'api', 'mock', 'file', 'database']
        if v not in valid_types:
            raise ValueError(f'无效的数据源类型: {v}，必须是 {valid_types} 之一')
        return v
    
    @validator('update_frequency')
    def validate_update_frequency(cls, v):
        valid_frequencies = ['hourly', 'daily', 'weekly', 'monthly', 'never']
        if v not in valid_frequencies:
            raise ValueError(f'无效的更新频率: {v}，必须是 {valid_frequencies} 之一')
        return v
    
    @validator('url')
    def validate_url(cls, v, values):
        if values.get('type') in ['rss', 'api'] and not v:
            raise ValueError(f'{values.get("type")} 类型的数据源必须提供URL')
        return v


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    enabled: bool = True
    use_mock_data: bool = False
    mock_data_count: int = 10
    sources: List[Dict[str, Any]] = field(default_factory=list)
    request_timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    user_agent: str = "Mozilla/5.0 (compatible; AutoNewsAnalyzer/2.0)"
    max_concurrent: int = 10
    cache_enabled: bool = True
    cache_ttl: int = 3600
    proxy_enabled: bool = False
    proxy_list: List[str] = field(default_factory=list)
    
    def get_source(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定名称的数据源"""
        for source in self.sources:
            if source.get('name') == name:
                return source
        return None
    
    def add_source(self, source: Dict[str, Any]) -> None:
        """添加数据源"""
        # 检查名称是否已存在
        existing = self.get_source(source.get('name', ''))
        if existing:
            raise ValueError(f"数据源 '{source.get('name')}' 已存在")
        
        # 验证必需字段
        if 'name' not in source:
            raise ValueError("数据源必须包含 'name' 字段")
        if 'type' not in source:
            raise ValueError("数据源必须包含 'type' 字段")
        
        self.sources.append(source)
    
    def remove_source(self, name: str) -> bool:
        """移除数据源"""
        for i, source in enumerate(self.sources):
            if source.get('name') == name:
                self.sources.pop(i)
                return True
        return False
    
    def validate_sources(self) -> List[str]:
        """验证所有数据源，返回错误列表"""
        errors = []
        seen_names = set()
        
        for i, source in enumerate(self.sources):
            # 检查名称唯一性
            name = source.get('name', f'源#{i}')
            if name in seen_names:
                errors.append(f"数据源名称重复: {name}")
            seen_names.add(name)
            
            # 检查必需字段
            if 'type' not in source:
                errors.append(f"数据源 '{name}' 缺少 'type' 字段")
            
            # 验证类型
            source_type = source.get('type', '')
            valid_types = ['rss', 'api', 'mock', 'file']
            if source_type not in valid_types:
                errors.append(f"数据源 '{name}' 的 type 必须是 {valid_types} 之一，实际为: {source_type}")
            
            # 验证URL（对于rss和api类型）
            if source_type in ['rss', 'api'] and 'url' not in source:
                errors.append(f"数据源 '{name}' ({source_type}) 必须提供 'url' 字段")
        
        return errors


class CrawlerSchema(BaseModel):
    """爬虫配置模式验证"""
    enabled: bool = Field(True, description="是否启用爬虫")
    use_mock_data: bool = Field(False, description="是否使用模拟数据")
    mock_data_count: int = Field(10, ge=0, le=10000, description="模拟数据数量")
    sources: List[CrawlerSource] = Field(default_factory=list, description="数据源列表")
    request_timeout: int = Field(30, ge=1, le=300, description="请求超时时间（秒）")
    max_retries: int = Field(3, ge=0, le=10, description="最大重试次数")
    rate_limit_delay: float = Field(1.0, ge=0.0, le=10.0, description="请求间隔延迟（秒）")
    user_agent: str = Field(
        "Mozilla/5.0 (compatible; AutoNewsAnalyzer/2.0)",
        description="用户代理字符串"
    )
    max_concurrent: int = Field(10, ge=1, le=100, description="最大并发请求数")
    cache_enabled: bool = Field(True, description="是否启用缓存")
    cache_ttl: int = Field(3600, ge=0, description="缓存TTL（秒）")
    proxy_enabled: bool = Field(False, description="是否使用代理")
    proxy_list: List[str] = Field(default_factory=list, description="代理服务器列表")
    
    class Config:
        """Pydantic配置"""
        extra = "forbid"  # 禁止额外字段
        validate_assignment = True  # 赋值时验证
    
    @validator('sources')
    def validate_unique_source_names(cls, v):
        """验证数据源名称唯一性"""
        names = [source.name for source in v]
        if len(names) != len(set(names)):
            raise ValueError('数据源名称必须唯一')
        return v
    
    @validator('proxy_list', each_item=True)
    def validate_proxy_url(cls, v):
        """验证代理URL格式"""
        # 简单验证代理格式：http://host:port 或 https://host:port
        pattern = r'^https?://[a-zA-Z0-9.-]+:\d+$'
        if not re.match(pattern, v):
            raise ValueError(f'无效的代理URL格式: {v}')
        return v
    
    @root_validator
    def validate_mock_data_settings(cls, values):
        """验证模拟数据设置"""
        use_mock = values.get('use_mock_data', False)
        mock_count = values.get('mock_data_count', 0)
        
        if use_mock and mock_count == 0:
            raise ValueError('使用模拟数据时，mock_data_count 必须大于0')
        
        if not use_mock and mock_count > 0:
            # 如果有真实数据源，但 mock_count > 0，给出警告但不阻止
            print('警告: 未使用模拟数据但设置了 mock_data_count > 0')
        
        return values
    
    def to_crawler_config(self) -> CrawlerConfig:
        """转换为 CrawlerConfig 对象"""
        return CrawlerConfig(
            enabled=self.enabled,
            use_mock_data=self.use_mock_data,
            mock_data_count=self.mock_data_count,
            sources=[source.dict() for source in self.sources],
            request_timeout=self.request_timeout,
            max_retries=self.max_retries,
            rate_limit_delay=self.rate_limit_delay,
            user_agent=self.user_agent,
            max_concurrent=self.max_concurrent,
            cache_enabled=self.cache_enabled,
            cache_ttl=self.cache_ttl,
            proxy_enabled=self.proxy_enabled,
            proxy_list=self.proxy_list,
        )