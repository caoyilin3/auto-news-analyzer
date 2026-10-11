"""
专利证据管理器 - 管理证据收集和报告生成
"""
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np


class EvidenceManager:
    """证据管理器"""
    
    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
    
    def load_all_evidence(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载所有证据"""
        evidence = {
            "evolution": [],
            "decisions": [],
            "knowledge": [],
            "performance": [],
            "snapshots": []
        }
        
        # 加载JSONL文件
        for category in ["evolution", "decisions", "knowledge", "performance"]:
            pattern = f"{category}_*.jsonl"
            for file_path in self.evidence_dir.glob(pattern):
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            evidence[category].append(json.loads(line.strip()))
        
        # 加载快照
        for snapshot_file in self.evidence_dir.glob("snapshot_*.json"):
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                evidence["snapshots"].append(json.load(f))
        
        return evidence
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """生成摘要报告"""
        evidence = self.load_all_evidence()
        
        # 计算统计信息
        stats = {
            "total_evolution_records": len(evidence["evolution"]),
            "total_decision_logs": len(evidence["decisions"]),
            "total_knowledge_discoveries": len(evidence["knowledge"]),
            "total_performance_metrics": len(evidence["performance"]),
            "total_snapshots": len(evidence["snapshots"]),
            "time_range": self._get_time_range(evidence)
        }
        
        # 关键发现
        key_findings = self._extract_key_findings(evidence)
        
        # 性能趋势
        performance_trends = self._analyze_performance_trends(evidence)
        
        # 进化轨迹
        evolution_trajectory = self._analyze_evolution_trajectory(evidence)
        
        return {
            "report_generated_at": datetime.now().isoformat(),
            "statistics": stats,
            "key_findings": key_findings,
            "performance_trends": performance_trends,
            "evolution_trajectory": evolution_trajectory,
            "evidence_summary": {
                "evolution_samples": evidence["evolution"][-5:] if evidence["evolution"] else [],
                "decision_samples": evidence["decisions"][-5:] if evidence["decisions"] else [],
                "knowledge_samples": evidence["knowledge"][-5:] if evidence["knowledge"] else []
            }
        }
    
    def export_to_excel(self) -> Path:
        """导出到Excel"""
        evidence = self.load_all_evidence()
        
        # 创建DataFrame
        dfs = {}
        
        for category, records in evidence.items():
            if records:
                dfs[category] = pd.DataFrame(records)
        
        # 导出
        export_file = self.evidence_dir / f"evidence_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        with pd.ExcelWriter(export_file, engine='openpyxl') as writer:
            # 写入数据
            for sheet_name, df in dfs.items():
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            
            # 写入摘要
            summary = self.generate_summary_report()
            summary_df = pd.DataFrame([{
                "统计项": k,
                "值": str(v)[:500]  # 限制长度
            } for k, v in summary.items()])
            summary_df.to_excel(writer, sheet_name="摘要", index=False)
        
        return export_file
    
    def _get_time_range(self, evidence: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
        """获取时间范围"""
        all_timestamps = []
        
        for category, records in evidence.items():
            for record in records:
                if "timestamp" in record:
                    all_timestamps.append(datetime.fromisoformat(record["timestamp"]))
        
        if all_timestamps:
            return {
                "start": min(all_timestamps).isoformat(),
                "end": max(all_timestamps).isoformat(),
                "duration_days": (max(all_timestamps) - min(all_timestamps)).days
            }
        
        return {"start": "", "end": "", "duration_days": 0}
    
    def _extract_key_findings(self, evidence: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """提取关键发现"""
        key_findings = []
        
        # 从知识发现中提取新模式
        for record in evidence["knowledge"]:
            if record.get("is_new_pattern", False):
                key_findings.append({
                    "type": "new_pattern",
                    "description": f"发现新模式: {record.get('entity')} - {record.get('relation')} - {record.get('value')}",
                    "confidence": record.get("confidence", 0),
                    "timestamp": record.get("timestamp")
                })
        
        # 从进化记录中提取重大变更
        for record in evidence["evolution"]:
            if record.get("impact_score", 0) > 0.7:  # 高影响变更
                key_findings.append({
                    "type": "major_evolution",
                    "description": f"重大系统进化: {record.get('decision')}",
                    "impact": record.get("impact_score", 0),
                    "timestamp": record.get("timestamp")
                })
        
        # 从性能指标中提取显著改进
        for record in evidence["performance"]:
            if abs(record.get("improvement_percentage", 0)) > 20:  # 超过20%的改进
                key_findings.append({
                    "type": "significant_improvement",
                    "description": f"性能显著{('提升' if record.get('improvement', 0) > 0 else '下降')}: {record.get('metric_name')} ({record.get('improvement_percentage', 0):.1f}%)",
                    "metric": record.get("metric_name"),
                    "improvement": record.get("improvement_percentage", 0),
                    "timestamp": record.get("timestamp")
                })
        
        return key_findings
    
    def _analyze_performance_trends(self, evidence: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """分析性能趋势"""
        if not evidence["performance"]:
            return {"status": "no_data"}
        
        # 按指标分组
        metrics_by_name = {}
        for record in evidence["performance"]:
            metric_name = record.get("metric_name")
            if metric_name not in metrics_by_name:
                metrics_by_name[metric_name] = []
            metrics_by_name[metric_name].append(record)
        
        trends = {}
        for metric_name, records in metrics_by_name.items():
            # 按时间排序
            sorted_records = sorted(records, key=lambda x: x.get("timestamp", ""))
            
            if len(sorted_records) >= 2:
                first = sorted_records[0]
                last = sorted_records[-1]
                
                improvement = last.get("new_value", 0) - first.get("old_value", 0)
                improvement_pct = (improvement / first.get("old_value", 0) * 100) if first.get("old_value", 0) != 0 else 0
                
                trends[metric_name] = {
                    "initial_value": first.get("old_value", 0),
                    "final_value": last.get("new_value", 0),
                    "total_improvement": improvement,
                    "improvement_percentage": improvement_pct,
                    "measurements": len(records)
                }
        
        return trends
    
    def _analyze_evolution_trajectory(self, evidence: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """分析进化轨迹"""
        if not evidence["evolution"]:
            return []
        
        # 按时间排序
        sorted_evolution = sorted(evidence["evolution"], key=lambda x: x.get("timestamp", ""))
        
        trajectory = []
        for i, record in enumerate(sorted_evolution):
            trajectory.append({
                "sequence": i + 1,
                "timestamp": record.get("timestamp"),
                "module": record.get("module"),
                "decision": record.get("decision"),
                "impact": record.get("impact_score", 0),
                "reason": record.get("reason", "")[:100]
            })
        
        return trajectory


def setup_patent_directory(evidence_dir: Path):
    """设置专利证据目录"""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建README
    readme_file = evidence_dir / "README.md"
    readme_content = """# Patent Evidence Directory

This directory contains evidence collected for patent applications related to the autonomous evolution capabilities of AutoNewsAnalyzer v2.0.

## File Structure

- `evolution_YYYYMMDD.jsonl`: Evolution records showing system self-improvement
- `decisions_YYYYMMDD.jsonl`: Decision-making process logs
- `knowledge_YYYYMMDD.jsonl`: Knowledge discoveries and new patterns
- `performance_YYYYMMDD.jsonl`: Performance improvement metrics
- `snapshot_YYYYMMDD_HHMMSS.json`: System state snapshots
- `evidence_report_*.xlsx`: Comprehensive evidence reports

## Evidence Categories

1. **Evolution Evidence**: Records of autonomous system improvements
2. **Decision Evidence**: Documentation of AI decision-making processes
3. **Knowledge Evidence**: Novel knowledge discoveries and patterns
4. **Performance Evidence**: Quantifiable performance improvements
5. **Snapshot Evidence**: System state at specific points in time

## Patent Relevance

This evidence demonstrates:
- Autonomous system evolution capability
- Novel AI decision-making mechanisms
- Knowledge discovery and pattern recognition
- Continuous performance improvement
- Self-optimizing system architecture
"""
    
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    return evidence_dir