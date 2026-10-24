"""集成测试：配置加载、调度器、进化闭环、状态持久化、长期效果评估"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.loader import build_engine_config, to_engine_config
from src.core import SystemEngine
from src.core.orchestrator import Orchestrator
from tests.test_engine import make_config


# --------------------------------------------------------------------- 配置加载
def test_config_loader_maps_yaml_to_engine_config():
    """YAML 的 thresholds.high/medium 必须映射到引擎使用的 theta_high/theta_low"""
    config = build_engine_config(
        "development", overrides={"crawler": {"mock_data_count": 3}}
    )
    assert config["crawler"]["mock_data_count"] == 3
    assert config["crawler"]["use_mock_data"] is True
    assert config["credibility"]["theta_high"] == 0.8
    assert config["credibility"]["theta_low"] == 0.5
    assert abs(sum(config["credibility"]["weights"].values()) - 1.0) < 1e-9
    assert config["knowledge"].get("llm") is None or isinstance(
        config["knowledge"]["llm"], dict
    )


def test_production_config_uses_real_sources():
    """生产配置应关闭模拟数据，并把 {name,type,url} 源结构拍平成 URL 列表"""
    config = build_engine_config("production")
    assert config["crawler"]["use_mock_data"] is False
    sources = config["crawler"]["sources"]
    assert sources and all(isinstance(s, str) and s.startswith("http") for s in sources)


def test_to_engine_config_tolerates_missing_sections():
    """最小 YAML 也应能转换出不缺键的配置"""
    config = to_engine_config({"system": {"name": "X"}})
    for key in ("crawler", "credibility", "knowledge", "evolution", "memory", "reporting"):
        assert key in config


# --------------------------------------------------------------------- 调度器
class _DummyModule:
    def __init__(self):
        self.calls = []

    def step_a(self, params):
        self.calls.append(("a", params))
        return {"status": "ok", "value": 1}

    async def step_b(self, params):
        self.calls.append(("b", params))
        return {"status": "ok", "value": params.get("x", 0) * 2}


def test_orchestrator_executes_real_modules_in_dependency_order():
    """Orchestrator 不再使用占位实现，而是真正调用已注册模块（含异步方法）"""
    module = _DummyModule()
    orchestrator = Orchestrator({"max_workers": 4})
    orchestrator.register_module("dummy", module)

    workflow_id = orchestrator.create_workflow("wf_test", [
        {"name": "a", "module": "dummy", "function": "step_a", "parameters": {"x": 1}},
        {
            "name": "b",
            "module": "dummy",
            "function": "step_b",
            "parameters": {"x": 21},
            "dependencies": ["a"],  # 名字依赖应被翻译成任务 ID
        },
    ])
    assert orchestrator.submit_workflow(workflow_id)

    deadline = time.time() + 10
    while time.time() < deadline:
        status = orchestrator.get_workflow_status(workflow_id)
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)

    try:
        assert status["status"] == "completed", status
        assert [c[0] for c in module.calls] == ["a", "b"]
        assert module.calls[1][1] == {"x": 21}

        tasks = status["tasks"]
        assert all(t["status"] == "completed" for t in tasks)
        assert any(t["name"] == "b" for t in tasks)
    finally:
        orchestrator.shutdown()


def test_orchestrator_reports_failure_for_registered_but_broken_task():
    """模块方法内部抛错时应标记任务失败，而不是静默成功"""
    class Broken:
        def boom(self, params):
            raise RuntimeError("boom")

    orchestrator = Orchestrator({"max_workers": 2})
    orchestrator.register_module("broken", Broken())
    workflow_id = orchestrator.create_workflow("wf_broken", [
        {"name": "boom", "module": "broken", "function": "boom", "max_retries": 0},
    ])
    orchestrator.submit_workflow(workflow_id)

    deadline = time.time() + 10
    while time.time() < deadline:
        status = orchestrator.get_workflow_status(workflow_id)
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)

    try:
        assert status["status"] == "failed", status
        assert status["tasks"][0]["error"] == "boom"
    finally:
        orchestrator.shutdown()


# --------------------------------------------------------------------- 进化闭环
def test_evolution_closed_loop_applies_parameter_change(tmp_path):
    """学习计划必须真正落到参数上，并写入可追溯的进化历史"""
    engine = SystemEngine(make_config(tmp_path, mock_count=6))
    assert engine.initialize_modules()
    evolution = engine.modules["evolution"]
    before = evolution.get_tunable_values()["credibility.theta_high"]

    try:
        result = engine.run_workflow()
    finally:
        engine.shutdown()

    data = result["context"]["data"]
    changes = data["changes"]
    assert result["status"] == "completed"
    assert data["evolved"] is True
    assert changes and changes[0]["parameter"] == "credibility.theta_high"
    assert changes[0]["after"] < before
    assert data["tunables"]["credibility.theta_high"] == changes[0]["after"]

    # 进化历史 + 状态持久化
    assert (tmp_path / "evolution_history.jsonl").exists()
    assert (tmp_path / "state" / "engine_state.pkl").exists()


def test_orchestrator_runs_independent_tasks_in_parallel():
    """无依赖的任务应并发执行（总耗时明显小于串行之和）"""
    import threading

    class Slow:
        def __init__(self):
            self.active = 0
            self.peak = 0
            self.lock = threading.Lock()
            self.done = []

        def work(self, params):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            time.sleep(0.3)
            with self.lock:
                self.active -= 1
                self.done.append(params.get("tag"))
            return {"status": "ok", "tag": params.get("tag")}

    module = Slow()
    orchestrator = Orchestrator({"max_workers": 3})
    orchestrator.register_module("slow", module)
    workflow_id = orchestrator.create_workflow("wf_parallel", [
        {"name": "t1", "module": "slow", "function": "work", "parameters": {"tag": 1}},
        {"name": "t2", "module": "slow", "function": "work", "parameters": {"tag": 2}},
        {"name": "t3", "module": "slow", "function": "work", "parameters": {"tag": 3}},
    ])

    started = time.time()
    orchestrator.submit_workflow(workflow_id)
    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        status = orchestrator.get_workflow_status(workflow_id)
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.02)
    elapsed = time.time() - started
    try:
        assert status["status"] == "completed", status
        assert module.peak >= 2, "任务没有并发执行"
        assert elapsed < 0.3 * 3, f"并行执行耗时过长: {elapsed:.2f}s"
        assert sorted(module.done) == [1, 2, 3]
    finally:
        orchestrator.shutdown()


def test_engine_supports_sequential_and_orchestrated_execution(tmp_path):
    """两种执行器产出一致：同样的 6 个步骤、同样的关键指标"""
    results = {}
    for kind in ("sequential", "orchestrator"):
        config = make_config(tmp_path / kind, mock_count=6)
        config["workflow"] = {"executor": kind, "max_workers": 2}
        engine = SystemEngine(config)
        assert engine.initialize_modules()
        try:
            result = engine.run_workflow()
        finally:
            engine.shutdown()
        results[kind] = result

    for kind, result in results.items():
        assert result["status"] == "completed", (kind, result.get("error"))
        steps = [r["step"] for r in result["context"]["step_results"]]
        assert len(steps) == 6, (kind, steps)
        assert results[kind]["context"]["data"]["total"] == 6

    seq = results["sequential"]["context"]["data"]
    orc = results["orchestrator"]["context"]["data"]
    for key in ("total", "rejected_count", "total_entities", "total_relations"):
        assert seq[key] == orc[key], (key, seq[key], orc[key])


def test_state_manager_restores_persisted_values(tmp_path):
    """状态持久化回归测试：load_state 后必须能 get_state（此前锁未补建导致恒返回 None）"""
    from src.core.state_manager import StateType, SystemStateManager

    path = str(tmp_path / "state" / "s.pkl")
    first = SystemStateManager({"persistence_path": path})
    try:
        first.set_state("evolution.tunables", {"credibility.theta_high": 0.76}, StateType.CONFIG)
        first.save_state()
    finally:
        first.shutdown()

    second = SystemStateManager({"persistence_path": path})
    try:
        assert second.get_state("evolution.tunables") == {"credibility.theta_high": 0.76}
    finally:
        second.shutdown()


def test_engine_metrics_snapshot_is_numeric(tmp_path):
    """Prometheus 端点依赖的指标快照必须是纯数值"""
    engine = SystemEngine(make_config(tmp_path, mock_count=3))
    assert engine.initialize_modules()
    try:
        engine.run_workflow()
        snapshot = engine.metrics_snapshot()
    finally:
        engine.shutdown()

    assert snapshot["autonews_cycles_total"] == 1
    assert 0.0 <= snapshot["autonews_theta_high"] <= 1.0
    assert all(
        isinstance(v, (int, float)) and not isinstance(v, bool)
        for v in snapshot.values()
    )


# --------------------------------------------------------------------- 长期效果
def test_engine_run_metrics_are_per_process(tmp_path):
    """跨进程恢复的是累计指标，命令行汇总只能统计本次运行"""
    first = SystemEngine(make_config(tmp_path, mock_count=3))
    assert first.initialize_modules()
    try:
        first.run_workflow()
        first.run_workflow()
    finally:
        first.shutdown()
    assert first.run_metrics["total_cycles"] == 2
    assert first.metrics["total_cycles"] == 2

    second = SystemEngine(make_config(tmp_path, mock_count=3))
    assert second.initialize_modules()
    try:
        assert second.metrics["total_cycles"] == 2  # 从状态文件恢复的累计值
        assert second.run_metrics["total_cycles"] == 0
        second.run_workflow()
        assert second.run_metrics["total_cycles"] == 1
        assert second.metrics["total_cycles"] == 3
    finally:
        second.shutdown()


def test_knowledge_llm_triples_are_per_cycle():
    """LLM 三元组必须返回本周期数量，而不是跨周期累计值"""
    import asyncio

    from src.knowledge.manager import KnowledgeManager

    class FakeLLM:
        enabled = True
        model = "fake"

        def extract_triples(self, text):
            return [{"subject": "A公司", "predicate": "收购", "object": "B公司"}]

        def get_status(self):
            return {"enabled": True, "model": "fake"}

    manager = KnowledgeManager({"llm": {"api_key": "dummy"}})
    manager.llm_client = FakeLLM()
    context = {"articles": [{"id": "a1", "title": "t", "content": "A公司收购了B公司。"}]}

    first = asyncio.run(manager.extract_knowledge(context))
    second = asyncio.run(manager.extract_knowledge(context))

    assert first["llm_triples"] == 1
    assert second["llm_triples"] == 1
    assert second["llm_triples_total"] == 2


def test_load_env_file_reads_and_respects_existing_vars(tmp_path, monkeypatch):
    """.env 应被自动加载，但不得覆盖已经存在的环境变量"""
    from config.loader import load_env_file

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# 注释行\nDEMO_KEY_A=abc123\nDEMO_KEY_B='quoted value'\n空白=  \n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEMO_KEY_A", raising=False)
    monkeypatch.delenv("DEMO_KEY_B", raising=False)
    monkeypatch.setenv("DEMO_KEY_C", "preset")

    applied = load_env_file(str(env_file))
    assert applied["DEMO_KEY_A"] == "abc123"
    assert os.environ["DEMO_KEY_A"] == "abc123"
    assert os.environ["DEMO_KEY_B"] == "quoted value"

    # 已存在的变量优先级更高
    env_file.write_text("DEMO_KEY_C=from-file\n", encoding="utf-8")
    applied2 = load_env_file(str(env_file))
    assert "DEMO_KEY_C" not in applied2
    assert os.environ["DEMO_KEY_C"] == "preset"


def test_load_env_file_missing_file_is_silent(tmp_path):
    from config.loader import load_env_file

    assert load_env_file(str(tmp_path / "nope.env")) == {}


def test_effectiveness_evaluator_computes_trends(tmp_path):
    """长期效果评估：趋势方向、参数漂移、洞察与 CSV 导出"""
    from src.evolution.effectiveness import LearningEffectivenessEvaluator

    evaluator = LearningEffectivenessEvaluator(str(tmp_path / "metrics.jsonl"))
    for i in range(6):
        evaluator.record_cycle(
            metrics={
                "learn_rate": 0.05 * i,
                "reject_rate": 0.1,
                "accuracy_rate": 0.8,
                "extraction_yield": 1.5,
                "relation_yield": 0.5,
            },
            tunables={"credibility.theta_high": round(0.8 - 0.02 * i, 4)},
            tunables_before={"credibility.theta_high": round(0.82 - 0.02 * i, 4)},
            changes=[{"parameter": "credibility.theta_high"}] if i else [],
        )

    result = evaluator.evaluate()
    assert result["samples"] == 6
    assert result["trends"]["learn_rate"]["direction"] == "up"
    assert result["trends"]["learn_rate"]["delta"] > 0
    assert result["parameter_drift"]["credibility.theta_high"]["delta"] < 0
    assert result["verdict"] == "improving"
    assert result["insights"] and all(isinstance(s, str) and s for s in result["insights"])

    exported = evaluator.export_csv()
    assert exported and Path(exported).exists()


def test_effectiveness_evaluator_handles_empty_dataset(tmp_path):
    from src.evolution.effectiveness import LearningEffectivenessEvaluator

    evaluator = LearningEffectivenessEvaluator(str(tmp_path / "none.jsonl"))
    result = evaluator.evaluate()
    assert result["samples"] == 0
    assert result["verdict"] == "insufficient_data"
    assert result["insights"]


def test_engine_writes_cycle_dataset_and_metrics(tmp_path):
    """引擎每个周期都应写入效果数据集，并在关闭时导出指标快照"""
    engine = SystemEngine(make_config(tmp_path, mock_count=3))
    assert engine.initialize_modules()
    try:
        engine.run_workflow()
        engine.run_workflow()
    finally:
        engine.shutdown()

    dataset = tmp_path / "cycle_metrics.jsonl"
    assert dataset.exists()
    records = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 2
    assert all("metrics" in r and "tunables" in r for r in records)
    assert "tunables_before" in records[0]

    metrics_file = tmp_path / "metrics" / "engine_metrics.json"
    assert metrics_file.exists()
    exported = json.loads(metrics_file.read_text(encoding="utf-8"))
    assert "articles_collected" in exported["metrics"]
    assert len(exported["metrics"]["articles_collected"]) == 2
