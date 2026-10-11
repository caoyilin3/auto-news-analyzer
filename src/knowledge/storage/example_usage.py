"""
存储模块使用示例
"""

import json
from datetime import datetime
from typing import Dict, Any

# 导入存储模块
from .base_storage import StorageRecord, StorageQuery, StorageResult
from .memory_storage import MemoryStorage, MemoryStorageConfig
from .sql_storage import SQLStorage, SQLStorageConfig, DatabaseType
from .vector_storage import VectorStorage, VectorStorageConfig, VectorIndexType
from .graph_storage import GraphStorage, GraphStorageConfig, GraphDatabaseType
from .hybrid_storage import HybridStorage, HybridStorageConfig, StorageStrategy

def example_memory_storage():
    """内存存储示例"""
    print("=== Memory Storage Example ===")
    
    # 创建配置
    config = MemoryStorageConfig(
        max_size=1000,
        auto_cleanup=True,
        ttl_seconds=3600  # 1小时
    )
    
    # 创建存储
    storage = MemoryStorage(config)
    storage.initialize()
    
    # 创建记录
    record = StorageRecord(
        id="test_memory_1",
        data={
            "name": "Test Record",
            "value": 42,
            "description": "A test record for memory storage"
        },
        metadata={
            "category": "test",
            "priority": "high"
        }
    )
    
    # 存储记录
    result = storage.create(record)
    print(f"Create result: {result.success}")
    
    # 读取记录
    result = storage.read("test_memory_1")
    if result.success:
        record = result.data
        print(f"Read record: {record.id}, data: {record.data}")
    
    # 搜索记录
    query = StorageQuery(
        filters={"category": "test"},
        limit=10
    )
    result = storage.search(query)
    print(f"Search found {len(result.data) if result.data else 0} records")
    
    # 获取统计信息
    stats = storage.get_statistics()
    print(f"Storage statistics: {stats}")
    
    storage.close()
    return storage

def example_sql_storage():
    """SQL存储示例"""
    print("\n=== SQL Storage Example ===")
    
    # 创建配置（使用SQLite）
    config = SQLStorageConfig(
        db_type=DatabaseType.SQLITE,
        db_name="test.db",
        table_name="test_records"
    )
    
    # 创建存储
    storage = SQLStorage(config)
    storage.initialize()
    
    # 创建记录
    records = []
    for i in range(5):
        record = StorageRecord(
            id=f"test_sql_{i}",
            data={
                "index": i,
                "name": f"Record {i}",
                "data": f"Sample data for record {i}"
            },
            metadata={
                "created_by": "example",
                "batch": "test"
            }
        )
        records.append(record)
    
    # 批量创建
    result = storage.batch_create(records)
    print(f"Batch create: {result.success}, created: {result.metadata.get('success_count', 0)}")
    
    # 搜索记录
    query = StorageQuery(
        filters={"batch": "test"},
        sort_by=[("index", "asc")],
        limit=10
    )
    result = storage.search(query)
    if result.success:
        print(f"Found {len(result.data)} records")
        for record in result.data:
            print(f"  - {record.id}: {record.data.get('name')}")
    
    # 获取表统计
    result = storage.get_table_stats()
    if result.success:
        print(f"Table stats: {result.data}")
    
    storage.close()
    return storage

def example_vector_storage():
    """向量存储示例"""
    print("\n=== Vector Storage Example ===")
    
    # 创建配置
    config = VectorStorageConfig(
        vector_dimension=384,
        index_type=VectorIndexType.FLAT,
        similarity_threshold=0.7
    )
    
    # 创建存储
    storage = VectorStorage(config)
    storage.initialize()
    
    # 创建带有文本的记录
    texts = [
        "人工智能是计算机科学的一个分支",
        "机器学习是人工智能的核心技术",
        "深度学习使用神经网络进行学习",
        "自然语言处理让计算机理解人类语言",
        "计算机视觉让计算机看懂世界"
    ]
    
    for i, text in enumerate(texts):
        record = StorageRecord(
            id=f"text_{i}",
            data={
                "text": text,
                "index": i
            },
            metadata={
                "type": "ai_concept",
                "language": "zh"
            }
        )
        
        result = storage.create(record)
        print(f"Created vector record {i}: {result.success}")
    
    # 文本相似性搜索
    query_text = "什么是人工智能？"
    result = storage.search_by_text(query_text, limit=3)
    
    if result.success:
        print(f"Search for '{query_text}' found {len(result.data)} results:")
        for item in result.data:
            print(f"  - ID: {item['record_id']}, Similarity: {item['similarity']:.3f}")
    
    # 获取统计信息
    stats = storage.get_statistics()
    print(f"Vector storage stats: vector_count={stats.get('vector_count', 0)}")
    
    storage.close()
    return storage

