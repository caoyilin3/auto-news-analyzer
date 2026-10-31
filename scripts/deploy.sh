#!/usr/bin/env bash
# AutoNewsAnalyzer 一键部署（Linux / macOS，幂等）
#
# 用法:
#   bash scripts/deploy.sh                 # 最小依赖 + 测试 + 冒烟（规则模式）
#   bash scripts/deploy.sh --full          # 安装完整依赖
#   bash scripts/deploy.sh --start         # 部署后常驻启动并验证 /metrics
#   bash scripts/deploy.sh --with-llm      # 冒烟测试调用大模型（产生费用）
#   bash scripts/deploy.sh --skip-tests    # 跳过 pytest
#
# 真实 API Key 只会写入 .env（已被 .gitignore 忽略），不会进入任何源码。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQ="requirements-core.txt"
SKIP_TESTS=0
WITH_LLM=0
START=0
CYCLES=1
METRICS_PORT=9090

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)       REQ="requirements.txt" ;;
    --skip-tests) SKIP_TESTS=1 ;;
    --with-llm)   WITH_LLM=1 ;;
    --start)      START=1 ;;
    --cycles)     CYCLES="${2:?}"; shift ;;
    --port)       METRICS_PORT="${2:?}"; shift ;;
    -h|--help)    sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
  shift
done

step() { printf '\n=== %s ===\n' "$1"; }
ok()   { printf '  [OK] %s\n' "$1"; }
warn() { printf '  [!]  %s\n' "$1"; }
fail() { printf '  [X]  %s\n' "$1" >&2; exit 1; }

echo "AutoNewsAnalyzer 部署脚本"
echo "项目目录: $ROOT"

# ---------------------------------------------------------------- 0. 环境检查
step "0. 环境检查"
command -v python3 >/dev/null 2>&1 || fail "未找到 python3，请先安装 Python 3.10+"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || fail "Python 版本过低（需要 3.10+，当前 $(python3 --version 2>&1)）"
ok "$(python3 --version 2>&1)"

VENV_DIR="$ROOT/.venv"
VENV_PY="$VENV_DIR/bin/python"

# ---------------------------------------------------------------- 1. 虚拟环境
step "1. 虚拟环境"
if [[ -x "$VENV_PY" ]]; then
  ok "已存在: .venv"
else
  python3 -m venv "$VENV_DIR"
  ok "已创建: .venv"
fi
"$VENV_PY" -m pip install --disable-pip-version-check -q --upgrade pip

# ---------------------------------------------------------------- 2. 依赖
step "2. 安装依赖"
echo "  使用: $REQ"
"$VENV_PY" -m pip install --disable-pip-version-check -q -r "$REQ" \
  || fail "依赖安装失败（检查网络，或改用 --full）"
ok "依赖安装完成"

# ---------------------------------------------------------------- 3. 配置
step "3. 环境变量"
if [[ -f .env ]]; then
  ok ".env 已存在，保持不动（不覆盖已有密钥）"
else
  cp .env.example .env
  ok "已从 .env.example 生成 .env（DEEPSEEK_API_KEY 为空 = 规则提取模式）"
fi
if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
  ok "检测到环境变量 DEEPSEEK_API_KEY（优先于 .env）"
elif grep -Eq '^[[:space:]]*DEEPSEEK_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]+' .env; then
  ok ".env 中已配置 DEEPSEEK_API_KEY"
else
  warn "未配置大模型密钥，将以规则提取模式运行（不影响主流程）"
fi

# ---------------------------------------------------------------- 4. 测试
if [[ "$SKIP_TESTS" -eq 0 ]]; then
  step "4. 运行测试"
  "$VENV_PY" -m pytest tests/ -q || fail "测试未通过，部署中止"
  ok "测试全部通过"
else
  step "4. 运行测试（已跳过）"
fi

# ---------------------------------------------------------------- 5. 冒烟
step "5. 冒烟运行"
SMOKE_ARGS=(main.py --cycles "$CYCLES")
[[ "$WITH_LLM" -eq 0 ]] && SMOKE_ARGS+=(--no-llm)
"$VENV_PY" "${SMOKE_ARGS[@]}" || fail "冒烟运行失败（见上方输出）"

LATEST_REPORT="$(ls -t output/*.json 2>/dev/null | head -n 1 || true)"
[[ -n "$LATEST_REPORT" ]] || fail "未生成运行报告"
ok "报告已生成: $LATEST_REPORT"

# ---------------------------------------------------------------- 6. 常驻启动
if [[ "$START" -eq 1 ]]; then
  step "6. 常驻启动"
  mkdir -p data/logs
  nohup "$VENV_PY" main.py --continuous --interval 3600 --metrics-port "$METRICS_PORT" \
    > data/logs/run.out.log 2> data/logs/run.err.log &
  echo $! > data/run.pid
  ok "已启动 (PID $(cat data/run.pid))，日志: data/logs/run.out.log"

  ready=0
  for _ in $(seq 1 20); do
    sleep 0.5
    if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:${METRICS_PORT}/metrics" 2>/dev/null | grep -q 'autonews_'; then
      ready=1; break
    fi
  done
  if [[ "$ready" -eq 1 ]]; then
    ok "指标端点正常: http://127.0.0.1:${METRICS_PORT}/metrics"
  else
    warn "指标端点暂未就绪，可稍后重试（进程仍在运行）"
  fi
fi

# ---------------------------------------------------------------- 7. 汇总
step "完成"
cat <<'EOF'
  启动:     .venv/bin/python main.py --cycles 3
  常驻:     .venv/bin/python main.py --continuous --interval 3600 --metrics-port 9090
  查看评估: .venv/bin/python main.py --evaluate
  停止常驻: kill "$(cat data/run.pid)"
EOF
printf '\n  部署成功。\n'
