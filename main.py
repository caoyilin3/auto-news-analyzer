#!/usr/bin/env python3
"""
AutoNewsAnalyzer - 自主进化的 AI 新闻分析系统（主入口）

用法:
    python main.py                     # 运行一个分析周期
    python main.py --cycles 3          # 连续运行 3 个周期
    python main.py --no-llm            # 关闭大模型，仅用规则提取
    python main.py --mock-count 10     # 覆盖模拟新闻条数
    python main.py --mode production   # 使用 config/production.yaml（真实数据源）
    python main.py --continuous --interval 600   # 常驻运行
"""
import json
import os
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.loader import build_engine_config, load_env_file
from src.core import SystemEngine, SystemLifecycleManager
from src.utils.console import ensure_utf8_console
from src.utils.helpers import format_duration

ensure_utf8_console()


def build_llm_config(args) -> dict:
    """大模型配置：密钥只从环境变量读取，禁止硬编码在源码中"""
    return {
        "enabled": not args.no_llm,
        "api_key": os.getenv("DEEPSEEK_API_KEY", "").strip(),
        "base_url": os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions"
        ),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    }


def build_overrides(args) -> dict:
    """把命令行参数转成配置覆盖项"""
    overrides = {}
    crawler = {}
    if args.mock_count is not None:
        crawler["mock_data_count"] = args.mock_count
    if args.mock is not None:
        crawler["use_mock_data"] = bool(args.mock)
    if crawler:
        overrides["crawler"] = crawler
    return overrides


def print_summary(result: dict):
    """打印一个周期的关键结果"""
    ctx = result["context"]
    data = ctx["data"]
    changes = data.get("changes") or []

    print("\n  ── 本周期结果 ──")
    print(f"  采集文章 : {data.get('total', 0)}")
    print(f"  通过评估 : {len(data.get('articles', []))}")
    print(f"  拦截文章 : {data.get('rejected_count', 0)}")
    print(f"  提取实体 : {data.get('total_entities', 0)}")
    llm_calls = data.get("llm_calls", 0)
    llm_failures = data.get("llm_failures", 0)
    suffix = f"（其中 LLM 三元组 {data.get('llm_triples', 0)}）"
    if llm_failures:
        suffix = (f"（LLM 三元组 {data.get('llm_triples', 0)}，"
                  f"调用失败 {llm_failures}/{llm_calls}）")
    print(f"  提取关系 : {data.get('total_relations', 0)}{suffix}")
    if changes:
        evolution_state = "已进化"
    elif data.get("reason") == "within_target_band":
        evolution_state = "已收敛（本轮无需调整）"
    else:
        evolution_state = "未进化"
    print(f"  进化状态 : {evolution_state}（参数调整 {len(changes)} 项）")
    for change in changes:
        print(f"    - {change['parameter']}: {change['before']} → {change['after']}"
              f"  # {change.get('reason', '')}")

    evaluation = data.get("evaluation") or {}
    if evaluation.get("samples"):
        print(f"  长期效果 : {evaluation.get('verdict')}"
              f"（{evaluation.get('samples')} 个周期样本）")
    if llm_failures:
        print(f"  ⚠️ 大模型 : {str(data.get('llm_last_error', ''))[:120]}")
        print("     已降级为规则提取，请检查 .env 中的 DEEPSEEK_API_KEY / DEEPSEEK_MODEL")
    print(f"  耗时     : {format_duration(result['metrics'].get('total_duration', 0))}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AutoNewsAnalyzer - 自主进化的AI新闻分析系统"
    )
    parser.add_argument(
        "--mode", choices=["development", "production", "testing"], default="development",
        help="运行模式，决定加载 config/<mode>.yaml",
    )
    parser.add_argument("--config", default=None, help="自定义配置文件路径（覆盖 --mode）")
    parser.add_argument("--cycles", type=int, default=None,
                        help="运行周期数（默认 1；常驻模式下不指定则无限循环）")
    parser.add_argument("--mock-count", type=int, default=None, help="模拟新闻数量（覆盖配置）")
    parser.add_argument("--no-llm", action="store_true", help="关闭 DeepSeek 大模型")
    parser.add_argument("--mock", dest="mock", action="store_true", help="强制使用模拟数据")
    parser.add_argument("--no-mock", dest="mock", action="store_false", help="强制使用真实数据源")
    parser.set_defaults(mock=None)
    parser.add_argument("--continuous", action="store_true", help="常驻运行（按 --interval 轮询）")
    parser.add_argument("--interval", type=int, default=3600, help="常驻模式的周期间隔（秒）")
    parser.add_argument("--metrics-port", type=int, default=None,
                        help="在本端口暴露 Prometheus 指标端点（例如 9090）")
    parser.add_argument("--evidence-report", action="store_true",
                        help="只汇总 data/patent_evidence 下的证据并输出 JSON，不运行分析")
    parser.add_argument("--evaluate", action="store_true",
                        help="输出长期学习效果评估（数据集趋势与参数漂移），不运行分析")
    parser.add_argument("--evaluate-window", type=int, default=50,
                        help="长期效果评估的窗口（最近 N 个周期）")
    parser.add_argument("--verbose", action="store_true", help="详细日志")
    return parser


