"""配置加载器

把 config/*.yaml 转换成 SystemEngine 需要的扁平 dict，并负责加载项目根目录的 .env。

此前 config/ 目录下一篇 "死代码"：YAML 与 pydantic 模式都没有被主链路读取，
引擎配置全靠 main.py 里的硬编码字典。本模块负责两者的衔接，并修正了历史遗留的
键名差异（YAML 里是 credibility.thresholds.high / medium，代码里读的是
theta_high / theta_low）。
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent

DEFAULT_WEIGHTS = {
    "source": 0.35,
    "freshness": 0.20,
    "author": 0.15,
    "content": 0.20,
    "url": 0.10,
}


def load_env_file(path: Optional[str] = None) -> Dict[str, str]:
    """加载项目根目录的 .env，返回本次写入的环境变量。

    优先使用 python-dotenv；未安装时退化为最简单的 KEY=VALUE 解析，
    这样即使只装了最小依赖，密钥配置也能生效。
    已存在的环境变量不会被覆盖（命令行/系统变量的优先级更高）。
    """
    env_path = Path(path) if path else PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}

    values: Dict[str, str] = {}
    try:
        from dotenv import dotenv_values

        parsed = dotenv_values(env_path)
        values = {k: str(v) for k, v in parsed.items() if k and v is not None}
    except ImportError:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if value:
                values[key.strip()] = value
    except Exception:
        return {}

    applied = {}
    for key, value in values.items():
        if os.getenv(key) is None:
            os.environ[key] = value
            applied[key] = value
    return applied


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并字典（override 优先）"""
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_yaml(mode: str = "development", config_path: Optional[str] = None) -> Dict[str, Any]:
    """读取 YAML 配置；config_path 为空时按 mode 定位 config/<mode>.yaml"""
    path = Path(config_path) if config_path else CONFIG_DIR / f"{mode}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def to_engine_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    """把 YAML 的嵌套结构映射为引擎使用的配置结构"""
    raw = raw or {}
    system_raw = raw.get("system", {}) or {}
    crawler_raw = raw.get("crawler", {}) or {}
    cred_raw = raw.get("credibility", {}) or {}
    knowledge_raw = raw.get("knowledge", {}) or {}
    evolution_raw = raw.get("evolution", {}) or {}
    memory_raw = raw.get("memory", {}) or {}

    thresholds = cred_raw.get("thresholds", {}) or {}
    theta_high = thresholds.get("high", cred_raw.get("theta_high", 0.8))
    theta_low = thresholds.get("medium", cred_raw.get("theta_low", 0.5))

    raw_sources = crawler_raw.get("sources", []) or []
    # 爬虫只接受 URL 字符串；YAML 里的 {name, type, url} 结构在此拍平
    sources = []
    for item in raw_sources:
        if isinstance(item, str):
            sources.append(item)
        elif isinstance(item, dict):
            url = item.get("url") or item.get("name")
            if url:
                sources.append(url)

    return {
        "system": {
            "name": system_raw.get("name", "AutoNewsAnalyzer"),
            "mode": system_raw.get("mode", "development"),
            "debug": bool(system_raw.get("debug", True)),
            "data_path": system_raw.get("data_path", "./data"),
        },
        "crawler": {
            "enabled": bool(crawler_raw.get("enabled", True)),
            "use_mock_data": bool(crawler_raw.get("use_mock_data", True)),
            "mock_data_count": int(crawler_raw.get("mock_data_count", 6) or 0),
            "sources": sources,
            "request_timeout": crawler_raw.get("request_timeout", 30),
            "max_retries": crawler_raw.get("max_retries", 3),
            "rate_limit_delay": crawler_raw.get("rate_limit_delay", 1.0),
            "user_agent": crawler_raw.get("user_agent", "AutoNewsAnalyzer/2.0"),
        },
        "credibility": {
            "enabled": bool(cred_raw.get("enabled", True)),
            "weights": cred_raw.get("weights") or dict(DEFAULT_WEIGHTS),
            "theta_high": float(theta_high),
            "theta_low": float(theta_low),
            "source_reputation": cred_raw.get("source_reputation") or {},
        },
        "knowledge": {
            "enabled": bool(knowledge_raw.get("enabled", True)),
            "graph_storage": knowledge_raw.get("graph_storage", "memory"),
            "extractors": knowledge_raw.get("extractors", []),
        },
        "evolution": dict(evolution_raw),
        "memory": {
            "enabled": bool(memory_raw.get("enabled", True)),
            "capacity": int(memory_raw.get("capacity", 10000)),
            "retention_policies": memory_raw.get("retention_policies", {}),
        },
        "reporting": {
            "output_dir": (raw.get("reporting") or {}).get("output_dir", "output"),
        },
        "state": {
            "persistence_enabled": True,
            "persistence_path": "data/state/engine_state.pkl",
        },
        "feedback": {"max_history_size": 500},
        "patent_evidence": {"enabled": True},
        "evaluation": {
            "dataset_path": (raw.get("evaluation") or {}).get(
                "dataset_path", "data/cycle_metrics.jsonl"
            ),
            "export_csv": bool((raw.get("evaluation") or {}).get("export_csv", True)),
        },
        "monitoring": {
            "metrics_path": (raw.get("monitoring") or {}).get(
                "metrics_path", "data/metrics/engine_metrics.json"
            ),
        },
    }


def build_engine_config(
    mode: str = "development",
    config_path: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    llm: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """加载 + 转换 + 合并命令行覆盖项，得到最终的引擎配置"""
    raw = load_yaml(mode=mode, config_path=config_path)
    config = to_engine_config(raw)

    # 以 YAML 内声明的 mode 为准（--config 指向其它环境的文件时更符合直觉）
    config["system"]["mode"] = config["system"].get("mode") or mode

    if overrides:
        config = _deep_merge(config, overrides)

    if llm is not None:
        config["knowledge"]["llm"] = llm

    return config
