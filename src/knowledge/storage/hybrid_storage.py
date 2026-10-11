"""
混合存储实现
结合多种存储后端，根据数据类型和访问模式自动选择最佳存储
"""

from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import threading
import json
import time

from .base_storage import (
    BaseStorage, StorageConfig, StorageRecord, StorageQuery,
    StorageResult, StorageOperation, StorageError, StorageBackend
)
from .memory_storage import MemoryStorage, MemoryStorageConfig
from .sql_storage import SQLStorage, SQLStorageConfig, DatabaseType
from .vector_storage import VectorStorage, VectorStorageConfig, VectorIndexType
from .graph_storage import GraphStorage, GraphStorageConfig, GraphDatabaseType

class StorageStrategy(Enum):
    """存储策略"""
    AUTO = "auto"              # 自动选择
    MEMORY_FIRST = "memory_first"  # 内存优先
    SQL_FIRST = "sql_first"        # SQL优先
    VECTOR_FIRST = "vector_first"  # 向量优先
    GRAPH_FIRST = "graph_first"    # 图优先
    COST_BASED = "cost_based"      # 基于成本

@dataclass
class HybridStorageConfig(StorageConfig):
    """混合存储配置"""
    # 存储后端配置
    memory_config: Optional[MemoryStorageConfig] = None
    sql_config: Optional[SQLStorageConfig] = None
    vector_config: Optional[VectorStorageConfig] = None
    graph_config: Optional[GraphStorageConfig] = None
    
    # 策略配置
    default_strategy: StorageStrategy = StorageStrategy.AUTO
    auto_migration: bool = True  # 自动迁移数据
    migration_threshold: float = 0.8  # 迁移阈值（使用率）
    
    # 缓存配置
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300  # 缓存生存时间
    cache_max_size: int = 10000
    
    # 监控配置
    monitor_performance: bool = True
    performance_window: int = 100  # 性能统计窗口大小

