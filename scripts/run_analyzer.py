#!/usr/bin/env python3
"""
运行分析器脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from main import main as analyzer_main


if __name__ == "__main__":
    # 设置命令行参数
    sys.argv = [
        "main.py",
        "--mode", "development",
        "--cycles", "1",
        "--verbose"
    ]
    
    # 运行主程序
    exit_code = asyncio.run(analyzer_main())
    sys.exit(exit_code)