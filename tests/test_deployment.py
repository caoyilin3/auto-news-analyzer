"""部署配置的静态校验

本机没有 Docker，无法真正执行 `docker build`；这里用可执行的方式校验
部署文件之间的一致性（Dockerfile 引用的文件是否存在、compose 挂载路径是否存在、
Prometheus 抓取目标是否与指标端点一致等），把"配置漂移"变成可回归的测试。
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_references_existing_files():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.10" in text

    copy_sources = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("COPY "):
            parts = stripped.split()[1:-1]  # 最后一个是目标路径
            copy_sources.extend(p for p in parts if not p.startswith("--"))

    assert "requirements-core.txt" in copy_sources
    for source in copy_sources:
        if "*" in source or "$" in source:
            continue
        assert (ROOT / source).exists(), f"Dockerfile COPY 引用了不存在的路径: {source}"

    assert "main.py" in text and (ROOT / "main.py").exists()
    assert (ROOT / "requirements-core.txt").exists()


def test_docker_compose_mounts_exist():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "autonews-analyzer" in services

    app = services["autonews-analyzer"]
    assert app["build"] == "."
    assert (ROOT / "Dockerfile").exists()

    for volume in app.get("volumes", []):
        host = volume.split(":")[0]
        assert (ROOT / host).exists(), f"compose 挂载了不存在的宿主机路径: {host}"

    for name, service in services.items():
        for volume in service.get("volumes", []):
            host = volume.split(":")[0]
            if host.startswith("./"):
                assert (ROOT / host).exists(), f"{name} 挂载了不存在的路径: {host}"


def test_prometheus_scrapes_app_metrics_endpoint():
    config = yaml.safe_load((ROOT / "deployments" / "prometheus.yml").read_text(encoding="utf-8"))
    jobs = {job["job_name"]: job for job in config["scrape_configs"]}
    assert "autonews-analyzer" in jobs

    job = jobs["autonews-analyzer"]
    assert job["metrics_path"] == "/metrics"
    targets = job["static_configs"][0]["targets"]
    assert targets == ["autonews-analyzer:9090"]


def test_requirements_core_covers_pipeline_imports():
    """主链路所需的第三方包必须出现在最小依赖清单里"""
    text = (ROOT / "requirements-core.txt").read_text(encoding="utf-8").lower()
    # 模块名 -> 发行包名
    required = {
        "jieba": "jieba",
        "aiohttp": "aiohttp",
        "backoff": "backoff",
        "bs4": "beautifulsoup4",
        "lxml": "lxml",
        "numpy": "numpy",
        "networkx": "networkx",
        "requests": "requests",
        "yaml": "pyyaml",
        "psutil": "psutil",
        "packaging": "packaging",
    }
    missing = [pkg for pkg in required.values() if pkg not in text]
    assert not missing, f"requirements-core.txt 缺少: {missing}"


def test_requirements_files_are_pip_readable_on_non_utf8_locale():
    """pip 会按系统 locale 解码 requirements 文件（Windows 默认 GBK），
    含中文注释时必须声明 utf-8 编码或带 BOM，否则 `pip install -r` 直接报错。"""
    import re

    for name in ("requirements.txt", "requirements-core.txt", "requirements-dev.txt"):
        data = (ROOT / name).read_bytes()
        has_bom = data.startswith(b"\xef\xbb\xbf")
        first_two_lines = b"\n".join(data.split(b"\n")[:2])
        has_coding = re.search(rb"coding[:=]\s*([-\w.]+)", first_two_lines) is not None
        has_non_ascii = any(byte > 127 for byte in data)
        assert has_bom or has_coding or not has_non_ascii, (
            f"{name} 含非 ASCII 字符却未声明编码，非 UTF-8 locale 下 pip 会解析失败"
        )


def test_metrics_server_renders_prometheus_text():
    from src.interfaces.metrics_server import render_metrics

    rendered = render_metrics({
        "autonews_cycles_total": 3,
        "learn_rate": 0.5,
        "ignored_text": "not-a-number",
        "ignored_bool": True,
    })
    assert "autonews_cycles_total 3" in rendered
    assert "autonews_learn_rate 0.5" in rendered
    assert "# TYPE autonews_learn_rate gauge" in rendered
    assert "ignored_text" not in rendered
    assert "ignored_bool" not in rendered


def test_deploy_scripts_are_present_and_portable():
    """部署脚本存在，且 .ps1 带 UTF-8 BOM（Windows PowerShell 5.1 需要）"""
    ps1 = ROOT / "scripts" / "deploy.ps1"
    sh = ROOT / "scripts" / "deploy.sh"
    assert ps1.exists(), "缺少 scripts/deploy.ps1"
    assert sh.exists(), "缺少 scripts/deploy.sh"
    assert ps1.read_bytes().startswith(b"\xef\xbb\xbf"), (
        "deploy.ps1 必须以 UTF-8 BOM 保存，否则 PowerShell 5.1 会按 GBK 解析导致语法错误"
    )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/deploy-with-ai.md" in readme
    assert (ROOT / "docs" / "deploy-with-ai.md").exists()