class HybridStorage(BaseStorage):
    """混合存储实现"""
    
    def __init__(self, config: HybridStorageConfig):
        super().__init__(config)
        self.config = config
        self.strategy = config.default_strategy
        
        # 存储后端
        self._memory_storage: Optional[MemoryStorage] = None
        self._sql_storage: Optional[SQLStorage] = None
        self._vector_storage: Optional[VectorStorage] = None
        self._graph_storage: Optional[GraphStorage] = None
        
        # 活跃后端列表
        self._active_backends: List[Tuple[StorageBackend, BaseStorage]] = []
        
        # 缓存
        self._cache: Dict[str, Tuple[StorageRecord, float]] = {}  # id -> (record, timestamp)
        
        # 路由规则
        self._routing_rules: Dict[str, StorageBackend] = {}
        
        # 性能统计
        self._performance_stats: Dict[StorageBackend, Dict[str, Any]] = {}
        self._operation_history: List[Dict[str, Any]] = []
        
        # 锁
        self._lock = threading.RLock()
        self._cache_lock = threading.RLock()
        
        # 迁移线程
        self._migration_thread: Optional[threading.Thread] = None
        self._migration_running = False
    
    def initialize(self) -> bool:
        """初始化混合存储"""
        try:
            with self._lock:
                # 初始化各个存储后端
                self._initialize_backends()
                
                # 初始化性能统计
                self._initialize_performance_stats()
                
                # 启动迁移线程
                if self.config.auto_migration:
                    self._start_migration_thread()
                
                self.initialized = True
                return True
                
        except Exception as e:
            raise StorageError(
                f"Failed to initialize hybrid storage: {e}",
                StorageOperation.CREATE,
                "INIT_ERROR"
            )
    
    def _initialize_backends(self):
        """初始化各个存储后端"""
        # 初始化内存存储
        if self.config.memory_config:
            try:
                self._memory_storage = MemoryStorage(self.config.memory_config)
                self._memory_storage.initialize()
                self._active_backends.append((StorageBackend.MEMORY, self._memory_storage))
                print("Memory storage initialized")
            except Exception as e:
                print(f"Failed to initialize memory storage: {e}")
        
        # 初始化SQL存储
        if self.config.sql_config:
            try:
                self._sql_storage = SQLStorage(self.config.sql_config)
                self._sql_storage.initialize()
                self._active_backends.append((StorageBackend.SQL, self._sql_storage))
                print("SQL storage initialized")
            except Exception as e:
                print(f"Failed to initialize SQL storage: {e}")
        
        # 初始化向量存储
        if self.config.vector_config:
            try:
                self._vector_storage = VectorStorage(self.config.vector_config)
                self._vector_storage.initialize()
                self._active_backends.append((StorageBackend.VECTOR, self._vector_storage))
                print("Vector storage initialized")
            except Exception as e:
                print(f"Failed to initialize vector storage: {e}")
        
        # 初始化图存储
        if self.config.graph_config:
            try:
                self._graph_storage = GraphStorage(self.config.graph_config)
                self._graph_storage.initialize()
                self._active_backends.append((StorageBackend.GRAPH, self._graph_storage))
                print("Graph storage initialized")
            except Exception as e:
                print(f"Failed to initialize graph storage: {e}")
        
        if not self._active_backends:
            raise StorageError(
                "No storage backends available",
                StorageOperation.CREATE,
                "NO_BACKENDS"
            )
    
    def _initialize_performance_stats(self):
        """初始化性能统计"""
        for backend, _ in self._active_backends:
            self._performance_stats[backend] = {
                "operations": {op.value: 0 for op in StorageOperation},
                "total_time_ms": 0.0,
                "avg_time_ms": 0.0,
                "success_rate": 1.0,
                "last_operation": None
            }
    
    def _start_migration_thread(self):
        """启动迁移线程"""
        if self._migration_thread and self._migration_thread.is_alive():
            return
        
        self._migration_running = True
        self._migration_thread = threading.Thread(
            target=self._migration_worker,
            daemon=True,
            name="HybridStorageMigration"
        )
        self._migration_thread.start()
    
    def _stop_migration_thread(self):
        """停止迁移线程"""
        self._migration_running = False
        if self._migration_thread:
            self._migration_thread.join(timeout=5.0)
    
    def _migration_worker(self):
        """迁移工作线程"""
        while self._migration_running:
            try:
                with self._lock:
                    self._perform_migration()
            except Exception as e:
                print(f"Migration error: {e}")
            
            # 每60秒检查一次
            time.sleep(60)
    
    def _perform_migration(self):
        """执行数据迁移"""
        # 简化的迁移逻辑
        # 在实际系统中，这里需要实现更复杂的数据迁移策略
        
        # 检查内存使用率
        if self._memory_storage and len(self._active_backends) > 1:
            memory_stats = self._memory_storage.get_statistics()
            memory_usage = memory_stats.get("total_records", 0) / self.config.memory_config.max_size
            
            if memory_usage > self.config.migration_threshold:
                print(f"Memory usage high ({memory_usage:.2%}), considering migration")
                
                # 这里可以添加具体的数据迁移逻辑
                # 例如：将不常访问的数据迁移到SQL存储
                
        print("Migration check completed")
    
    def create(self, record: StorageRecord) -> StorageResult:
        """创建记录"""
        import time
        start_time = time.time()
        
        try:
            with self._lock:
                # 验证记录
                is_valid, error_msg = self._validate_record(record)
                if not is_valid:
                    raise StorageError(error_msg, StorageOperation.CREATE)
                
                # 选择存储后端
                selected_backend = self._select_backend_for_create(record)
                
                if not selected_backend:
                    raise StorageError(
                        "No suitable storage backend found",
                        StorageOperation.CREATE,
                        "NO_BACKEND"
                    )
                
                # 执行创建操作
                result = selected_backend.create(record)
                
                # 更新性能统计
                execution_time = (time.time() - start_time) * 1000
                self._update_performance_stats(selected_backend, StorageOperation.CREATE, 
                                             execution_time, result.success)
                
                # 添加到缓存
                if result.success and self.config.cache_enabled:
                    self._add_to_cache(record)
                
                # 记录操作
                self._record_operation_history(StorageOperation.CREATE, record.id, 
                                             selected_backend, execution_time, result.success)
                
                # 更新操作统计
                self._record_operation(StorageOperation.CREATE, result.success)
                
                return result
                
        except StorageError as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise e
        except Exception as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise StorageError(
                f"Failed to create record in hybrid storage: {e}",
                StorageOperation.CREATE,
                "CREATE_ERROR"
            )
    
    def _select_backend_for_create(self, record: StorageRecord) -> Optional[BaseStorage]:
        """为创建操作选择存储后端"""
        # 检查路由规则
        record_type = self._get_record_type(record)
        if record_type in self._routing_rules:
            backend_type = self._routing_rules[record_type]
            return self._get_backend_by_type(backend_type)
        
        # 根据策略选择
        if self.strategy == StorageStrategy.AUTO:
            return self._select_backend_auto(record)
        elif self.strategy == StorageStrategy.MEMORY_FIRST:
            return self._memory_storage if self._memory_storage else self._select_backend_auto(record)
        elif self.strategy == StorageStrategy.SQL_FIRST:
            return self._sql_storage if self._sql_storage else self._select_backend_auto(record)
        elif self.strategy == StorageStrategy.VECTOR_FIRST:
            return self._vector_storage if self._vector_storage else self._select_backend_auto(record)
        elif self.strategy == StorageStrategy.GRAPH_FIRST:
            return self._graph_storage if self._graph_storage else self._select_backend_auto(record)
        elif self.strategy == StorageStrategy.COST_BASED:
            return self._select_backend_cost_based(record, StorageOperation.CREATE)
        else:
            return self._select_backend_auto(record)
    
    def _get_record_type(self, record: StorageRecord) -> str:
        """获取记录类型"""
        # 基于内容和元数据判断记录类型
        if "vector" in record.data or "embedding" in record.data:
            return "vector"
        elif "source" in record.data or "target" in record.data:
            return "graph"
        elif "text" in record.data and len(str(record.data.get("text", ""))) > 100:
            return "vector"
        elif record.metadata.get("type") == "graph":
            return "graph"
        elif record.metadata.get("type") == "vector":
            return "vector"
        else:
            return "general"
    
    def _get_backend_by_type(self, backend_type: StorageBackend) -> Optional[BaseStorage]:
        """根据类型获取存储后端"""
        if backend_type == StorageBackend.MEMORY:
            return self._memory_storage
        elif backend_type == StorageBackend.SQL:
            return self._sql_storage
        elif backend_type == StorageBackend.VECTOR:
            return self._vector_storage
        elif backend_type == StorageBackend.GRAPH:
            return self._graph_storage
        else:
            return None
    
    def _select_backend_auto(self, record: StorageRecord) -> Optional[BaseStorage]:
        """自动选择存储后端"""
        record_type = self._get_record_type(record)
        
        if record_type == "vector" and self._vector_storage:
            return self._vector_storage
        elif record_type == "graph" and self._graph_storage:
            return self._graph_storage
        elif self._memory_storage:
            # 对于小记录，使用内存存储
            record_size = self._calculate_size(record)
            if record_size < 1024:  # 小于1KB
                return self._memory_storage
            else:
                return self._sql_storage if self._sql_storage else self._memory_storage
        else:
            # 返回第一个可用的后端
            for _, backend in self._active_backends:
                return backend
        
        return None
    
    def _select_backend_cost_based(self, record: StorageRecord, operation: StorageOperation) -> Optional[BaseStorage]:
        """基于成本选择存储后端"""
        # 简化的成本计算
        costs = {}
        
        for backend_type, backend in self._active_backends:
            cost = self._calculate_operation_cost(backend_type, operation, record)
            costs[backend_type] = (cost, backend)
        
        if not costs:
            return None
        
        # 选择成本最低的后端
        best_backend_type = min(costs.keys(), key=lambda k: costs[k][0])
        return costs[best_backend_type][1]
    
    def _calculate_operation_cost(self, backend_type: StorageBackend, 
                                operation: StorageOperation, 
                                record: StorageRecord) -> float:
        """计算操作成本"""
        # 简化的成本模型
        base_costs = {
            StorageBackend.MEMORY: 1.0,
            StorageBackend.SQL: 2.0,
            StorageBackend.VECTOR: 3.0,
            StorageBackend.GRAPH: 4.0
        }
        
        operation_costs = {
            StorageOperation.CREATE: 1.0,
            StorageOperation.READ: 0.5,
            StorageOperation.UPDATE: 1.5,
            StorageOperation.DELETE: 1.0,
            StorageOperation.SEARCH: 2.0
        }
        
        base_cost = base_costs.get(backend_type, 10.0)
        op_cost = operation_costs.get(operation, 1.0)
        
        # 考虑记录大小
        record_size = self._calculate_size(record)
        size_factor = min(10.0, record_size / 1024)  # 每KB增加1个成本单位
        
        # 考虑性能历史
        perf_stats = self._performance_stats.get(backend_type, {})
        success_rate = perf_stats.get("success_rate", 1.0)
        avg_time = perf_stats.get("avg_time_ms", 0.0)
        
        # 成功率影响成本（成功率越低，成本越高）
        success_factor = 1.0 / max(0.1, success_rate)
        
        # 平均时间影响成本
        time_factor = avg_time / 100.0  # 每100ms增加1个成本单位
        
        total_cost = base_cost * op_cost * size_factor * success_factor * time_factor
        
        return total_cost
    
    def read(self, record_id: str) -> StorageResult:
        """读取记录"""
        import time
        start_time = time.time()
        
        try:
            # 首先检查缓存
            if self.config.cache_enabled:
                cached_record = self._get_from_cache(record_id)
                if cached_record:
                    execution_time = (time.time() - start_time) * 1000
                    
                    self._record_operation(StorageOperation.READ, True)
                    
                    return StorageResult(
                        success=True,
                        operation=StorageOperation.READ,
                        data=cached_record,
                        metadata={
                            "record_id": record_id,
                            "source": "cache",
                            "execution_time_ms": execution_time
                        }
                    )
            
            with self._lock:
                # 在所有后端中查找记录
                for backend_type, backend in self._active_backends:
                    result = backend.read(record_id)
                    
                    if result.success and result.data:
                        execution_time = (time.time() - start_time) * 1000
                        
                        # 更新性能统计
                        self._update_performance_stats(backend, StorageOperation.READ, 
                                                     execution_time, result.success)
                        
                        # 添加到缓存
                        if self.config.cache_enabled:
                            self._add_to_cache(result.data)
                        
                        # 记录操作
                        self._record_operation_history(StorageOperation.READ, record_id, 
                                                     backend, execution_time, result.success)
                        
                        # 更新操作统计
                        self._record_operation(StorageOperation.READ, result.success)
                        
                        return StorageResult(
                            success=True,
                            operation=StorageOperation.READ,
                            data=result.data,
                            metadata={
                                **result.metadata,
                                "record_id": record_id,
                                "source": backend_type.value,
                                "execution_time_ms": execution_time
                            }
                        )
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.READ, False)
                
                return StorageResult(
                    success=False,
                    operation=StorageOperation.READ,
                    error=f"Record {record_id} not found in any backend",
                    execution_time_ms=execution_time
                )
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._record_operation(StorageOperation.READ, False)
            
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def update(self, record_id: str, data: Dict[str, Any], 
              metadata: Optional[Dict[str, Any]] = None) -> StorageResult:
        """更新记录"""
        import time
        start_time = time.time()
        
        try:
            with self._lock:
                # 在所有后端中更新记录
                results = []
                backends_updated = []
                
                for backend_type, backend in self._active_backends:
                    # 检查记录是否存在
                    if backend.exists(record_id):
                        result = backend.update(record_id, data, metadata)
                        results.append((backend_type, result))
                        
                        if result.success:
                            backends_updated.append(backend_type)
                            
                            # 更新性能统计
                            execution_time = (time.time() - start_time) * 1000
                            self._update_performance_stats(backend, StorageOperation.UPDATE, 
                                                         execution_time, result.success)
                
                if not results:
                    execution_time = (time.time() - start_time) * 1000
                    self._record_operation(StorageOperation.UPDATE, False)
                    
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.UPDATE,
                        error=f"Record {record_id} not found in any backend",
                        execution_time_ms=execution_time
                    )
                
                # 检查所有更新是否成功
                all_success = all(result.success for _, result in results)
                
                # 更新缓存
                if self.config.cache_enabled and all_success:
                    # 从任一后端获取更新后的记录
                    for backend_type, backend in self._active_backends:
                        if backend.exists(record_id):
                            result = backend.read(record_id)
                            if result.success and result.data:
                                self._add_to_cache(result.data)
                                break
                
                execution_time = (time.time() - start_time) * 1000
                
                # 记录操作
                for backend_type, result in results:
                    if result.success:
                        self._record_operation_history(StorageOperation.UPDATE, record_id, 
                                                     backend, execution_time, result.success)
                
                # 更新操作统计
                self._record_operation(StorageOperation.UPDATE, all_success)
                
                return StorageResult(
                    success=all_success,
                    operation=StorageOperation.UPDATE,
                    data={"record_id": record_id, **data},
                    metadata={
                        "record_id": record_id,
                        "backends_updated": [b.value for b in backends_updated],
                        "total_backends": len(results),
                        "success_count": len(backends_updated),
                        "execution_time_ms": execution_time
                    }
                )
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._record_operation(StorageOperation.UPDATE, False)
            
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def delete(self, record_id: str) -> StorageResult:
        """删除记录"""
        import time
        start_time = time.time()
        
        try:
            with self._lock:
                # 在所有后端中删除记录
                results = []
                backends_deleted = []
                
                for backend_type, backend in self._active_backends:
                    result = backend.delete(record_id)
                    results.append((backend_type, result))
                    
                    if result.success:
                        backends_deleted.append(backend_type)
                        
                        # 更新性能统计
                        execution_time = (time.time() - start_time) * 1000
                        self._update_performance_stats(backend, StorageOperation.DELETE, 
                                                     execution_time, result.success)
                
                # 从缓存中删除
                if self.config.cache_enabled:
                    self._remove_from_cache(record_id)
                
                execution_time = (time.time() - start_time) * 1000
                
                # 检查是否有任何后端成功删除
                any_success = any(result.success for _, result in results)
                
                # 记录操作
                for backend_type, result in results:
                    if result.success:
                        self._record_operation_history(StorageOperation.DELETE, record_id, 
                                                     backend, execution_time, result.success)
                
                # 更新操作统计
                self._record_operation(StorageOperation.DELETE, any_success)
                
                return StorageResult(
                    success=any_success,
                    operation=StorageOperation.DELETE,
                    data={"record_id": record_id},
                    metadata={
                        "record_id": record_id,
                        "backends_deleted": [b.value for b in backends_deleted],
                        "total_backends": len(results),
                        "success_count": len(backends_deleted),
                        "execution_time_ms": execution_time
                    }
                )
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._record_operation(StorageOperation.DELETE, False)
            
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def search(self, query: StorageQuery) -> StorageResult:
        """搜索记录"""
        import time
        start_time = time.time()
        
        try:
            with self._lock:
                # 根据查询类型选择后端
                selected_backends = self._select_backends_for_search(query)
                
                if not selected_backends:
                    execution_time = (time.time() - start_time) * 1000
                    
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.SEARCH,
                        error="No suitable backend for search query",
                        execution_time_ms=execution_time
                    )
                
                # 在所有选中的后端中执行搜索
                all_results = []
                
                for backend in selected_backends:
                    result = backend.search(query)
                    
                    if result.success and result.data:
                        if isinstance(result.data, list):
                            all_results.extend(result.data)
                        
                        # 更新性能统计
                        execution_time = (time.time() - start_time) * 1000
                        self._update_performance_stats(backend, StorageOperation.SEARCH, 
                                                     execution_time, result.success)
                        
                        # 记录操作
                        self._record_operation_history(StorageOperation.SEARCH, "query", 
                                                     backend, execution_time, result.success)
                
                # 去重和排序
                if all_results:
                    # 简单的去重（基于ID）
                    seen_ids = set()
                    unique_results = []
                    
                    for result in all_results:
                        result_id = None
                        
                        if isinstance(result, StorageRecord):
                            result_id = result.id
                        elif isinstance(result, dict) and "id" in result:
                            result_id = result["id"]
                        
                        if result_id and result_id not in seen_ids:
                            seen_ids.add(result_id)
                            unique_results.append(result)
                    
                    all_results = unique_results
                
                # 应用查询限制
                if query.limit and len(all_results) > query.limit:
                    all_results = all_results[:query.limit]
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.SEARCH, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.SEARCH,
                    data=all_results,
                    metadata={
                        "total_results": len(all_results),
                        "unique_results": len(seen_ids) if 'seen_ids' in locals() else len(all_results),
                        "backends_searched": len(selected_backends),
                        "execution_time_ms": execution_time
                    }
                )
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._record_operation(StorageOperation.SEARCH, False)
            
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def _select_backends_for_search(self, query: StorageQuery) -> List[BaseStorage]:
        """为搜索选择存储后端"""
        selected_backends = []
        
        # 检查查询类型
        if "vector" in query.filters or "text" in query.filters:
            # 向量搜索
            if self._vector_storage:
                selected_backends.append(self._vector_storage)
        
        if "source" in query.filters or "target" in query.filters or "relationship" in query.filters:
            # 图搜索
            if self._graph_storage:
                selected_backends.append(self._graph_storage)
        
        # 通用搜索
        if not selected_backends:
            # 使用所有支持搜索的后端
            for _, backend in self._active_backends:
                if backend != self._vector_storage and backend != self._graph_storage:
                    selected_backends.append(backend)
        
        return selected_backends
    
    def _add_to_cache(self, record: StorageRecord):
        """添加到缓存"""
        with self._cache_lock:
            # 检查缓存大小
            if len(self._cache) >= self.config.cache_max_size:
                # 移除最旧的缓存项
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            
            # 添加记录
            self._cache[record.id] = (record, time.time())
    
    def _get_from_cache(self, record_id: str) -> Optional[StorageRecord]:
        """从缓存获取"""
        with self._cache_lock:
            if record_id in self._cache:
                record, timestamp = self._cache[record_id]
                
                # 检查TTL
                if time.time() - timestamp < self.config.cache_ttl_seconds:
                    return record
                else:
                    # 缓存过期，移除
                    del self._cache[record_id]
            
            return None
    
    def _remove_from_cache(self, record_id: str):
        """从缓存移除"""
        with self._cache_lock:
            if record_id in self._cache:
                del self._cache[record_id]
    
    def _update_performance_stats(self, backend: BaseStorage, operation: StorageOperation,
                                execution_time: float, success: bool):
        """更新性能统计"""
        # 获取后端类型
        backend_type = None
        for bt, b in self._active_backends:
            if b == backend:
                backend_type = bt
                break
        
        if not backend_type:
            return
        
        stats = self._performance_stats.get(backend_type, {})
        
        # 更新操作计数
        if "operations" in stats:
            stats["operations"][operation.value] += 1
        
        # 更新总时间和平均时间
        stats["total_time_ms"] = stats.get("total_time_ms", 0.0) + execution_time
        stats["avg_time_ms"] = stats["total_time_ms"] / max(1, sum(stats["operations"].values()))
        
        # 更新成功率
        total_ops = sum(stats["operations"].values())
        if total_ops > 0:
            # 简化的成功率计算
            if "success_count" not in stats:
                stats["success_count"] = 0
            if success:
                stats["success_count"] += 1
            stats["success_rate"] = stats["success_count"] / total_ops
        
        # 更新最后操作时间
        stats["last_operation"] = {
            "operation": operation.value,
            "timestamp": time.time(),
            "execution_time_ms": execution_time,
            "success": success
        }
        
        self._performance_stats[backend_type] = stats
    
    def _record_operation_history(self, operation: StorageOperation, record_id: str,
                                backend: BaseStorage, execution_time: float, success: bool):
        """记录操作历史"""
        # 获取后端类型
        backend_type = None
        for bt, b in self._active_backends:
            if b == backend:
                backend_type = bt
                break
        
        operation_record = {
            "timestamp": time.time(),
            "operation": operation.value,
            "record_id": record_id,
            "backend": backend_type.value if backend_type else "unknown",
            "execution_time_ms": execution_time,
            "success": success
        }
        
        self._operation_history.append(operation_record)
        
        # 限制历史记录长度
        if len(self._operation_history) > self.config.performance_window:
            self._operation_history = self._operation_history[-self.config.performance_window:]
    
    def add_routing_rule(self, record_type: str, backend_type: StorageBackend):
        """添加路由规则"""
        self._routing_rules[record_type] = backend_type
    
    def remove_routing_rule(self, record_type: str):
        """移除路由规则"""
        if record_type in self._routing_rules:
            del self._routing_rules[record_type]
    
    def set_strategy(self, strategy: StorageStrategy):
        """设置存储策略"""
        self.strategy = strategy
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "strategy": self.strategy.value,
            "active_backends": [b.value for b, _ in self._active_backends],
            "performance_by_backend": self._performance_stats,
            "cache_stats": {
                "size": len(self._cache),
                "max_size": self.config.cache_max_size,
                "ttl_seconds": self.config.cache_ttl_seconds
            },
            "routing_rules": {k: v.value for k, v in self._routing_rules.items()},
            "recent_operations": self._operation_history[-10:] if self._operation_history else []
        }
    
    def sync_backends(self, source_backend: StorageBackend, target_backend: StorageBackend) -> StorageResult:
        """同步两个后端的数据"""
        import time
        start_time = time.time()
        
        try:
            with self._lock:
                # 获取后端
                source = self._get_backend_by_type(source_backend)
                target = self._get_backend_by_type(target_backend)
                
                if not source or not target:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.BATCH,
                        error="Source or target backend not found"
                    )
                
                # 获取源后端的所有记录
                query = StorageQuery()
                result = source.search(query)
                
                if not result.success or not result.data:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.BATCH,
                        error="Failed to get records from source backend"
                    )
                
                records = result.data
                if not isinstance(records, list):
                    records = [records]
                
                # 同步到目标后端
                synced_count = 0
                for record in records:
                    if isinstance(record, StorageRecord):
                        # 检查记录是否已存在
                        if not target.exists(record.id):
                            # 创建记录
                            create_result = target.create(record)
                            if create_result.success:
                                synced_count += 1
                        else:
                            # 更新记录
                            update_result = target.update(record.id, record.data, record.metadata)
                            if update_result.success:
                                synced_count += 1
                
                execution_time = (time.time() - start_time) * 1000
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.BATCH,
                    data={"synced_count": synced_count, "total_records": len(records)},
                    metadata={
                        "source": source_backend.value,
                        "target": target_backend.value,
                        "execution_time_ms": execution_time
                    }
                )
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            return StorageResult(
                success=False,
                operation=StorageOperation.BATCH,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def get_backend_stats(self) -> Dict[str, Any]:
        """获取各个后端的统计信息"""
        stats = {}
        
        for backend_type, backend in self._active_backends:
            backend_stats = backend.get_statistics()
            stats[backend_type.value] = backend_stats
        
        return stats
    
    def clear_cache(self):
        """清空缓存"""
        with self._cache_lock:
            self._cache.clear()
    
    def clear_all(self):
        """清空所有后端的数据"""
        with self._lock:
            for _, backend in self._active_backends:
                if hasattr(backend, 'clear'):
                    backend.clear()
            
            self.clear_cache()
    
    def close(self):
        """关闭混合存储"""
        self._stop_migration_thread()
        
        # 关闭各个后端
        for _, backend in self._active_backends:
            backend.close()
        
        self.initialized = False