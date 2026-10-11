#!/usr/bin/env python3
"""
项目设置脚本
"""
import os
import sys
import shutil
from pathlib import Path


def setup_project():
    """设置项目环境"""
    print("🚀 AutoNewsAnalyzer v2.0 项目设置")
    print("=" * 60)
    
    # 项目根目录
    project_root = Path(__file__).parent.parent
    
    # 创建必要目录
    directories = [
        project_root / "data" / "patent_evidence",
        project_root / "data" / "logs",
        project_root / "data" / "cache",
        project_root / "tests",
        project_root / "docs",
        project_root / "scripts"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建目录: {directory.relative_to(project_root)}")
    
    # 创建 .env 文件（如果不存在）
    env_example = project_root / ".env.example"
    env_file = project_root / ".env"
    
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        print(f"✅ 创建环境文件: {env_file.name}")
    
    # 安装依赖
    print("\n📦 安装依赖...")
    os.system("pip install -e .")
    
    print("\n🎉 项目设置完成!")
    print("\n接下来可以运行:")
    print("  python main.py --mode development --cycles 1")


if __name__ == "__main__":
    setup_project()