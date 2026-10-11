"""
图数据库存储实现
支持多种图数据库：NetworkX（内存）、Neo4j等
"""

import warnings
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import networkx as nx
import json

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    warnings.warn("neo4j not installed, Neo4j support disabled")

from .base_storage import (
    BaseStorage, StorageConfig, StorageRecord, StorageQuery,
    StorageResult, StorageOperation, StorageError
)

class GraphDatabaseType(Enum):
    """图数据库类型枚举"""
    NETWORKX = "networkx"  # 内存图数据库
    NEO4J = "neo4j"        # Neo4j图数据库

@dataclass
class GraphStorageConfig(StorageConfig):
    """图存储配置"""
    db_type: GraphDatabaseType = GraphDatabaseType.NETWORKX
    uri: str = "bolt://localhost:7687"  # Neo4j连接URI
    database: str = "neo4j"  # Neo4j数据库名
    username: str = "neo4j"
    password: str = "password"
    
    # 图配置
    directed: bool = True  # 是否是有向图
    multigraph: bool = False  # 是否允许多重边
    
    # 节点和边属性
    node_id_field: str = "id"
    node_label_field: str = "label"
    edge_id_field: str = "id"
    edge_label_field: str = "label"
    
    # 索引配置
    auto_create_indexes: bool = True

