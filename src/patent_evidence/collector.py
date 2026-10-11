"""
专利证据收集器 - 收集和管理创新证据
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd


class PatentEvidenceCollector:
    """专利证据收集器"""
    
    _instances = {}
    
    def __new__(cls, system_name: str):
        """单例模式"""
        if system_name not in cls._instances:
            cls._instances[system_name] = super().__new__(cls)
        return cls._instances[system_name]
    
    def __init__(self, system_name: str):
        if not hasattr(self, '_initialized'):
            self.system_name = system_name
            self.evidence_dir = Path("./data/patent_evidence")
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            
            # 证据存储
            self.evolution_records = []
            self.decision_logs = []
            self.knowledge_discoveries = []
            self.performance_metrics = []
            self.snapshots = []
            
            self._initialized = True
    
    def log_evolution(self, module: str, decision: str, reason: str,
                     before_state: Dict[str, Any], after_state: Dict[str, Any],
                     impact_score: float):
        """记录系统进化证据"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "decision": decision,
            "reason": reason,
            "before_state": before_state,
            "after_state": after_state,
            "impact_score": impact_score,
            "system_name": self.system_name
        }
        
        self.evolution_records.append(record)
        self._save_to_file("evolution", record)
        return record
    
    def log_decision(self, decision_point: str, options: List[Dict[str, Any]],
                    chosen_option: Dict[str, Any], reasoning: str,
                    confidence: float, context: Optional[Dict[str, Any]] = None):
        """记录决策过程证据"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "decision_point": decision_point,
            "options": options,
            "chosen_option": chosen_option,
            "reasoning": reasoning,
            "confidence": confidence,
            "context": context or {},
            "system_name": self.system_name
        }
        
        self.decision_logs.append(record)
        self._save_to_file("decisions", record)
        return record
    
    def log_knowledge(self, entity: str, relation: str, value: Any,
                     source: str, confidence: float, is_new_pattern: bool):
        """记录知识发现证据"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "entity": entity,
            "relation": relation,
            "value": str(value),
            "source": source,
            "confidence": confidence,
            "is_new_pattern": is_new_pattern,
            "system_name": self.system_name
        }
        
        self.knowledge_discoveries.append(record)
        self._save_to_file("knowledge", record)
        return record
    
    def log_performance(self, metric_name: str, old_value: float, new_value: float,
                       test_dataset: str, conditions: Dict[str, Any]):
        """记录性能改进证据"""
        improvement = new_value - old_value
        improvement_pct = (improvement / old_value * 100) if old_value != 0 else 0
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "metric_name": metric_name,
            "old_value": old_value,
            "new_value": new_value,
            "improvement": improvement,
            "improvement_percentage": improvement_pct,
            "test_dataset": test_dataset,
            "conditions": conditions,
            "system_name": self.system_name
        }
        
        self.performance_metrics.append(record)
        self._save_to_file("performance", record)
        return record
    
    def take_snapshot(self, snapshot_type: str, system_state: Dict[str, Any]) -> Path:
        """拍摄系统快照"""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "snapshot_type": snapshot_type,
            "system_state": system_state,
            "system_name": self.system_name
        }
        
        self.snapshots.append(snapshot)
        
        # 保存快照文件
        snapshot_file = self.evidence_dir / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        
        return snapshot_file
    
    def _save_to_file(self, category: str, record: Dict[str, Any]):
        """保存记录到文件"""
        # 按日期组织文件
        date_str = datetime.now().strftime('%Y%m%d')
        file_path = self.evidence_dir / f"{category}_{date_str}.jsonl"
        
        # 追加记录
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    def export_to_excel(self) -> Path:
        """导出所有证据到Excel"""
        # 准备数据
        data = {
            "Evolution Records": pd.DataFrame(self.evolution_records),
            "Decision Logs": pd.DataFrame(self.decision_logs),
            "Knowledge Discoveries": pd.DataFrame(self.knowledge_discoveries),
            "Performance Metrics": pd.DataFrame(self.performance_metrics)
        }
        
        # 导出到Excel
        export_file = self.evidence_dir / f"patent_evidence_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        with pd.ExcelWriter(export_file, engine='openpyxl') as writer:
            for sheet_name, df in data.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return export_file


def get_collector(system_name: str) -> PatentEvidenceCollector:
    """获取专利证据收集器实例"""
    return PatentEvidenceCollector(system_name)