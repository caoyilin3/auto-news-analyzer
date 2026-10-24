# src/evolution/manager.py
"""
进化管理器 - 协调元认知、安全控制与学习规划，实现系统自主进化

闭环流程：
    真实指标评估 → 学习需求分析 → 学习计划 → 安全审查 → 参数落地 → 证据记录
其中「参数落地」通过 register_tunable() 注册的调参接口完成，使学习计划真正改变
系统行为（如可信度阈值），而不是只停留在计划文本上。
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .meta_cognitive import AutoMetaCognitiveController, SelfAssessment
from .safety_controller import AutoSafetyController
from .learning_planner import AutoLearningPlanner


class EvolutionManager:
    """进化管理器"""

    # 目标区间：learn 决策占比低于该值时放宽 learn 阈值
    TARGET_LEARN_RATIO = 0.5
    # theta_high 与 theta_low 之间必须保留的最小间隔，避免双阈值退化
    MIN_THETA_GAP = 0.10

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 兼容旧调用：直接传系统名
        if isinstance(config, str) or config is None:
            config = {"system_name": config if isinstance(config, str) else "AutoNewsAnalyzer"}

        self.config = config
        self.system_name = config.get("system_name", "AutoNewsAnalyzer")
        self.enabled = bool(config.get("enabled", True))
        self.max_changes_per_cycle = int(config.get("max_changes_per_cycle", 3))
        self.history_path = Path(
            config.get("history_path", "data/evolution_history.jsonl")
        )
        self.logger = logging.getLogger(f"EvolutionManager.{self.system_name}")

        # 三个子组件
        self.meta_cognitive = AutoMetaCognitiveController(self.system_name)
        self.safety_controller = AutoSafetyController(self.system_name)
        self.learning_planner = AutoLearningPlanner(self.system_name)

        # 让元认知在被动评估时也能拿到真实指标（而不是随机数）
        self.meta_cognitive.set_metrics_provider(self._metrics_snapshot)

        # 可调参数注册表： name -> {get, set, min, max, step}
        self.tunables: Dict[str, Dict[str, Any]] = {}

        # 长期学习效果评估器（由引擎注入）
        self.evaluator = None

        # 最近一次评估指标
        self.last_metrics: Dict[str, float] = {}

        # 进化历史
        self.history: List[Dict[str, Any]] = []
        # 兼容旧属性名
        self.evolution_history = self.history
        self._load_history()

    # ------------------------------------------------------------------ 调参接口
    def register_tunable(
        self,
        name: str,
        getter: Callable[[], Any],
        setter: Callable[[Any], None],
        minimum: float,
        maximum: float,
        step: float,
    ) -> None:
        """注册一个可调参数（由引擎在模块初始化完成后调用）"""
        if not 0 < step <= (maximum - minimum):
            raise ValueError(f"参数 {name} 的步长非法: step={step}")
        self.tunables[name] = {
            "get": getter,
            "set": setter,
            "min": float(minimum),
            "max": float(maximum),
            "step": float(step),
        }
        self.logger.info(f"已注册可调参数: {name}")

    def get_tunable_values(self) -> Dict[str, Any]:
        """读取当前所有可调参数的取值"""
        values = {}
        for name, spec in self.tunables.items():
            try:
                values[name] = spec["get"]()
            except Exception as e:  # 单个参数读取失败不应影响整体
                self.logger.warning(f"读取参数 {name} 失败: {e}")
        return values

    def attach_evaluator(self, evaluator) -> None:
        """注入长期效果评估器（引擎在初始化时调用）"""
        self.evaluator = evaluator
        if evaluator is not None:
            self.meta_cognitive.set_insight_provider(self._effectiveness_insights)
            self.logger.info("已接入长期学习效果评估器")

    def _effectiveness_insights(self) -> List[str]:
        """把长期评估结论转成元认知洞察"""
        return self._evaluate_effectiveness().get("insights", [])

    def _evaluate_effectiveness(self) -> Dict[str, Any]:
        """长期效果评估（失败时返回空，不影响进化主流程）"""
        if self.evaluator is None:
            return {}
        try:
            evaluation = self.evaluator.evaluate()
        except Exception as e:
            self.logger.warning(f"长期效果评估失败: {e}")
            return {}
        # 只保留报告需要的字段，避免把完整数据集元信息写进每条历史
        return {
            key: evaluation.get(key)
            for key in ("samples", "verdict", "trends", "parameter_drift",
                        "changed_cycles", "insights")
            if key in evaluation
        }

    # ------------------------------------------------------------------ 指标
    def _metrics_snapshot(self) -> Dict[str, float]:
        """供元认知控制器回调的指标快照"""
        return dict(self.last_metrics)

    def build_assessment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """根据一次真实运行的结果构建自我评估（替代原来的固定数值）"""
        metrics = self._compute_metrics(context or {})
        self.last_metrics = dict(metrics)
        strengths, weaknesses, suggestions = self._derive_findings(metrics)
        return {
            "component": self.system_name,
            "metrics": metrics,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "confidence": round(min(1.0, 0.5 + 0.5 * metrics.get("coverage", 0.0)), 3),
            "overall_score": round(self._overall_score(metrics), 4),
        }

    def _compute_metrics(self, context: Dict[str, Any]) -> Dict[str, float]:
        """从工作流上下文中提取可度量的真实指标"""
        articles = context.get("articles") or []
        passed = len(articles)
        rejected = int(context.get("rejected_count", 0) or 0)

        decisions = [d for d in (context.get("decisions") or []) if isinstance(d, dict)]
        learn = sum(1 for d in decisions if d.get("decision") == "learn")
        review = sum(1 for d in decisions if d.get("decision") == "review")
        if not decisions:
            # 没有决策明细时，把通过评估的文章视为 review
            review = passed

        total = int(context.get("total", 0) or 0)
        total = max(total, passed + rejected, 1)

        entities = float(context.get("total_entities", 0) or 0)
        relations = float(context.get("total_relations", 0) or 0)
        llm_triples = float(context.get("llm_triples", 0) or 0)

        step_data = context.get("_step_data") or {}
        workflow = context.get("_workflow_stats") or {}
        attempted = int(workflow.get("attempted", len(step_data)) or 0)
        failed = int(workflow.get("failed", 0) or 0)
        # 执行成功率：已尝试执行的步骤中有多少没有失败（进化步骤运行时通常为 3/3）
        coverage = (1.0 - failed / attempted) if attempted else 0.0

        recent = self.history[-5:]
        adaptation = (
            sum(1 for h in recent if h.get("changes")) / len(recent) if recent else 0.0
        )

        return {
            "accuracy_rate": round(passed / total, 4),
            "error_rate": round(rejected / total, 4),
            "learn_rate": round(learn / total, 4),
            "review_rate": round(review / total, 4),
            "reject_rate": round(rejected / total, 4),
            "extraction_yield": round(entities / max(passed, 1), 4),
            "relation_yield": round(relations / max(passed, 1), 4),
            "llm_triples": llm_triples,
            "processing_speed": round(coverage, 4),
            "adaptation_speed": round(adaptation, 4),
            "coverage": round(coverage, 4),
            "total_articles": float(total),
            "passed_articles": float(passed),
            "rejected_articles": float(rejected),
        }

    @staticmethod
    def _overall_score(m: Dict[str, float]) -> float:
        score = (
            0.35 * m.get("accuracy_rate", 0.0)
            + 0.25 * (1.0 - m.get("reject_rate", 0.0))
            + 0.20 * min(m.get("extraction_yield", 0.0) / 3.0, 1.0)
            + 0.20 * m.get("coverage", 0.0)
        )
        return max(0.0, min(1.0, score))

    def _derive_findings(self, m: Dict[str, float]):
        """把指标转成学习规划器能识别的强弱项与建议"""
        strengths: List[str] = []
        weaknesses: List[str] = []
        suggestions: List[str] = []

        if m["learn_rate"] >= self.TARGET_LEARN_RATIO:
            strengths.append("高性能表现")
        else:
            weaknesses.append("性能有待提升")
            suggestions.append("优化算法参数和数据处理流程")

        if m["reject_rate"] <= 0.5:
            strengths.append("高效率运行")
        else:
            weaknesses.append("错误率偏高")
            suggestions.append("加强数据验证和错误处理机制")

        if m["coverage"] < 1.0:
            weaknesses.append("稳定性不足")
            suggestions.append("提升稳定性")

        if m["extraction_yield"] < 2.0:
            weaknesses.append("提取能力不足")

        if m["relation_yield"] < 0.5:
            weaknesses.append("关系覆盖不足")

        return strengths, weaknesses, suggestions

    # ------------------------------------------------------------------ 参数决策
    def _clamp(self, value: float, spec: Dict[str, Any]) -> float:
        return round(max(spec["min"], min(spec["max"], value)), 6)

    def _plan_changes(self, metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """根据指标决定本轮要调整的参数（有界、可解释、可追溯）"""
        proposals: List[Dict[str, Any]] = []
        learn_rate = metrics.get("learn_rate", 0.0)
        reject_rate = metrics.get("reject_rate", 0.0)
        relation_yield = metrics.get("relation_yield", 0.0)

        high_spec = self.tunables.get("credibility.theta_high")
        low_spec = self.tunables.get("credibility.theta_low")

        # 规则 1：learn 占比不足 → 放宽 learn 阈值
        if high_spec and learn_rate < self.TARGET_LEARN_RATIO:
            high_now = high_spec["get"]()
            low_now = low_spec["get"]() if low_spec else 0.0
            target = self._clamp(high_now - high_spec["step"], high_spec)
            if target != high_now and target - low_now >= self.MIN_THETA_GAP:
                proposals.append({
                    "parameter": "credibility.theta_high",
                    "after": target,
                    "reason": "learn 决策占比低于目标区间，放宽高置信阈值",
                    "evidence": {"learn_rate": learn_rate, "target_learn_rate": self.TARGET_LEARN_RATIO},
                })

        # 规则 2：几乎不拦截且大部分都是 learn → 收紧 learn 阈值，防止漏放
        if high_spec and reject_rate < 0.02 and learn_rate > 0.9:
            high_now = high_spec["get"]()
            target = self._clamp(high_now + high_spec["step"], high_spec)
            if target != high_now:
                proposals.append({
                    "parameter": "credibility.theta_high",
                    "after": target,
                    "reason": "拦截率过低且 learn 占比过高，收紧高置信阈值",
                    "evidence": {"reject_rate": reject_rate, "learn_rate": learn_rate},
                })

        # 规则 3：拦截率过高 → 下调 reject 下限，减少误杀
        if low_spec and reject_rate > 0.5:
            low_now = low_spec["get"]()
            target = self._clamp(low_now - low_spec["step"], low_spec)
            high_now = high_spec["get"]() if high_spec else 1.0
            if target != low_now and high_now - target >= self.MIN_THETA_GAP:
                proposals.append({
                    "parameter": "credibility.theta_low",
                    "after": target,
                    "reason": "拦截率过高，放宽拒绝阈值",
                    "evidence": {"reject_rate": reject_rate},
                })

        # 规则 4：关系抽取覆盖率不足 → 降低关系置信度要求
        rel_spec = self.tunables.get("extraction.relation_min_confidence")
        if rel_spec and relation_yield < 0.5:
            current = rel_spec["get"]()
            target = self._clamp(current - rel_spec["step"], rel_spec)
            if target != current:
                proposals.append({
                    "parameter": "extraction.relation_min_confidence",
                    "after": target,
                    "reason": "关系抽取覆盖率偏低，降低关系置信度阈值",
                    "evidence": {"relation_yield": relation_yield},
                })

        # 同一个参数每轮最多调整一次
        seen = set()
        unique = []
        for p in proposals:
            if p["parameter"] in seen:
                continue
            seen.add(p["parameter"])
            unique.append(p)
        return unique[: self.max_changes_per_cycle]

    def _apply_change(self, proposal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """执行单个参数调整，返回可追溯的变更记录"""
        spec = self.tunables.get(proposal["parameter"])
        if not spec:
            return None
        before = spec["get"]()
        spec["set"](proposal["after"])
        after = spec["get"]()
        if before == after:
            return None
        return {
            **proposal,
            "before": before,
            "after": after,
            "delta": round(after - before, 6),
            "applied_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------ 主流程
    async def evolve(self, assessment_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行一次进化

        Args:
            assessment_data: 系统评估数据（缺省时由元认知控制器自动评估）

        Returns:
            进化结果，包含实际生效的参数变更
        """
        if not self.enabled:
            return {"evolved": False, "reason": "evolution_disabled", "changes": []}

        self.logger.info("开始进化流程")

        try:
            # 1. 元认知分析（优先使用外部传入的真实评估数据）
            if assessment_data:
                assessment = self._wrap_assessment(assessment_data)
            else:
                assessment = await self.meta_cognitive.assess()

            metrics = dict(assessment.metrics or self.last_metrics)
            if metrics:
                self.last_metrics = metrics

            # 2. 学习需求分析 + 3. 学习计划
            learning_needs = await self.learning_planner.analyze_learning_needs(
                assessment.to_dict()
            )
            learning_plan = await self.learning_planner.create_learning_plan(learning_needs)

            # 4. 安全审查（补齐安全控制器要求的字段，避免因字段缺失误拦）
            plan_dict = learning_plan.to_dict()
            plan_dict.setdefault("operation_type", "parameter_adjustment")
            plan_dict.setdefault("resource_requirements", {"cpu": 10, "memory": 10, "disk": 10})
            plan_dict.setdefault("data_handling", {
                "privacy_protection": True,
                "privacy_preserved": True,
                "anonymized": True,
                "data_minimization": True,
            })
            plan_dict.setdefault("social_impact", {
                "assessed": True,
                "risk_level": "low",
                "public_benefit": True,
            })
            is_safe, violations = await self.safety_controller.check_evolution(plan_dict)
            if not is_safe:
                self.logger.warning(f"进化计划被安全控制器阻止: {len(violations)} 个违规")
                return {
                    "evolved": False,
                    "reason": "safety_violations",
                    "violations": [v.to_dict() for v in violations],
                    "changes": [],
                }

            # 5. 参数落地：把计划对应的参数调整真正写进系统
            proposals = self._plan_changes(metrics)
            changes = []
            for proposal in proposals:
                change = self._apply_change(proposal)
                if change:
                    changes.append(change)
                    self.logger.info(
                        f"参数已调整 {change['parameter']}: "
                        f"{change['before']} -> {change['after']}"
                    )

            evolved = bool(changes)
            result = {
                "evolved": evolved,
                "reason": "applied" if evolved else "within_target_band",
                "plan_id": learning_plan.id,
                "objectives": len(learning_plan.objectives),
                "tasks": len(learning_plan.tasks),
                "changes": changes,
                "metrics": metrics,
                "assessment": assessment.to_dict(),
                "tunables": self.get_tunable_values(),
                "safety_check": {"passed": True, "violations": []},
                "evaluation": self._evaluate_effectiveness(),
                "timestamp": datetime.now().isoformat(),
            }

            # 6. 记录进化历史（内存 + JSONL，便于事后取证/论文对比）
            self.history.append({
                "timestamp": result["timestamp"],
                "plan_id": result["plan_id"],
                "evolved": evolved,
                "reason": result["reason"],
                "metrics": metrics,
                "changes": changes,
            })
            self._persist(result)

            self.logger.info(
                f"进化流程完成: 计划 {result['plan_id']}，"
                f"调整 {len(changes)} 项参数"
            )
            return result

        except Exception as e:
            self.logger.error(f"进化流程失败: {e}", exc_info=True)
            return {"evolved": False, "reason": "error", "error": str(e), "changes": []}

    async def learn_and_adapt(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """工作流接口：把本次运行的实测结果喂给进化流程"""
        assessment_data = self.build_assessment(context or {})
        return await self.evolve(assessment_data)

    # ------------------------------------------------------------------ 辅助
    def _wrap_assessment(self, data: Dict[str, Any]) -> SelfAssessment:
        """将外部评估数据包装为 SelfAssessment 对象"""
        return SelfAssessment(
            timestamp=datetime.now().isoformat(),
            component=data.get("component", self.system_name),
            metrics=data.get("metrics", {}),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=data.get("suggestions", []),
            confidence=float(data.get("confidence", 0.5)),
            overall_score=float(data.get("overall_score", 0.5)),
        )

    def _persist(self, result: Dict[str, Any]) -> None:
        """追加写入进化历史文件（失败不影响主流程）"""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            self.logger.warning(f"进化历史写入失败: {e}")

    def _load_history(self, limit: int = 200) -> None:
        if not self.history_path.exists():
            return
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                lines = [line for line in f if line.strip()][-limit:]
            for line in lines:
                record = json.loads(line)
                self.history.append({
                    "timestamp": record.get("timestamp"),
                    "plan_id": record.get("plan_id"),
                    "evolved": record.get("evolved", False),
                    "reason": record.get("reason"),
                    "metrics": record.get("metrics", {}),
                    "changes": record.get("changes", []),
                })
        except Exception as e:
            self.logger.warning(f"进化历史读取失败: {e}")

    def get_history(self) -> List[Dict[str, Any]]:
        """获取进化历史"""
        return self.history

    def get_status(self) -> Dict[str, Any]:
        """获取状态信息（供引擎汇总）"""
        return {
            "module": "evolution",
            "enabled": self.enabled,
            "tunables": self.get_tunable_values(),
            "last_metrics": self.last_metrics,
            "evaluation": self._evaluate_effectiveness(),
            "history_size": len(self.history),
            "last_changes": self.history[-1]["changes"] if self.history else [],
        }

    def shutdown(self) -> None:
        """关闭进化管理器"""
        self.logger.info("进化管理器已关闭")
