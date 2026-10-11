"""
基础存储接口
定义所有存储后端的统一接口和抽象基类
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple, Iterator
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid
import json
import hashlib

class StorageBackend(Enum):
    """存储后端类型枚举"""
    MEMORY = "memory"
    SQL = "sql"
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"

class StorageOperation(Enum):
    """存储操作类型枚举"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    SEARCH = "search"
    BATCH = "batch"
    TRANSACTION = "transaction"

@dataclass
class StorageRecord:
    """存储记录"""
    id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 版本控制
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 存储信息
    storage_id: Optional[str] = None
    partition_key: Optional[str] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        record_dict = asdict(self)
        # 处理datetime对象
        for field_name in ['created_at', 'updated_at']:
            if isinstance(record_dict[field_name], datetime):
                record_dict[field_name] = record_dict[field_name].isoformat()
        return record_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageRecord':
        """从字典创建"""
        # 处理datetime字符串
        for field_name in ['created_at', 'updated_at']:
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return cls(**data)
    
    def calculate_hash(self) -> str:
        """计算数据哈希"""
        data_str = json.dumps(self.data, sort_keys=True, default=str)
        metadata_str = json.dumps(self.metadata, sort_keys=True, default=str)
        combined = f"{data_str}:{metadata_str}:{self.version}"
        return hashlib.sha256(combined.encode()).hexdigest()

@dataclass
class StorageQuery:
    """存储查询"""
    filters: Dict[str, Any] = field(default_factory=dict)
    sort_by: List[Tuple[str, str]] = field(default_factory=list)  # [(field, direction)]
    limit: Optional[int] = None
    offset: int = 0
    include_metadata: bool = True
    projections: List[str] = field(default_factory=list)  # 指定返回字段
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageQuery':
        """从字典创建"""
        return cls(**data)

@dataclass
class StorageResult:
    """存储操作结果"""
    success: bool
    operation: StorageOperation
    data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result_dict = asdict(self)
        if 'operation' in result_dict and isinstance(result_dict['operation'], StorageOperation):
            result_dict['operation'] = result_dict['operation'].value
        return result_dict

@dataclass
class StorageConfig:
    """存储配置"""
    backend: StorageBackend
    connection_string: Optional[str] = None
    connection_params: Dict[str, Any] = field(default_factory=dict)
    auto_create_tables: bool = True
    auto_index: bool = True
    cache_enabled: bool = True
    cache_size: int = 10000
    compression_enabled: bool = False
    encryption_enabled: bool = False
    encryption_key: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        config_dict = asdict(self)
        if 'backend' in config_dict and isinstance(config_dict['backend'], StorageBackend):
            config_dict['backend'] = config_dict['backend'].value
        return config_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageConfig':
        """从字典创建"""
        if 'backend' in data and isinstance(data['backend'], str):
            data['backend'] = StorageBackend(data['backend'])
        return cls(**data)

class StorageError(Exception):
    """存储异常"""
    def __init__(self, message: str, operation: StorageOperation, error_code: str = "STORAGE_ERROR"):
        self.message = message
        self.operation = operation
        self.error_code = error_code
        super().__init__(self.message)
    
    def __str__(self):
        return f"StorageError[{self.error_code}]: {self.message} (operation: {self.operation.value})"

class BaseStorage(ABC):
    """存储基类"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.backend = config.backend
        self.initialized = False
        self.statistics = {
            "operations": {op.value: 0 for op in StorageOperation},
            "total_records": 0,
            "total_size_bytes": 0,
            "last_operation": None,
            "errors": 0
        }
    
    @abstractmethod
    def initialize(self) -> bool:
        """初始化存储"""
        pass
    
    @abstractmethod
    def create(self, record: StorageRecord) -> StorageResult:
        """创建记录"""
        pass
    
    @abstractmethod
    def read(self, record_id: str) -> StorageResult:
        """读取记录"""
        pass
    
    @abstractmethod
    def update(self, record_id: str, data: Dict[str, Any], 
              metadata: Optional[Dict[str, Any]] = None) -> StorageResult:
        """更新记录"""
        pass
    
    @abstractmethod
    def delete(self, record_id: str) -> StorageResult:
        """删除记录"""
        pass
    
    @abstractmethod
    def search(self, query: StorageQuery) -> StorageResult:
        """搜索记录"""
        pass
    
    def batch_create(self, records: List[StorageRecord]) -> StorageResult:
        """批量创建记录"""
        results = []
        for record in records:
            result = self.create(record)
            results.append(result)
        
        success = all(r.success for r in results)
        return StorageResult(
            success=success,
            operation=StorageOperation.BATCH,
            data=results,
            metadata={"count": len(records), "success_count": sum(1 for r in results if r.success)}
        )
    
    def batch_update(self, updates: List[Tuple[str, Dict[str, Any]]]) -> StorageResult:
        """批量更新记录"""
        results = []
        for record_id, data in updates:
            result = self.update(record_id, data)
            results.append(result)
        
        success = all(r.success for r in results)
        return StorageResult(
            success=success,
            operation=StorageOperation.BATCH,
            data=results,
            metadata={"count": len(updates), "success_count": sum(1 for r in results if r.success)}
        )
    
    def batch_delete(self, record_ids: List[str]) -> StorageResult:
        """批量删除记录"""
        results = []
        for record_id in record_ids:
            result = self.delete(record_id)
            results.append(result)
        
        success = all(r.success for r in results)
        return StorageResult(
            success=success,
            operation=StorageOperation.BATCH,
            data=results,
            metadata={"count": len(record_ids), "success_count": sum(1 for r in results if r.success)}
        )
    
    def exists(self, record_id: str) -> bool:
        """检查记录是否存在"""
        result = self.read(record_id)
        return result.success and result.data is not None
    
    def count(self, query: Optional[StorageQuery] = None) -> int:
        """统计记录数量"""
        if query is None:
            query = StorageQuery()
        
        result = self.search(query)
        if result.success and isinstance(result.data, list):
            return len(result.data)
        return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.statistics.copy()
    
    def reset_statistics(self):
        """重置统计信息"""
        self.statistics = {
            "operations": {op.value: 0 for op in StorageOperation},
            "total_records": self.count(),
            "total_size_bytes": 0,
            "last_operation": None,
            "errors": 0
        }
    
    def _record_operation(self, operation: StorageOperation, success: bool = True):
        """记录操作"""
        self.statistics["operations"][operation.value] += 1
        self.statistics["last_operation"] = {
            "operation": operation.value,
            "timestamp": datetime.now().isoformat(),
            "success": success
        }
        
        if not success:
            self.statistics["errors"] += 1
    
    def _validate_record(self, record: StorageRecord) -> Tuple[bool, str]:
        """验证记录"""
        if not record.id:
            return False, "Record ID is required"
        
        if not isinstance(record.data, dict):
            return False, "Record data must be a dictionary"
        
        if not isinstance(record.metadata, dict):
            return False, "Record metadata must be a dictionary"
        
        return True, ""
    
    def _calculate_size(self, record: StorageRecord) -> int:
        """计算记录大小（字节）"""
        try:
            record_dict = record.to_dict()
            record_json = json.dumps(record_dict, default=str)
            return len(record_json.encode('utf-8'))
        except:
            return 0
    
    def close(self):
        """关闭存储连接"""
        pass
    
    def __enter__(self):
        """上下文管理器入口"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()