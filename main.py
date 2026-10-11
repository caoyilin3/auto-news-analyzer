#!/usr/bin/env python3
"""
AutoNewsAnalyzer - 自主进化的 AI 新闻分析系统（主入口）

用法:
    python main.py                 # 运行一个分析周期（启用 DeepSeek LLM）
    python main.py --cycles 3      # 连续运行 3 个周期
    python main.py --no-llm        # 关闭大模型，仅用规则提取
    python main.py --mock-count 10 # 生成 10 条模拟新闻
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core import SystemEngine


def build_config(args) -> dict:
    """根据命令行参数构建系统配置"""
    return {
        "system": {"name": "AutoNewsAnalyzer", "mode": args.mode, "debug": True},
        "crawler": {
            "enabled": True,
            "use_mock_data": True,
            "mock_data_count": args.mock_count,
        },
        "credibility": {
            "enabled": True,
            "weights": {"source": 0.35, "freshness": 0.20, "author": 0.15, "content": 0.20, "url": 0.10},
            "theta_high": 0.8,
            "theta_low": 0.5,
        },
        "knowledge": {
            "enabled": True,
            "graph_storage": "memory",
            # ============================================================
            # 【API 配置位置】想用大模型时，把下面三项填上即可：
            #   api_key  : 你的 API 密钥
            #   base_url : 接口地址（OpenAI 兼容格式）
            #   model    : 模型名
            # 不填则纯规则运行，不会联网。
            # ============================================================
            "llm": {
                "enabled": not args.no_llm,
                "api_key": "__FILL_YOUR_API_KEY_HERE__",
                "base_url": "__FILL_API_BASE_URL_HERE__",
                "model": "__FILL_MODEL_NAME_HERE__",
            },
        },
        "evolution": {"enabled": True},
        "memory": {"enabled": True, "capacity": 10000},
        "reporting": {"output_dir": "output"},
    }


def print_summary(result: dict):
    """打印一个周期的关键结果"""
    ctx = result["context"]
    data = ctx["data"]
    print("\n  ── 本周期结果 ──")
    print(f"  采集文章 : {data.get('total', 0)}")
    print(f"  通过评估 : {len(data.get('articles', []))}")
    print(f"  拦截文章 : {data.get('rejected_count', 0)}")
    print(f"  提取实体 : {data.get('total_entities', 0)}")
    print(f"  提取关系 : {data.get('total_relations', 0)}"
          f"（其中 LLM 三元组 {data.get('llm_triples', 0)}）")
    print(f"  进化状态 : {'已进化' if data.get('evolved') else '未进化'}")
    print(f"  耗时     : {result['metrics'].get('total_duration', 0):.2f}s")


def main():
    parser = argparse.ArgumentParser(description="AutoNewsAnalyzer - 自主进化的AI新闻分析系统")
    parser.add_argument("--mode", choices=["development", "production", "testing"], default="development")
    parser.add_argument("--cycles", type=int, default=1, help="运行周期数")
    parser.add_argument("--mock-count", type=int, default=6, help="模拟新闻数量")
    parser.add_argument("--no-llm", action="store_true", help="关闭 DeepSeek 大模型")
    parser.add_argument("--verbose", action="store_true", help="详细日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    print("=" * 60)
    print("        AutoNewsAnalyzer v2.0  自主进化新闻分析系统")
    print("=" * 60)
    print(f"模式: {args.mode}   周期: {args.cycles}   LLM: {'关闭' if args.no_llm else 'DeepSeek'}")

    config = build_config(args)
    engine = SystemEngine(config)

    if not engine.initialize_modules():
        print("❌ 模块初始化失败")
        engine.shutdown()
        sys.exit(1)

    print("\n模块初始化完成，开始分析...")
    success = 0
    for i in range(1, args.cycles + 1):
        print(f"\n▶ 第 {i}/{args.cycles} 个周期")
        result = engine.run_workflow()
        if result["status"] == "completed":
            success += 1
            print_summary(result)
        else:
            print(f"❌ 周期失败: {result.get('error', result['status'])}")

    engine.shutdown()
    print("\n" + "=" * 60)
    print(f"完成：{success}/{args.cycles} 个周期成功。报告已输出到 output/ 目录")
    print("=" * 60)
    sys.exit(0 if success == args.cycles else 1)


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
