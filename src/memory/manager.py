# src/memory/manager.py
"""
记忆管理器 - 对应论文《动态知识库的分类策略驱动型自动化生命周期管理研究》
封装 memory_manager.MemoryManager，向引擎暴露统一的 manage_memory / get_status / shutdown 接口
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from .memory_manager import MemoryManager as _MemoryManager
from .memory_manager import MemoryType, MemoryState
from .retention_policy import RetentionPolicy
from .forgetting_algorithm import ForgettingAlgorithm
from .importance_evaluator import ImportanceEvaluator


class MemoryManager:
    """记忆管理器适配器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.logger = logging.getLogger(__name__)
        self.config = config

        # 内部实现
        self.memory = _MemoryManager(
            capacity=int(config.get("capacity", 10000)),
            persistence_path=config.get("persistence_path"),
        )

        # 生命周期组件（分类策略驱动）
        self.retention_policy = RetentionPolicy()
        self.forgetting_algorithm = ForgettingAlgorithm()
        self.importance_evaluator = ImportanceEvaluator()

        self.stats = {
            "manage_cycles": 0,
            "memories_added": 0,
            "memories_cleaned": 0,
            "last_manage": None,
        }

    def _compute_importance(self, article: Dict[str, Any]) -> float:
        """计算文章的重要性评分（0-1）"""
        try:
            metadata = {
                "confidence": article.get("credibility", {}).get("score", 0.5),
                "domain": str(article.get("category", "general")).lower(),
            }
            result = self.importance_evaluator.evaluate(
                memory_content=str(article.get("content", "")),
                metadata=metadata,
                context={"title": article.get("title", "")},
            )
            return float(getattr(result, "overall", 0.5))
        except Exception:
            return 0.5

    async def manage_memory(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行一次记忆生命周期管理

        Args:
            context: 执行上下文，包含知识提取结果与通过评估的文章

        Returns:
            {status, added, cleaned, active, forgotten}
        """
        context = context or {}
        self.logger.info("开始记忆生命周期管理...")

        added = 0
        # 1. 将从知识提取中获得的文章写入记忆
        articles = context.get("articles", [])
        for article in articles:
            title = article.get("title", "")
            if not title:
                continue
            try:
                importance = self._compute_importance(article)
                self.memory.add_memory(
                    content=title,
                    memory_type=MemoryType.FACT,
                    metadata={
                        "source": article.get("source", "unknown"),
                        "category": article.get("category", ""),
                        "url": article.get("url", ""),
                    },
                    importance_score=importance,
                )
                added += 1
            except Exception as e:
                self.logger.debug(f"写入记忆失败: {e}")

        # 2. 应用衰减并触发清理（分类策略驱动的生命周期管理）
        try:
            self.memory.apply_decay(decay_rate=0.01)
            self.memory._trigger_cleanup()
        except Exception as e:
            self.logger.debug(f"生命周期清理失败: {e}")

        self.stats["manage_cycles"] += 1
        self.stats["memories_added"] += added
        self.stats["last_manage"] = datetime.now().isoformat()

        self.logger.info(f"记忆管理完成：新增 {added} 条记忆")
        return {
            "status": "completed",
            "added": added,
            "active": self.memory.stats.get("active_memories", 0),
            "forgotten": self.memory.stats.get("forgotten_memories", 0),
            "stats": self.memory.get_statistics(),
        }

    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "module": "memory",
            "stats": self.stats,
            "memory": self.memory.get_statistics(),
        }

    def shutdown(self):
        """关闭记忆管理器"""
        self.logger.info("记忆管理器已关闭")
