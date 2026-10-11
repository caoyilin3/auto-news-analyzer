"""
基础配置类定义
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


@dataclass
class SystemConfig:
    """系统基础配置"""
    name: str = "AutoNewsAnalyzer"
    version: str = "2.0.0"
    mode: str = "development"  # development, production, testing
    debug: bool = False
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    data_path: str = "./data"
    max_concurrent_tasks: int = 10
    enable_health_check: bool = True


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    enabled: bool = True
    use_mock_data: bool = True
    mock_data_count: int = 5
    sources: List[Dict[str, Any]] = field(default_factory=list)
    request_timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    user_agent: str = "Mozilla/5.0 (compatible; AutoNewsAnalyzer/2.0; +http://autonews.dev/bot)"


@dataclass
class CredibilityConfig:
    """可信度评估配置"""
    enabled: bool = True
    min_score: float = 0.7
    auto_learn: bool = True
    weights: Dict[str, float] = field(default_factory=lambda: {
        "source": 0.35,
        "freshness": 0.20,
        "author": 0.15,
        "content": 0.20,
        "url": 0.10,
    })
    thresholds: Dict[str, float] = field(default_factory=lambda: {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.0,
    })


@dataclass
class KnowledgeConfig:
    """知识管理配置"""
    enabled: bool = True
    extractors: List[str] = field(default_factory=lambda: ["financial", "technical", "market"])
    graph_storage: str = "memory"  # memory, postgres, neo4j, elasticsearch
    vector_storage: str = "memory"  # memory, faiss, elasticsearch
    embedding_model: str = "all-MiniLM-L6-v2"
    conflict_resolution: str = "credibility"  # credibility, timestamp, evidence
    enable_inference: bool = True


@dataclass
class EvolutionConfig:
    """进化配置"""
    enabled: bool = True
    learning_rate: float = 0.01
    meta_cognitive: bool = True
    goal_setting: bool = True
    performance_threshold: float = 0.8
    adaptation_speed: float = 0.1


@dataclass
class MemoryConfig:
    """记忆配置"""
    enabled: bool = True
    retention_policies: Dict[str, int] = field(default_factory=lambda: {
        "breaking_news": 7,
        "research": 180,
        "fundamental": 0,  # 0表示永久保留
    })
    max_storage_gb: int = 100
    auto_cleanup: bool = True
    backup_enabled: bool = True


@dataclass
class APIConfig:
    """API配置"""
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 4
    cors_enabled: bool = True
    rate_limit: int = 100  # 每分钟请求数
    enable_docs: bool = True
    docs_path: str = "/docs"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    postgres: Dict[str, Any] = field(default_factory=lambda: {
        "host": "localhost",
        "port": 5432,
        "database": "autonews",
        "user": "postgres",
        "password": "postgres",
        "pool_size": 10,
        "max_overflow": 20,
    })
    redis: Dict[str, Any] = field(default_factory=lambda: {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": "",
        "decode_responses": True,
    })
    elasticsearch: Dict[str, Any] = field(default_factory=lambda: {
        "hosts": ["http://localhost:9200"],
        "username": "",
        "password": "",
    })


@dataclass
class MonitoringConfig:
    """监控配置"""
    enabled: bool = True
    prometheus_port: int = 9090
    health_check_interval: int = 30  # 秒
    metrics_enabled: bool = True
    logging_enabled: bool = True
    alerting_enabled: bool = False
    alert_rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TestingConfig:
    """测试配置"""
    enabled: bool = True
    mock_data_enabled: bool = True
    test_timeout: int = 30  # 秒
    coverage_enabled: bool = True
    integration_tests: bool = True
    performance_tests: bool = False


class Config:
    """主配置类"""
    
    def __init__(
        self,
        system: SystemConfig = None,
        crawler: CrawlerConfig = None,
        credibility: CredibilityConfig = None,
        knowledge: KnowledgeConfig = None,
        evolution: EvolutionConfig = None,
        memory: MemoryConfig = None,
        api: APIConfig = None,
        database: DatabaseConfig = None,
        monitoring: MonitoringConfig = None,
        testing: TestingConfig = None,
        custom: Dict[str, Any] = None,
    ):
        self.system = system or SystemConfig()
        self.crawler = crawler or CrawlerConfig()
        self.credibility = credibility or CredibilityConfig()
        self.knowledge = knowledge or KnowledgeConfig()
        self.evolution = evolution or EvolutionConfig()
        self.memory = memory or MemoryConfig()
        self.api = api or APIConfig()
        self.database = database or DatabaseConfig()
        self.monitoring = monitoring or MonitoringConfig()
        self.testing = testing or TestingConfig()
        self.custom = custom or {}
        self._loaded_at = datetime.now()
        self._source_file: Optional[Path] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """从字典创建配置"""
        # 提取各个部分的配置
        system_data = data.get("system", {})
        crawler_data = data.get("crawler", {})
        credibility_data = data.get("credibility", {})
        knowledge_data = data.get("knowledge", {})
        evolution_data = data.get("evolution", {})
        memory_data = data.get("memory", {})
        api_data = data.get("api", {})
        database_data = data.get("database", {})
        monitoring_data = data.get("monitoring", {})
        testing_data = data.get("testing", {})
        custom_data = data.get("custom", {})
        
        # 创建配置对象
        return cls(
            system=SystemConfig(**system_data),
            crawler=CrawlerConfig(**crawler_data),
            credibility=CredibilityConfig(**credibility_data),
            knowledge=KnowledgeConfig(**knowledge_data),
            evolution=EvolutionConfig(**evolution_data),
            memory=MemoryConfig(**memory_data),
            api=APIConfig(**api_data),
            database=DatabaseConfig(**database_data),
            monitoring=MonitoringConfig(**monitoring_data),
            testing=TestingConfig(**testing_data),
            custom=custom_data,
        )
    
    @classmethod
    def from_yaml(cls, filepath: Union[str, Path]) -> 'Config':
        """从YAML文件加载配置"""
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        config = cls.from_dict(data)
        config._source_file = filepath
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "system": asdict(self.system),
            "crawler": asdict(self.crawler),
            "credibility": asdict(self.credibility),
            "knowledge": asdict(self.knowledge),
            "evolution": asdict(self.evolution),
            "memory": asdict(self.memory),
            "api": asdict(self.api),
            "database": asdict(self.database),
            "monitoring": asdict(self.monitoring),
            "testing": asdict(self.testing),
            "custom": self.custom,
            "metadata": {
                "loaded_at": self._loaded_at.isoformat(),
                "source_file": str(self._source_file) if self._source_file else None,
            }
        }
    
    def to_yaml(self, filepath: Union[str, Path] = None) -> str:
        """转换为YAML格式"""
        data = self.to_dict()
        yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        if filepath:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(yaml_str)
        
        return yaml_str
    
    def to_json(self) -> str:
        """转换为JSON格式"""
        data = self.to_dict()
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号分隔的路径）"""
        keys = key.split('.')
        value = self.to_dict()
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值（支持点号分隔的路径）"""
        keys = key.split('.')
        data = self.to_dict()
        current = data
        
        # 导航到目标位置
        for i, k in enumerate(keys[:-1]):
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # 设置值
        current[keys[-1]] = value
        
        # 重新加载配置
        self.__dict__.update(self.from_dict(data).__dict__)
    
    def merge(self, other: 'Config', overwrite: bool = True) -> 'Config':
        """合并另一个配置"""
        this_dict = self.to_dict()
        other_dict = other.to_dict()
        
        merged_dict = self._merge_dicts(this_dict, other_dict, overwrite)
        return self.from_dict(merged_dict)
    
    def _merge_dicts(self, dict1: Dict, dict2: Dict, overwrite: bool = True) -> Dict:
        """递归合并字典"""
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value, overwrite)
            elif overwrite or key not in result:
                result[key] = value
        
        return result
    
    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []
        
        # 验证系统配置
        if self.system.mode not in ["development", "production", "testing"]:
            errors.append(f"无效的系统模式: {self.system.mode}")
        
        if self.system.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            errors.append(f"无效的日志级别: {self.system.log_level}")
        
        # 验证可信度配置
        if not 0 <= self.credibility.min_score <= 1:
            errors.append(f"可信度最小分数必须在0-1之间: {self.credibility.min_score}")
        
        total_weight = sum(self.credibility.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            errors.append(f"可信度权重总和应为1.0，实际为: {total_weight}")
        
        # 验证知识配置
        if self.knowledge.graph_storage not in ["memory", "postgres", "neo4j", "elasticsearch"]:
            errors.append(f"无效的知识图谱存储: {self.knowledge.graph_storage}")
        
        # 验证API配置
        if not 0 < self.api.port < 65536:
            errors.append(f"无效的API端口: {self.api.port}")
        
        return errors
    
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        return len(self.validate()) == 0
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Config(system={self.system.name}, mode={self.system.mode}, loaded_at={self._loaded_at})"
    
    def __repr__(self) -> str:
        """详细表示"""
        return f"Config({self.to_dict()})"