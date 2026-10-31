"""启动器辅助函数测试（.env 读写、密钥脱敏）"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import start


def test_upsert_creates_and_updates(tmp_path):
    env = tmp_path / ".env"
    start.upsert_env_value("DEEPSEEK_API_KEY", "sk-aaa", env)
    assert "DEEPSEEK_API_KEY=sk-aaa" in env.read_text(encoding="utf-8")

    start.upsert_env_value("DEEPSEEK_API_KEY", "sk-bbb", env)
    text = env.read_text(encoding="utf-8")
    assert text.count("DEEPSEEK_API_KEY=") == 1
    assert "sk-bbb" in text


def test_upsert_preserves_other_lines_and_comments(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# 注释\nOTHER=1\n", encoding="utf-8")
    start.upsert_env_value("NEW_KEY", "v", env)
    text = env.read_text(encoding="utf-8")
    assert "# 注释" in text and "OTHER=1" in text
    assert "NEW_KEY=v" in text


def test_empty_value_removes_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nDEEPSEEK_API_KEY=sk-x\nB=2\n", encoding="utf-8")
    start.upsert_env_value("DEEPSEEK_API_KEY", "", env)
    text = env.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY" not in text
    assert "A=1" in text and "B=2" in text


def test_read_env_value(tmp_path):
    env = tmp_path / ".env"
    env.write_text('DEEPSEEK_API_KEY="sk-quoted"\n', encoding="utf-8")
    assert start.read_env_value("DEEPSEEK_API_KEY", env) == "sk-quoted"
    assert start.read_env_value("MISSING", env) == ""


def test_mask_secret():
    assert start.mask_secret("") == "未配置"
    masked = start.mask_secret("sk-test-0123456789abcdef0123456789")
    assert masked.startswith("sk-test-") and masked.endswith("6789")
    assert "0123456789abcdef012" not in masked


def test_required_modules_cover_pipeline_imports():
    """自检清单必须覆盖主链路真正 import 的模块（曾漏掉 bs4/backoff/packaging）"""
    from start import REQUIRED_MODULES

    must_have = {
        "jieba", "networkx", "yaml", "requests", "aiohttp", "numpy",
        "bs4", "backoff", "packaging",
    }
    assert must_have <= set(REQUIRED_MODULES), (
        f"自检清单缺少: {must_have - set(REQUIRED_MODULES)}"
    )


def test_missing_packages_returns_list():
    from start import missing_packages

    missing = missing_packages()
    assert isinstance(missing, list)
    # 当前环境装了核心依赖，不应报告缺失
    assert missing == []
