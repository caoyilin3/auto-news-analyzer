"""
向量存储实现
支持向量相似性搜索和语义检索
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import warnings
import threading
import json
import pickle
import hashlib
import time

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    warnings.warn("faiss not installed, using numpy-based similarity search")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    warnings.warn("sentence-transformers not installed, embedding generation disabled")

from .base_storage import (
    BaseStorage, StorageConfig, StorageRecord, StorageQuery,
    StorageResult, StorageOperation, StorageError
)

class VectorIndexType(Enum):
    """向量索引类型"""
    FLAT = "flat"            # 精确搜索，速度慢
    IVF = "ivf"              # 倒排索引，快速近似搜索
    HNSW = "hnsw"            # 分层可导航小世界图
    PQ = "pq"                # 乘积量化
    HYBRID = "hybrid"        # 混合索引

@dataclass
class VectorStorageConfig(StorageConfig):
    """向量存储配置"""
    # 向量配置
    vector_dimension: int = 384  # 向量维度
    index_type: VectorIndexType = VectorIndexType.HNSW
    
    # 嵌入模型配置
    embedding_model: str = "all-MiniLM-L6-v2"  # 默认模型
    embedding_device: str = "cpu"  # cpu or cuda
    
    # 索引参数
    nlist: int = 100  # IVF聚类中心数
    nprobe: int = 10  # IVF搜索时探查的聚类数
    m: int = 32  # HNSW的层间连接数
    ef_construction: int = 200  # HNSW构建时的邻居数
    ef_search: int = 100  # HNSW搜索时的邻居数
    
    # 量化参数
    pq_m: int = 8  # 乘积量化子空间数
    pq_nbits: int = 8  # 每个子空间的比特数
    
    # 缓存配置
    embedding_cache_size: int = 10000
    similarity_threshold: float = 0.7  # 相似度阈值

class VectorStorage(BaseStorage):
    """向量存储实现"""
    
    def __init__(self, config: VectorStorageConfig):
        super().__init__(config)
        self.config = config
        
        # 嵌入模型
        self._embedding_model = None
        
        # 向量索引
        self._vector_index = None
        self._index_type = config.index_type
        
        # 向量数据存储
        self._vectors: Dict[str, np.ndarray] = {}  # id -> vector
        self._id_to_index: Dict[str, int] = {}  # id -> index in FAISS
        self._index_to_id: Dict[int, str] = {}  # index in FAISS -> id
        
        # 缓存
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._similarity_cache: Dict[str, Dict[str, float]] = {}
        
        # 锁
        self._index_lock = threading.RLock()
        
        # 统计
        self._index_size = 0
        self._next_index_id = 0
    
    def initialize(self) -> bool:
        """初始化向量存储"""
        try:
            with self._index_lock:
                # 初始化嵌入模型
                if SENTENCE_TRANSFORMERS_AVAILABLE:
                    self._embedding_model = SentenceTransformer(
                        self.config.embedding_model,
                        device=self.config.embedding_device
                    )
                
                # 初始化向量索引
                self._initialize_vector_index()
                
                self.initialized = True
                return True
                
        except Exception as e:
            raise StorageError(
                f"Failed to initialize vector storage: {e}",
                StorageOperation.CREATE,
                "INIT_ERROR"
            )
    
    def _initialize_vector_index(self):
        """初始化向量索引"""
        dim = self.config.vector_dimension
        
        if FAISS_AVAILABLE:
            if self._index_type == VectorIndexType.FLAT:
                # 精确搜索索引
                self._vector_index = faiss.IndexFlatL2(dim)
                
            elif self._index_type == VectorIndexType.IVF:
                # 倒排索引
                quantizer = faiss.IndexFlatL2(dim)
                self._vector_index = faiss.IndexIVFFlat(
                    quantizer, dim, self.config.nlist
                )
                self._vector_index.nprobe = self.config.nprobe
                
            elif self._index_type == VectorIndexType.HNSW:
                # HNSW图索引
                self._vector_index = faiss.IndexHNSWFlat(dim, self.config.m)
                self._vector_index.hnsw.efConstruction = self.config.ef_construction
                self._vector_index.hnsw.efSearch = self.config.ef_search
                
            elif self._index_type == VectorIndexType.PQ:
                # 乘积量化索引
                self._vector_index = faiss.IndexPQ(
                    dim, self.config.pq_m, self.config.pq_nbits
                )
                
            elif self._index_type == VectorIndexType.HYBRID:
                # 混合索引：IVF + PQ
                quantizer = faiss.IndexFlatL2(dim)
                self._vector_index = faiss.IndexIVFPQ(
                    quantizer, dim, self.config.nlist,
                    self.config.pq_m, self.config.pq_nbits
                )
                self._vector_index.nprobe = self.config.nprobe
            else:
                raise ValueError(f"Unsupported index type: {self._index_type}")
        else:
            # 使用numpy实现简单的向量存储
            self._vector_index = None
            print("FAISS not available, using numpy-based vector storage")
    
    def create(self, record: StorageRecord) -> StorageResult:
        """创建记录（并生成向量）"""
        import time
        start_time = time.time()
        
        try:
            with self._index_lock:
                # 验证记录
                is_valid, error_msg = self._validate_record(record)
                if not is_valid:
                    raise StorageError(error_msg, StorageOperation.CREATE)
                
                # 检查记录是否存在
                if record.id in self._vectors:
                    raise StorageError(
                        f"Record {record.id} already exists",
                        StorageOperation.CREATE,
                        "DUPLICATE_RECORD"
                    )
                
                # 生成向量
                vector = self._generate_vector(record)
                
                # 存储向量
                self._vectors[record.id] = vector
                self._id_to_index[record.id] = self._next_index_id
                self._index_to_id[self._next_index_id] = record.id
                
                # 添加到索引
                if FAISS_AVAILABLE and self._vector_index is not None:
                    # 转换为正确的形状
                    vector_array = vector.reshape(1, -1).astype('float32')
                    
                    if isinstance(self._vector_index, faiss.IndexIVFFlat):
                        # IVF索引需要训练
                        if not self._vector_index.is_trained:
                            # 收集训练数据
                            training_vectors = np.vstack(list(self._vectors.values())).astype('float32')
                            if len(training_vectors) >= self.config.nlist:
                                self._vector_index.train(training_vectors)
                    
                    # 添加到索引
                    self._vector_index.add(vector_array)
                
                self._next_index_id += 1
                self._index_size += 1
                
                # 更新缓存
                if len(self._embedding_cache) > self.config.embedding_cache_size:
                    # 移除最旧的缓存项
                    oldest_key = next(iter(self._embedding_cache))
                    del self._embedding_cache[oldest_key]
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.CREATE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.CREATE,
                    data=record,
                    metadata={
                        "record_id": record.id,
                        "vector_dimension": vector.shape[0],
                        "index_size": self._index_size,
                        "execution_time_ms": execution_time
                    }
                )
                
        except StorageError as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise e
        except Exception as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise StorageError(
                f"Failed to create vector record: {e}",
                StorageOperation.CREATE,
                "CREATE_ERROR"
            )
    
    def read(self, record_id: str) -> StorageResult:
        """读取记录（不支持直接读取向量记录）"""
        # 向量存储主要用于相似性搜索，不直接支持按ID读取
        return StorageResult(
            success=False,
            operation=StorageOperation.READ,
            error="Vector storage does not support direct record reading",
            execution_time_ms=0
        )
    
    def update(self, record_id: str, data: Dict[str, Any], 
              metadata: Optional[Dict[str, Any]] = None) -> StorageResult:
        """更新记录（重新生成向量）"""
        import time
        start_time = time.time()
        
        try:
            with self._index_lock:
                if record_id not in self._vectors:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.UPDATE,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 创建新记录
                new_record = StorageRecord(
                    id=record_id,
                    data=data,
                    metadata=metadata or {}
                )
                
                # 生成新向量
                new_vector = self._generate_vector(new_record)
                
                # 更新向量
                old_vector = self._vectors[record_id]
                self._vectors[record_id] = new_vector
                
                # 更新索引（需要重建索引，因为FAISS不支持直接更新）
                if FAISS_AVAILABLE and self._vector_index is not None:
                    self._rebuild_index()
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.UPDATE, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.UPDATE,
                    data=new_record,
                    metadata={
                        "record_id": record_id,
                        "vector_updated": True,
                        "execution_time_ms": execution_time
                    }
                )
                
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
        import time
        start_time = time.time()
        
        try:
            with self._index_lock:
                if record_id not in self._vectors:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.DELETE,
                        error=f"Record {record_id} not found",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 从向量存储中移除
                del self._vectors[record_id]
                
                # 从索引映射中移除
                if record_id in self._id_to_index:
                    index_id = self._id_to_index[record_id]
                    del self._id_to_index[record_id]
                    if index_id in self._index_to_id:
                        del self._index_to_id[index_id]
                
                # 重建索引
                if FAISS_AVAILABLE and self._vector_index is not None:
                    self._rebuild_index()
                
                self._index_size -= 1
                
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
        """向量相似性搜索"""
        import time
        start_time = time.time()
        
        try:
            with self._index_lock:
                # 检查是否有查询向量
                if "vector" not in query.filters and "text" not in query.filters:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.SEARCH,
                        error="Vector search requires 'vector' or 'text' filter",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 获取查询向量
                query_vector = None
                if "vector" in query.filters:
                    query_vector = query.filters["vector"]
                    if isinstance(query_vector, list):
                        query_vector = np.array(query_vector, dtype=np.float32)
                elif "text" in query.filters:
                    # 从文本生成向量
                    query_text = query.filters["text"]
                    query_vector = self._generate_vector_from_text(query_text)
                
                if query_vector is None:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.SEARCH,
                        error="Failed to generate query vector",
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                
                # 执行搜索
                results = self._search_similar(query_vector, query)
                
                execution_time = (time.time() - start_time) * 1000
                self._record_operation(StorageOperation.SEARCH, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.SEARCH,
                    data=results,
                    metadata={
                        "query_vector_dim": query_vector.shape[0],
                        "results_returned": len(results),
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
    
    def _search_similar(self, query_vector: np.ndarray, query: StorageQuery) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        k = query.limit or 10
        threshold = query.filters.get("threshold", self.config.similarity_threshold)
        
        results = []
        
        if FAISS_AVAILABLE and self._vector_index is not None and self._index_size > 0:
            # 使用FAISS搜索
            query_vector = query_vector.reshape(1, -1).astype('float32')
            
            # 执行搜索
            distances, indices = self._vector_index.search(query_vector, k)
            
            # 处理结果
            for i in range(min(len(indices[0]), k)):
                index_id = indices[0][i]
                distance = distances[0][i]
                
                if index_id in self._index_to_id:
                    record_id = self._index_to_id[index_id]
                    
                    # 计算相似度（从距离转换）
                    similarity = self._distance_to_similarity(distance)
                    
                    if similarity >= threshold:
                        results.append({
                            "record_id": record_id,
                            "similarity": similarity,
                            "distance": float(distance),
                            "vector": self._vectors[record_id].tolist() if query.include_metadata else None
                        })
        else:
            # 使用numpy计算相似度
            similarities = []
            for record_id, vector in self._vectors.items():
                similarity = self._calculate_similarity(query_vector, vector)
                if similarity >= threshold:
                    similarities.append((record_id, similarity))
            
            # 按相似度排序
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # 取前k个
            for record_id, similarity in similarities[:k]:
                results.append({
                    "record_id": record_id,
                    "similarity": similarity,
                    "distance": 1.0 - similarity,
                    "vector": self._vectors[record_id].tolist() if query.include_metadata else None
                })
        
        return results
    
    def _generate_vector(self, record: StorageRecord) -> np.ndarray:
        """为记录生成向量"""
        # 首先检查缓存
        cache_key = self._get_record_cache_key(record)
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key].copy()
        
        # 生成向量
        vector = None
        
        # 尝试从记录中提取向量
        if "vector" in record.data:
            vector_data = record.data["vector"]
            if isinstance(vector_data, list):
                vector = np.array(vector_data, dtype=np.float32)
            elif isinstance(vector_data, np.ndarray):
                vector = vector_data.astype(np.float32)
        
        # 如果记录中没有向量，尝试从文本生成
        if vector is None and "text" in record.data:
            text = record.data["text"]
            vector = self._generate_vector_from_text(text)
        
        # 如果仍然没有向量，使用随机向量
        if vector is None:
            # 生成随机向量（单位向量）
            vector = np.random.randn(self.config.vector_dimension).astype(np.float32)
            vector = vector / np.linalg.norm(vector)
        
        # 确保向量维度正确
        if len(vector) != self.config.vector_dimension:
            if len(vector) > self.config.vector_dimension:
                vector = vector[:self.config.vector_dimension]
            else:
                # 填充零向量
                padded = np.zeros(self.config.vector_dimension, dtype=np.float32)
                padded[:len(vector)] = vector
                vector = padded
        
        # 归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        # 缓存
        if cache_key not in self._embedding_cache:
            self._embedding_cache[cache_key] = vector.copy()
        
        return vector
    
    def _generate_vector_from_text(self, text: str) -> np.ndarray:
        """从文本生成向量"""
        # 检查缓存
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key].copy()
        
        # 生成嵌入
        if self._embedding_model is not None:
            # 使用sentence-transformers
            vector = self._embedding_model.encode(text)
            vector = vector.astype(np.float32)
        else:
            # 使用简单的词袋模型（简化实现）
            words = text.lower().split()
            word_vectors = []
            
            for word in words:
                # 简单的哈希嵌入
                word_hash = hash(word) % 1000
                word_vec = np.zeros(100, dtype=np.float32)
                word_vec[word_hash % 100] = 1.0
                word_vectors.append(word_vec)
            
            if word_vectors:
                vector = np.mean(word_vectors, axis=0)
            else:
                vector = np.zeros(100, dtype=np.float32)
            
            # 调整维度
            if len(vector) != self.config.vector_dimension:
                if self.config.vector_dimension == 384 and len(vector) == 100:
                    # 常见情况：扩展到384维
                    vector = np.pad(vector, (0, 284), mode='constant')
                else:
                    # 通用调整
                    if len(vector) > self.config.vector_dimension:
                        vector = vector[:self.config.vector_dimension]
                    else:
                        padded = np.zeros(self.config.vector_dimension, dtype=np.float32)
                        padded[:len(vector)] = vector
                        vector = padded
        
        # 归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        # 缓存
        self._embedding_cache[cache_key] = vector.copy()
        
        return vector
    
    def _get_record_cache_key(self, record: StorageRecord) -> str:
        """获取记录缓存键"""
        # 基于记录内容和元数据生成缓存键
        content_str = json.dumps(record.data, sort_keys=True, default=str)
        metadata_str = json.dumps(record.metadata, sort_keys=True, default=str)
        combined = f"{content_str}:{metadata_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算向量相似度"""
        # 余弦相似度
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # 确保在[0, 1]范围内
        return max(0.0, min(1.0, similarity))
    
    def _distance_to_similarity(self, distance: float) -> float:
        """将距离转换为相似度"""
        # 欧氏距离转换为相似度
        # 距离越大，相似度越小
        similarity = 1.0 / (1.0 + distance)
        return max(0.0, min(1.0, similarity))
    
    def _rebuild_index(self):
        """重建索引"""
        if not FAISS_AVAILABLE or self._vector_index is None:
            return
        
        # 收集所有向量
        vectors = []
        id_mapping = {}
        
        for i, (record_id, vector) in enumerate(self._vectors.items()):
            vectors.append(vector.astype('float32'))
            id_mapping[i] = record_id
        
        if not vectors:
            # 没有向量，重新初始化索引
            self._initialize_vector_index()
            self._id_to_index.clear()
            self._index_to_id.clear()
            self._next_index_id = 0
            return
        
        # 创建新索引
        vectors_array = np.vstack(vectors)
        
        # 重新初始化索引
        old_index_type = self._index_type
        self._initialize_vector_index()
        
        # 训练索引（如果需要）
        if isinstance(self._vector_index, faiss.IndexIVFFlat):
            if len(vectors_array) >= self.config.nlist:
                self._vector_index.train(vectors_array)
        
        # 添加向量到新索引
        self._vector_index.add(vectors_array)
        
        # 更新映射
        self._id_to_index.clear()
        self._index_to_id.clear()
        
        for i, record_id in id_mapping.items():
            self._id_to_index[record_id] = i
            self._index_to_id[i] = record_id
        
        self._next_index_id = len(vectors)
        self._index_type = old_index_type
    
    def search_by_text(self, text: str, limit: int = 10, threshold: float = 0.7) -> StorageResult:
        """通过文本搜索"""
        query = StorageQuery(
            filters={"text": text, "threshold": threshold},
            limit=limit
        )
        return self.search(query)
    
    def search_by_vector(self, vector: Union[List[float], np.ndarray], 
                        limit: int = 10, threshold: float = 0.7) -> StorageResult:
        """通过向量搜索"""
        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)
        
        query = StorageQuery(
            filters={"vector": vector, "threshold": threshold},
            limit=limit
        )
        return self.search(query)
    
    def get_similarity(self, record_id1: str, record_id2: str) -> float:
        """获取两个记录的相似度"""
        if record_id1 not in self._vectors or record_id2 not in self._vectors:
            return 0.0
        
        # 检查缓存
        cache_key = f"{record_id1}:{record_id2}"
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key].get("similarity", 0.0)
        
        # 计算相似度
        vec1 = self._vectors[record_id1]
        vec2 = self._vectors[record_id2]
        similarity = self._calculate_similarity(vec1, vec2)
        
        # 缓存
        self._similarity_cache[cache_key] = {
            "similarity": similarity,
            "timestamp": time.time()
        }
        
        return similarity
    
    def get_clusters(self, n_clusters: int = 10) -> Dict[int, List[str]]:
        """聚类向量"""
        if len(self._vectors) < n_clusters:
            return {}
        
        try:
            from sklearn.cluster import KMeans
        except ImportError:
            print("scikit-learn not installed, clustering disabled")
            return {}
        
        # 收集向量
        vectors = []
        record_ids = []
        
        for record_id, vector in self._vectors.items():
            vectors.append(vector)
            record_ids.append(record_id)
        
        vectors_array = np.vstack(vectors)
        
        # 执行K-means聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        clusters = kmeans.fit_predict(vectors_array)
        
        # 组织结果
        result = {}
        for i, cluster_id in enumerate(clusters):
            if cluster_id not in result:
                result[cluster_id] = []
            result[cluster_id].append(record_ids[i])
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = super().get_statistics()
        
        stats.update({
            "vector_count": len(self._vectors),
            "index_type": self._index_type.value if self._index_type else "none",
            "vector_dimension": self.config.vector_dimension,
            "embedding_cache_size": len(self._embedding_cache),
            "similarity_cache_size": len(self._similarity_cache),
            "faiss_available": FAISS_AVAILABLE,
            "embedding_model_available": self._embedding_model is not None
        })
        
        return stats
    
    def clear(self):
        """清空所有数据"""
        with self._index_lock:
            self._vectors.clear()
            self._id_to_index.clear()
            self._index_to_id.clear()
            self._embedding_cache.clear()
            self._similarity_cache.clear()
            self._next_index_id = 0
            self._index_size = 0
            
            # 重新初始化索引
            if FAISS_AVAILABLE and self._vector_index is not None:
                self._initialize_vector_index()
    
    def save_index(self, filepath: str) -> bool:
        """保存索引到文件"""
        try:
            with self._index_lock:
                if FAISS_AVAILABLE and self._vector_index is not None:
                    faiss.write_index(self._vector_index, filepath)
                    
                    # 保存映射数据
                    mapping_data = {
                        "id_to_index": self._id_to_index,
                        "index_to_id": self._index_to_id,
                        "vectors": {k: v.tolist() for k, v in self._vectors.items()},
                        "next_index_id": self._next_index_id
                    }
                    
                    with open(filepath + ".mapping", 'wb') as f:
                        pickle.dump(mapping_data, f)
                    
                    return True
                else:
                    return False
        except Exception as e:
            print(f"Failed to save index: {e}")
            return False
    
    def load_index(self, filepath: str) -> bool:
        """从文件加载索引"""
        try:
            with self._index_lock:
                if FAISS_AVAILABLE:
                    self._vector_index = faiss.read_index(filepath)
                    
                    # 加载映射数据
                    mapping_file = filepath + ".mapping"
                    with open(mapping_file, 'rb') as f:
                        mapping_data = pickle.load(f)
                    
                    self._id_to_index = mapping_data.get("id_to_index", {})
                    self._index_to_id = mapping_data.get("index_to_id", {})
                    self._vectors = {k: np.array(v, dtype=np.float32) 
                                for k, v in mapping_data.get("vectors", {}).items()}
                    self._next_index_id = mapping_data.get("next_index_id", 0)
                    self._index_size = len(self._vectors)
                    
                    return True
                else:
                    return False
        except Exception as e:
            print(f"Failed to load index: {e}")
            return False
    
    def close(self):
        """关闭存储"""
        self._embedding_model = None
        self._vector_index = None
        self.initialized = False