def main():
    args = build_parser().parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    load_env_file()

    if args.evidence_report:
        from src.patent_evidence import EvidenceManager

        evidence_dir = Path("data/patent_evidence")
        if not evidence_dir.exists():
            print(f"❌ 证据目录不存在: {evidence_dir}")
            sys.exit(2)
        summary = EvidenceManager(evidence_dir).generate_summary_report()
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        sys.exit(0)

    try:
        config = build_engine_config(
            mode=args.mode,
            config_path=args.config,
            overrides=build_overrides(args),
            llm=build_llm_config(args),
        )
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(2)

    if args.evaluate:
        from src.evolution.effectiveness import LearningEffectivenessEvaluator

        evaluator = LearningEffectivenessEvaluator(
            dataset_path=config.get("evaluation", {}).get(
                "dataset_path", "data/cycle_metrics.jsonl"
            )
        )
        evaluation = evaluator.evaluate(window=args.evaluate_window)
        print(json.dumps(evaluation, ensure_ascii=False, indent=2, default=str))
        sys.exit(0)

    llm_cfg = config.get("knowledge", {}).get("llm", {})
    if args.no_llm or not llm_cfg.get("api_key"):
        llm_state = "未配置密钥，规则提取" if not llm_cfg.get("api_key") else "关闭"
    else:
        llm_state = f"DeepSeek ({llm_cfg.get('model')})"

    # 常驻模式：不指定 --cycles 表示无限循环；普通模式默认跑 1 个周期
    cycles = args.cycles if args.cycles is not None else 1
    max_cycles = args.cycles  # 常驻模式下 None 即无限

    print("=" * 60)
    print("        AutoNewsAnalyzer v2.0  自主进化新闻分析系统")
    print("=" * 60)
    print(f"模式: {config['system']['mode']}   数据源: "
          f"{'模拟' if config['crawler']['use_mock_data'] else '真实'}   LLM: {llm_state}")
    print(f"周期: {'∞' if args.continuous and max_cycles is None else cycles}"
          f"   常驻: {'是' if args.continuous else '否'}")

    engine = SystemEngine(config)
    # 生命周期管理器负责有序初始化/启动/停止，并在退出时统一回收组件
    lifecycle = SystemLifecycleManager({
        "health_check_enabled": False,
        "maintenance_enabled": False,
        "recovery_enabled": False,
    })
    lifecycle.register_component("engine", engine, priority=1)

    if not lifecycle.initialize_system():
        print("❌ 系统初始化失败")
        lifecycle.shutdown()
        sys.exit(1)
    if not lifecycle.start_system():
        print("❌ 系统启动失败")
        lifecycle.shutdown()
        sys.exit(1)

    print("\n模块初始化完成，开始分析...")
    success = 0
    metrics_server = None
    if args.metrics_port:
        from src.interfaces.metrics_server import MetricsServer

        metrics_server = MetricsServer(engine.metrics_snapshot, port=args.metrics_port)
        if metrics_server.start():
            print(f"📊 指标端点: http://127.0.0.1:{args.metrics_port}/metrics")
        else:
            print(f"⚠️ 指标端点 {args.metrics_port} 启动失败，继续运行")
            metrics_server = None

    try:
        if args.continuous:
            engine.run_continuous(
                interval=args.interval,
                max_cycles=max_cycles if (max_cycles is None or max_cycles > 0) else None,
            )
            success = engine.run_metrics["successful_cycles"]
        else:
            for i in range(1, cycles + 1):
                print(f"\n▶ 第 {i}/{cycles} 个周期")
                result = engine.run_workflow()
                if result["status"] == "completed":
                    success += 1
                    print_summary(result)
                else:
                    print(f"❌ 周期失败: {result.get('error', result['status'])}")
    except KeyboardInterrupt:
        print("\n🛑 程序被用户中断")
    finally:
        if metrics_server is not None:
            metrics_server.stop()
        lifecycle.shutdown()

    if args.continuous:
        display_total = "∞" if max_cycles is None else str(max_cycles)
    else:
        display_total = str(cycles)

    print("\n" + "=" * 60)
    print(f"完成：{success}/{display_total} 个周期成功。报告已输出到 "
          f"{config['reporting']['output_dir']}/ 目录")
    print("=" * 60)
    exit_ok = success > 0 and (args.continuous or success == cycles)
    sys.exit(0 if exit_ok else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
# I love auto news
