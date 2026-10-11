"""
全局状态管理器
管理系统的全局状态、上下文和配置
"""

import asyncio
import logging
import threading
import json
import copy
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pickle
import hashlib
import time


class StateType(Enum):
    """状态类型枚举"""
    SYSTEM = "system"          # 系统状态
    MODULE = "module"          # 模块状态
    WORKFLOW = "workflow"      # 工作流状态
    DATA = "data"              # 数据状态
    CONFIG = "config"          # 配置状态
    SESSION = "session"        # 会话状态
    CACHE = "cache"            # 缓存状态
    METRIC = "metric"          # 指标状态


class StateEvent(Enum):
    """状态事件枚举"""
    CREATED = "created"        # 状态创建
    UPDATED = "updated"        # 状态更新
    DELETED = "deleted"        # 状态删除
    EXPIRED = "expired"        # 状态过期
    LOADED = "loaded"          # 状态加载
    SAVED = "saved"            # 状态保存
    SYNCED = "synced"          # 状态同步


@dataclass
class StateEntry:
    """状态条目定义"""
    key: str
    value: Any
    state_type: StateType
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None
    
    def is_expired(self) -> bool:
        """检查是否已过期"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def update_value(self, new_value: Any, metadata: Optional[Dict[str, Any]] = None) -> 'StateEntry':
        """更新状态值"""
        self.value = new_value
        self.updated_at = datetime.now()
        self.version += 1
        
        if metadata:
            self.metadata.update(metadata)
        
        # 更新校验和
        self.checksum = self._calculate_checksum()
        
        return self
    
    def _calculate_checksum(self) -> str:
        """计算校验和"""
        data = {
            "key": self.key,
            "value": self.value,
            "type": self.state_type.value,
            "version": self.version,
            "timestamp": self.updated_at.isoformat(),
        }
        
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "state_type": self.state_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
            "metadata": self.metadata,
            "checksum": self.checksum,
            "expired": self.is_expired(),
        }
    
    def clone(self) -> 'StateEntry':
        """克隆状态条目"""
        return StateEntry(
            key=self.key,
            value=copy.deepcopy(self.value),
            state_type=self.state_type,
            created_at=self.created_at,
            updated_at=self.updated_at,
            expires_at=self.expires_at,
            version=self.version,
            metadata=copy.deepcopy(self.metadata),
            checksum=self.checksum,
        )


class SystemStateManager:
    """系统状态管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化状态管理器
        
        Args:
            config: 管理器配置
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 状态存储
        self.states: Dict[str, StateEntry] = {}
        self.state_locks: Dict[str, threading.RLock] = {}
        self.global_lock = threading.RLock()
        
        # 状态历史（版本控制）
        self.state_history: Dict[str, List[StateEntry]] = {}
        self.max_history_size = self.config.get("max_history_size", 100)
        
        # 状态索引（按类型索引）
        self.type_index: Dict[StateType, Set[str]] = {}
        
        # 持久化配置
        self.persistence_enabled = self.config.get("persistence_enabled", True)
        self.persistence_path = self.config.get("persistence_path", "./data/state")
        self.autosave_interval = self.config.get("autosave_interval", 300)  # 秒
        self.compaction_interval = self.config.get("compaction_interval", 3600)  # 秒
        
        # 清理配置
        self.cleanup_enabled = self.config.get("cleanup_enabled", True)
        self.cleanup_interval = self.config.get("cleanup_interval", 600)  # 秒
        self.ttl_check_interval = self.config.get("ttl_check_interval", 60)  # 秒
        
        # 回调函数
        self.callbacks: Dict[StateEvent, List[Callable]] = {
            StateEvent.CREATED: [],
            StateEvent.UPDATED: [],
            StateEvent.DELETED: [],
            StateEvent.EXPIRED: [],
            StateEvent.LOADED: [],
            StateEvent.SAVED: [],
            StateEvent.SYNCED: [],
        }
        
        # 统计信息
        self.stats = {
            "total_states": 0,
            "state_types": {},
            "total_updates": 0,
            "total_deletes": 0,
            "total_expirations": 0,
            "last_cleanup": None,
            "last_save": None,
            "start_time": datetime.now().isoformat(),
        }
        
        # 后台任务
        self.background_tasks = []
        self.is_running = False
        
        # 初始化索引
        self._initialize_type_index()
        
        # 加载持久化状态
        if self.persistence_enabled:
            self.load_state()
        
        self.logger.info("系统状态管理器初始化完成")
    
    def _initialize_type_index(self):
        """初始化类型索引"""
        for state_type in StateType:
            self.type_index[state_type] = set()
    
    def set_state(self, key: str, value: Any, state_type: StateType = StateType.SYSTEM,
                 ttl: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None,
                 overwrite: bool = True) -> StateEntry:
        """
        设置状态
        
        Args:
            key: 状态键
            value: 状态值
            state_type: 状态类型
            ttl: 存活时间（秒）
            metadata: 元数据
            overwrite: 是否覆盖现有状态
            
        Returns:
            状态条目
        """
        with self.global_lock:
            # 获取键锁
            if key not in self.state_locks:
                self.state_locks[key] = threading.RLock()
            
            with self.state_locks[key]:
                # 检查是否已存在
                existing_entry = self.states.get(key)
                
                if existing_entry and not overwrite:
                    self.logger.warning(f"状态已存在且不允许覆盖: {key}")
                    return existing_entry
                
                # 创建过期时间
                expires_at = None
                if ttl:
                    expires_at = datetime.now() + timedelta(seconds=ttl)
                
                # 创建状态条目
                entry = StateEntry(
                    key=key,
                    value=value,
                    state_type=state_type,
                    expires_at=expires_at,
                    metadata=metadata or {},
                )
                
                # 计算校验和
                entry.checksum = entry._calculate_checksum()
                
                # 保存状态
                self.states[key] = entry
                
                # 更新索引
                if existing_entry:
                    # 从旧索引中移除
                    old_type = existing_entry.state_type
                    if key in self.type_index.get(old_type, set()):
                        self.type_index[old_type].remove(key)
                
                # 添加到新索引
                if key not in self.type_index[state_type]:
                    self.type_index[state_type].add(key)
                
                # 保存到历史
                self._add_to_history(entry)
                
                # 更新统计
                self.stats["total_states"] = len(self.states)
                self.stats["state_types"][state_type.value] = self.stats["state_types"].get(state_type.value, 0) + 1
                
                if existing_entry:
                    self.stats["total_updates"] += 1
                    event = StateEvent.UPDATED
                else:
                    event = StateEvent.CREATED
                
                # 触发回调
                self._trigger_callbacks(event, entry, existing_entry)
                
                self.logger.debug(f"设置状态: {key} ({state_type.value})")
                
                return entry
    
    def get_state(self, key: str, default: Any = None) -> Optional[Any]:
        """
        获取状态值
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值，如果不存在或已过期则返回默认值
        """
        with self.global_lock:
            if key not in self.state_locks:
                return default
            
            with self.state_locks[key]:
                entry = self.states.get(key)
                
                if not entry:
                    return default
                
                # 检查是否过期
                if entry.is_expired():
                    self.logger.debug(f"状态已过期: {key}")
                    self._expire_state(key)
                    return default
                
                return entry.value
    
    def get_state_entry(self, key: str) -> Optional[StateEntry]:
        """
        获取状态条目
        
        Args:
            key: 状态键
            
        Returns:
            状态条目，如果不存在则返回None
        """
        with self.global_lock:
            if key not in self.state_locks:
                return None
            
            with self.state_locks[key]:
                entry = self.states.get(key)
                
                if entry and entry.is_expired():
                    self._expire_state(key)
                    return None
                
                return entry.clone() if entry else None
    
    def delete_state(self, key: str, force: bool = False) -> bool:
        """
        删除状态
        
        Args:
            key: 状态键
            force: 是否强制删除（即使有锁）
            
        Returns:
            是否成功删除
        """
        with self.global_lock:
            if key not in self.states:
                return False
            
            # 获取锁（如果可能）
            if not force and key in self.state_locks:
                lock_acquired = self.state_locks[key].acquire(timeout=1)
                if not lock_acquired:
                    self.logger.warning(f"无法获取状态锁: {key}")
                    return False
            
            try:
                entry = self.states[key]
                state_type = entry.state_type
                
                # 从存储中删除
                del self.states[key]
                
                # 从索引中删除
                if key in self.type_index.get(state_type, set()):
                    self.type_index[state_type].remove(key)
                
                # 从锁字典中删除
                if key in self.state_locks:
                    lock = self.state_locks.pop(key)
                    if hasattr(lock, 'release'):
                        lock.release()
                
                # 更新统计
                self.stats["total_states"] = len(self.states)
                self.stats["state_types"][state_type.value] = self.stats["state_types"].get(state_type.value, 0) - 1
                self.stats["total_deletes"] += 1
                
                # 触发回调
                self._trigger_callbacks(StateEvent.DELETED, entry)
                
                self.logger.debug(f"删除状态: {key}")
                
                return True
                
            finally:
                # 确保释放锁
                if key in self.state_locks:
                    try:
                        self.state_locks[key].release()
                    except:
                        pass
    
    def update_state(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Optional[StateEntry]:
        """
        更新状态
        
        Args:
            key: 状态键
            value: 新的状态值
            metadata: 更新的元数据
            
        Returns:
            更新后的状态条目，如果不存在则返回None
        """
        with self.global_lock:
            if key not in self.states:
                return None
            
            if key not in self.state_locks:
                return None
            
            with self.state_locks[key]:
                entry = self.states.get(key)
                
                if not entry:
                    return None
                
                # 检查是否过期
                if entry.is_expired():
                    self._expire_state(key)
                    return None
                
                # 更新状态
                old_entry = entry.clone()
                entry.update_value(value, metadata)
                
                # 保存到历史
                self._add_to_history(entry)
                
                # 更新统计
                self.stats["total_updates"] += 1
                
                # 触发回调
                self._trigger_callbacks(StateEvent.UPDATED, entry, old_entry)
                
                self.logger.debug(f"更新状态: {key} (v{entry.version})")
                
                return entry.clone()
    
    def _expire_state(self, key: str):
        """标记状态为过期"""
        with self.global_lock:
            if key not in self.states:
                return
            
            entry = self.states[key]
            state_type = entry.state_type
            
            # 从存储中删除
            del self.states[key]
            
            # 从索引中删除
            if key in self.type_index.get(state_type, set()):
                self.type_index[state_type].remove(key)
            
            # 更新统计
            self.stats["total_states"] = len(self.states)
            self.stats["total_expirations"] += 1
            
            # 触发回调
            self._trigger_callbacks(StateEvent.EXPIRED, entry)
            
            self.logger.debug(f"状态过期: {key}")
    
    def _add_to_history(self, entry: StateEntry):
        """添加到历史记录"""
        key = entry.key
        
        if key not in self.state_history:
            self.state_history[key] = []
        
        # 添加历史记录
        self.state_history[key].append(entry.clone())
        
        # 限制历史记录大小
        if len(self.state_history[key]) > self.max_history_size:
            self.state_history[key] = self.state_history[key][-self.max_history_size:]
    
    def _trigger_callbacks(self, event: StateEvent, entry: StateEntry, old_entry: Optional[StateEntry] = None):
        """触发回调函数"""
        for callback in self.callbacks.get(event, []):
            try:
                callback(event, entry, old_entry)
            except Exception as e:
                self.logger.error(f"状态回调执行失败: {event.value} - {e}")
    
    def get_states_by_type(self, state_type: StateType) -> Dict[str, StateEntry]:
        """
        获取指定类型的所有状态
        
        Args:
            state_type: 状态类型
            
        Returns:
            状态字典
        """
        with self.global_lock:
            keys = list(self.type_index.get(state_type, set()))
            result = {}
            
            for key in keys:
                entry = self.get_state_entry(key)
                if entry:
                    result[key] = entry
            
            return result
    
    def get_state_history(self, key: str, limit: int = 10) -> List[StateEntry]:
        """
        获取状态历史
        
        Args:
            key: 状态键
            limit: 限制返回的历史记录数量
            
        Returns:
            历史记录列表
        """
        with self.global_lock:
            history = self.state_history.get(key, [])
            return history[-limit:]
    
    def search_states(self, query: Dict[str, Any]) -> List[StateEntry]:
        """
        搜索状态
        
        Args:
            query: 查询条件
            
        Returns:
            匹配的状态条目列表
        """
        results = []
        
        with self.global_lock:
            for key, entry in self.states.items():
                if entry.is_expired():
                    continue
                
                # 检查查询条件
                match = True
                
                for field, expected_value in query.items():
                    if field == "key":
                        if key != expected_value:
                            match = False
                            break
                    elif field == "type":
                        if entry.state_type.value != expected_value:
                            match = False
                            break
                    elif field == "metadata":
                        # 检查元数据是否包含指定键值对
                        if not all(entry.metadata.get(k) == v for k, v in expected_value.items()):
                            match = False
                            break
                    elif field.startswith("value."):
                        # 检查嵌套值
                        value_field = field[6:]  # 移除"value."
                        actual_value = entry.value
                        
                        try:
                            for part in value_field.split('.'):
                                if isinstance(actual_value, dict):
                                    actual_value = actual_value.get(part)
                                else:
                                    match = False
                                    break
                        except:
                            match = False
                        
                        if match and actual_value != expected_value:
                            match = False
                    
                    if not match:
                        break
                
                if match:
                    results.append(entry.clone())
        
        return results
    
    def register_callback(self, event: StateEvent, callback: Callable):
        """
        注册回调函数
        
        Args:
            event: 状态事件
            callback: 回调函数
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"已注册回调函数到事件: {event.value}")
        else:
            self.logger.warning(f"未知的事件类型: {event}")
    
    def start_background_tasks(self):
        """启动后台任务"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 自动保存任务
        if self.persistence_enabled and self.autosave_interval > 0:
            save_thread = threading.Thread(
                target=self._autosave_task,
                daemon=True,
                name="StateAutosave"
            )
            save_thread.start()
            self.background_tasks.append(save_thread)
        
        # 清理任务
        if self.cleanup_enabled:
            cleanup_thread = threading.Thread(
                target=self._cleanup_task,
                daemon=True,
                name="StateCleanup"
            )
            cleanup_thread.start()
            self.background_tasks.append(cleanup_thread)
        
        # TTL检查任务
        if self.ttl_check_interval > 0:
            ttl_thread = threading.Thread(
                target=self._ttl_check_task,
                daemon=True,
                name="StateTTLCheck"
            )
            ttl_thread.start()
            self.background_tasks.append(ttl_thread)
        
        self.logger.info("后台任务已启动")
    
    def _autosave_task(self):
        """自动保存任务"""
        while self.is_running:
            time.sleep(self.autosave_interval)
            
            try:
                self.save_state()
                self.stats["last_save"] = datetime.now().isoformat()
                self.logger.debug("自动保存状态完成")
            except Exception as e:
                self.logger.error(f"自动保存状态失败: {e}")
    
    def _cleanup_task(self):
        """清理任务"""
        while self.is_running:
            time.sleep(self.cleanup_interval)
            
            try:
                self._perform_cleanup()
                self.stats["last_cleanup"] = datetime.now().isoformat()
                self.logger.debug("状态清理完成")
            except Exception as e:
                self.logger.error(f"状态清理失败: {e}")
    
    def _ttl_check_task(self):
        """TTL检查任务"""
        while self.is_running:
            time.sleep(self.ttl_check_interval)
            
            try:
                self._check_expired_states()
                self.logger.debug("TTL检查完成")
            except Exception as e:
                self.logger.error(f"TTL检查失败: {e}")
    
    def _perform_cleanup(self):
        """执行清理"""
        with self.global_lock:
            # 清理过期的状态
            expired_keys = []
            
            for key, entry in self.states.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._expire_state(key)
            
            # 清理历史记录（保留最近N个版本）
            for key in list(self.state_history.keys()):
                if key not in self.states:
                    # 如果状态已删除，清理历史记录
                    del self.state_history[key]
                elif len(self.state_history[key]) > self.max_history_size:
                    # 限制历史记录大小
                    self.state_history[key] = self.state_history[key][-self.max_history_size:]
            
            # 清理锁字典
            stale_locks = [k for k in self.state_locks if k not in self.states]
            for key in stale_locks:
                lock = self.state_locks.pop(key, None)
                if lock and hasattr(lock, 'release'):
                    try:
                        lock.release()
                    except:
                        pass
            
            if expired_keys:
                self.logger.info(f"清理了 {len(expired_keys)} 个过期状态")
    
    def _check_expired_states(self):
        """检查过期状态"""
        with self.global_lock:
            expired_count = 0
            
            for key, entry in self.states.items():
                if entry.is_expired():
                    self._expire_state(key)
                    expired_count += 1
            
            if expired_count:
                self.logger.debug(f"标记了 {expired_count} 个过期状态")
    
    def save_state(self, filepath: Optional[str] = None):
        """
        保存状态到文件
        
        Args:
            filepath: 文件路径，如果为None则使用配置的路径
        """
        if not self.persistence_enabled:
            return
        
        filepath = filepath or self.persistence_path
        
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with self.global_lock:
            # 准备要保存的数据
            save_data = {
                "states": {},
                "state_history": {},
                "metadata": {
                    "saved_at": datetime.now().isoformat(),
                    "total_states": len(self.states),
                    "version": "1.0",
                }
            }
            
            # 保存当前状态
            for key, entry in self.states.items():
                # 不保存过期的状态
                if not entry.is_expired():
                    save_data["states"][key] = {
                        "value": entry.value,
                        "state_type": entry.state_type.value,
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat(),
                        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                        "version": entry.version,
                        "metadata": entry.metadata,
                        "checksum": entry.checksum,
                    }
            
            # 保存历史记录（只保存最近N个）
            for key, history in self.state_history.items():
                if history:
                    save_data["state_history"][key] = [
                        {
                            "value": entry.value,
                            "state_type": entry.state_type.value,
                            "created_at": entry.created_at.isoformat(),
                            "updated_at": entry.updated_at.isoformat(),
                            "version": entry.version,
                            "metadata": entry.metadata,
                        }
                        for entry in history[-10:]  # 只保存最近10个版本
                    ]
            
            # 写入文件
            try:
                with open(filepath, 'wb') as f:
                    pickle.dump(save_data, f)
                
                # 触发回调
                for callback in self.callbacks[StateEvent.SAVED]:
                    callback(filepath, save_data)
                
                self.logger.info(f"状态已保存到: {filepath}")
                
            except Exception as e:
                self.logger.error(f"保存状态失败: {e}")
                raise
    
    def load_state(self, filepath: Optional[str] = None):
        """
        从文件加载状态
        
        Args:
            filepath: 文件路径，如果为None则使用配置的路径
        """
        if not self.persistence_enabled:
            return
        
        filepath = filepath or self.persistence_path
        
        import os
        if not os.path.exists(filepath):
            self.logger.warning(f"状态文件不存在: {filepath}")
            return
        
        with self.global_lock:
            try:
                with open(filepath, 'rb') as f:
                    save_data = pickle.load(f)
                
                # 清除当前状态
                self.states.clear()
                self.state_history.clear()
                self._initialize_type_index()
                
                # 加载状态
                for key, state_data in save_data.get("states", {}).items():
                    # 创建状态条目
                    entry = StateEntry(
                        key=key,
                        value=state_data["value"],
                        state_type=StateType(state_data["state_type"]),
                        created_at=datetime.fromisoformat(state_data["created_at"]),
                        updated_at=datetime.fromisoformat(state_data["updated_at"]),
                        expires_at=datetime.fromisoformat(state_data["expires_at"]) if state_data.get("expires_at") else None,
                        version=state_data["version"],
                        metadata=state_data.get("metadata", {}),
                        checksum=state_data.get("checksum"),
                    )
                    
                    # 添加到存储
                    self.states[key] = entry
                    
                    # 添加到索引
                    self.type_index[entry.state_type].add(key)
                
                # 加载历史记录
                for key, history_data in save_data.get("state_history", {}).items():
                    history_entries = []
                    
                    for hist_data in history_data:
                        entry = StateEntry(
                            key=key,
                            value=hist_data["value"],
                            state_type=StateType(hist_data["state_type"]),
                            created_at=datetime.fromisoformat(hist_data["created_at"]),
                            updated_at=datetime.fromisoformat(hist_data["updated_at"]),
                            version=hist_data["version"],
                            metadata=hist_data.get("metadata", {}),
                        )
                        history_entries.append(entry)
                    
                    self.state_history[key] = history_entries
                
                # 更新统计
                self.stats["total_states"] = len(self.states)
                for entry in self.states.values():
                    state_type = entry.state_type.value
                    self.stats["state_types"][state_type] = self.stats["state_types"].get(state_type, 0) + 1
                
                # 触发回调
                for callback in self.callbacks[StateEvent.LOADED]:
                    callback(filepath, save_data)
                
                self.logger.info(f"状态已从 {filepath} 加载，共 {len(self.states)} 个状态")
                
            except Exception as e:
                self.logger.error(f"加载状态失败: {e}")
                raise
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.global_lock:
            return {
                **self.stats,
                "current_states": len(self.states),
                "state_types_count": {k.value: len(v) for k, v in self.type_index.items()},
                "total_history_entries": sum(len(h) for h in self.state_history.values()),
                "active_locks": len(self.state_locks),
                "background_tasks": len(self.background_tasks),
                "is_running": self.is_running,
            }
    
    def stop_background_tasks(self):
        """停止后台任务"""
        self.is_running = False
        
        for task in self.background_tasks:
            if task.is_alive():
                task.join(timeout=5)
        
        self.background_tasks.clear()
        self.logger.info("后台任务已停止")
    
    def shutdown(self):
        """关闭状态管理器"""
        self.stop_background_tasks()
        
        # 保存状态
        if self.persistence_enabled:
            self.save_state()
        
        self.logger.info("系统状态管理器已关闭")