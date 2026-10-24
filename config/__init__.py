"""
AutoNewsAnalyzer 配置中心
提供统一的配置管理和加载机制
"""

from pathlib import Path
from typing import Dict, Any, Optional

# 导入配置类
# 说明：.base 只依赖标准库 + pyyaml；schema/* 依赖 pydantic。二者都用 try 包裹，
# 这样即使只装了最小依赖（无 pydantic），config.loader 也能正常导入使用。
try:
    from .base import Config, SystemConfig, CredibilityConfig, KnowledgeConfig, EvolutionConfig
except Exception:  # pragma: no cover
    Config = SystemConfig = CredibilityConfig = KnowledgeConfig = EvolutionConfig = None

try:
    from .schema.crawler import CrawlerConfig
except Exception:  # pragma: no cover
    CrawlerConfig = None

try:
    from .schema.credibility import CredibilitySchema
except Exception:  # pragma: no cover
    CredibilitySchema = None

try:
    from .schema.knowledge import KnowledgeSchema
except Exception:  # pragma: no cover
    KnowledgeSchema = None

__version__ = "2.0.0"
__all__ = [
    "Config",
    "SystemConfig",
    "CrawlerConfig",
    "CredibilityConfig",
    "KnowledgeConfig",
    "EvolutionConfig",
    "CredibilitySchema",
    "KnowledgeSchema",
    "load_config",
    "get_config_path",
]


def load_config(env: str = "development") -> Config:
    """
    加载指定环境的配置
    
    Args:
        env: 环境名称，可选 "development", "production", "testing"
        
    Returns:
        Config: 配置对象
        
    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 环境参数无效
    """
    env = env.lower()
    if env not in ["development", "production", "testing"]:
        raise ValueError(f"无效的环境参数: {env}，必须是 development, production 或 testing")
    
    config_path = get_config_path(env)
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    return Config.from_yaml(config_path)


def get_config_path(env: str = "development") -> Path:
    """
    获取配置文件的路径
    
    Args:
        env: 环境名称
        
    Returns:
        Path: 配置文件路径
    """
    config_dir = Path(__file__).parent
    return config_dir / f"{env}.yaml"


def create_default_configs(overwrite: bool = False):
    """
    创建默认配置文件
    
    Args:
        overwrite: 是否覆盖已存在的文件
    """
    config_dir = Path(__file__).parent
    
    # 开发环境配置
    dev_config = Config(
        system=SystemConfig(
            name="AutoNewsAnalyzer",
            version="2.0.0",
            mode="development",
            debug=True,
        ),
        crawler=CrawlerConfig(
            enabled=True,
            use_mock_data=True,
            mock_data_count=5,
        ),
        credibility=CredibilityConfig(
            enabled=True,
            min_score=0.5,
            weights={
                "source": 0.35,
                "freshness": 0.20,
                "author": 0.15,
                "content": 0.20,
                "url": 0.10,
            },
        ),
        knowledge=KnowledgeConfig(
            enabled=True,
            extractors=["financial", "technical", "market"],
            graph_storage="memory",
        ),
        evolution=EvolutionConfig(
            enabled=True,
            learning_rate=0.01,
            meta_cognitive=True,
        ),
    )
    
    # 生产环境配置
    prod_config = Config(
        system=SystemConfig(
            name="AutoNewsAnalyzer",
            version="2.0.0",
            mode="production",
            debug=False,
        ),
        crawler=CrawlerConfig(
            enabled=True,
            use_mock_data=False,
            mock_data_count=0,
        ),
        credibility=CredibilityConfig(
            enabled=True,
            min_score=0.7,
            weights={
                "source": 0.35,
                "freshness": 0.20,
                "author": 0.15,
                "content": 0.20,
                "url": 0.10,
            },
        ),
        knowledge=KnowledgeConfig(
            enabled=True,
            extractors=["financial", "technical", "market", "sentiment"],
            graph_storage="postgres",
        ),
        evolution=EvolutionConfig(
            enabled=True,
            learning_rate=0.001,
            meta_cognitive=True,
        ),
    )
    
    # 测试环境配置
    test_config = Config(
        system=SystemConfig(
            name="AutoNewsAnalyzer",
            version="2.0.0",
            mode="testing",
            debug=True,
        ),
        crawler=CrawlerConfig(
            enabled=True,
            use_mock_data=True,
            mock_data_count=10,
        ),
        credibility=CredibilityConfig(
            enabled=True,
            min_score=0.3,
            weights={
                "source": 0.35,
                "freshness": 0.20,
                "author": 0.15,
                "content": 0.20,
                "url": 0.10,
            },
        ),
        knowledge=KnowledgeConfig(
            enabled=True,
            extractors=["financial"],
            graph_storage="memory",
        ),
        evolution=EvolutionConfig(
            enabled=False,
            learning_rate=0.0,
            meta_cognitive=False,
        ),
    )
    
    # 保存配置文件
    for env_name, config in [
        ("development", dev_config),
        ("production", prod_config),
        ("testing", test_config),
    ]:
        file_path = config_dir / f"{env_name}.yaml"
        
        if file_path.exists() and not overwrite:
            print(f"配置文件已存在: {file_path}")
            continue
        
        config.to_yaml(file_path)
        print(f"已创建配置文件: {file_path}")


if __name__ == "__main__":
    # 如果直接运行，创建默认配置文件
    create_default_configs()