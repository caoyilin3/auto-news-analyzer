"""
记忆管理器
负责记忆的存储、检索、更新和生命周期管理
"""

import json
import uuid
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set
from dataclasses import dataclass, field, asdict
import numpy as np
from collections import defaultdict, deque
import pickle
import hashlib

class MemoryType(Enum):
    """记忆类型枚举"""
    FACT = "fact"           # 事实性记忆
    EVENT = "event"         # 事件记忆
    SKILL = "skill"         # 技能记忆
    PATTERN = "pattern"     # 模式记忆
    RELATIONSHIP = "relationship"  # 关系记忆
    GOAL = "goal"           # 目标记忆
    EXPERIENCE = "experience"  # 经验记忆
    METACOGNITIVE = "metacognitive"  # 元认知记忆

class MemoryState(Enum):
    """记忆状态枚举"""
    ACTIVE = "active"       # 活跃状态
    DORMANT = "dormant"     # 休眠状态
    FORGOTTEN = "forgotten" # 已遗忘
    ARCHIVED = "archived"   # 归档状态

@dataclass
class MemoryMetadata:
    """记忆元数据"""
    source: str = ""                     # 记忆来源
    confidence: float = 1.0              # 置信度
    created_by: str = "system"           # 创建者
    version: int = 1                     # 版本号
    tags: List[str] = field(default_factory=list)  # 标签
    dependencies: List[str] = field(default_factory=list)  # 依赖的记忆ID
    related_memories: List[str] = field(default_factory=list)  # 相关记忆ID

@dataclass
class MemoryAccessRecord:
    """记忆访问记录"""
    timestamp: datetime
    access_type: str  # read, update, reinforce, associate
    context: Dict[str, Any]
    retention_boost: float = 0.0  # 本次访问对记忆保留的增强

@dataclass
class MemoryRecord:
    """记忆记录数据类"""
    id: str
    content: Any
    memory_type: MemoryType
    metadata: MemoryMetadata
    
    # 时间属性
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    
    # 记忆属性
    importance_score: float = 0.5
    retention_score: float = 1.0
    activation_level: float = 0.0
    state: MemoryState = MemoryState.ACTIVE
    
    # 访问历史
    access_history: List[MemoryAccessRecord] = field(default_factory=list)
    access_count: int = 0
    
    # 关联记忆
    associations: Dict[str, float] = field(default_factory=dict)  # 关联记忆ID -> 关联强度
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理datetime对象
        for time_field in ['created_at', 'updated_at', 'last_accessed']:
            if time_field in data and data[time_field]:
                data[time_field] = data[time_field].isoformat()
        
        # 处理MemoryAccessRecord中的datetime
        if 'access_history' in data:
            for record in data['access_history']:
                if 'timestamp' in record and record['timestamp']:
                    record['timestamp'] = record['timestamp'].isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryRecord':
        """从字典创建MemoryRecord"""
        # 处理datetime字符串
        time_fields = ['created_at', 'updated_at', 'last_accessed']
        for field in time_fields:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])
        
        # 处理access_history中的datetime
        if 'access_history' in data:
            for record in data['access_history']:
                if 'timestamp' in record and isinstance(record['timestamp'], str):
                    record['timestamp'] = datetime.fromisoformat(record['timestamp'])
        
        # 创建对象
        memory = cls(
            id=data['id'],
            content=data['content'],
            memory_type=MemoryType(data['memory_type']),
            metadata=MemoryMetadata(**data['metadata']),
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            last_accessed=data['last_accessed'],
            importance_score=data['importance_score'],
            retention_score=data['retention_score'],
            activation_level=data['activation_level'],
            state=MemoryState(data['state']),
            access_history=[MemoryAccessRecord(**r) for r in data['access_history']],
            access_count=data['access_count'],
            associations=data.get('associations', {})
        )
        
        return memory
    
    def record_access(self, access_type: str = "read", context: Dict[str, Any] = None):
        """记录访问"""
        self.last_accessed = datetime.now()
        self.access_count += 1
        
        record = MemoryAccessRecord(
            timestamp=datetime.now(),
            access_type=access_type,
            context=context or {},
            retention_boost=self._calculate_retention_boost(access_type)
        )
        
        self.access_history.append(record)
        
        # 限制历史记录长度
        if len(self.access_history) > 100:
            self.access_history = self.access_history[-100:]
    
    def _calculate_retention_boost(self, access_type: str) -> float:
        """计算保留增强值"""
        boosts = {
            "read": 0.1,
            "update": 0.3,
            "reinforce": 0.5,
            "associate": 0.2
        }
        return boosts.get(access_type, 0.05)
    
    def reinforce(self, strength: float = 0.1):
        """增强记忆"""
        self.retention_score = min(1.0, self.retention_score + strength)
        self.activation_level = min(1.0, self.activation_level + strength * 0.5)
        self.record_access("reinforce", {"strength": strength})
    
    def decay(self, decay_rate: float = 0.01):
        """记忆衰减"""
        self.retention_score = max(0.0, self.retention_score - decay_rate)
        
        # 如果retention_score过低，进入休眠状态
        if self.retention_score < 0.2 and self.state == MemoryState.ACTIVE:
            self.state = MemoryState.DORMANT
    
    def add_association(self, other_memory_id: str, strength: float = 0.1):
        """添加关联记忆"""
        if other_memory_id == self.id:
            return
        
        current_strength = self.associations.get(other_memory_id, 0)
        new_strength = min(1.0, current_strength + strength)
        self.associations[other_memory_id] = new_strength
        
        # 对称关联（在实际实现中可能需要双向关联）
        self.record_access("associate", {
            "associated_memory": other_memory_id,
            "strength": new_strength
        })


