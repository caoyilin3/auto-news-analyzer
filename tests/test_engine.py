"""引擎与主工作流的集成测试

覆盖：工作流定义、模块初始化、端到端运行、低质量内容拦截、报告内容正确性。
全部使用模拟数据源与规则提取（不访问网络、不调用大模型），可离线稳定运行。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import SystemEngine
from src.credibility.evaluator import CredibilityEvaluator


def make_config(tmp_path: Path, mock_count: int = 4) -> dict:
    """构造测试配置：模拟数据 + 关闭 LLM + 报告写入临时目录"""
    return {
        "system": {"name": "AutoNewsAnalyzer", "mode": "testing", "debug": True},
        "crawler": {
            "enabled": True,
            "use_mock_data": True,
            "mock_data_count": mock_count,
        },
        "credibility": {
            "enabled": True,
            "weights": {
                "source": 0.35,
                "freshness": 0.20,
                "author": 0.15,
                "content": 0.20,
                "url": 0.10,
            },
            "theta_high": 0.8,
            "theta_low": 0.5,
        },
        "knowledge": {
            "enabled": True,
            "graph_storage": "memory",
            "llm": {"enabled": False, "api_key": ""},
        },
        "evolution": {
            "enabled": True,
            "history_path": str(tmp_path / "evolution_history.jsonl"),
        },
        "memory": {"enabled": True, "capacity": 1000},
        "reporting": {"output_dir": str(tmp_path / "output")},
        # 测试隔离：状态与证据都写到临时目录，不污染项目 data/
        "state": {"persistence_path": str(tmp_path / "state" / "engine_state.pkl")},
        "patent_evidence": {"enabled": False},
        "evaluation": {
            "dataset_path": str(tmp_path / "cycle_metrics.jsonl"),
            "export_csv": True,
        },
        "monitoring": {"metrics_path": str(tmp_path / "metrics" / "engine_metrics.json")},
    }


def test_workflow_steps_definition():
    """工作流步骤齐全，且依赖顺序自洽"""
    engine = SystemEngine({})
    names = [step.name for step in engine.workflow_steps]
    assert names == [
        "data_acquisition",
        "credibility_assessment",
        "knowledge_extraction",
        "evolution_learning",
        "memory_management",
        "report_generation",
    ]

    seen = set()
    for step in engine.workflow_steps:
        assert set(step.dependencies) <= seen, f"{step.name} 依赖了尚未执行的步骤"
        seen.add(step.name)


def test_initialize_modules(tmp_path):
    """六个模块都能初始化（依赖 jieba/networkx 等基础库）"""
    engine = SystemEngine(make_config(tmp_path))
    try:
        assert engine.initialize_modules() is True
        assert set(engine.modules) == {
            "data_acquisition",
            "credibility",
            "knowledge",
            "evolution",
            "memory",
            "interfaces",
        }
    finally:
        engine.shutdown()


def test_run_workflow_end_to_end(tmp_path):
    """完整跑通一个周期，且报告数据与各阶段一致"""
    engine = SystemEngine(make_config(tmp_path, mock_count=4))
    assert engine.initialize_modules()
    try:
        result = engine.run_workflow()
    finally:
        engine.shutdown()

    assert result["status"] == "completed"
    context = result["context"]
    data = context["data"]

    # 采集数量 = 模拟数据条数
    assert data["total"] == 4
    # 通过评估的是采集结果的子集（模拟数据里有一条推广文会被拦截）
    assert 0 < len(data["articles"]) <= 4
    assert data["rejected_count"] >= 1
    # 知识提取在通过的文章上执行
    assert data["total_entities"] >= 0
    assert data["total_relations"] >= 0

    # 报告已落盘
    reports = sorted((tmp_path / "output").glob("*.json"))
    assert reports, "未生成报告文件"
    report = json.loads(reports[-1].read_text(encoding="utf-8"))

    assert report["summary"]["articles_collected"] == 4
    assert report["summary"]["articles_passed"] == len(data["articles"])
    assert report["summary"]["articles_rejected"] == data["rejected_count"]

    # 回归测试：data_acquisition 的统计不能被 memory 模块的同名 stats 覆盖
    acq_stats = report["stages"]["data_acquisition"]["stats"]
    assert acq_stats.get("total_articles") == 4
    assert "memory_type_distribution" not in acq_stats

    # 每个步骤都成功执行（skipped 也允许，但当前配置下不应出现）
    statuses = {r["step"]: r["status"] for r in context["step_results"]}
    assert all(status == "completed" for status in statuses.values())


def test_credibility_decision_boundaries():
    """五维加权 + 双阈值：优质来源判 learn，推广文判 reject"""
    evaluator = CredibilityEvaluator({"theta_high": 0.8, "theta_low": 0.5})
    now = datetime.now().isoformat()

    good = {
        "id": "good",
        "title": "量子计算新进展",
        "content": "研究团队公布了一项量子计算实验进展。" * 30,
        "source": "arxiv_mock",
        "author": "Dr. Zhang",
        "url": "https://arxiv.org/abs/2401.00001",
        "published_at": now,
    }
    bad = {
        "id": "bad",
        "title": "点击领取免费大奖",
        "content": "点击链接立即领取大奖，限时优惠。",
        "source": "ad_source",
        "author": "未知",
        "url": "https://ads.example.com/sponsored/click-1",
        "published_at": now,
    }

    good_result = evaluator.evaluate_article(good)
    bad_result = evaluator.evaluate_article(bad)

    assert good_result["decision"] == "learn", good_result
    assert bad_result["decision"] == "reject", bad_result
    assert 0.0 <= bad_result["score"] < good_result["score"] <= 1.0
    assert set(good_result["dimensions"]) == {
        "source",
        "freshness",
        "author",
        "content",
        "url",
    }
    # 权重归一化后和为 1
    assert abs(sum(good_result["weights"].values()) - 1.0) < 1e-9
