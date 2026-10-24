#!/usr/bin/env python3
"""
运行分析器脚本（命令行快捷入口）

等价于：python main.py --mode development --cycles 1 --verbose
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from main import main as analyzer_main


if __name__ == "__main__":
    # 设置命令行参数
    sys.argv = [
        "main.py",
        "--mode", "development",
        "--cycles", "1",
        "--verbose",
    ]

    # main() 是同步函数，内部以 sys.exit(状态码) 结束，直接调用即可
    analyzer_main()