class MemoryIndex:
    """记忆索引"""
    
    def __init__(self):
        self.index_by_type: Dict[MemoryType, Set[str]] = defaultdict(set)
        self.index_by_tag: Dict[str, Set[str]] = defaultdict(set)
        self.index_by_source: Dict[str, Set[str]] = defaultdict(set)
        self.index_by_state: Dict[MemoryState, Set[str]] = defaultdict(set)
        self.content_hash_index: Dict[str, str] = {}  # 内容哈希 -> 记忆ID
    
    def add_memory(self, memory: MemoryRecord):
        """添加记忆到索引"""
        # 按类型索引
        self.index_by_type[memory.memory_type].add(memory.id)
        
        # 按标签索引
        for tag in memory.metadata.tags:
            self.index_by_tag[tag].add(memory.id)
        
        # 按来源索引
        if memory.metadata.source:
            self.index_by_source[memory.metadata.source].add(memory.id)
        
        # 按状态索引
        self.index_by_state[memory.state].add(memory.id)
        
        # 内容哈希索引
        content_hash = self._hash_content(memory.content)
        self.content_hash_index[content_hash] = memory.id
    
    def remove_memory(self, memory: MemoryRecord):
        """从索引中移除记忆"""
        self.index_by_type[memory.memory_type].discard(memory.id)
        
        for tag in memory.metadata.tags:
            self.index_by_tag[tag].discard(memory.id)
        
        if memory.metadata.source:
            self.index_by_source[memory.metadata.source].discard(memory.id)
        
        self.index_by_state[memory.state].discard(memory.id)
        
        content_hash = self._hash_content(memory.content)
        if content_hash in self.content_hash_index:
            del self.content_hash_index[content_hash]
    
    def update_memory(self, old_memory: MemoryRecord, new_memory: MemoryRecord):
        """更新索引中的记忆"""
        self.remove_memory(old_memory)
        self.add_memory(new_memory)
    
    def search_by_type(self, memory_type: MemoryType) -> List[str]:
        """按类型搜索"""
        return list(self.index_by_type.get(memory_type, set()))
    
    def search_by_tag(self, tag: str) -> List[str]:
        """按标签搜索"""
        return list(self.index_by_tag.get(tag, set()))
    
    def search_by_state(self, state: MemoryState) -> List[str]:
        """按状态搜索"""
        return list(self.index_by_state.get(state, set()))
    
    def search_by_source(self, source: str) -> List[str]:
        """按来源搜索"""
        return list(self.index_by_source.get(source, set()))
    
    def find_duplicate(self, content: Any) -> Optional[str]:
        """查找重复内容"""
        content_hash = self._hash_content(content)
        return self.content_hash_index.get(content_hash)
    
    def _hash_content(self, content: Any) -> str:
        """计算内容哈希"""
        if isinstance(content, (str, int, float, bool, type(None))):
            content_str = str(content)
        else:
            # 对于复杂对象，使用pickle序列化
            try:
                content_bytes = pickle.dumps(content)
                content_str = content_bytes.decode('latin-1')
            except:
                content_str = str(content)
        
        return hashlib.sha256(content_str.encode()).hexdigest()


