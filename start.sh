#!/usr/bin/env bash
# AutoNewsAnalyzer 启动器（Linux / macOS）
# 用法: ./start.sh            进入交互菜单
#       ./start.sh run --cycles 3
#       ./start.sh test

set -u
cd "$(dirname "$0")" || exit 1

if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "未找到 python3，请先安装 Python 3.10+"
  exit 1
fi

exec "$PY" start.py "$@"
