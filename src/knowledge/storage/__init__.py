"""
存储后端模块
提供多种存储引擎：内存存储、SQL数据库、向量存储、图数据库和混合存储
"""

from .base_storage import (
    BaseStorage, StorageBackend, StorageConfig, StorageRecord, 
    StorageQuery, StorageResult, StorageOperation, StorageError
)
from .memory_storage import MemoryStorage, MemoryStorageConfig
from .sql_storage import SQLStorage, SQLStorageConfig, DatabaseType
from .vector_storage import VectorStorage, VectorStorageConfig, VectorIndexType
from .graph_storage import GraphStorage, GraphStorageConfig, GraphDatabaseType
from .hybrid_storage import HybridStorage, HybridStorageConfig, StorageStrategy

__all__ = [
    # 基础接口
    'BaseStorage', 'StorageBackend', 'StorageConfig', 'StorageRecord',
    'StorageQuery', 'StorageResult', 'StorageOperation', 'StorageError',
    
    # 内存存储
    'MemoryStorage', 'MemoryStorageConfig',
    
    # SQL存储
    'SQLStorage', 'SQLStorageConfig', 'DatabaseType',
    
    # 向量存储
    'VectorStorage', 'VectorStorageConfig', 'VectorIndexType',
    
    # 图存储
    'GraphStorage', 'GraphStorageConfig', 'GraphDatabaseType',
    
    # 混合存储
    'HybridStorage', 'HybridStorageConfig', 'StorageStrategy'
]