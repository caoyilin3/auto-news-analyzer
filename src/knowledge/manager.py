# src/knowledge/manager.py
"""
知识管理器 - 模式词典驱动的知识提取与知识图谱构建

对应论文《一种面向垂直领域的模式词典驱动知识提取方法》：
- 命名实体识别（jieba）+ 模式词典关系提取（规则基线）
- 可选：DeepSeek 大模型辅助抽取三元组（未配置 api_key 时自动降级）
- 提取结果以三元组形式写入知识图谱
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import ExtractedEntity, ExtractedRelation, ExtractedKnowledge
from .graph import KnowledgeGraph
from .extractors import NERExtractor, RelationExtractor
from ..utils.llm_client import LLMClient


class KnowledgeManager:
    """知识管理器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 规则提取器
        try:
            self.entity_extractor = NERExtractor()
        except Exception as e:
            self.logger.warning(f"实体提取器初始化失败（降级为规则提取）: {e}")
            self.entity_extractor = None
        self.relation_extractor = RelationExtractor()

        # 可选 LLM 增强
        llm_cfg = self.config.get("llm", {}) or {}
        self.llm_client = LLMClient(llm_cfg) if llm_cfg.get("api_key") else None
        if self.llm_client and self.llm_client.enabled:
            self.logger.info(f"LLM 知识抽取已启用: {self.llm_client.model}")

        # 知识图谱（内存存储）
        self.graph = KnowledgeGraph()

        self.stats = {
            "articles_processed": 0,
            "entities_extracted": 0,
            "relations_extracted": 0,
            "llm_triples": 0,
            "start_time": datetime.now(),
        }

    def _extract_single(self, text: str) -> ExtractedKnowledge:
        """对单篇文本做知识提取：规则基线 + 可选 LLM 增强"""
        entities: List[ExtractedEntity] = []
        if self.entity_extractor is not None:
            try:
                entities = self.entity_extractor.extract_entities(text)
            except Exception as e:
                self.logger.warning(f"实体提取失败: {e}")

        relations: List[ExtractedRelation] = []
        try:
            relations = self.relation_extractor.extract_relations(text, entities)
        except Exception as e:
            self.logger.warning(f"关系提取失败: {e}")

        # LLM 增强抽取三元组
        llm_entities: List[ExtractedEntity] = []
        llm_relations: List[ExtractedRelation] = []
        if self.llm_client is not None:
            try:
                triples = self.llm_client.extract_triples(text)
                for t in triples:
                    s, p, o = t["subject"], t["predicate"], t["object"]
                    llm_entities.append(ExtractedEntity(text=s, label="ORG", start_pos=0, end_pos=len(s), confidence=0.8))
                    llm_entities.append(ExtractedEntity(text=o, label="MISC", start_pos=0, end_pos=len(o), confidence=0.8))
                    llm_relations.append(ExtractedRelation(
                        subject=s, predicate=p, object=o, confidence=0.8, context=text[:200]
                    ))
                self.stats["llm_triples"] += len(triples)
            except Exception as e:
                self.logger.warning(f"LLM 三元组抽取失败: {e}")

        return ExtractedKnowledge(
            text=text,
            entities=entities + llm_entities,
            relations=relations + llm_relations,
            metadata={
                "extractor": "pattern_dictionary+llm" if self.llm_client else "pattern_dictionary",
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def extract_knowledge(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        从文章集合提取知识并写入知识图谱

        Args:
            context: 执行上下文，包含已通过可信度评估的文章

        Returns:
            {status, graph_stats, total_entities, total_relations}
        """
        context = context or {}
        articles = context.get("articles", [])
        self.logger.info(f"开始知识提取，共 {len(articles)} 篇")

        total_entities = 0
        total_relations = 0
        article_results = []

        for article in articles:
            content = str(article.get("content", ""))
            if not content.strip():
                continue

            knowledge = self._extract_single(content)
            knowledge.metadata["article_id"] = article.get("id")
            knowledge.metadata["title"] = article.get("title", "")

            self.graph.build_from_knowledge(knowledge)
            total_entities += len(knowledge.entities)
            total_relations += len(knowledge.relations)

            article_results.append({
                "article_id": article.get("id"),
                "entities": len(knowledge.entities),
                "relations": len(knowledge.relations),
                "knowledge": knowledge.to_dict(),
            })
            self.stats["articles_processed"] += 1

        self.stats["entities_extracted"] += total_entities
        self.stats["relations_extracted"] += total_relations

        self.logger.info(
            f"知识提取完成：实体 {total_entities} 个，关系 {total_relations} 条"
            f"（LLM 三元组 {self.stats['llm_triples']} 个）"
        )
        return {
            "status": "completed",
            "total_entities": total_entities,
            "total_relations": total_relations,
            "llm_triples": self.stats["llm_triples"],
            "articles_processed": len(article_results),
            "article_results": article_results,
            "graph_stats": self.graph.get_statistics() if hasattr(self.graph, "get_statistics") else None,
        }

    def get_graph(self) -> KnowledgeGraph:
        """获取知识图谱"""
        return self.graph

    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "module": "knowledge",
            "stats": self.stats,
            "graph_nodes": len(getattr(self.graph, "node_map", {})),
            "graph_edges": len(getattr(self.graph, "edge_map", {})),
            "llm": self.llm_client.get_status() if self.llm_client else {"enabled": False},
        }

    def shutdown(self):
        """关闭知识管理器"""
        self.logger.info("知识管理器已关闭")
