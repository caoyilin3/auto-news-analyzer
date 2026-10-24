"""长期学习效果评估

把每个周期的实测指标与当时生效的参数写入数据集（JSONL/CSV），并基于历史数据
做趋势分析，输出可复核的结论与洞察。

设计目标：替代此前"规则话术"式的反思文本——每条结论都必须能由数据集中
的样本算出来，便于论文/答辩时逐条核对。
"""

import csv
import json
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 参与趋势分析的指标
TRACKED_METRICS = (
    "learn_rate",
    "reject_rate",
    "accuracy_rate",
    "extraction_yield",
    "relation_yield",
)

# 参与漂移分析的参数
TRACKED_PARAMS = (
    "credibility.theta_high",
    "credibility.theta_low",
    "extraction.relation_min_confidence",
)

# 趋势判定阈值（变化超过该值才认为有方向性）
TREND_EPSILON = 0.02


class LearningEffectivenessEvaluator:
    """基于周期数据集的学习效果评估器"""

    def __init__(self, dataset_path: str = "data/cycle_metrics.jsonl"):
        self.dataset_path = Path(dataset_path)
        self.logger = logging.getLogger("Evolution.Effectiveness")

    # ------------------------------------------------------------------ 数据集
    def record_cycle(
        self,
        metrics: Dict[str, Any],
        tunables: Optional[Dict[str, Any]] = None,
        changes: Optional[List[Dict[str, Any]]] = None,
        cycle_id: Optional[str] = None,
        tunables_before: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """追加写入一个周期的样本

        tunables 记录周期结束时的参数值；tunables_before 记录周期开始前的值，
        用于准确计算参数漂移（否则第一条样本已经是调整后的值）。
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "cycle_id": cycle_id,
            "metrics": {
                k: round(float(v), 6)
                for k, v in (metrics or {}).items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            },
            "tunables": dict(tunables or {}),
            "tunables_before": dict(tunables_before or tunables or {}),
            "changes": changes or [],
            "changed": bool(changes),
        }
        try:
            self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.dataset_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            self.logger.warning(f"写入周期数据集失败: {e}")
        return record

    def load_records(self, limit: int = 200) -> List[Dict[str, Any]]:
        """读取最近的周期样本"""
        if not self.dataset_path.exists():
            return []
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                lines = [line for line in f if line.strip()][-limit:]
            records = []
            for line in lines:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return records
        except Exception as e:
            self.logger.warning(f"读取周期数据集失败: {e}")
            return []

    def export_csv(self, path: Optional[str] = None) -> Optional[str]:
        """把数据集导出为 CSV（便于用 Excel/pandas 做图表）"""
        records = self.load_records(limit=10000)
        if not records:
            return None

        target = Path(path) if path else self.dataset_path.with_suffix(".csv")
        metric_keys = sorted({k for r in records for k in (r.get("metrics") or {})})
        param_keys = sorted({k for r in records for k in (r.get("tunables") or {})})
        columns = ["timestamp", "cycle_id", "changed"] + metric_keys + param_keys

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for record in records:
                    row = {
                        "timestamp": record.get("timestamp"),
                        "cycle_id": record.get("cycle_id"),
                        "changed": int(bool(record.get("changed"))),
                    }
                    row.update(record.get("metrics") or {})
                    row.update(record.get("tunables") or {})
                    writer.writerow({k: row.get(k, "") for k in columns})
            return str(target)
        except Exception as e:
            self.logger.warning(f"导出 CSV 失败: {e}")
            return None

    # ------------------------------------------------------------------ 评估
    def evaluate(self, window: int = 50) -> Dict[str, Any]:
        """基于最近 window 个周期做趋势与漂移分析"""
        records = self.load_records(limit=window)
        result: Dict[str, Any] = {
            "samples": len(records),
            "window": window,
            "dataset": {
                "path": str(self.dataset_path),
                "exists": self.dataset_path.exists(),
            },
            "verdict": "insufficient_data",
            "trends": {},
            "parameter_drift": {},
            "insights": [],
        }
        if records:
            result["dataset"]["first_cycle"] = records[0].get("timestamp")
            result["dataset"]["last_cycle"] = records[-1].get("timestamp")

        if len(records) < 2:
            result["insights"] = [
                f"数据集样本不足（{len(records)} 个周期），至少需要 2 个周期才能判断趋势"
            ]
            return result

        half = max(1, len(records) // 2)
        first, second = records[:half], records[half:]

        # 1. 指标趋势：前半段 vs 后半段均值
        trends = {}
        for key in TRACKED_METRICS:
            first_values = [r["metrics"][key] for r in first if key in (r.get("metrics") or {})]
            second_values = [r["metrics"][key] for r in second if key in (r.get("metrics") or {})]
            if not first_values or not second_values:
                continue
            before = sum(first_values) / len(first_values)
            after = sum(second_values) / len(second_values)
            delta = after - before
            direction = "flat"
            if delta > TREND_EPSILON:
                direction = "up"
            elif delta < -TREND_EPSILON:
                direction = "down"
            trends[key] = {
                "first_half_mean": round(before, 4),
                "second_half_mean": round(after, 4),
                "delta": round(delta, 4),
                "direction": direction,
            }
        result["trends"] = trends

        # 2. 参数漂移：首末样本对比（首次取周期开始前的值，避免漏掉第一轮调整）
        drift = {}
        for key in TRACKED_PARAMS:
            first_value = next(
                (
                    (r.get("tunables_before") or {}).get(key)
                    for r in records
                    if key in (r.get("tunables_before") or r.get("tunables") or {})
                ),
                None,
            )
            last_value = next(
                (r["tunables"][key] for r in reversed(records) if key in (r.get("tunables") or {})),
                None,
            )
            if first_value is None or last_value is None:
                continue
            drift[key] = {
                "first": first_value,
                "last": last_value,
                "delta": round(float(last_value) - float(first_value), 6),
            }
        result["parameter_drift"] = drift

        # 3. 综合结论
        changed_cycles = sum(1 for r in records if r.get("changed"))
        learn = trends.get("learn_rate", {})
        reject = trends.get("reject_rate", {})
        verdict = "stable"
        if learn.get("delta", 0) > 0.05 and reject.get("delta", 0) <= 0.05:
            verdict = "improving"
        elif learn.get("delta", 0) < -0.05 or reject.get("delta", 0) > 0.1:
            verdict = "degrading"
        if changed_cycles == 0:
            verdict = "no_adaptation"
        result["verdict"] = verdict
        result["changed_cycles"] = changed_cycles

        # 4. 数据驱动的洞察（每条都可以从数据集中复算）
        insights: List[str] = []
        if learn:
            insights.append(
                f"learn 占比 {learn['first_half_mean']:.3f} → {learn['second_half_mean']:.3f}"
                f"（{learn['delta']:+.3f}），趋势：{self._direction_text(learn['direction'])}"
            )
        if reject:
            insights.append(
                f"拦截率 {reject['first_half_mean']:.3f} → {reject['second_half_mean']:.3f}"
                f"（{reject['delta']:+.3f}）"
            )
        for key, value in drift.items():
            if value["delta"] != 0:
                insights.append(
                    f"参数 {key} 由 {value['first']} 调整到 {value['last']}"
                    f"（{value['delta']:+.3f}）"
                )
        for key in ("extraction_yield", "relation_yield"):
            trend = trends.get(key)
            if trend:
                values = [
                    r["metrics"][key] for r in records if key in (r.get("metrics") or {})
                ]
                spread = statistics.pstdev(values) if len(values) > 1 else 0.0
                insights.append(
                    f"{self._metric_label(key)} 均值 {trend['second_half_mean']:.3f}，"
                    f"波动 ±{spread:.3f}"
                )
        insights.append(
            f"共 {len(records)} 个周期，其中 {changed_cycles} 个周期发生参数调整；"
            f"综合判定：{self._verdict_text(verdict)}"
        )
        result["insights"] = insights
        return result

    # ------------------------------------------------------------------ 文案
    @staticmethod
    def _direction_text(direction: str) -> str:
        return {"up": "上升", "down": "下降"}.get(direction, "基本持平")

    @staticmethod
    def _verdict_text(verdict: str) -> str:
        return {
            "improving": "持续改善",
            "degrading": "出现退化",
            "stable": "保持稳定",
            "no_adaptation": "未发生自适应调整",
            "insufficient_data": "样本不足",
        }.get(verdict, verdict)

    @staticmethod
    def _metric_label(key: str) -> str:
        return {
            "extraction_yield": "单篇实体产出",
            "relation_yield": "单篇关系产出",
        }.get(key, key)