def example_graph_storage():
    """图存储示例"""
    print("\n=== Graph Storage Example ===")
    
    # 创建配置（使用NetworkX内存图）
    config = GraphStorageConfig(
        db_type=GraphDatabaseType.NETWORKX,
        directed=True
    )
    
    # 创建存储
    storage = GraphStorage(config)
    storage.initialize()
    
    # 创建节点
    nodes = [
        StorageRecord(
            id="person_1",
            data={
                "name": "Alice",
                "age": 30,
                "occupation": "Engineer"
            },
            metadata={
                "type": "person",
                "label": "Person"
            }
        ),
        StorageRecord(
            id="person_2",
            data={
                "name": "Bob",
                "age": 35,
                "occupation": "Scientist"
            },
            metadata={
                "type": "person",
                "label": "Person"
            }
        ),
        StorageRecord(
            id="company_1",
            data={
                "name": "TechCorp",
                "industry": "Technology"
            },
            metadata={
                "type": "organization",
                "label": "Company"
            }
        )
    ]
    
    for node in nodes:
        result = storage.create(node)
        print(f"Created node {node.id}: {result.success}")
    
    # 创建边（关系）
    edges = [
        StorageRecord(
            id="works_at_1",
            data={
                "source": "person_1",
                "target": "company_1",
                "role": "Senior Engineer",
                "since": "2020"
            },
            metadata={
                "type": "employment",
                "label": "WORKS_AT"
            }
        ),
        StorageRecord(
            id="works_at_2",
            data={
                "source": "person_2",
                "target": "company_1",
                "role": "Research Lead",
                "since": "2019"
            },
            metadata={
                "type": "employment",
                "label": "WORKS_AT"
            }
        ),
        StorageRecord(
            id="knows_1",
            data={
                "source": "person_1",
                "target": "person_2",
                "since": "2018"
            },
            metadata={
                "type": "social",
                "label": "KNOWS"
            }
        )
    ]
    
    for edge in edges:
        result = storage.create(edge)
        print(f"Created edge {edge.id}: {result.success}")
    
    # 图遍历
    result = storage.traverse("person_1", max_depth=2, direction="out")
    if result.success:
        print(f"Traversal from person_1 found {len(result.data)} paths:")
        for path in result.data[:3]:  # 显示前3条路径
            print(f"  - {' -> '.join(path)}")
    
    # 获取图统计
    result = storage.get_graph_statistics()
    if result.success:
        stats = result.data
        print(f"Graph stats: nodes={stats.get('node_count', 0)}, edges={stats.get('edge_count', 0)}")
    
    storage.close()
    return storage

