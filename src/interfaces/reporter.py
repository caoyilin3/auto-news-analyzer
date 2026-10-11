# src/interfaces/reporter.py
"""
报告生成器 - 汇总各模块执行结果，生成结构化运行报告
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


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
        report = {
            "report_id": f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "system": {
                "name": context.get("system_name", "AutoNewsAnalyzer"),
                "mode": context.get("mode", "development"),
            },
            "summary": {
                "articles_collected": context.get("total", context.get("articles_collected", 0)),
                "articles_passed": context.get("articles_passed", len(context.get("articles", []))),
                "articles_rejected": context.get("rejected_count", 0),
                "entities_extracted": context.get("total_entities", 0),
                "relations_extracted": context.get("total_relations", 0),
                "evolved": context.get("evolved", False),
            },
            "stages": {
                "data_acquisition": {
                    "stats": context.get("stats", {}),
                },
                "credibility": {
                    "total_assessed": context.get("total_assessed", 0),
                    "rejected": context.get("rejected_count", 0),
                },
                "knowledge_extraction": {
                    "entities": context.get("total_entities", 0),
                    "relations": context.get("total_relations", 0),
                },
                "lifecycle": {
                    "added": context.get("added", 0),
                },
                "evolution": {
                    "evolved": context.get("evolved", False),
                },
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
        return "\n".join(lines)

    async def get_report(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成并保存报告，返回报告"""
        report = await self.generate_report(context)
        self.save_report(report, fmt="json")
        return report
