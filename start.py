#!/usr/bin/env python3
"""
AutoNewsAnalyzer 启动器

两种用法：
  1) 直接双击 start.bat（Windows）或运行 python start.py —— 进入交互菜单
  2) 命令行：python start.py run --cycles 3 / python start.py eval / python start.py test

菜单里可以：
  - 输入 / 更新 DeepSeek API Key（写入 .env，不碰源码）
  - 选择运行方式：单周期、多周期、常驻、真实数据源
  - 查看长期评估、专利证据、运行测试、安装依赖

本文件只依赖标准库，未装项目依赖时也能正常打开菜单。
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
IS_WINDOWS = os.name == "nt"
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
REEXEC_FLAG = "AUTONEWS_NO_REEXEC"

DEFAULT_MODEL = "deepseek-chat"


# ---------------------------------------------------------------- 基础工具
def ensure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_env_value(key: str, path: Path = ENV_FILE) -> str:
    """从 .env 读取某个键（不存在返回空串）"""
    if not path.exists():
        return ""
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*)$")
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match:
                return match.group(1).strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def upsert_env_value(key: str, value: str, path: Path = ENV_FILE) -> Path:
    """写入/更新 .env 中的键；值为空时删除该键。保留其它行与注释。"""
    lines = []
    if path.exists():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replacement = f"{key}={value}"
    output = []
    written = False

    for line in lines:
        if pattern.match(line):
            if written or not value:
                continue  # 删除重复项，或删除该键
            output.append(replacement)
            written = True
        else:
            output.append(line)

    if value and not written:
        output.append(replacement)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip("\n") + "\n", encoding="utf-8")
    return path


def mask_secret(value: str) -> str:
    if not value:
        return "未配置"
    if len(value) <= 10:
        return value[:2] + "****"
    return f"{value[:8]}****{value[-4:]}"


def effective_key() -> str:
    """实际生效的 Key：环境变量优先于 .env（与 main.py 的加载逻辑一致）"""
    return os.getenv("DEEPSEEK_API_KEY", "").strip() or read_env_value("DEEPSEEK_API_KEY")


def pause() -> None:
    try:
        input("\n按回车返回菜单...")
    except (KeyboardInterrupt, EOFError):
        print()


def clear_screen() -> None:
    if not os.getenv("AUTONEWS_NO_CLEAR"):
        os.system("cls" if IS_WINDOWS else "clear")


# ---------------------------------------------------------------- 环境
def in_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == VENV_PY.resolve()
    except OSError:
        return False


def reexec_in_venv() -> None:
    """若存在 .venv 且当前不是它，切换到 .venv 的解释器重新运行自己"""
    if os.getenv(REEXEC_FLAG) or in_venv() or not VENV_PY.exists():
        return
    env = dict(os.environ)
    env[REEXEC_FLAG] = "1"
    result = subprocess.call([str(VENV_PY), str(Path(__file__)), *sys.argv[1:]], env=env)
    sys.exit(result)


def python_version_text() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


# 主链路真正 import 的第三方模块（少一个都会让 `import src` 失败）
REQUIRED_MODULES = {
    "jieba": "jieba",
    "networkx": "networkx",
    "yaml": "pyyaml",
    "requests": "requests",
    "aiohttp": "aiohttp",
    "numpy": "numpy",
    "bs4": "beautifulsoup4",
    "backoff": "backoff",
    "packaging": "packaging",
    "pandas": "pandas",
    "psutil": "psutil",
}


def missing_packages() -> list:
    """检查主流程依赖是否可导入"""
    missing = []
    for module, package in REQUIRED_MODULES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    return missing


def run_command(args: list, title: str = "") -> int:
    if title:
        print(f"\n=== {title} ===")
    print(f"$ python {' '.join(args)}\n")
    try:
        return subprocess.call([sys.executable, *args], cwd=str(ROOT))
    except KeyboardInterrupt:
        print("\n已中断")
        return 130


# ---------------------------------------------------------------- 功能
def setup_environment() -> bool:
    """创建 .venv 并安装最小依赖（幂等）"""
    print("\n=== 环境初始化 ===")
    print(f"Python: {python_version_text()}")

    if not VENV_PY.exists():
        print("创建虚拟环境 .venv ...")
        code = subprocess.call([sys.executable, "-m", "venv", str(ROOT / ".venv")], cwd=str(ROOT))
        if code != 0 or not VENV_PY.exists():
            print("❌ 创建虚拟环境失败")
            return False
        print("✅ 已创建 .venv")
    else:
        print("✅ 虚拟环境已存在")

    print("\n安装依赖（requirements-core.txt）...")
    code = subprocess.call(
        [str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check",
         "-q", "-r", "requirements-core.txt"],
        cwd=str(ROOT),
    )
    if code != 0:
        print("❌ 依赖安装失败（检查网络，或手动执行 pip install -r requirements-core.txt）")
        return False
    print("✅ 依赖安装完成")

    if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
        ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print("✅ 已生成 .env（可在菜单里填入 API Key）")

    return True


def test_api_key(key: str, model: str = DEFAULT_MODEL) -> bool:
    """调用一次极小的补全请求验证 Key 是否可用"""
    import json
    import urllib.error
    import urllib.request

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 4,
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"✅ 连通性正常（模型返回: {content.strip()[:20] or 'ok'}）")
        return True
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        print(f"❌ 接口返回 HTTP {e.code}: {body}")
    except Exception as e:
        print(f"❌ 调用失败: {e}")
    return False


def configure_key() -> None:
    print("\n=== 设置 API Key ===")
    current = read_env_value("DEEPSEEK_API_KEY")
    print(f"当前 .env: {mask_secret(current)}")
    if os.getenv("DEEPSEEK_API_KEY"):
        print(f"环境变量覆盖: {mask_secret(os.getenv('DEEPSEEK_API_KEY', ''))}（优先级更高）")
    print("提示：直接回车保留当前值；输入 - 清除（切回纯规则提取）。")

    # 交互终端里隐藏输入；输入被重定向（脚本/CI）时退回普通 input，
    # 否则 Windows 的 getpass 会去读控制台而卡住
    if sys.stdin.isatty():
        try:
            import getpass

            raw = getpass.getpass("粘贴新的 API Key（不显示）: ").strip()
        except Exception:
            raw = input("粘贴新的 API Key: ").strip()
    else:
        raw = input("粘贴新的 API Key（当前为非交互输入，会回显）: ").strip()

    if raw == "":
        print("已保留当前配置。")
        return
    if raw == "-":
        upsert_env_value("DEEPSEEK_API_KEY", "")
        print("✅ 已清除 API Key，之后将使用规则提取模式。")
        return
    if not raw.startswith("sk-") or len(raw) < 20:
        confirm = input("⚠️ 格式不像 DeepSeek Key（通常以 sk- 开头），仍要保存？(y/N): ").strip().lower()
        if confirm != "y":
            print("已取消。")
            return

    model = read_env_value("DEEPSEEK_MODEL") or DEFAULT_MODEL
    typed_model = input(f"模型名称（回车使用 {model}）: ").strip()
    if typed_model:
        model = typed_model

    upsert_env_value("DEEPSEEK_API_KEY", raw)
    upsert_env_value("DEEPSEEK_MODEL", model)
    # 清除本进程内的环境变量，避免旧值覆盖新写入的 .env
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("DEEPSEEK_MODEL", None)
    print(f"✅ 已写入 .env: {mask_secret(raw)}  模型: {model}")

    if input("是否立即测试连通性？(Y/n): ").strip().lower() in ("", "y", "yes"):
        test_api_key(raw, model)


def ensure_key_or_warn() -> None:
    if not effective_key():
        print("\nℹ️ 未配置 API Key，本次将以「规则提取」模式运行（功能完整，只是没有 LLM 三元组）。")


def open_output_dir() -> None:
    target = ROOT / "output"
    target.mkdir(parents=True, exist_ok=True)
    if IS_WINDOWS:
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.call(["open", str(target)])
    else:
        subprocess.call(["xdg-open", str(target)])


# ---------------------------------------------------------------- 菜单
def show_header() -> None:
    key = effective_key()
    if in_venv():
        venv_state = "已启用"
    elif VENV_PY.exists():
        venv_state = "存在但未启用"
    else:
        venv_state = "未创建"
    print("=" * 58)
    print("        AutoNewsAnalyzer v2.0  启动器")
    print("=" * 58)
    print(f"  项目目录 : {ROOT}")
    print(f"  Python   : {python_version_text()}  虚拟环境: {venv_state}")
    print(f"  API Key  : {mask_secret(key)}" + ("" if key else "   （规则提取模式）"))
    print("-" * 58)


def menu() -> None:
    while True:
        clear_screen()
        show_header()
        print("  1. 运行 1 个周期")
        print("  2. 连续运行（自选周期数）")
        print("  3. 常驻运行（定时轮询 + 监控端口）")
        print("  4. 用真实新闻源运行（需联网）")
        print("  5. 设置 / 更新 API Key")
        print("  6. 查看长期效果评估")
        print("  7. 查看专利证据汇总")
        print("  8. 运行测试")
        print("  9. 环境自检 / 安装依赖")
        print("  10. 打开报告目录")
        print("  0. 退出")
        print("-" * 58)

        try:
            choice = input("请选择 [0-10]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出。")
            return

        if choice == "0":
            print("\n再见。")
            return
        elif choice == "1":
            ensure_key_or_warn()
            run_command(["main.py", "--cycles", "1"], "运行 1 个周期")
            pause()
        elif choice == "2":
            count = input("运行多少个周期？[3]: ").strip() or "3"
            if not count.isdigit() or int(count) < 1:
                print("❌ 请输入正整数")
                pause()
                continue
            ensure_key_or_warn()
            run_command(["main.py", "--cycles", count], f"连续运行 {count} 个周期")
            pause()
        elif choice == "3":
            interval = input("周期间隔（秒）[3600]: ").strip() or "3600"
            if not interval.isdigit() or int(interval) < 1:
                print("❌ 间隔必须是正整数，已改用默认 3600")
                interval = "3600"
            port = input("监控端口（回车默认 9090，输入 0 不开启）: ").strip()
            if port == "":
                port = "9090"
            args = ["main.py", "--continuous", "--interval", interval]
            if port != "0":
                args += ["--metrics-port", port]
                endpoint = f"http://127.0.0.1:{port}/metrics"
            else:
                endpoint = "（已关闭，不监听端口）"
            ensure_key_or_warn()
            print(f"\n常驻运行，Ctrl+C 结束。指标端点: {endpoint}")
            run_command(args, "常驻运行")
            pause()
        elif choice == "4":
            confirm = input("将抓取真实 RSS（需联网，可能较慢），继续？(y/N): ").strip().lower()
            if confirm == "y":
                ensure_key_or_warn()
                run_command(["main.py", "--mode", "production", "--cycles", "1"], "真实数据源")
            pause()
        elif choice == "5":
            configure_key()
            pause()
        elif choice == "6":
            run_command(["main.py", "--evaluate"], "长期效果评估")
            pause()
        elif choice == "7":
            run_command(["main.py", "--evidence-report"], "专利证据汇总")
            pause()
        elif choice == "8":
            run_command(["-m", "pytest", "tests/", "-q"], "运行测试")
            pause()
        elif choice == "9":
            missing = missing_packages()
            if missing:
                print(f"\n缺少依赖: {', '.join(missing)}")
            else:
                print("\n✅ 主流程依赖齐全")
            if not VENV_PY.exists() or missing:
                if input("是否现在创建虚拟环境并安装依赖？(Y/n): ").strip().lower() in ("", "y"):
                    setup_environment()
                    print("\n提示：安装完成后重新打开启动器即可使用。")
            pause()
        elif choice == "10":
            open_output_dir()
            pause()
        else:
            print("❌ 无效选择")
            pause()


# ---------------------------------------------------------------- 命令行入口
def cli(argv: list) -> int:
    if not argv:
        return -1

    command = argv[0]
    rest = argv[1:]

    if command in ("run", "dev"):
        return run_command(["main.py", *rest] if rest else ["main.py", "--cycles", "1"])
    if command == "cycles":
        count = rest[0] if rest else "3"
        return run_command(["main.py", "--cycles", count])
    if command == "prod":
        return run_command(["main.py", "--mode", "production", "--cycles", rest[0] if rest else "1"])
    if command == "continuous":
        return run_command(["main.py", "--continuous", *rest])
    if command == "eval":
        return run_command(["main.py", "--evaluate"])
    if command == "evidence":
        return run_command(["main.py", "--evidence-report"])
    if command == "test":
        return run_command(["-m", "pytest", "tests/", "-q"])
    if command == "check":
        key = effective_key()
        print(f"Python : {python_version_text()}（{'venv' if in_venv() else '系统'}）")
        print(f"目录   : {ROOT}")
        print(f"Key    : {mask_secret(key)}")
        print(f"依赖   : {'齐全' if not missing_packages() else '缺少 ' + ', '.join(missing_packages())}")
        return 0
    if command == "setup":
        return 0 if setup_environment() else 1
    if command in ("-h", "--help", "help"):
        print("用法:")
        print("  python start.py                  进入交互菜单")
        print("  python start.py run [--cycles N] 直接运行")
        print("  python start.py prod [N]         真实数据源运行")
        print("  python start.py continuous [...] 常驻运行")
        print("  python start.py eval             长期效果评估")
        print("  python start.py evidence         专利证据汇总")
        print("  python start.py test             运行测试")
        print("  python start.py check            环境自检")
        print("  python start.py setup            创建环境并安装依赖")
        return 0

    print(f"未知命令: {command}（用 python start.py help 查看用法）")
    return 2


def main() -> int:
    ensure_utf8_console()
    reexec_in_venv()
    argv = sys.argv[1:]
    code = cli(argv)
    if code >= 0:
        return code
    try:
        menu()
        return 0
    except KeyboardInterrupt:
        print("\n已退出。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
