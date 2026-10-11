"""
知识图谱实现
基于NetworkX的图数据结构
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime
import json
import pickle

import networkx as nx
import matplotlib.pyplot as plt

from ..base import ExtractedEntity, ExtractedRelation


@dataclass
class KnowledgeGraphConfig:
    """知识图谱配置"""
    storage_backend: str = "networkx"
    enable_persistence: bool = True
    persistence_path: str = "./data/knowledge_graph"
    max_nodes: int = 10000
    max_edges: int = 50000
    enable_visualization: bool = True


@dataclass
class GraphNode:
    """图谱节点"""
    id: str
    label: str
    node_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "label": self.label,
            "type": self.node_type,
            "properties": self.properties,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class GraphEdge:
    """图谱边"""
    id: str
    source: str
    target: str
    label: str
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "weight": self.weight,
            "properties": self.properties,
            "created_at": self.created_at
        }


class KnowledgeGraph:
    """知识图谱"""
    
    def __init__(self, config: Optional[KnowledgeGraphConfig] = None):
        self.config = config or KnowledgeGraphConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 初始化图结构
        self.graph = nx.MultiDiGraph()
        self.node_map: Dict[str, GraphNode] = {}
        self.edge_map: Dict[str, GraphEdge] = {}
        
        # 索引
        self.type_index: Dict[str, Set[str]] = defaultdict(set)
        self.property_index: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        
        self.logger.info("知识图谱初始化完成")
    
    def build_from_knowledge(self, knowledge) -> bool:
        """从提取的知识构建图谱"""
        try:
            # 添加实体作为节点
            for entity in knowledge.entities:
                node = GraphNode(
                    id=entity.id or entity.text,
                    label=entity.text,
                    node_type=entity.label,
                    properties=entity.attributes
                )
                self.add_node(node)
            
            # 添加关系作为边
            for relation in knowledge.relations:
                edge = GraphEdge(
                    id=relation.id or f"{relation.subject}->{relation.predicate}->{relation.object}",
                    source=relation.subject,
                    target=relation.object,
                    label=relation.predicate,
                    weight=relation.confidence,
                    properties=relation.attributes
                )
                self.add_edge(edge)
            
            self.logger.info(f"从知识构建图谱: {len(knowledge.entities)} 节点, {len(knowledge.relations)} 边")
            return True
            
        except Exception as e:
            self.logger.error(f"构建图谱失败: {e}")
            return False
    
    def add_node(self, node: GraphNode) -> bool:
        """添加节点"""
        try:
            if node.id in self.node_map:
                self.logger.debug(f"节点已存在: {node.id}")
                return False
            
            self.graph.add_node(node.id, **node.properties)
            self.node_map[node.id] = node
            
            # 更新索引
            self.type_index[node.node_type].add(node.id)
            for key, value in node.properties.items():
                self.property_index[key][str(value)].add(node.id)
            
            self.logger.debug(f"添加节点: {node.id} ({node.node_type})")
            return True
            
        except Exception as e:
            self.logger.error(f"添加节点失败: {e}")
            return False
    
    def add_edge(self, edge: GraphEdge) -> bool:
        """添加边"""
        try:
            # 检查节点是否存在
            if edge.source not in self.node_map or edge.target not in self.node_map:
                self.logger.error(f"节点不存在: {edge.source} -> {edge.target}")
                return False
            
            self.graph.add_edge(edge.source, edge.target, key=edge.id,
                              label=edge.label, weight=edge.weight, **edge.properties)
            self.edge_map[edge.id] = edge
            
            self.logger.debug(f"添加边: {edge.id} ({edge.label})")
            return True
            
        except Exception as e:
            self.logger.error(f"添加边失败: {e}")
            return False
    
    def query(self, query_type: str, **kwargs) -> List[Any]:
        """查询图谱"""
        if query_type == "node_by_type":
            return self.find_nodes_by_type(kwargs.get('node_type'))
        elif query_type == "node_by_property":
            return self.find_nodes_by_property(kwargs.get('property'), kwargs.get('value'))
        elif query_type == "neighbors":
            return self.get_neighbors(kwargs.get('node_id'), kwargs.get('depth', 1))
        elif query_type == "path":
            return self.find_path(kwargs.get('source'), kwargs.get('target'))
        else:
            raise ValueError(f"未知查询类型: {query_type}")
    
    def find_nodes_by_type(self, node_type: str) -> List[GraphNode]:
        """按类型查找节点"""
        node_ids = self.type_index.get(node_type, set())
        return [self.node_map[nid] for nid in node_ids]
    
    def find_nodes_by_property(self, property_name: str, property_value: Any) -> List[GraphNode]:
        """按属性查找节点"""
        if property_name not in self.property_index:
            return []
        
        value_str = str(property_value)
        if value_str not in self.property_index[property_name]:
            return []
        
        node_ids = self.property_index[property_name][value_str]
        return [self.node_map[nid] for nid in node_ids]
    
    def get_neighbors(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        """获取邻居节点"""
        if node_id not in self.node_map:
            return {"error": f"节点不存在: {node_id}"}
        
        visited = set()
        queue = deque([(node_id, 0)])
        neighbors = []
        
        while queue:
            current_id, current_depth = queue.popleft()
            
            if current_id in visited or current_depth > depth:
                continue
            
            visited.add(current_id)
            
            # 获取邻居
            for neighbor in self.graph.neighbors(current_id):
                if neighbor not in visited and current_depth < depth:
                    queue.append((neighbor, current_depth + 1))
                    neighbors.append({
                        "node": self.node_map[neighbor].to_dict(),
                        "distance": current_depth + 1,
                        "edges": list(self.graph.edges(current_id, neighbor, data=True))
                    })
        
        return {
            "center": self.node_map[node_id].to_dict(),
            "depth": depth,
            "neighbors": neighbors
        }
    
    def find_path(self, source: str, target: str, max_length: int = 10) -> List[List[str]]:
        """查找路径"""
        try:
            if source not in self.graph or target not in self.graph:
                return []
            
            return list(nx.all_simple_paths(self.graph, source, target, cutoff=max_length))
        except Exception as e:
            self.logger.error(f"查找路径失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "node_count": len(self.node_map),
            "edge_count": len(self.edge_map),
            "node_types": {k: len(v) for k, v in self.type_index.items()},
            "graph_density": nx.density(self.graph),
            "is_connected": nx.is_weakly_connected(self.graph),
            "connected_components": nx.number_weakly_connected_components(self.graph)
        }
        
        return stats
    
    def visualize(self, output_path: Optional[str] = None):
        """可视化图谱"""
        if not self.config.enable_visualization:
            return
        
        try:
            plt.figure(figsize=(12, 8))
            pos = nx.spring_layout(self.graph, seed=42)
            
            # 绘制节点和边
            nx.draw_networkx_nodes(self.graph, pos, node_size=500, alpha=0.8)
            nx.draw_networkx_edges(self.graph, pos, alpha=0.5)
            
            # 标签
            labels = {node: self.node_map[node].label for node in self.graph.nodes()}
            nx.draw_networkx_labels(self.graph, pos, labels, font_size=10)
            
            plt.title(f"知识图谱 - {len(self.node_map)} 节点, {len(self.edge_map)} 边")
            plt.axis('off')
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"图谱已保存: {output_path}")
            else:
                plt.show()
                
        except Exception as e:
            self.logger.error(f"可视化失败: {e}")
    
    def save(self, filepath: str) -> bool:
        """保存图谱"""
        try:
            data = {
                "config": self.config.__dict__,
                "node_map": {k: v.__dict__ for k, v in self.node_map.items()},
                "edge_map": {k: v.__dict__ for k, v in self.edge_map.items()},
                "type_index": dict(self.type_index),
                "property_index": {k: dict(v) for k, v in self.property_index.items()}
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            
            self.logger.info(f"图谱已保存: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存失败: {e}")
            return False
    
    def load(self, filepath: str) -> bool:
        """加载图谱"""
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            # 恢复配置
            self.config = KnowledgeGraphConfig(**data.get("config", {}))
            
            # 重建图
            self.graph = nx.MultiDiGraph()
            self.node_map = {}
            self.edge_map = {}
            self.type_index = defaultdict(set)
            self.property_index = defaultdict(lambda: defaultdict(set))
            
            # 恢复节点
            for node_id, node_data in data.get("node_map", {}).items():
                node = GraphNode(**node_data)
                self.node_map[node_id] = node
                self.graph.add_node(node_id, **node.properties)
            
            # 恢复边
            for edge_id, edge_data in data.get("edge_map", {}).items():
                edge = GraphEdge(**edge_data)
                self.edge_map[edge_id] = edge
                self.graph.add_edge(edge.source, edge.target, key=edge_id,
                                  label=edge.label, weight=edge.weight, **edge.properties)
            
            # 恢复索引
            self.type_index.update(data.get("type_index", {}))
            self.property_index.update(data.get("property_index", {}))
            
            self.logger.info(f"图谱已加载: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"加载失败: {e}")
            return False