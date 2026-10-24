# src/interfaces/reporter.py
"""
报告生成器 - 汇总各模块执行结果，生成结构化运行报告
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from ..utils.helpers import format_duration, generate_unique_id


class ReportGenerator:
    """报告生成器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        output_dir = config.get("output_dir") or "output"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    async def generate_report(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        生成系统运行报告

        Args:
            context: 执行上下文，包含各模块结果

        Returns:
            报告内容
        """
        context = context or {}
        # 引擎会把每个步骤的独立产出放在 _step_data 里，按步骤取数可避免同名键互相覆盖
        step_data = context.get("_step_data", {}) or {}
        acquisition = step_data.get("data_acquisition", {})
        credibility = step_data.get("credibility_assessment", {})
        knowledge = step_data.get("knowledge_extraction", {})
        lifecycle = step_data.get("memory_management", {})
        evolution = step_data.get("evolution_learning", {})

        passed = len(credibility.get("articles", []))
        rejected = credibility.get("rejected_count", 0)
        collected = acquisition.get("total", context.get("total", passed + rejected if passed or rejected else 0))
        evolved = bool(evolution.get("evolved", context.get("evolved", False)))
        changes = evolution.get("changes") or context.get("changes") or []

        # 本周期已耗时（用于报告中的可读时长）
        duration_seconds = 0.0
        if context.get("start_time"):
            try:
                duration_seconds = max(
                    0.0,
                    (datetime.now() - datetime.fromisoformat(context["start_time"])).total_seconds(),
                )
            except Exception:
                duration_seconds = 0.0

        report = {
            # 秒级时间戳在快速连续运行时可能重名，这里加随机后缀保证唯一
            "report_id": generate_unique_id("report"),
            "generated_at": datetime.now().isoformat(),
            "duration_text": format_duration(duration_seconds),
            "system": {
                "name": context.get("system_name", "AutoNewsAnalyzer"),
                "mode": context.get("mode", "development"),
            },
            "summary": {
                "articles_collected": collected,
                "articles_passed": passed,
                "articles_rejected": rejected,
                "entities_extracted": knowledge.get("total_entities", 0),
                "relations_extracted": knowledge.get("total_relations", 0),
                "evolved": evolved,
                "adjustments": len(changes),
            },
            "stages": {
                "data_acquisition": {
                    "stats": acquisition.get("stats", {}),
                },
                "credibility": {
                    "total_assessed": credibility.get("total_assessed", 0),
                    "rejected": rejected,
                },
                "knowledge_extraction": {
                    "entities": knowledge.get("total_entities", 0),
                    "relations": knowledge.get("total_relations", 0),
                    "llm_triples": knowledge.get("llm_triples", 0),
                },
                "lifecycle": {
                    "added": lifecycle.get("added", 0),
                },
                "evolution": {
                    "evolved": evolved,
                    "reason": evolution.get("reason"),
                    "changes": changes,
                    "tunables": evolution.get("tunables") or context.get("tunables", {}),
                    "metrics": evolution.get("metrics", {}),
                },
                "evaluation": context.get("evaluation") or {},
                "feedback": context.get("feedback_summary", {}),
            },
        }
        # 顺带保存 JSON 报告到输出目录
        try:
            self.save_report(report, fmt="json")
        except Exception as e:
            self.logger.warning(f"报告保存失败: {e}")
        return report

    def save_report(self, report: Dict[str, Any], fmt: str = "json") -> str:
        """
        保存报告到文件

        Args:
            report: 报告内容
            fmt: 输出格式（json / markdown）

        Returns:
            保存的文件路径
        """
        if fmt == "json":
            path = self.output_dir / f"{report['report_id']}.json"
            path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        elif fmt == "markdown":
            path = self.output_dir / f"{report['report_id']}.md"
            path.write_text(self._to_markdown(report), encoding="utf-8")
        else:
            raise ValueError(f"不支持的格式: {fmt}")

        self.logger.info(f"报告已保存: {path}")
        return str(path)

    @staticmethod
    def _to_markdown(report: Dict[str, Any]) -> str:
        """将报告转换为 Markdown"""
        lines = [
            f"# {report['system']['name']} 运行报告",
            "",
            f"- 生成时间：{report['generated_at']}",
            f"- 运行模式：{report['system']['mode']}",
            "",
            "## 汇总",
            "",
            f"- 采集文章：{report['summary']['articles_collected']}",
            f"- 通过评估：{report['summary']['articles_passed']}",
            f"- 拦截文章：{report['summary']['articles_rejected']}",
            f"- 提取实体：{report['summary']['entities_extracted']}",
            f"- 提取关系：{report['summary']['relations_extracted']}",
            f"- 是否进化：{'是' if report['summary']['evolved'] else '否'}",
            "",
        ]
        changes = report.get("stages", {}).get("evolution", {}).get("changes") or []
        if changes:
            lines.append("## 本轮参数调整")
            lines.append("")
            for change in changes:
                lines.append(
                    f"- `{change.get('parameter')}`：{change.get('before')} → "
                    f"{change.get('after')}（{change.get('reason', '')}）"
                )
            lines.append("")

        evaluation = report.get("stages", {}).get("evaluation") or {}
        if evaluation.get("insights"):
            lines.append("## 长期学习效果")
            lines.append("")
            lines.append(
                f"- 样本数：{evaluation.get('samples')}，"
                f"判定：{evaluation.get('verdict')}"
            )
            for insight in evaluation["insights"]:
                lines.append(f"- {insight}")
            lines.append("")
        return "\n".join(lines)

    async def get_report(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成并保存报告，返回报告"""
        report = await self.generate_report(context)
        self.save_report(report, fmt="json")
        return report
