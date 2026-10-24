"""AutoNewsAnalyzer 全链路冒烟测试：验证引擎能跑通完整工作流"""
import os
import sys
import asyncio
import logging

sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

from src.core import SystemEngine
from src.utils.console import ensure_utf8_console

ensure_utf8_console()

# 先加载 .env，再构造配置（CONFIG 在模块级读取环境变量）
from config.loader import load_env_file

load_env_file()

# 密钥只从环境变量读取；未配置时自动降级为纯规则提取
CONFIG = {
    "system": {"name": "AutoNewsAnalyzer", "mode": "development", "debug": True},
    "crawler": {
        "enabled": True,
        "use_mock_data": True,
        "mock_data_count": 6,
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
        "llm": {
            "enabled": True,
            "api_key": os.getenv("DEEPSEEK_API_KEY", "").strip(),
            "base_url": os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions"
            ),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        },
    },
    "evolution": {"enabled": True},
    "memory": {"enabled": True, "capacity": 10000},
    "reporting": {"output_dir": "output"},
}


def main():
    engine = SystemEngine(CONFIG)
    ok = engine.initialize_modules()
    if not ok:
        print("模块初始化失败")
        engine.shutdown()
        return 1

    print("\n=== 模块初始化完成 ===")
    for name, mod in engine.modules.items():
        print(f"  - {name}: {type(mod).__name__}")

    print("\n=== 开始运行工作流 ===")
    result = engine.run_workflow()
    status = result["status"]
    print(f"\n工作流状态: {status}")

    ctx = result["context"]
    data = ctx["data"]

    print("\n=== 各步骤结果 ===")
    for step in ctx["step_results"]:
        print(f"  {step['step']:<24} {step['status']:<18} {step.get('duration', 0):.2f}s")

    print("\n=== 关键指标 ===")
    print(f"  采集文章: {data.get('total', data.get('total_assessed', 0))}")
    print(f"  通过评估: {len(data.get('articles', []))}")
    print(f"  拦截文章: {data.get('rejected_count', 0)}")
    print(f"  提取实体: {data.get('total_entities', 0)}")
    print(f"  提取关系: {data.get('total_relations', 0)}")

    print("\n=== 引擎状态 ===")
    st = engine.get_status()
    print(f"  state: {st['state']}")
    for name, s in st["modules"].items():
        if isinstance(s, dict):
            print(f"  {name}: {s.get('stats', s)}")

    engine.shutdown()
    print("\n=== 引擎已关闭 ===")

    if status == "completed":
        print("\n✓ 全链路运行成功")
        return 0
    else:
        print(f"\n✗ 工作流状态: {status}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