class GraphStorage(BaseStorage):
    """图数据库存储实现"""
    
    def __init__(self, config: GraphStorageConfig):
        super().__init__(config)
        self.config = config
        self.db_type = config.db_type
        
        # 图数据库连接
        self._driver = None
        self._graph = None
        
        # 缓存
        self._node_cache: Dict[str, Dict[str, Any]] = {}
        self._edge_cache: Dict[str, Dict[str, Any]] = {}
    
    def initialize(self) -> bool:
        """初始化图存储"""
        try:
            if self.db_type == GraphDatabaseType.NETWORKX:
                # 初始化NetworkX图
                if self.config.directed:
                    if self.config.multigraph:
                        self._graph = nx.MultiDiGraph()
                    else:
                        self._graph = nx.DiGraph()
                else:
                    if self.config.multigraph:
                        self._graph = nx.MultiGraph()
                    else:
                        self._graph = nx.Graph()
                        
            elif self.db_type == GraphDatabaseType.NEO4J:
                if not NEO4J_AVAILABLE:
                    raise ImportError("neo4j driver not installed")
                
                # 初始化Neo4j驱动
                self._driver = GraphDatabase.driver(
                    self.config.uri,
                    auth=(self.config.username, self.config.password)
                )
                
                # 测试连接
                with self._driver.session(database=self.config.database) as session:
                    session.run("RETURN 1")
                
                # 创建索引
                if self.config.auto_create_indexes:
                    self._create_neo4j_indexes()
                    
            else:
                raise ValueError(f"Unsupported graph database type: {self.db_type}")
            
            self.initialized = True
            return True
            
        except Exception as e:
            raise StorageError(
                f"Failed to initialize graph storage: {e}",
                StorageOperation.CREATE,
                "INIT_ERROR"
            )
    
    def _create_neo4j_indexes(self):
        """创建Neo4j索引"""
        if not self._driver:
            return
        
        with self._driver.session(database=self.config.database) as session:
            # 创建节点ID索引
            session.run(f"""
            CREATE INDEX IF NOT EXISTS FOR (n:Node) ON (n.{self.config.node_id_field})
            """)
            
            # 创建边ID索引
            session.run(f"""
            CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATIONSHIP]-() ON (r.{self.config.edge_id_field})
            """)
    
    def create(self, record: StorageRecord) -> StorageResult:
        """创建图节点或边"""
        import time
        start_time = time.time()
        
        try:
            # 验证记录
            is_valid, error_msg = self._validate_record(record)
            if not is_valid:
                raise StorageError(error_msg, StorageOperation.CREATE)
            
            # 确定记录类型（节点或边）
            record_type = self._determine_record_type(record)
            
            if record_type == "node":
                result = self._create_node(record)
            elif record_type == "edge":
                result = self._create_edge(record)
            else:
                raise StorageError(
                    "Cannot determine record type (node or edge)",
                    StorageOperation.CREATE,
                    "INVALID_RECORD_TYPE"
                )
            
            execution_time = (time.time() - start_time) * 1000
            result.metadata["execution_time_ms"] = execution_time
            
            return result
            
        except StorageError as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise e
        except Exception as e:
            self._record_operation(StorageOperation.CREATE, False)
            raise StorageError(
                f"Failed to create graph record: {e}",
                StorageOperation.CREATE,
                "CREATE_ERROR"
            )
    
    def _determine_record_type(self, record: StorageRecord) -> str:
        """确定记录类型（节点或边）"""
        # 检查是否有source和target字段（边）
        if ("source" in record.data and "target" in record.data) or \
           ("from" in record.data and "to" in record.data):
            return "edge"
        
        # 检查元数据中的类型
        if "type" in record.metadata:
            if record.metadata["type"] in ["node", "vertex"]:
                return "node"
            elif record.metadata["type"] in ["edge", "relationship", "link"]:
                return "edge"
        
        # 默认是节点
        return "node"
    
    def _create_node(self, record: StorageRecord) -> StorageResult:
        """创建节点"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._create_node_networkx(record)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._create_node_neo4j(record)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _create_node_networkx(self, record: StorageRecord) -> StorageResult:
        """在NetworkX中创建节点"""
        node_id = record.id
        
        # 检查节点是否存在
        if node_id in self._graph.nodes:
            raise StorageError(
                f"Node {node_id} already exists",
                StorageOperation.CREATE,
                "DUPLICATE_NODE"
            )
        
        # 准备节点属性
        node_attrs = record.data.copy()
        
        # 添加元数据
        node_attrs["_metadata"] = record.metadata
        node_attrs["_version"] = record.version
        node_attrs["_created_at"] = record.created_at.isoformat()
        node_attrs["_updated_at"] = record.updated_at.isoformat()
        
        # 添加标签
        if "label" not in node_attrs and self.config.node_label_field != "label":
            node_attrs["label"] = record.metadata.get("label", "Node")
        
        # 添加节点
        self._graph.add_node(node_id, **node_attrs)
        
        # 更新缓存
        self._node_cache[node_id] = node_attrs
        
        self._record_operation(StorageOperation.CREATE, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.CREATE,
            data=record,
            metadata={
                "record_type": "node",
                "node_id": node_id,
                "attributes_count": len(node_attrs)
            }
        )
    
    def _create_node_neo4j(self, record: StorageRecord) -> StorageResult:
        """在Neo4j中创建节点"""
        if not self._driver:
            raise StorageError(
                "Neo4j driver not initialized",
                StorageOperation.CREATE,
                "DRIVER_ERROR"
            )
        
        node_id = record.id
        
        with self._driver.session(database=self.config.database) as session:
            # 检查节点是否存在
            check_query = f"""
            MATCH (n:Node {{{self.config.node_id_field}: $id}}) 
            RETURN n
            """
            result = session.run(check_query, id=node_id)
            if result.single():
                raise StorageError(
                    f"Node {node_id} already exists",
                    StorageOperation.CREATE,
                    "DUPLICATE_NODE"
                )
            
            # 准备属性
            properties = record.data.copy()
            properties[self.config.node_id_field] = node_id
            
            # 添加元数据
            metadata_props = {
                f"_metadata_{k}": v for k, v in record.metadata.items()
            }
            properties.update(metadata_props)
            
            properties["_version"] = record.version
            properties["_created_at"] = record.created_at.isoformat()
            properties["_updated_at"] = record.updated_at.isoformat()
            
            # 获取标签
            labels = ["Node"]
            if "labels" in record.metadata and isinstance(record.metadata["labels"], list):
                labels.extend(record.metadata["labels"])
            
            # 创建节点
            label_str = ":".join(labels)
            create_query = f"""
            CREATE (n:{label_str} $props)
            RETURN n
            """
            
            result = session.run(create_query, props=properties)
            created_node = result.single()
            
            if not created_node:
                raise StorageError(
                    "Failed to create node",
                    StorageOperation.CREATE,
                    "CREATE_FAILED"
                )
            
            self._record_operation(StorageOperation.CREATE, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.CREATE,
                data=record,
                metadata={
                    "record_type": "node",
                    "node_id": node_id,
                    "labels": labels
                }
            )
    
    def _create_edge(self, record: StorageRecord) -> StorageResult:
        """创建边"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._create_edge_networkx(record)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._create_edge_neo4j(record)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _create_edge_networkx(self, record: StorageRecord) -> StorageResult:
        """在NetworkX中创建边"""
        # 获取源节点和目标节点
        source = record.data.get("source") or record.data.get("from")
        target = record.data.get("target") or record.data.get("to")
        
        if not source or not target:
            raise StorageError(
                "Edge record must contain 'source'/'from' and 'target'/'to' fields",
                StorageOperation.CREATE,
                "INVALID_EDGE"
            )
        
        # 检查节点是否存在
        if source not in self._graph.nodes:
            raise StorageError(
                f"Source node {source} does not exist",
                StorageOperation.CREATE,
                "NODE_NOT_FOUND"
            )
        
        if target not in self._graph.nodes:
            raise StorageError(
                f"Target node {target} does not exist",
                StorageOperation.CREATE,
                "NODE_NOT_FOUND"
            )
        
        # 准备边属性
        edge_attrs = record.data.copy()
        
        # 移除源和目标字段（它们已经是图结构的一部分）
        edge_attrs.pop("source", None)
        edge_attrs.pop("from", None)
        edge_attrs.pop("target", None)
        edge_attrs.pop("to", None)
        
        # 添加元数据
        edge_attrs["_metadata"] = record.metadata
        edge_attrs["_version"] = record.version
        edge_attrs["_created_at"] = record.created_at.isoformat()
        edge_attrs["_updated_at"] = record.updated_at.isoformat()
        
        # 添加标签
        if "label" not in edge_attrs and self.config.edge_label_field != "label":
            edge_attrs["label"] = record.metadata.get("label", "RELATED_TO")
        
        # 生成边ID
        edge_id = record.id or f"{source}_{target}_{hash(str(edge_attrs))}"
        edge_attrs["id"] = edge_id
        
        # 添加边
        self._graph.add_edge(source, target, **edge_attrs)
        
        # 更新缓存
        self._edge_cache[edge_id] = {
            "source": source,
            "target": target,
            **edge_attrs
        }
        
        self._record_operation(StorageOperation.CREATE, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.CREATE,
            data=record,
            metadata={
                "record_type": "edge",
                "edge_id": edge_id,
                "source": source,
                "target": target,
                "attributes_count": len(edge_attrs)
            }
        )
    
    def _create_edge_neo4j(self, record: StorageRecord) -> StorageResult:
        """在Neo4j中创建边"""
        if not self._driver:
            raise StorageError(
                "Neo4j driver not initialized",
                StorageOperation.CREATE,
                "DRIVER_ERROR"
            )
        
        # 获取源节点和目标节点
        source = record.data.get("source") or record.data.get("from")
        target = record.data.get("target") or record.data.get("to")
        
        if not source or not target:
            raise StorageError(
                "Edge record must contain 'source'/'from' and 'target'/'to' fields",
                StorageOperation.CREATE,
                "INVALID_EDGE"
            )
        
        edge_id = record.id or f"{source}_{target}_{hash(str(record.data))}"
        
        with self._driver.session(database=self.config.database) as session:
            # 检查边是否存在
            check_query = f"""
            MATCH ()-[r:RELATIONSHIP {{{self.config.edge_id_field}: $id}}]-() 
            RETURN r
            """
            result = session.run(check_query, id=edge_id)
            if result.single():
                raise StorageError(
                    f"Edge {edge_id} already exists",
                    StorageOperation.CREATE,
                    "DUPLICATE_EDGE"
                )
            
            # 准备属性
            properties = record.data.copy()
            properties[self.config.edge_id_field] = edge_id
            
            # 添加元数据
            metadata_props = {
                f"_metadata_{k}": v for k, v in record.metadata.items()
            }
            properties.update(metadata_props)
            
            properties["_version"] = record.version
            properties["_created_at"] = record.created_at.isoformat()
            properties["_updated_at"] = record.updated_at.isoformat()
            
            # 获取关系类型
            rel_type = "RELATED_TO"
            if "type" in record.metadata:
                rel_type = record.metadata["type"]
            elif "label" in properties:
                rel_type = properties["label"]
                del properties["label"]
            
            # 移除源和目标字段
            properties.pop("source", None)
            properties.pop("from", None)
            properties.pop("target", None)
            properties.pop("to", None)
            
            # 创建关系
            create_query = f"""
            MATCH (a:Node {{{self.config.node_id_field}: $source}})
            MATCH (b:Node {{{self.config.node_id_field}: $target}})
            CREATE (a)-[r:{rel_type} $props]->(b)
            RETURN r
            """
            
            result = session.run(create_query, 
                               source=source, target=target, props=properties)
            created_edge = result.single()
            
            if not created_edge:
                raise StorageError(
                    "Failed to create edge",
                    StorageOperation.CREATE,
                    "CREATE_FAILED"
                )
            
            self._record_operation(StorageOperation.CREATE, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.CREATE,
                data=record,
                metadata={
                    "record_type": "edge",
                    "edge_id": edge_id,
                    "source": source,
                    "target": target,
                    "relationship_type": rel_type
                }
            )
    
    def read(self, record_id: str) -> StorageResult:
        """读取节点或边"""
        import time
        start_time = time.time()
        
        try:
            # 首先尝试作为节点读取
            node_result = self._read_node(record_id)
            if node_result.success:
                execution_time = (time.time() - start_time) * 1000
                node_result.metadata["execution_time_ms"] = execution_time
                return node_result
            
            # 然后尝试作为边读取
            edge_result = self._read_edge(record_id)
            if edge_result.success:
                execution_time = (time.time() - start_time) * 1000
                edge_result.metadata["execution_time_ms"] = execution_time
                return edge_result
            
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=f"Record {record_id} not found",
                execution_time_ms=(time.time() - start_time) * 1000
            )
                
        except Exception as e:
            self._record_operation(StorageOperation.READ, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _read_node(self, node_id: str) -> StorageResult:
        """读取节点"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._read_node_networkx(node_id)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._read_node_neo4j(node_id)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _read_node_networkx(self, node_id: str) -> StorageResult:
        """从NetworkX读取节点"""
        if node_id not in self._graph.nodes:
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=f"Node {node_id} not found"
            )
        
        # 获取节点属性
        node_attrs = self._graph.nodes[node_id]
        
        # 提取数据和元数据
        data = {}
        metadata = {}
        
        for key, value in node_attrs.items():
            if key.startswith("_metadata_"):
                metadata_key = key[10:]  # 移除"_metadata_"前缀
                metadata[metadata_key] = value
            elif key.startswith("_"):
                # 跳过内部属性
                continue
            else:
                data[key] = value
        
        # 从缓存中恢复完整的元数据
        if "_metadata" in node_attrs and isinstance(node_attrs["_metadata"], dict):
            metadata.update(node_attrs["_metadata"])
        
        # 创建记录
        record = StorageRecord(
            id=node_id,
            data=data,
            metadata=metadata
        )
        
        self._record_operation(StorageOperation.READ, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.READ,
            data=record,
            metadata={
                "record_type": "node",
                "node_id": node_id,
                "degree": self._graph.degree(node_id)
            }
        )
    
    def _read_node_neo4j(self, node_id: str) -> StorageResult:
        """从Neo4j读取节点"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            query = f"""
            MATCH (n:Node {{{self.config.node_id_field}: $id}})
            RETURN n
            """
            
            result = session.run(query, id=node_id)
            record = result.single()
            
            if not record:
                return StorageResult(
                    success=False,
                    operation=StorageOperation.READ,
                    error=f"Node {node_id} not found"
                )
            
            # 提取节点属性
            node = record["n"]
            properties = dict(node)
            
            # 提取数据和元数据
            data = {}
            metadata = {}
            
            for key, value in properties.items():
                if key.startswith("_metadata_"):
                    metadata_key = key[10:]  # 移除"_metadata_"前缀
                    metadata[metadata_key] = value
                elif key.startswith("_"):
                    # 跳过内部属性
                    continue
                elif key == self.config.node_id_field:
                    # 跳过ID字段（它已经是记录的ID）
                    continue
                else:
                    data[key] = value
            
            # 创建记录
            record = StorageRecord(
                id=node_id,
                data=data,
                metadata=metadata
            )
            
            # 获取度
            degree_query = f"""
            MATCH (n:Node {{{self.config.node_id_field}: $id}})
            RETURN size((n)--()) as degree
            """
            degree_result = session.run(degree_query, id=node_id)
            degree = degree_result.single()["degree"] if degree_result.single() else 0
            
            self._record_operation(StorageOperation.READ, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.READ,
                data=record,
                metadata={
                    "record_type": "node",
                    "node_id": node_id,
                    "degree": degree,
                    "labels": list(node.labels)
                }
            )
    
    def _read_edge(self, edge_id: str) -> StorageResult:
        """读取边"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._read_edge_networkx(edge_id)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._read_edge_neo4j(edge_id)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _read_edge_networkx(self, edge_id: str) -> StorageResult:
        """从NetworkX读取边"""
        # 在边缓存中查找
        if edge_id in self._edge_cache:
            edge_data = self._edge_cache[edge_id]
            
            # 创建记录
            data = edge_data.copy()
            source = data.pop("source", None)
            target = data.pop("target", None)
            
            if source and target:
                data["source"] = source
                data["target"] = target
            
            # 提取元数据
            metadata = {}
            if "_metadata" in data:
                metadata = data.pop("_metadata", {})
            
            record = StorageRecord(
                id=edge_id,
                data=data,
                metadata=metadata
            )
            
            self._record_operation(StorageOperation.READ, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.READ,
                data=record,
                metadata={
                    "record_type": "edge",
                    "edge_id": edge_id,
                    "source": source,
                    "target": target
                }
            )
        
        # 在图中查找边
        for u, v, edge_data in self._graph.edges(data=True):
            if edge_data.get("id") == edge_id:
                # 找到边，更新缓存
                edge_data_with_nodes = {
                    "source": u,
                    "target": v,
                    **edge_data
                }
                self._edge_cache[edge_id] = edge_data_with_nodes
                
                # 创建记录
                data = edge_data.copy()
                data["source"] = u
                data["target"] = v
                
                # 提取元数据
                metadata = {}
                if "_metadata" in data:
                    metadata = data.pop("_metadata", {})
                
                record = StorageRecord(
                    id=edge_id,
                    data=data,
                    metadata=metadata
                )
                
                self._record_operation(StorageOperation.READ, True)
                
                return StorageResult(
                    success=True,
                    operation=StorageOperation.READ,
                    data=record,
                    metadata={
                        "record_type": "edge",
                        "edge_id": edge_id,
                        "source": u,
                        "target": v
                    }
                )
        
        return StorageResult(
            success=False,
            operation=StorageOperation.READ,
            error=f"Edge {edge_id} not found"
        )
    
    def _read_edge_neo4j(self, edge_id: str) -> StorageResult:
        """从Neo4j读取边"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            query = f"""
            MATCH (a)-[r {{{self.config.edge_id_field}: $id}}]->(b)
            RETURN a, r, b, type(r) as relationship_type
            """
            
            result = session.run(query, id=edge_id)
            record = result.single()
            
            if not record:
                return StorageResult(
                    success=False,
                    operation=StorageOperation.READ,
                    error=f"Edge {edge_id} not found"
                )
            
            # 提取边属性
            edge = record["r"]
            properties = dict(edge)
            
            # 获取源节点和目标节点ID
            source_node = record["a"]
            target_node = record["b"]
            
            source_id = source_node[self.config.node_id_field]
            target_id = target_node[self.config.node_id_field]
            
            # 提取数据和元数据
            data = {"source": source_id, "target": target_id}
            metadata = {"relationship_type": record["relationship_type"]}
            
            for key, value in properties.items():
                if key.startswith("_metadata_"):
                    metadata_key = key[10:]  # 移除"_metadata_"前缀
                    metadata[metadata_key] = value
                elif key.startswith("_"):
                    # 跳过内部属性
                    continue
                elif key == self.config.edge_id_field:
                    # 跳过ID字段
                    continue
                else:
                    data[key] = value
            
            # 创建记录
            record = StorageRecord(
                id=edge_id,
                data=data,
                metadata=metadata
            )
            
            self._record_operation(StorageOperation.READ, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.READ,
                data=record,
                metadata={
                    "record_type": "edge",
                    "edge_id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "relationship_type": record["relationship_type"]
                }
            )
    
    def update(self, record_id: str, data: Dict[str, Any], 
              metadata: Optional[Dict[str, Any]] = None) -> StorageResult:
        """更新节点或边"""
        import time
        start_time = time.time()
        
        try:
            # 首先尝试更新节点
            node_result = self._update_node(record_id, data, metadata)
            if node_result.success:
                execution_time = (time.time() - start_time) * 1000
                node_result.metadata["execution_time_ms"] = execution_time
                return node_result
            
            # 然后尝试更新边
            edge_result = self._update_edge(record_id, data, metadata)
            if edge_result.success:
                execution_time = (time.time() - start_time) * 1000
                edge_result.metadata["execution_time_ms"] = execution_time
                return edge_result
            
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=f"Record {record_id} not found",
                execution_time_ms=(time.time() - start_time) * 1000
            )
                
        except Exception as e:
            self._record_operation(StorageOperation.UPDATE, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _update_node(self, node_id: str, data: Dict[str, Any], 
                    metadata: Optional[Dict[str, Any]]) -> StorageResult:
        """更新节点"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._update_node_networkx(node_id, data, metadata)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._update_node_neo4j(node_id, data, metadata)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _update_node_networkx(self, node_id: str, data: Dict[str, Any], 
                             metadata: Optional[Dict[str, Any]]) -> StorageResult:
        """在NetworkX中更新节点"""
        if node_id not in self._graph.nodes:
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=f"Node {node_id} not found"
            )
        
        # 获取当前属性
        current_attrs = self._graph.nodes[node_id]
        
        # 合并数据
        new_data = current_attrs.copy()
        
        # 更新数据字段
        for key, value in data.items():
            if not key.startswith("_"):  # 跳过内部属性
                new_data[key] = value
        
        # 更新元数据
        if metadata:
            # 保存到_metadata字段
            current_metadata = new_data.get("_metadata", {})
            current_metadata.update(metadata)
            new_data["_metadata"] = current_metadata
        
        # 更新内部属性
        new_data["_updated_at"] = datetime.now().isoformat()
        
        # 如果有版本号，增加版本
        if "_version" in new_data:
            new_data["_version"] = new_data["_version"] + 1
        
        # 更新节点属性
        self._graph.nodes[node_id].update(new_data)
        
        # 更新缓存
        if node_id in self._node_cache:
            self._node_cache[node_id] = new_data
        
        self._record_operation(StorageOperation.UPDATE, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.UPDATE,
            data={"node_id": node_id, **data},
            metadata={
                "record_type": "node",
                "node_id": node_id
            }
        )
    
    def _update_node_neo4j(self, node_id: str, data: Dict[str, Any], 
                          metadata: Optional[Dict[str, Any]]) -> StorageResult:
        """在Neo4j中更新节点"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            # 检查节点是否存在
            check_query = f"""
            MATCH (n:Node {{{self.config.node_id_field}: $id}})
            RETURN n
            """
            result = session.run(check_query, id=node_id)
            if not result.single():
                return StorageResult(
                    success=False,
                    operation=StorageOperation.UPDATE,
                    error=f"Node {node_id} not found"
                )
            
            # 准备更新属性
            set_clauses = []
            params = {"id": node_id}
            
            # 数据字段
            for i, (key, value) in enumerate(data.items()):
                if not key.startswith("_"):  # 跳过内部属性
                    param_name = f"val{i}"
                    set_clauses.append(f"n.{key} = ${param_name}")
                    params[param_name] = value
            
            # 元数据字段
            if metadata:
                for i, (key, value) in enumerate(metadata.items(), start=len(data)):
                    param_name = f"meta{i}"
                    set_clauses.append(f"n._metadata_{key} = ${param_name}")
                    params[param_name] = value
            
            # 内部属性
            set_clauses.append("n._updated_at = datetime()")
            
            # 如果有版本字段
            set_clauses.append("n._version = COALESCE(n._version, 0) + 1")
            
            # 执行更新
            if set_clauses:
                update_query = f"""
                MATCH (n:Node {{{self.config.node_id_field}: $id}})
                SET {', '.join(set_clauses)}
                RETURN n
                """
                
                result = session.run(update_query, **params)
                updated = result.single()
                
                if not updated:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.UPDATE,
                        error="Failed to update node"
                    )
            
            self._record_operation(StorageOperation.UPDATE, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.UPDATE,
                data={"node_id": node_id, **data},
                metadata={
                    "record_type": "node",
                    "node_id": node_id
                }
            )
    
    def _update_edge(self, edge_id: str, data: Dict[str, Any], 
                    metadata: Optional[Dict[str, Any]]) -> StorageResult:
        """更新边"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._update_edge_networkx(edge_id, data, metadata)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._update_edge_neo4j(edge_id, data, metadata)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _update_edge_networkx(self, edge_id: str, data: Dict[str, Any], 
                             metadata: Optional[Dict[str, Any]]) -> StorageResult:
        """在NetworkX中更新边"""
        # 查找边
        found_edge = None
        for u, v, edge_data in self._graph.edges(data=True):
            if edge_data.get("id") == edge_id:
                found_edge = (u, v, edge_data)
                break
        
        if not found_edge:
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error=f"Edge {edge_id} not found"
            )
        
        u, v, current_attrs = found_edge
        
        # 合并数据
        new_data = current_attrs.copy()
        
        # 更新数据字段（但不能更新源和目标）
        for key, value in data.items():
            if key not in ["source", "target", "from", "to"]:
                new_data[key] = value
        
        # 更新元数据
        if metadata:
            current_metadata = new_data.get("_metadata", {})
            current_metadata.update(metadata)
            new_data["_metadata"] = current_metadata
        
        # 更新内部属性
        new_data["_updated_at"] = datetime.now().isoformat()
        
        # 如果有版本号，增加版本
        if "_version" in new_data:
            new_data["_version"] = new_data["_version"] + 1
        
        # 更新边属性
        self._graph[u][v].update(new_data)
        
        # 更新缓存
        if edge_id in self._edge_cache:
            self._edge_cache[edge_id] = {
                "source": u,
                "target": v,
                **new_data
            }
        
        self._record_operation(StorageOperation.UPDATE, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.UPDATE,
            data={"edge_id": edge_id, **data},
            metadata={
                "record_type": "edge",
                "edge_id": edge_id,
                "source": u,
                "target": v
            }
        )
    
    def _update_edge_neo4j(self, edge_id: str, data: Dict[str, Any], 
                          metadata: Optional[Dict[str, Any]]) -> StorageResult:
        """在Neo4j中更新边"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.UPDATE,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            # 检查边是否存在
            check_query = f"""
            MATCH ()-[r {{{self.config.edge_id_field}: $id}}]-()
            RETURN r
            """
            result = session.run(check_query, id=edge_id)
            if not result.single():
                return StorageResult(
                    success=False,
                    operation=StorageOperation.UPDATE,
                    error=f"Edge {edge_id} not found"
                )
            
            # 准备更新属性（不能更新源和目标）
            set_clauses = []
            params = {"id": edge_id}
            
            # 数据字段（排除源和目标字段）
            filtered_data = {k: v for k, v in data.items() 
                           if k not in ["source", "target", "from", "to"]}
            
            for i, (key, value) in enumerate(filtered_data.items()):
                param_name = f"val{i}"
                set_clauses.append(f"r.{key} = ${param_name}")
                params[param_name] = value
            
            # 元数据字段
            if metadata:
                for i, (key, value) in enumerate(metadata.items(), start=len(filtered_data)):
                    param_name = f"meta{i}"
                    set_clauses.append(f"r._metadata_{key} = ${param_name}")
                    params[param_name] = value
            
            # 内部属性
            set_clauses.append("r._updated_at = datetime()")
            
            # 如果有版本字段
            set_clauses.append("r._version = COALESCE(r._version, 0) + 1")
            
            # 执行更新
            if set_clauses:
                update_query = f"""
                MATCH ()-[r {{{self.config.edge_id_field}: $id}}]-()
                SET {', '.join(set_clauses)}
                RETURN r
                """
                
                result = session.run(update_query, **params)
                updated = result.single()
                
                if not updated:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.UPDATE,
                        error="Failed to update edge"
                    )
            
            self._record_operation(StorageOperation.UPDATE, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.UPDATE,
                data={"edge_id": edge_id, **data},
                metadata={
                    "record_type": "edge",
                    "edge_id": edge_id
                }
            )
    
    def delete(self, record_id: str) -> StorageResult:
        """删除节点或边"""
        import time
        start_time = time.time()
        
        try:
            # 首先尝试删除节点
            node_result = self._delete_node(record_id)
            if node_result.success:
                execution_time = (time.time() - start_time) * 1000
                node_result.metadata["execution_time_ms"] = execution_time
                return node_result
            
            # 然后尝试删除边
            edge_result = self._delete_edge(record_id)
            if edge_result.success:
                execution_time = (time.time() - start_time) * 1000
                edge_result.metadata["execution_time_ms"] = execution_time
                return edge_result
            
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error=f"Record {record_id} not found",
                execution_time_ms=(time.time() - start_time) * 1000
            )
                
        except Exception as e:
            self._record_operation(StorageOperation.DELETE, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _delete_node(self, node_id: str) -> StorageResult:
        """删除节点"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._delete_node_networkx(node_id)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._delete_node_neo4j(node_id)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _delete_node_networkx(self, node_id: str) -> StorageResult:
        """在NetworkX中删除节点"""
        if node_id not in self._graph.nodes:
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error=f"Node {node_id} not found"
            )
        
        # 获取节点度（删除前）
        degree = self._graph.degree(node_id)
        
        # 删除节点（会自动删除关联的边）
        self._graph.remove_node(node_id)
        
        # 从缓存中移除
        if node_id in self._node_cache:
            del self._node_cache[node_id]
        
        self._record_operation(StorageOperation.DELETE, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.DELETE,
            data={"node_id": node_id},
            metadata={
                "record_type": "node",
                "node_id": node_id,
                "edges_deleted": degree
            }
        )
    
    def _delete_node_neo4j(self, node_id: str) -> StorageResult:
        """在Neo4j中删除节点"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            # 删除节点及其所有关系
            delete_query = f"""
            MATCH (n:Node {{{self.config.node_id_field}: $id}})
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """
            
            result = session.run(delete_query, id=node_id)
            deleted_count = result.single()["deleted_count"]
            
            if deleted_count == 0:
                return StorageResult(
                    success=False,
                    operation=StorageOperation.DELETE,
                    error=f"Node {node_id} not found"
                )
            
            self._record_operation(StorageOperation.DELETE, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.DELETE,
                data={"node_id": node_id},
                metadata={
                    "record_type": "node",
                    "node_id": node_id,
                    "deleted_count": deleted_count
                }
            )
    
    def _delete_edge(self, edge_id: str) -> StorageResult:
        """删除边"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            return self._delete_edge_networkx(edge_id)
        elif self.db_type == GraphDatabaseType.NEO4J:
            return self._delete_edge_neo4j(edge_id)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _delete_edge_networkx(self, edge_id: str) -> StorageResult:
        """在NetworkX中删除边"""
        # 查找边
        found_edge = None
        for u, v, edge_data in self._graph.edges(data=True):
            if edge_data.get("id") == edge_id:
                found_edge = (u, v)
                break
        
        if not found_edge:
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error=f"Edge {edge_id} not found"
            )
        
        u, v = found_edge
        
        # 删除边
        self._graph.remove_edge(u, v)
        
        # 从缓存中移除
        if edge_id in self._edge_cache:
            del self._edge_cache[edge_id]
        
        self._record_operation(StorageOperation.DELETE, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.DELETE,
            data={"edge_id": edge_id},
            metadata={
                "record_type": "edge",
                "edge_id": edge_id,
                "source": u,
                "target": v
            }
        )
    
    def _delete_edge_neo4j(self, edge_id: str) -> StorageResult:
        """在Neo4j中删除边"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.DELETE,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            # 删除边
            delete_query = f"""
            MATCH ()-[r {{{self.config.edge_id_field}: $id}}]-()
            DELETE r
            RETURN count(r) as deleted_count
            """
            
            result = session.run(delete_query, id=edge_id)
            deleted_count = result.single()["deleted_count"]
            
            if deleted_count == 0:
                return StorageResult(
                    success=False,
                    operation=StorageOperation.DELETE,
                    error=f"Edge {edge_id} not found"
                )
            
            self._record_operation(StorageOperation.DELETE, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.DELETE,
                data={"edge_id": edge_id},
                metadata={
                    "record_type": "edge",
                    "edge_id": edge_id,
                    "deleted_count": deleted_count
                }
            )
    
    def search(self, query: StorageQuery) -> StorageResult:
        """图搜索"""
        import time
        start_time = time.time()
        
        try:
            if self.db_type == GraphDatabaseType.NETWORKX:
                result = self._search_networkx(query)
            elif self.db_type == GraphDatabaseType.NEO4J:
                result = self._search_neo4j(query)
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
            
            execution_time = (time.time() - start_time) * 1000
            result.metadata["execution_time_ms"] = execution_time
            
            return result
                
        except Exception as e:
            self._record_operation(StorageOperation.SEARCH, False)
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _search_networkx(self, query: StorageQuery) -> StorageResult:
        """在NetworkX中搜索"""
        results = []
        
        # 节点搜索
        if "type" not in query.filters or query.filters.get("type") == "node":
            for node_id, node_attrs in self._graph.nodes(data=True):
                if self._matches_filters(node_attrs, query.filters, "node"):
                    results.append({
                        "type": "node",
                        "id": node_id,
                        "data": node_attrs,
                        "degree": self._graph.degree(node_id)
                    })
        
        # 边搜索
        if "type" not in query.filters or query.filters.get("type") == "edge":
            for u, v, edge_attrs in self._graph.edges(data=True):
                if self._matches_filters(edge_attrs, query.filters, "edge"):
                    results.append({
                        "type": "edge",
                        "id": edge_attrs.get("id", f"{u}_{v}"),
                        "source": u,
                        "target": v,
                        "data": edge_attrs
                    })
        
        # 应用排序
        if query.sort_by:
            results = self._apply_sorting(results, query.sort_by)
        
        # 应用分页
        if query.offset > 0:
            results = results[query.offset:]
        if query.limit:
            results = results[:query.limit]
        
        self._record_operation(StorageOperation.SEARCH, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.SEARCH,
            data=results,
            metadata={
                "total_results": len(results)
            }
        )
    
    def _search_neo4j(self, query: StorageQuery) -> StorageResult:
        """在Neo4j中搜索"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            # 构建查询
            cypher_query, params = self._build_cypher_query(query)
            
            # 执行查询
            result = session.run(cypher_query, **params)
            records = list(result)
            
            # 处理结果
            results = []
            for record in records:
                result_item = {}
                
                if "n" in record:
                    # 节点结果
                    node = record["n"]
                    node_id = node[self.config.node_id_field]
                    node_props = dict(node)
                    
                    results.append({
                        "type": "node",
                        "id": node_id,
                        "data": node_props,
                        "labels": list(node.labels)
                    })
                
                if "r" in record:
                    # 边结果
                    edge = record["r"]
                    edge_id = edge[self.config.edge_id_field]
                    edge_props = dict(edge)
                    
                    # 获取源和目标
                    source = record.get("a")
                    target = record.get("b")
                    
                    source_id = source[self.config.node_id_field] if source else None
                    target_id = target[self.config.node_id_field] if target else None
                    
                    results.append({
                        "type": "edge",
                        "id": edge_id,
                        "source": source_id,
                        "target": target_id,
                        "data": edge_props,
                        "relationship_type": record.get("relationship_type")
                    })
            
            # 应用排序和分页
            if query.sort_by:
                results = self._apply_sorting(results, query.sort_by)
            
            if query.offset > 0:
                results = results[query.offset:]
            if query.limit:
                results = results[:query.limit]
            
            self._record_operation(StorageOperation.SEARCH, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.SEARCH,
                data=results,
                metadata={
                    "total_results": len(results)
                }
            )
    
    def _build_cypher_query(self, query: StorageQuery) -> Tuple[str, Dict[str, Any]]:
        """构建Cypher查询"""
        # 简化的实现
        base_query = ""
        params = {}
        
        # 确定搜索类型
        search_type = query.filters.get("type", "both")
        
        if search_type == "node" or search_type == "both":
            base_query = "MATCH (n:Node) WHERE 1=1"
            
            # 添加过滤器
            where_clauses = []
            for key, value in query.filters.items():
                if key != "type":
                    param_name = f"param_{len(params)}"
                    where_clauses.append(f"n.{key} = ${param_name}")
                    params[param_name] = value
            
            if where_clauses:
                base_query += " AND " + " AND ".join(where_clauses)
            
            base_query += " RETURN n"
            
            # 限制
            if query.limit:
                base_query += f" LIMIT {query.limit}"
            if query.offset:
                base_query += f" SKIP {query.offset}"
        
        elif search_type == "edge":
            base_query = "MATCH (a)-[r]->(b) WHERE 1=1"
            
            # 添加过滤器
            where_clauses = []
            for key, value in query.filters.items():
                if key != "type":
                    param_name = f"param_{len(params)}"
                    where_clauses.append(f"r.{key} = ${param_name}")
                    params[param_name] = value
            
            if where_clauses:
                base_query += " AND " + " AND ".join(where_clauses)
            
            base_query += " RETURN a, r, b, type(r) as relationship_type"
            
            # 限制
            if query.limit:
                base_query += f" LIMIT {query.limit}"
            if query.offset:
                base_query += f" SKIP {query.offset}"
        
        return base_query, params
    
    def _matches_filters(self, attrs: Dict[str, Any], filters: Dict[str, Any], 
                        record_type: str) -> bool:
        """检查属性是否匹配过滤器"""
        for key, value in filters.items():
            if key == "type":
                # 已经处理过了
                continue
            
            if key not in attrs:
                return False
            
            if isinstance(value, dict):
                # 复杂过滤器
                for op, op_value in value.items():
                    if op == "$eq":
                        if attrs[key] != op_value:
                            return False
                    elif op == "$ne":
                        if attrs[key] == op_value:
                            return False
                    elif op == "$in":
                        if attrs[key] not in op_value:
                            return False
                    elif op == "$regex":
                        import re
                        if not re.search(op_value, str(attrs[key])):
                            return False
            else:
                # 简单相等
                if attrs[key] != value:
                    return False
        
        return True
    
    def _apply_sorting(self, results: List[Dict[str, Any]], 
                      sort_by: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """应用排序"""
        def sort_key(item):
            key = []
            for field_name, direction in sort_by:
                # 查找字段值
                value = None
                
                if field_name in item:
                    value = item[field_name]
                elif "data" in item and field_name in item["data"]:
                    value = item["data"][field_name]
                
                # 处理None值
                if value is None:
                    value = "" if direction == "asc" else "ZZZZZZZZZZ"
                
                # 根据排序方向调整
                if direction == "desc":
                    if isinstance(value, (int, float)):
                        value = -value
                    else:
                        value = str(value)
                
                key.append(value)
            return tuple(key)
        
        return sorted(results, key=sort_key)
    
    def traverse(self, start_node_id: str, max_depth: int = 3, 
                direction: str = "both") -> StorageResult:
        """图遍历"""
        import time
        start_time = time.time()
        
        try:
            if self.db_type == GraphDatabaseType.NETWORKX:
                result = self._traverse_networkx(start_node_id, max_depth, direction)
            elif self.db_type == GraphDatabaseType.NEO4J:
                result = self._traverse_neo4j(start_node_id, max_depth, direction)
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
            
            execution_time = (time.time() - start_time) * 1000
            result.metadata["execution_time_ms"] = execution_time
            
            return result
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _traverse_networkx(self, start_node_id: str, max_depth: int, 
                          direction: str) -> StorageResult:
        """在NetworkX中遍历"""
        if start_node_id not in self._graph.nodes:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=f"Start node {start_node_id} not found"
            )
        
        # 执行遍历
        if direction == "out":
            # 出方向遍历
            paths = []
            visited = set()
            
            def dfs(current, path, depth):
                if depth > max_depth:
                    return
                
                visited.add(current)
                path.append(current)
                
                for neighbor in self._graph.successors(current):
                    if neighbor not in visited:
                        dfs(neighbor, path.copy(), depth + 1)
                
                if len(path) > 1:  # 至少包含起始节点
                    paths.append(path.copy())
                
                visited.remove(current)
                path.pop()
            
            dfs(start_node_id, [], 0)
            
        elif direction == "in":
            # 入方向遍历
            paths = []
            visited = set()
            
            def dfs(current, path, depth):
                if depth > max_depth:
                    return
                
                visited.add(current)
                path.append(current)
                
                for neighbor in self._graph.predecessors(current):
                    if neighbor not in visited:
                        dfs(neighbor, path.copy(), depth + 1)
                
                if len(path) > 1:
                    paths.append(path.copy())
                
                visited.remove(current)
                path.pop()
            
            dfs(start_node_id, [], 0)
            
        else:  # both
            # 双向遍历
            paths = []
            visited = set()
            
            def dfs(current, path, depth):
                if depth > max_depth:
                    return
                
                visited.add(current)
                path.append(current)
                
                for neighbor in self._graph.neighbors(current):
                    if neighbor not in visited:
                        dfs(neighbor, path.copy(), depth + 1)
                
                if len(path) > 1:
                    paths.append(path.copy())
                
                visited.remove(current)
                path.pop()
            
            dfs(start_node_id, [], 0)
        
        self._record_operation(StorageOperation.SEARCH, True)
        
        return StorageResult(
            success=True,
            operation=StorageOperation.SEARCH,
            data=paths,
            metadata={
                "start_node": start_node_id,
                "max_depth": max_depth,
                "direction": direction,
                "path_count": len(paths)
            }
        )
    
    def _traverse_neo4j(self, start_node_id: str, max_depth: int, 
                       direction: str) -> StorageResult:
        """在Neo4j中遍历"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            # 构建遍历查询
            if direction == "out":
                relationship_pattern = "->"
            elif direction == "in":
                relationship_pattern = "<-"
            else:  # both
                relationship_pattern = "-"
            
            query = f"""
            MATCH path = (start:Node {{{self.config.node_id_field}: $start_id}})
            {relationship_pattern[:1]}[*1..{max_depth}]{relationship_pattern[1:]}(end)
            RETURN nodes(path) as nodes, relationships(path) as relationships
            """
            
            result = session.run(query, start_id=start_node_id)
            records = list(result)
            
            # 处理路径
            paths = []
            for record in records:
                nodes = record["nodes"]
                relationships = record["relationships"]
                
                # 提取节点ID
                node_ids = [node[self.config.node_id_field] for node in nodes]
                paths.append(node_ids)
            
            self._record_operation(StorageOperation.SEARCH, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.SEARCH,
                data=paths,
                metadata={
                    "start_node": start_node_id,
                    "max_depth": max_depth,
                    "direction": direction,
                    "path_count": len(paths)
                }
            )
    
    def get_shortest_path(self, start_node_id: str, end_node_id: str, 
                         weight_field: Optional[str] = None) -> StorageResult:
        """获取最短路径"""
        import time
        start_time = time.time()
        
        try:
            if self.db_type == GraphDatabaseType.NETWORKX:
                result = self._get_shortest_path_networkx(start_node_id, end_node_id, weight_field)
            elif self.db_type == GraphDatabaseType.NEO4J:
                result = self._get_shortest_path_neo4j(start_node_id, end_node_id, weight_field)
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
            
            execution_time = (time.time() - start_time) * 1000
            result.metadata["execution_time_ms"] = execution_time
            
            return result
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _get_shortest_path_networkx(self, start_node_id: str, end_node_id: str, 
                                   weight_field: Optional[str]) -> StorageResult:
        """在NetworkX中获取最短路径"""
        if start_node_id not in self._graph.nodes:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=f"Start node {start_node_id} not found"
            )
        
        if end_node_id not in self._graph.nodes:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=f"End node {end_node_id} not found"
            )
        
        try:
            if weight_field:
                # 带权重的路径
                path = nx.shortest_path(self._graph, start_node_id, end_node_id, 
                                       weight=weight_field)
                length = nx.shortest_path_length(self._graph, start_node_id, end_node_id, 
                                               weight=weight_field)
            else:
                # 无权路径
                path = nx.shortest_path(self._graph, start_node_id, end_node_id)
                length = nx.shortest_path_length(self._graph, start_node_id, end_node_id)
            
            self._record_operation(StorageOperation.SEARCH, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.SEARCH,
                data={
                    "path": path,
                    "length": length
                },
                metadata={
                    "start_node": start_node_id,
                    "end_node": end_node_id,
                    "path_length": len(path) - 1,  # 边数
                    "weighted": weight_field is not None
                }
            )
            
        except nx.NetworkXNoPath:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=f"No path found between {start_node_id} and {end_node_id}"
            )
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error=str(e)
            )
    
    def _get_shortest_path_neo4j(self, start_node_id: str, end_node_id: str, 
                                weight_field: Optional[str]) -> StorageResult:
        """在Neo4j中获取最短路径"""
        if not self._driver:
            return StorageResult(
                success=False,
                operation=StorageOperation.SEARCH,
                error="Neo4j driver not initialized"
            )
        
        with self._driver.session(database=self.config.database) as session:
            if weight_field:
                # 带权重的路径
                query = f"""
                MATCH (start:Node {{{self.config.node_id_field}: $start_id}})
                MATCH (end:Node {{{self.config.node_id_field}: $end_id}})
                MATCH path = shortestPath((start)-[*]-(end))
                WHERE ALL(r IN relationships(path) WHERE r.{weight_field} IS NOT NULL)
                RETURN nodes(path) as nodes, 
                       relationships(path) as relationships,
                       reduce(total = 0, r IN relationships(path) | total + r.{weight_field}) as total_weight
                """
            else:
                # 无权路径
                query = f"""
                MATCH (start:Node {{{self.config.node_id_field}: $start_id}})
                MATCH (end:Node {{{self.config.node_id_field}: $end_id}})
                MATCH path = shortestPath((start)-[*]-(end))
                RETURN nodes(path) as nodes, 
                       relationships(path) as relationships,
                       length(path) as path_length
                """
            
            result = session.run(query, start_id=start_node_id, end_id=end_node_id)
            record = result.single()
            
            if not record:
                return StorageResult(
                    success=False,
                    operation=StorageOperation.SEARCH,
                    error=f"No path found between {start_node_id} and {end_node_id}"
                )
            
            # 提取节点ID
            nodes = record["nodes"]
            node_ids = [node[self.config.node_id_field] for node in nodes]
            
            if weight_field:
                length = record["total_weight"]
            else:
                length = record["path_length"]
            
            self._record_operation(StorageOperation.SEARCH, True)
            
            return StorageResult(
                success=True,
                operation=StorageOperation.SEARCH,
                data={
                    "path": node_ids,
                    "length": length
                },
                metadata={
                    "start_node": start_node_id,
                    "end_node": end_node_id,
                    "path_length": len(node_ids) - 1,
                    "weighted": weight_field is not None
                }
            )
    
    def get_graph_statistics(self) -> StorageResult:
        """获取图统计信息"""
        import time
        start_time = time.time()
        
        try:
            if self.db_type == GraphDatabaseType.NETWORKX:
                stats = self._get_graph_statistics_networkx()
            elif self.db_type == GraphDatabaseType.NEO4J:
                stats = self._get_graph_statistics_neo4j()
            else:
                stats = {}
            
            execution_time = (time.time() - start_time) * 1000
            
            return StorageResult(
                success=True,
                operation=StorageOperation.READ,
                data=stats,
                metadata={
                    "execution_time_ms": execution_time
                }
            )
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.READ,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _get_graph_statistics_networkx(self) -> Dict[str, Any]:
        """获取NetworkX图统计"""
        stats = {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "is_directed": self._graph.is_directed(),
            "is_multigraph": self._graph.is_multigraph(),
            "density": nx.density(self._graph) if self._graph.number_of_nodes() > 1 else 0,
            "connected_components": nx.number_connected_components(self._graph.to_undirected()) 
                if not self._graph.is_directed() else 0,
            "strongly_connected_components": nx.number_strongly_connected_components(self._graph) 
                if self._graph.is_directed() else 0
        }
        
        # 度分布
        if self._graph.number_of_nodes() > 0:
            degrees = [deg for _, deg in self._graph.degree()]
            stats["average_degree"] = sum(degrees) / len(degrees)
            stats["max_degree"] = max(degrees) if degrees else 0
            stats["min_degree"] = min(degrees) if degrees else 0
        
        return stats
    
    def _get_graph_statistics_neo4j(self) -> Dict[str, Any]:
        """获取Neo4j图统计"""
        if not self._driver:
            return {}
        
        with self._driver.session(database=self.config.database) as session:
            # 获取节点和边数量
            count_query = """
            MATCH (n:Node)
            WITH count(n) as node_count
            MATCH ()-[r]->()
            RETURN node_count, count(r) as edge_count
            """
            
            result = session.run(count_query)
            record = result.single()
            
            if not record:
                return {}
            
            stats = {
                "node_count": record["node_count"],
                "edge_count": record["edge_count"]
            }
            
            return stats
    
    def export_graph(self, filepath: str, format: str = "graphml") -> StorageResult:
        """导出图"""
        import time
        start_time = time.time()
        
        try:
            if self.db_type == GraphDatabaseType.NETWORKX:
                if format == "graphml":
                    nx.write_graphml(self._graph, filepath)
                elif format == "gexf":
                    nx.write_gexf(self._graph, filepath)
                elif format == "json":
                    # NetworkX原生JSON格式
                    import json
                    graph_data = nx.node_link_data(self._graph)
                    with open(filepath, 'w') as f:
                        json.dump(graph_data, f, indent=2)
                else:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.CREATE,
                        error=f"Unsupported export format: {format}"
                    )
            else:
                return StorageResult(
                    success=False,
                    operation=StorageOperation.CREATE,
                    error="Export only supported for NetworkX backend"
                )
            
            execution_time = (time.time() - start_time) * 1000
            
            return StorageResult(
                success=True,
                operation=StorageOperation.CREATE,
                data={"filepath": filepath, "format": format},
                metadata={
                    "execution_time_ms": execution_time,
                    "node_count": self._graph.number_of_nodes(),
                    "edge_count": self._graph.number_of_edges()
                }
            )
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.CREATE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def import_graph(self, filepath: str, format: str = "graphml") -> StorageResult:
        """导入图"""
        import time
        start_time = time.time()
        
        try:
            if self.db_type == GraphDatabaseType.NETWORKX:
                if format == "graphml":
                    imported_graph = nx.read_graphml(filepath)
                elif format == "gexf":
                    imported_graph = nx.read_gexf(filepath)
                elif format == "json":
                    import json
                    with open(filepath, 'r') as f:
                        graph_data = json.load(f)
                    imported_graph = nx.node_link_graph(graph_data)
                else:
                    return StorageResult(
                        success=False,
                        operation=StorageOperation.CREATE,
                        error=f"Unsupported import format: {format}"
                    )
                
                # 合并到当前图
                self._graph = imported_graph
                
                # 重建缓存
                self._rebuild_caches()
                
            else:
                return StorageResult(
                    success=False,
                    operation=StorageOperation.CREATE,
                    error="Import only supported for NetworkX backend"
                )
            
            execution_time = (time.time() - start_time) * 1000
            
            return StorageResult(
                success=True,
                operation=StorageOperation.CREATE,
                data={"filepath": filepath, "format": format},
                metadata={
                    "execution_time_ms": execution_time,
                    "node_count": self._graph.number_of_nodes(),
                    "edge_count": self._graph.number_of_edges()
                }
            )
                
        except Exception as e:
            return StorageResult(
                success=False,
                operation=StorageOperation.CREATE,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _rebuild_caches(self):
        """重建缓存"""
        self._node_cache.clear()
        self._edge_cache.clear()
        
        # 重建节点缓存
        for node_id, node_attrs in self._graph.nodes(data=True):
            self._node_cache[node_id] = node_attrs
        
        # 重建边缓存
        for u, v, edge_attrs in self._graph.edges(data=True):
            edge_id = edge_attrs.get("id", f"{u}_{v}")
            self._edge_cache[edge_id] = {
                "source": u,
                "target": v,
                **edge_attrs
            }
    
    def clear(self):
        """清空图"""
        if self.db_type == GraphDatabaseType.NETWORKX:
            self._graph.clear()
        elif self.db_type == GraphDatabaseType.NEO4J:
            if self._driver:
                with self._driver.session(database=self.config.database) as session:
                    session.run("MATCH (n) DETACH DELETE n")
        
        self._node_cache.clear()
        self._edge_cache.clear()
    
    def close(self):
        """关闭存储"""
        if self.db_type == GraphDatabaseType.NEO4J and self._driver:
            self._driver.close()
        
        self.initialized = False