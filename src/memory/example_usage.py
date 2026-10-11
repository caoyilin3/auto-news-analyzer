"""
记忆模块使用示例
"""

import asyncio
from datetime import datetime, timedelta
from .memory_manager import MemoryManager, MemoryRecord, MemoryType, MemoryState
from .importance_evaluator import ImportanceEvaluator
from .retention_policy import RetentionPolicy, RetentionStrategy
from .forgetting_algorithm import ForgettingAlgorithm, ForgettingStrategy

def example_basic_usage():
    """基础使用示例"""
    
    # 1. 创建记忆管理器
    memory_manager = MemoryManager(
        capacity=1000,
        persistence_path="./data/memory_store.json"
    )
    
    # 2. 添加记忆
    memory_id = memory_manager.add_memory(
        content="Python是一种高级编程语言",
        memory_type=MemoryType.FACT,
        metadata={
            "source": "wikipedia",
            "confidence": 0.9,
            "tags": ["programming", "python", "language"]
        },
        importance_score=0.8
    )
    
    print(f"Added memory with ID: {memory_id}")
    
    # 3. 获取记忆
    memory = memory_manager.get_memory(memory_id)
    if memory:
        print(f"Retrieved memory: {memory.content}")
    
    # 4. 搜索记忆
    results = memory_manager.search_memories(
        query="python",
        tags=["programming"],
        min_importance=0.5
    )
    
    print(f"Found {len(results)} memories")
    
    # 5. 获取统计信息
    stats = memory_manager.get_statistics()
    print(f"Memory statistics: {stats}")
    
    return memory_manager

def example_importance_evaluation():
    """重要性评估示例"""
    
    # 创建评估器
    evaluator = ImportanceEvaluator()
    
    # 创建测试记忆数据
    memory_data = {
        "content": "人工智能正在改变世界",
        "metadata": {
            "source": "tech_news",
            "confidence": 0.85,
            "created_at": datetime.now(),
            "domain": "technology"
        }
    }
    
    # 评估重要性
    context = {
        "topics": ["ai", "technology", "innovation"],
        "current_focus": "artificial intelligence"
    }
    
    score = evaluator.evaluate(
        memory_data["content"],
        memory_data["metadata"],
        context
    )
    
    print(f"Importance score: {score.overall:.2f}")
    print(f"Score components: {score.components}")
    
    return score

def example_retention_policy():
    """保留策略示例"""
    
    # 创建保留策略
    policy = RetentionPolicy(strategy=RetentionStrategy.ADAPTIVE)
    
    # 测试记忆数据
    test_memory = {
        "id": "test_memory_1",
        "importance_score": 0.4,
        "age_days": 100,
        "access_count": 5,
        "last_accessed_days": 30,
        "is_critical": False
    }
    
    # 评估保留决策
    decision = policy.evaluate_memory(test_memory)
    
    print(f"Retention decision: {decision.action}")
    print(f"Confidence: {decision.confidence:.2f}")
    print(f"Reason: {decision.reason}")
    
    return decision

def example_forgetting_algorithm():
    """遗忘算法示例"""
    
    # 创建遗忘算法
    algorithm = ForgettingAlgorithm(strategy=ForgettingStrategy.GRADUAL)
    
    # 创建测试记忆列表
    test_memories = []
    for i in range(20):
        memory = {
            "id": f"test_memory_{i}",
            "content": f"Test content {i}",
            "importance_score": i * 0.05,  # 0.0到0.95
            "retention_score": max(0.1, 1.0 - i * 0.05),
            "age_days": i * 10,
            "access_count": i
        }
        test_memories.append(memory)
    
    # 选择要遗忘的记忆
    memories_to_forget = algorithm.select_memories_to_forget(
        test_memories,
        target_count=5
    )
    
    print(f"Selected {len(memories_to_forget)} memories to forget:")
    for memory in memories_to_forget:
        print(f"  - {memory['id']} (importance: {memory['importance_score']:.2f})")
    
    return memories_to_forget

def example_integrated_workflow():
    """集成工作流示例"""
    
    print("=== Memory Management Integrated Workflow ===")
    
    # 1. 初始化组件
    memory_manager = MemoryManager(capacity=100)
    importance_evaluator = ImportanceEvaluator()
    retention_policy = RetentionPolicy()
    forgetting_algorithm = ForgettingAlgorithm()
    
    # 2. 添加一些记忆
    memories_added = []
    
    sample_contents = [
        "机器学习是人工智能的一个分支",
        "深度学习使用神经网络",
        "强化学习通过试错学习",
        "监督学习需要标注数据",
        "无监督学习发现数据中的模式"
    ]
    
    for i, content in enumerate(sample_contents):
        memory_id = memory_manager.add_memory(
            content=content,
            memory_type=MemoryType.FACT,
            metadata={
                "source": "ai_textbook",
                "confidence": 0.9,
                "tags": ["ai", "machine_learning"]
            }
        )
        memories_added.append(memory_id)
    
    print(f"Added {len(memories_added)} memories")
    
    # 3. 模拟访问一些记忆
    for i in range(3):
        memory_manager.get_memory(memories_added[i])
        memory_manager.reinforce_memory(memories_added[i])
    
    # 4. 评估记忆重要性
    for memory_id in memories_added:
        memory = memory_manager.get_memory(memory_id)
        if memory:
            score = importance_evaluator.evaluate(
                memory.content,
                memory.metadata.__dict__
            )
            # 更新记忆的重要性分数
            memory.importance_score = score.overall
    
    # 5. 应用记忆衰减
    memory_manager.apply_decay(decay_rate=0.02)
    
    # 6. 检查是否需要遗忘
    stats = memory_manager.get_statistics()
    
    if stats["total_memories"] > memory_manager.capacity * 0.8:
        print("Memory capacity nearing limit. Applying forgetting algorithm...")
        
        all_memories = list(memory_manager.memories.values())
        memories_to_forget = forgetting_algorithm.select_memories_to_forget(
            all_memories,
            target_count=5
        )
        
        # 执行遗忘
        for memory in memories_to_forget:
            memory_manager.forget_memory(memory.id, "capacity_management")
    
    # 7. 最终统计
    final_stats = memory_manager.get_statistics()
    print(f"Final memory statistics: {final_stats}")
    
    return {
        "manager": memory_manager,
        "stats": final_stats
    }

if __name__ == "__main__":
    # 运行示例
    print("Running memory module examples...")
    print("\n1. Basic Usage Example:")
    example_basic_usage()
    
    print("\n2. Importance Evaluation Example:")
    example_importance_evaluation()
    
    print("\n3. Retention Policy Example:")
    example_retention_policy()
    
    print("\n4. Forgetting Algorithm Example:")
    example_forgetting_algorithm()
    
    print("\n5. Integrated Workflow Example:")
    example_integrated_workflow()