def example_hybrid_storage():
    """混合存储示例"""
    print("\n=== Hybrid Storage Example ===")
    
    # 创建配置
    config = HybridStorageConfig(
        default_strategy=StorageStrategy.AUTO,
        
        # 配置各个后端
        memory_config=MemoryStorageConfig(max_size=1000),
        sql_config=SQLStorageConfig(
            db_type=DatabaseType.SQLITE,
            db_name="hybrid.db"
        ),
        vector_config=VectorStorageConfig(
            vector_dimension=384,
            index_type=VectorIndexType.FLAT
        ),
        
        # 缓存配置
        cache_enabled=True,
        cache_max_size=5000,
        cache_ttl_seconds=600
    )
    
    # 创建混合存储
    storage = HybridStorage(config)
    storage.initialize()
    
    # 添加路由规则
    storage.add_routing_rule("vector", StorageBackend.VECTOR)
    storage.add_routing_rule("graph", StorageBackend.GRAPH)
    
    # 创建不同类型的记录
    records = [
        # 向量记录
        StorageRecord(
            id="doc_1",
            data={
                "text": "人工智能正在改变世界",
                "vector": [0.1] * 384  # 模拟向量
            },
            metadata={
                "type": "vector",
                "category": "ai_article"
            }
        ),
        
        # 通用记录（将根据大小决定存储位置）
        StorageRecord(
            id="config_1",
            data={
                "setting": "max_connections",
                "value": 100,
                "description": "Maximum database connections"
            },
            metadata={
                "type": "configuration",
                "application": "main"
            }
        ),
        
        # 小记录（可能存储在内存中）
        StorageRecord(
            id="cache_1",
            data={
                "key": "user_session",
                "value": "session_token_123",
                "expires": "2024-12-31"
            },
            metadata={
                "type": "cache",
                "ttl": 3600
            }
        )
    ]
    
    # 存储记录
    for record in records:
        result = storage.create(record)
        print(f"Created {record.id} ({record.metadata.get('type', 'unknown')}): {result.success}")
    
    # 读取记录（可能会从缓存中获取）
    result = storage.read("cache_1")
    if result.success:
        print(f"Read from {result.metadata.get('source', 'unknown')}: {result.data.id}")
    
    # 搜索记录
    query = StorageQuery(
        filters={"type": "configuration"},
        limit=10
    )
    result = storage.search(query)
    print(f"Search found {len(result.data) if result.data else 0} records")
    
    # 获取性能统计
    stats = storage.get_performance_stats()
    print(f"Hybrid storage stats: active_backends={stats.get('active_backends', [])}")
    
    # 同步后端数据
    if storage._sql_storage and storage._memory_storage:
        result = storage.sync_backends(
            StorageBackend.MEMORY,
            StorageBackend.SQL
        )
        print(f"Sync result: {result.success}, synced {result.data.get('synced_count', 0)} records")
    
    storage.close()
    return storage

def example_integration():
    """集成示例：使用多个存储后端"""
    print("\n=== Storage Integration Example ===")
    
    # 创建不同类型的存储
    memory_storage = MemoryStorage(MemoryStorageConfig(max_size=100))
    sql_storage = SQLStorage(SQLStorageConfig(db_type=DatabaseType.SQLITE, db_name="integration.db"))
    vector_storage = VectorStorage(VectorStorageConfig(vector_dimension=100))
    
    # 初始化所有存储
    memory_storage.initialize()
    sql_storage.initialize()
    vector_storage.initialize()
    
    # 根据数据类型选择存储
    test_data = [
        ("memory_record", {"type": "cache", "data": "small data"}, memory_storage),
        ("sql_record", {"type": "persistent", "data": "important data"}, sql_storage),
        ("vector_record", {"type": "text", "data": "sample text for vectorization"}, vector_storage)
    ]
    
    for record_id, data, target_storage in test_data:
        record = StorageRecord(
            id=record_id,
            data=data,
            metadata={"stored_at": datetime.now().isoformat()}
        )
        
        result = target_storage.create(record)
        print(f"Stored {record_id} in {target_storage.__class__.__name__}: {result.success}")
    
    # 从各个存储中读取
    for record_id, _, target_storage in test_data:
        result = target_storage.read(record_id)
        if result.success:
            print(f"Retrieved {record_id} from {target_storage.__class__.__name__}")
    
    # 清理
    memory_storage.close()
    sql_storage.close()
    vector_storage.close()

def run_all_examples():
    """运行所有示例"""
    print("Running storage module examples...")
    
    try:
        # 运行各个示例
        example_memory_storage()
        example_sql_storage()
        example_vector_storage()
        example_graph_storage()
        example_hybrid_storage()
        example_integration()
        
        print("\n✅ All storage examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error in storage examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_examples()