class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, 
                 capacity: int = 10000,
                 persistence_path: Optional[str] = None):
        """
        初始化记忆管理器
        
        Args:
            capacity: 记忆容量限制
            persistence_path: 持久化存储路径
        """
        self.capacity = capacity
        self.persistence_path = persistence_path
        
        # 记忆存储
        self.memories: Dict[str, MemoryRecord] = {}
        
        # 索引
        self.index = MemoryIndex()
        
        # 缓存
        self.recently_accessed: deque = deque(maxlen=100)
        self.hot_memories: Set[str] = set()  # 热点记忆
        
        # 统计信息
        self.stats = {
            "total_memories": 0,
            "active_memories": 0,
            "dormant_memories": 0,
            "forgotten_memories": 0,
            "memory_access_count": 0,
            "last_cleanup": datetime.now()
        }
        
        # 初始化
        self._load_persistent_memories()
    
    def _load_persistent_memories(self):
        """加载持久化记忆"""
        if not self.persistence_path:
            return
        
        try:
            with open(self.persistence_path, 'r') as f:
                data = json.load(f)
            
            for memory_data in data.get('memories', []):
                memory = MemoryRecord.from_dict(memory_data)
                self.memories[memory.id] = memory
                self.index.add_memory(memory)
            
            print(f"Loaded {len(self.memories)} memories from {self.persistence_path}")
        except FileNotFoundError:
            print(f"No persistent memory file found at {self.persistence_path}")
        except Exception as e:
            print(f"Error loading persistent memories: {e}")
    
    def _save_persistent_memories(self):
        """保存记忆到持久化存储"""
        if not self.persistence_path:
            return
        
        try:
            data = {
                "memories": [memory.to_dict() for memory in self.memories.values()],
                "saved_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            with open(self.persistence_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            print(f"Saved {len(self.memories)} memories to {self.persistence_path}")
        except Exception as e:
            print(f"Error saving persistent memories: {e}")
    
    def add_memory(self, 
                   content: Any,
                   memory_type: MemoryType,
                   metadata: Optional[Dict[str, Any]] = None,
                   importance_score: Optional[float] = None) -> str:
        """
        添加新记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            metadata: 元数据
            importance_score: 重要性评分
            
        Returns:
            记忆ID
        """
        # 检查是否已存在
        existing_id = self.index.find_duplicate(content)
        if existing_id:
            # 如果已存在，增强原有记忆
            existing_memory = self.memories[existing_id]
            existing_memory.reinforce(0.1)
            return existing_id
        
        # 创建元数据
        memory_metadata = MemoryMetadata()
        if metadata:
            for key, value in metadata.items():
                if hasattr(memory_metadata, key):
                    setattr(memory_metadata, key, value)
        
        # 创建记忆记录
        memory = MemoryRecord(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=memory_type,
            metadata=memory_metadata,
            importance_score=importance_score or 0.5
        )
        
        # 添加关联（基于元数据中的dependencies）
        for dep_id in memory_metadata.dependencies:
            if dep_id in self.memories:
                memory.add_association(dep_id, 0.2)
        
        # 存储记忆
        self.memories[memory.id] = memory
        self.index.add_memory(memory)
        
        # 更新统计
        self.stats["total_memories"] += 1
        self.stats["active_memories"] += 1
        
        # 检查容量
        if len(self.memories) > self.capacity:
            self._trigger_cleanup()
        
        # 自动保存
        self._save_persistent_memories()
        
        return memory.id
    
    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        """获取记忆"""
        if memory_id not in self.memories:
            return None
        
        memory = self.memories[memory_id]
        
        # 记录访问
        memory.record_access("read")
        self.recently_accessed.append(memory_id)
        self.stats["memory_access_count"] += 1
        
        # 更新热点记忆
        if memory.access_count > 10:
            self.hot_memories.add(memory_id)
        
        return memory
    
    def update_memory(self, 
                      memory_id: str, 
                      new_content: Any = None,
                      metadata_update: Dict[str, Any] = None) -> bool:
        """更新记忆"""
        if memory_id not in self.memories:
            return False
        
        memory = self.memories[memory_id]
        old_memory = MemoryRecord.from_dict(memory.to_dict())
        
        # 更新内容
        if new_content is not None:
            memory.content = new_content
        
        # 更新元数据
        if metadata_update:
            for key, value in metadata_update.items():
                if hasattr(memory.metadata, key):
                    setattr(memory.metadata, key, value)
        
        # 更新时间戳
        memory.updated_at = datetime.now()
        memory.record_access("update", {"update_data": metadata_update})
        
        # 更新索引
        self.index.update_memory(old_memory, memory)
        
        # 自动保存
        self._save_persistent_memories()
        
        return True
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id not in self.memories:
            return False
        
        memory = self.memories[memory_id]
        
        # 从索引中移除
        self.index.remove_memory(memory)
        
        # 从存储中移除
        del self.memories[memory_id]
        
        # 更新统计
        self.stats["total_memories"] -= 1
        if memory.state == MemoryState.ACTIVE:
            self.stats["active_memories"] -= 1
        elif memory.state == MemoryState.DORMANT:
            self.stats["dormant_memories"] -= 1
        
        # 清理相关数据
        self.recently_accessed = deque(
            [mid for mid in self.recently_accessed if mid != memory_id],
            maxlen=100
        )
        self.hot_memories.discard(memory_id)
        
        # 自动保存
        self._save_persistent_memories()
        
        return True
    
    def search_memories(self,
                       query: Optional[Any] = None,
                       memory_type: Optional[MemoryType] = None,
                       tags: Optional[List[str]] = None,
                       min_importance: float = 0.0,
                       state: Optional[MemoryState] = None,
                       limit: int = 100) -> List[MemoryRecord]:
        """
        搜索记忆
        
        Args:
            query: 查询内容（支持字符串或任意对象）
            memory_type: 记忆类型过滤
            tags: 标签过滤
            min_importance: 最小重要性分数
            state: 记忆状态过滤
            limit: 返回数量限制
            
        Returns:
            匹配的记忆列表
        """
        candidates = set(self.memories.keys())
        
        # 按类型过滤
        if memory_type:
            type_matches = set(self.index.search_by_type(memory_type))
            candidates &= type_matches
        
        # 按标签过滤
        if tags:
            tag_matches = set()
            for tag in tags:
                tag_matches |= set(self.index.search_by_tag(tag))
            candidates &= tag_matches
        
        # 按状态过滤
        if state:
            state_matches = set(self.index.search_by_state(state))
            candidates &= state_matches
        
        # 执行搜索
        results = []
        for memory_id in candidates:
            memory = self.memories[memory_id]
            
            # 重要性过滤
            if memory.importance_score < min_importance:
                continue
            
            # 内容匹配（简单实现，实际中可以使用向量搜索等）
            if query is not None:
                if self._content_matches(memory.content, query):
                    results.append(memory)
                else:
                    continue
            else:
                results.append(memory)
        
        # 排序：按激活级别和重要性
        results.sort(key=lambda m: (m.activation_level, m.importance_score), reverse=True)
        
        return results[:limit]
    
    def _content_matches(self, content: Any, query: Any) -> bool:
        """检查内容是否匹配查询"""
        if isinstance(query, str):
            if isinstance(content, str):
                return query.lower() in content.lower()
            else:
                return query.lower() in str(content).lower()
        elif callable(query):
            # 如果查询是可调用对象，使用它进行匹配
            try:
                return query(content)
            except:
                return False
        else:
            # 简单相等比较
            return content == query
    
    def get_associated_memories(self, memory_id: str, max_associations: int = 10) -> List[MemoryRecord]:
        """获取关联记忆"""
        if memory_id not in self.memories:
            return []
        
        memory = self.memories[memory_id]
        associations = []
        
        for assoc_id, strength in sorted(memory.associations.items(), 
                                         key=lambda x: x[1], 
                                         reverse=True):
            if assoc_id in self.memories:
                assoc_memory = self.memories[assoc_id]
                associations.append((assoc_memory, strength))
        
        # 返回记忆对象列表
        return [assoc[0] for assoc in associations[:max_associations]]
    
    def reinforce_memory(self, memory_id: str, strength: float = 0.1):
        """增强记忆"""
        if memory_id not in self.memories:
            return
        
        memory = self.memories[memory_id]
        memory.reinforce(strength)
        
        # 同时增强关联记忆
        for assoc_id in memory.associations.keys():
            if assoc_id in self.memories:
                assoc_memory = self.memories[assoc_id]
                assoc_memory.reinforce(strength * 0.5)
    
    def apply_decay(self, decay_rate: float = 0.01):
        """应用记忆衰减"""
        for memory in self.memories.values():
            if memory.state == MemoryState.ACTIVE:
                memory.decay(decay_rate)
        
        # 更新统计
        self._update_stats()
    
    def _trigger_cleanup(self):
        """触发记忆清理：仅在超出容量时真正执行遗忘"""
        overflow = len(self.memories) - self.capacity
        if overflow <= 0:
            # 未超容量，只刷新统计（此前无条件打印“容量已达上限”，且在 5/10000 时也触发）
            self._update_stats()
            return

        print(f"Memory capacity reached ({len(self.memories)}/{self.capacity}). Triggering cleanup...")
        
        # 识别需要遗忘的记忆
        from .forgetting_algorithm import ForgettingAlgorithm
        forgetting_algorithm = ForgettingAlgorithm()
        
        memories_to_forget = forgetting_algorithm.select_memories_to_forget(
            list(self.memories.values()),
            target_count=overflow  # 需要腾出的槽位数（此前用 len-capacity+1000，可能算出负数）
        )
        
        # 执行遗忘
        for memory in memories_to_forget:
            self.forget_memory(memory.id, "capacity_cleanup")
        
        self.stats["last_cleanup"] = datetime.now()
    
    def forget_memory(self, memory_id: str, reason: str = "manual"):
        """遗忘记忆"""
        if memory_id not in self.memories:
            return False
        
        memory = self.memories[memory_id]
        
        # 更改状态
        memory.state = MemoryState.FORGOTTEN
        memory.retention_score = 0.0
        
        # 更新索引
        self.index.remove_memory(memory)
        
        # 更新统计
        if memory.state == MemoryState.ACTIVE:
            self.stats["active_memories"] -= 1
        elif memory.state == MemoryState.DORMANT:
            self.stats["dormant_memories"] -= 1
        self.stats["forgotten_memories"] += 1
        
        print(f"Memory {memory_id} forgotten. Reason: {reason}")
        
        return True
    
    def recall_memory(self, memory_id: str) -> bool:
        """召回已遗忘的记忆"""
        if memory_id not in self.memories:
            return False
        
        memory = self.memories[memory_id]
        
        if memory.state != MemoryState.FORGOTTEN:
            return False
        
        # 召回记忆
        memory.state = MemoryState.ACTIVE
        memory.retention_score = 0.3  # 部分恢复
        memory.reinforce(0.2)
        
        # 重新加入索引
        self.index.add_memory(memory)
        
        # 更新统计
        self.stats["forgotten_memories"] -= 1
        self.stats["active_memories"] += 1
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        self._update_stats()
        
        # 计算额外统计
        importance_scores = [m.importance_score for m in self.memories.values()]
        retention_scores = [m.retention_score for m in self.memories.values()]
        
        stats = {
            **self.stats,
            "avg_importance": np.mean(importance_scores) if importance_scores else 0,
            "avg_retention": np.mean(retention_scores) if retention_scores else 0,
            "memory_type_distribution": self._get_type_distribution(),
            "recent_access_rate": len(self.recently_accessed) / 100,  # 最近访问率
            "hot_memory_count": len(self.hot_memories),
            "memory_age_days": self._calculate_average_age_days()
        }
        
        return stats
    
    def _update_stats(self):
        """更新统计信息"""
        active_count = dormant_count = forgotten_count = 0
        
        for memory in self.memories.values():
            if memory.state == MemoryState.ACTIVE:
                active_count += 1
            elif memory.state == MemoryState.DORMANT:
                dormant_count += 1
            elif memory.state == MemoryState.FORGOTTEN:
                forgotten_count += 1
        
        self.stats.update({
            "total_memories": len(self.memories),
            "active_memories": active_count,
            "dormant_memories": dormant_count,
            "forgotten_memories": forgotten_count
        })
    
    def _get_type_distribution(self) -> Dict[str, int]:
        """获取记忆类型分布"""
        distribution = {}
        for memory_type in MemoryType:
            count = len(self.index.search_by_type(memory_type))
            distribution[memory_type.value] = count
        return distribution
    
    def _calculate_average_age_days(self) -> float:
        """计算平均记忆年龄（天数）"""
        if not self.memories:
            return 0
        
        total_age_days = 0
        for memory in self.memories.values():
            age = datetime.now() - memory.created_at
            total_age_days += age.total_seconds() / 86400  # 转换为天数
        
        return total_age_days / len(self.memories)
    
    def export_memories(self, filepath: str, 
                        include_forgotten: bool = False) -> bool:
        """导出记忆到文件"""
        try:
            memories_to_export = []
            
            for memory in self.memories.values():
                if not include_forgotten and memory.state == MemoryState.FORGOTTEN:
                    continue
                memories_to_export.append(memory.to_dict())
            
            data = {
                "memories": memories_to_export,
                "exported_at": datetime.now().isoformat(),
                "total_count": len(memories_to_export),
                "manager_stats": self.get_statistics()
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            print(f"Exported {len(memories_to_export)} memories to {filepath}")
            return True
        except Exception as e:
            print(f"Error exporting memories: {e}")
            return False
    
    def import_memories(self, filepath: str, 
                        merge_strategy: str = "merge") -> bool:
        """从文件导入记忆"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            imported_count = 0
            skipped_count = 0
            
            for memory_data in data.get('memories', []):
                memory = MemoryRecord.from_dict(memory_data)
                
                # 检查是否已存在
                existing_id = self.index.find_duplicate(memory.content)
                
                if existing_id and merge_strategy == "skip":
                    skipped_count += 1
                    continue
                
                # 更新ID以避免冲突
                memory.id = str(uuid.uuid4())
                
                # 添加到管理器
                self.memories[memory.id] = memory
                self.index.add_memory(memory)
                imported_count += 1
            
            # 更新统计
            self._update_stats()
            
            print(f"Imported {imported_count} memories from {filepath} (skipped {skipped_count})")
            return True
        except Exception as e:
            print(f"Error importing memories: {e}")
            return False
    
    def clear_all_memories(self):
        """清空所有记忆"""
        self.memories.clear()
        self.index = MemoryIndex()
        self.recently_accessed.clear()
        self.hot_memories.clear()
        
        # 重置统计
        self.stats = {
            "total_memories": 0,
            "active_memories": 0,
            "dormant_memories": 0,
            "forgotten_memories": 0,
            "memory_access_count": 0,
            "last_cleanup": datetime.now()
        }
        
        print("All memories cleared")