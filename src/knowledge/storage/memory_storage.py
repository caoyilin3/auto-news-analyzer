"""
内存存储实现
基于Python内置数据结构的快速存储后端
"""

import threading
import time
import pickle
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
from .base_storage import (
    BaseStorage, StorageConfig, StorageRecord, StorageQuery, 
    StorageResult, StorageOperation, StorageError
)

@dataclass
class MemoryStorageConfig(StorageConfig):
    """内存存储配置"""
    max_size: int = 1000000  # 最大记录数
    auto_cleanup: bool = True  # 自动清理过期记录
    cleanup_interval_seconds: int = 300  # 清理间隔（秒）
    ttl_seconds: Optional[int] = None  # 记录生存时间（秒）
    lru_enabled: bool = True  # 启用LRU缓存淘汰
    compression_enabled: bool = False  # 内存压缩
    indexing_enabled: bool = True  # 启用索引

class MemoryStorage(BaseStorage):
    """内存存储实现"""
    
    def __init__(self, config: MemoryStorageConfig):
        super().__init__(config)
        self.config = config
        
        # 数据存储
        self._data: Dict[str, StorageRecord] = {}
        
        # 索引
        self._indexes: Dict[str, Dict[Any, Set[str]]] = defaultdict(lambda: defaultdict(set))
        
        # LRU缓存
        self._access_times: Dict[str, float] = {}
        self._lru_order = OrderedDict()
        
        # 分区支持
        self._partitions: Dict[str, Set[str]] = defaultdict(set)
        
        # 锁
        self._lock = threading.RLock()
        
        # 清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_running = False
        
        # 统计
        self._total_size_bytes = 0
    
    def initialize(self) -> bool:
        """初始化内存存储"""
        try:
            with self._lock:
                # 初始化索引
                self._create_default_indexes()
                
                # 启动清理线程
                if self.config.auto_cleanup:
                    self._start_cleanup_thread()
                
                self.initialized = True
                return True
        except Exception as e:
            raise StorageError(
                f"Failed to initialize memory storage: {e}",
                StorageOperation.CREATE,
                "INIT_ERROR"
            )
    
    def _create_default_indexes(self):
        """创建默认索引"""
        # 创建时间索引
        self._indexes["created_at"] = defaultdict(set)
        self._indexes["updated_at"] = defaultdict(set)
        
        # 创建分区索引
        if self.config.partition_enabled:
            self._indexes["partition_key"] = defaultdict(set)
    
    def _start_cleanup_thread(self):
        """启动清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True,
            name="MemoryStorageCleanup"
        )
        self._cleanup_thread.start()
    
    def _stop_cleanup_thread(self):
        """停止清理线程"""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
    
    def _cleanup_worker(self):
        """清理工作线程"""
        while self._cleanup_running:
            try:
                with self._lock:
                    self._perform_cleanup()
            except Exception as e:
                print(f"Cleanup error: {e}")
            
            # 休眠指定间隔
            time.sleep(self.config.cleanup_interval_seconds)
    
    def _perform_cleanup(self):
        """执行清理"""
        current_time = time.time()
        records_to_remove = []
        
        # 检查TTL过期
        if self.config.ttl_seconds:
            for record_id, record in self._data.items():
                record_age = current_time - record.created_at.timestamp()
                if record_age > self.config.ttl_seconds:
                    records_to_remove.append(record_id)
        
        # 检查LRU淘汰
        if self.config.lru_enabled and len(self._data) > self.config.max_size:
            # 按访问时间排序，移除最旧的记录
            sorted_records = sorted(
                self._access_times.items(),
                key=lambda x: x[1]
            )
            
            excess_count = len(self._data) - self.config.max_size
            for i in range(excess_count):
                if i < len(sorted_records):
                    record_id = sorted_records[i][0]
                    records_to_remove.append(record_id)
        
        # 移除记录
        for record_id in records_to_remove:
            self._remove_record(record_id)
        
        if records_to_remove:
            print(f"Cleaned up {len(records_to_remove)} records")
    
    def create(self, record: StorageRecord) -> StorageResult:
        """创建记录"""
        start_time = time.time()
        
        try:
            # 验证记录
            is_valid, error_msg = self._validate_record(record)
            if not is_valid:
                raise StorageError(error_msg, StorageOperation.CREATE)
            
            with self._lock:
                # 检查记录是否存在
                if record.id in self._data:
                    raise StorageError(
                        f"Record {record.id} already exists",
                        StorageOperation.CREATE,
                        "DUPLICATE_RECORD"
                    )
                
                # 设置存储ID
                record.storage_id = f"memory_{record.id}"
                
                # 存储记录
                self._data[record.id] = record
                
                # 更新索引
                self._update_indexes(record, is_new=True)
                
                # 更新LRU
                if self.config.lru_enabled:
                    self._update_access_time(record.id)
                
                # 添加到分区
                if record.partition_key:
                    self._partitions[record.partition_key].add(record.id)
                
                # 更新统计
                self.statistics["total_records"] += 1
                self._total_size_bytes += self._calculate_size(record)
                
                # 检查容量
                if len(self._data) > self.config.max_size:
                    self._perform_cleanup()
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.CREATE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.CREATE,
                    data=record,
                    metadata={
                        "record_id": record.id,
                        "size_bytes": self._calculate_size(record),
                        "execution_time_ms": execution_time
                    }
                )
                
        except StorageError as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise e
        except Exception as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise StorageError(
                f"Failed to create record: {e}",
                StorageOperation.CREATE,
                "CREATE_ERROR"
            )
    
    def read(self, record_id: str) -> StorageResult:
        """读取记录"""
        start_time = time.time()
        
        try:
            with self._lock:
                if record_id not in self._data:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.READ,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 获取记录
                record = self._data[record_id]
                
                # 更新访问时间
                if self.config.lru_enabled:
                    self._update_access_time(record_id)
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.READ, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.READ,
                    data=record,
                    metadata={
                        "record_id": record_id,
                        "execution_time_ms": execution_time
                    }
                )
                
        except Exception as e:
            self._record_operation(StorageOperation.READ, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def update(self, record_id: str, data: Dict[str, Any], 
              metadata: Optional[Dict[str, Any]] = None) -> StorageResult:
        """更新记录"""
        start_time = time.time()
        
        try:
            with self._lock:
                if record_id not in self._data:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.UPDATE,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 获取原记录
                old_record = self._data[record_id]
                
                # 创建新记录
                new_metadata = old_record.metadata.copy()
                if metadata:
                    new_metadata.update(metadata)
                
                new_record = StorageRecord(
                    id=record_id,
                    data=data,
                    metadata=new_metadata,
                    version=old_record.version + 1,
                    created_at=old_record.created_at,
                    updated_at=datetime.now(),
                    storage_id=old_record.storage_id,
                    partition_key=old_record.partition_key
                )
                
                # 验证新记录
                is_valid, error_msg = self._validate_record(new_record)
                if not is_valid:
                    raise StorageError(error_msg, StorageOperation.UPDATE)
                
                # 更新索引（先删除旧索引，再添加新索引）
                self._remove_from_indexes(old_record)
                self._update_indexes(new_record, is_new=False)
                
                # 存储新记录
                self._data[record_id] = new_record
                
                # 更新访问时间
                if self.config.lru_enabled:
                    self._update_access_time(record_id)
                
                # 更新统计
                old_size = self._calculate_size(old_record)
                new_size = self._calculate_size(new_record)
                self._total_size_bytes += (new_size - old_size)
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.UPDATE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.UPDATE,
                    data=new_record,
                    metadata={
                        "record_id": record_id,
                        "old_version": old_record.version,
                        "new_version": new_record.version,
                        "execution_time_ms": execution_time
                    }
                )
                
        except StorageError as e:
            self._record_operation(StorageOperation.UPDATE, False)
            raise e
        except Exception as e:
            self._record_operation(StorageOperation.UPDATE, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def delete(self, record_id: str) -> StorageResult:
        """删除记录"""
        start_time = time.time()
        
        try:
            with self._lock:
                if record_id not in self._data:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.DELETE,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 获取记录
                record = self._data[record_id]
                
                # 从索引中移除
                self._remove_from_indexes(record)
                
                # 从分区中移除
                if record.partition_key and record.partition_key in self._partitions:
                    self._partitions[record.partition_key].discard(record_id)
                
                # 从数据中移除
                del self._data[record_id]
                
                # 从LRU中移除
                if record_id in self._access_times:
                    del self._access_times[record_id]
                if record_id in self._lru_order:
                    del self._lru_order[record_id]
                
                # 更新统计
                self.statistics["total_records"] -= 1
                self._total_size_bytes -= self._calculate_size(record)
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.DELETE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.DELETE,
                    data={"record_id": record_id},
                    metadata={
                        "record_id": record_id,
                        "execution_time_ms": execution_time
                    }
                )
                
        except Exception as e:
            self._record_operation(StorageOperation.DELETE, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def search(self, query: StorageQuery) -> StorageResult:
        """搜索记录"""
        start_time = time.time()
        
        try:
            with self._lock:
                # 应用过滤器
                candidate_ids = self._apply_filters(query.filters)
                
                # 获取记录
                records = []
                for record_id in candidate_ids:
                    if record_id in self._data:
                        records.append(self._data[record_id])
                
                # 应用排序
                if query.sort_by:
                    records = self._apply_sorting(records, query.sort_by)
                
                # 应用分页
                if query.offset > 0:
                    records = records[query.offset:]
                if query.limit:
                    records = records[:query.limit]
                
                # 应用投影
                if query.projections:
                    records = self._apply_projections(records, query.projections)
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.SEARCH, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.SEARCH,
                    data=records,
                    metadata={
                        "total_matched": len(candidate_ids),
                        "returned": len(records),
                        "execution_time_ms": execution_time
                    }
                )
                
        except Exception as e:
            self._record_operation(StorageOperation.SEARCH, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _apply_filters(self, filters: Dict[str, Any]) -> Set[str]:
        """应用过滤器"""
        if not filters:
            # 返回所有记录ID
            return set(self._data.keys())
        
        # 收集所有匹配的记录ID
        matched_ids = None
        
        for field_name, filter_value in filters.items():
            field_matches = self._apply_field_filter(field_name, filter_value)
            
            if matched_ids is None:
                matched_ids = field_matches
            else:
                # AND逻辑：取交集
                matched_ids &= field_matches
        
        return matched_ids or set()
    
    def _apply_field_filter(self, field_name: str, filter_value: Any) -> Set[str]:
        """应用字段过滤器"""
        if field_name in self._indexes:
            # 使用索引
            if isinstance(filter_value, dict):
                # 复杂查询操作符
                return self._apply_complex_filter(field_name, filter_value)
            else:
                # 精确匹配
                return self._indexes[field_name].get(filter_value, set()).copy()
        else:
            # 全表扫描
            return self._scan_for_field(field_name, filter_value)
    
    def _apply_complex_filter(self, field_name: str, filter_ops: Dict[str, Any]) -> Set[str]:
        """应用复杂过滤器"""
        matched_ids = set()
        
        for op, value in filter_ops.items():
            if op == "$eq":
                # 等于
                ids = self._indexes[field_name].get(value, set())
                matched_ids.update(ids)
            elif op == "$ne":
                # 不等于
                all_ids = set(self._data.keys())
                eq_ids = self._indexes[field_name].get(value, set())
                matched_ids.update(all_ids - eq_ids)
            elif op == "$in":
                # 在列表中
                if isinstance(value, list):
                    for item in value:
                        ids = self._indexes[field_name].get(item, set())
                        matched_ids.update(ids)
            elif op == "$gt":
                # 大于（只对可排序字段有效）
                if field_name in ["created_at", "updated_at"]:
                    for key, ids in self._indexes[field_name].items():
                        if key > value:
                            matched_ids.update(ids)
            elif op == "$lt":
                # 小于
                if field_name in ["created_at", "updated_at"]:
                    for key, ids in self._indexes[field_name].items():
                        if key < value:
                            matched_ids.update(ids)
        
        return matched_ids
    
    def _scan_for_field(self, field_name: str, filter_value: Any) -> Set[str]:
        """扫描字段值"""
        matched_ids = set()
        
        for record_id, record in self._data.items():
            # 检查数据字段
            if field_name in record.data:
                if self._match_value(record.data[field_name], filter_value):
                    matched_ids.add(record_id)
            
            # 检查元数据字段
            if field_name in record.metadata:
                if self._match_value(record.metadata[field_name], filter_value):
                    matched_ids.add(record_id)
        
        return matched_ids
    
    def _match_value(self, actual_value: Any, filter_value: Any) -> bool:
        """匹配值"""
        if isinstance(filter_value, dict):
            # 复杂匹配
            for op, op_value in filter_value.items():
                if op == "$eq":
                    return actual_value == op_value
                elif op == "$ne":
                    return actual_value != op_value
                elif op == "$in":
                    return actual_value in op_value if isinstance(op_value, list) else False
                elif op == "$regex":
                    import re
                    return bool(re.search(op_value, str(actual_value)))
            return False
        else:
            # 简单匹配
            return actual_value == filter_value
    
    def _apply_sorting(self, records: List[StorageRecord], sort_by: List[Tuple[str, str]]) -> List[StorageRecord]:
        """应用排序"""
        if not records or not sort_by:
            return records
        
        def sort_key(record: StorageRecord):
            key = []
            for field_name, direction in sort_by:
                # 获取字段值
                value = None
                if field_name in record.data:
                    value = record.data[field_name]
                elif field_name in record.metadata:
                    value = record.metadata[field_name]
                elif hasattr(record, field_name):
                    value = getattr(record, field_name)
                
                # 处理None值
                if value is None:
                    value = "" if direction == "asc" else "ZZZZZZZZZZ"
                
                # 根据排序方向调整
                if direction == "desc":
                    # 对于降序，使用负值或反转比较
                    if isinstance(value, (int, float)):
                        value = -value
                    else:
                        # 对于字符串，我们需要反转排序
                        value = str(value)
                
                key.append(value)
            return tuple(key)
        
        return sorted(records, key=sort_key)
    
    def _apply_projections(self, records: List[StorageRecord], projections: List[str]) -> List[Dict[str, Any]]:
        """应用投影"""
        projected_records = []
        
        for record in records:
            projected = {}
            for field in projections:
                if field == "id":
                    projected["id"] = record.id
                elif field in record.data:
                    projected[field] = record.data[field]
                elif field in record.metadata:
                    projected[field] = record.metadata[field]
                elif hasattr(record, field):
                    projected[field] = getattr(record, field)
            
            projected_records.append(projected)
        
        return projected_records
    
    def _update_indexes(self, record: StorageRecord, is_new: bool = True):
        """更新索引"""
        if not self.config.indexing_enabled:
            return
        
        # 索引数据字段
        for field_name, field_value in record.data.items():
            if isinstance(field_value, (str, int, float, bool, datetime)):
                self._indexes[field_name][field_value].add(record.id)
        
        # 索引元数据字段
        for field_name, field_value in record.metadata.items():
            if isinstance(field_value, (str, int, float, bool, datetime)):
                self._indexes[field_name][field_value].add(record.id)
        
        # 索引特殊字段
        self._indexes["created_at"][record.created_at].add(record.id)
        self._indexes["updated_at"][record.updated_at].add(record.id)
        
        if record.partition_key:
            self._indexes["partition_key"][record.partition_key].add(record.id)
    
    def _remove_from_indexes(self, record: StorageRecord):
        """从索引中移除"""
        if not self.config.indexing_enabled:
            return
        
        # 从数据字段索引中移除
        for field_name, field_value in record.data.items():
            if field_name in self._indexes and field_value in self._indexes[field_name]:
                self._indexes[field_name][field_value].discard(record.id)
                # 如果集合为空，删除键
                if not self._indexes[field_name][field_value]:
                    del self._indexes[field_name][field_value]
        
        # 从元数据字段索引中移除
        for field_name, field_value in record.metadata.items():
            if field_name in self._indexes and field_value in self._indexes[field_name]:
                self._indexes[field_name][field_value].discard(record.id)
                if not self._indexes[field_name][field_value]:
                    del self._indexes[field_name][field_value]
        
        # 从特殊字段索引中移除
        for field_name in ["created_at", "updated_at", "partition_key"]:
            if field_name in self._indexes:
                field_value = getattr(record, field_name, None)
                if field_value and field_value in self._indexes[field_name]:
                    self._indexes[field_name][field_value].discard(record.id)
                    if not self._indexes[field_name][field_value]:
                        del self._indexes[field_name][field_value]
    
    def _update_access_time(self, record_id: str):
        """更新访问时间"""
        current_time = time.time()
        self._access_times[record_id] = current_time
        
        # 更新LRU顺序
        if record_id in self._lru_order:
            del self._lru_order[record_id]
        self._lru_order[record_id] = current_time
    
    def _remove_record(self, record_id: str):
        """移除记录（内部使用）"""
        if record_id in self._data:
            record = self._data[record_id]
            self._remove_from_indexes(record)
            
            if record.partition_key and record.partition_key in self._partitions:
                self._partitions[record.partition_key].discard(record_id)
            
            del self._data[record_id]
            
            if record_id in self._access_times:
                del self._access_times[record_id]
            if record_id in self._lru_order:
                del self._lru_order[record_id]
    
    def clear(self):
        """清空所有数据"""
        with self._lock:
            self._data.clear()
            self._indexes.clear()
            self._access_times.clear()
            self._lru_order.clear()
            self._partitions.clear()
            self.statistics["total_records"] = 0
            self._total_size_bytes = 0
    
    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计"""
        with self._lock:
            stats = {}
            for index_name, index_data in self._indexes.items():
                stats[index_name] = {
                    "unique_values": len(index_data),
                    "total_entries": sum(len(ids) for ids in index_data.values())
                }
            return stats
    
    def create_index(self, field_name: str):
        """创建索引"""
        with self._lock:
            if field_name not in self._indexes:
                self._indexes[field_name] = defaultdict(set)
                
                # 为现有数据建立索引
                for record_id, record in self._data.items():
                    value = None
                    if field_name in record.data:
                        value = record.data[field_name]
                    elif field_name in record.metadata:
                        value = record.metadata[field_name]
                    
                    if value is not None:
                        self._indexes[field_name][value].add(record_id)
    
    def drop_index(self, field_name: str):
        """删除索引"""
        with self._lock:
            if field_name in self._indexes:
                del self._indexes[field_name]
    
    def get_partition_stats(self) -> Dict[str, Any]:
        """获取分区统计"""
        with self._lock:
            stats = {}
            for partition_key, record_ids in self._partitions.items():
                stats[partition_key] = {
                    "record_count": len(record_ids),
                    "size_bytes": sum(self._calculate_size(self._data[rid]) for rid in record_ids if rid in self._data)
                }
            return stats
    
    def close(self):
        """关闭存储"""
        self._stop_cleanup_thread()
        self.initialized = False