"""
AutoNewsAnalyzer 版本信息
"""

import sys
import platform
from datetime import datetime
from typing import Dict, Any, Tuple


# 版本信息
__version__ = "2.0.0"
__version_info__ = (2, 0, 0)
__release_date__ = "2024-01-01"

# 作者信息
__author__ = "AutoNewsAnalyzer Team"
__author_email__ = "team@autonews.dev"
__maintainer__ = __author__
__maintainer_email__ = __author_email__

# 项目信息
__project_name__ = "AutoNewsAnalyzer"
__project_description__ = "An autonomous AI-driven news analysis system with self-evolution capabilities"
__project_url__ = "https://github.com/yourusername/autonews-analyzer"
__project_docs__ = "https://autonews.dev/docs"
__project_license__ = "MIT"

# 依赖版本要求
__requirements__ = {
    "python": ">=3.8",
    "torch": ">=2.0.0",
    "transformers": ">=4.33.0",
    "spacy": ">=3.6.0",
    "fastapi": ">=0.100.0",
    "sqlalchemy": ">=2.0.0",
    "redis": ">=5.0.0",
}


def get_version() -> str:
    """获取完整版本字符串"""
    return f"{__project_name__} v{__version__}"


def get_version_tuple() -> Tuple[int, int, int]:
    """获取版本元组"""
    return __version_info__


def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    return {
        "project": {
            "name": __project_name__,
            "version": __version__,
            "version_info": __version_info__,
            "release_date": __release_date__,
            "description": __project_description__,
            "url": __project_url__,
            "license": __project_license__,
        },
        "author": {
            "name": __author__,
            "email": __author_email__,
        },
        "system": {
            "python_version": sys.version,
            "python_implementation": platform.python_implementation(),
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "machine": platform.machine(),
        },
        "timestamp": datetime.now().isoformat(),
        "requirements": __requirements__,
    }


def check_compatibility() -> Dict[str, Any]:
    """检查系统兼容性"""
    import importlib.metadata as metadata
    import warnings
    
    issues = []
    warnings_list = []
    
    # 检查Python版本
    current_version = sys.version_info[:2]
    required_version = (3, 8)
    
    if current_version < required_version:
        issues.append(f"Python版本需要 {required_version[0]}.{required_version[1]}+，当前为 {current_version[0]}.{current_version[1]}")
    
    # 检查主要依赖
    required_packages = {
        "torch": "2.0.0",
        "transformers": "4.33.0",
        "spacy": "3.6.0",
        "fastapi": "0.100.0",
        "sqlalchemy": "2.0.0",
        "redis": "5.0.0",
    }
    
    for package, min_version in required_packages.items():
        try:
            installed_version = metadata.version(package)
            
            # 简单的版本比较
            from packaging import version
            
            if version.parse(installed_version) < version.parse(min_version):
                warnings_list.append(f"{package} 版本较低: {installed_version} < {min_version}")
        except metadata.PackageNotFoundError:
            issues.append(f"缺少依赖: {package}")
    
    return {
        "compatible": len(issues) == 0,
        "issues": issues,
        "warnings": warnings_list,
        "system_info": get_system_info(),
    }


def get_changelog() -> Dict[str, Dict[str, str]]:
    """获取变更日志"""
    return {
        "2.0.0": {
            "date": "2024-01-01",
            "changes": [
                "初始发布版本",
                "实现自主进化核心架构",
                "支持多源数据采集",
                "实现多维度可信度评估",
                "集成知识图谱构建",
                "提供REST API接口",
            ]
        },
        "1.0.0": {
            "date": "2023-12-01",
            "changes": [
                "概念验证版本",
                "基础爬虫功能",
                "简单知识提取",
                "命令行界面",
            ]
        }
    }


def get_roadmap() -> Dict[str, Dict[str, Any]]:
    """获取开发路线图"""
    return {
        "planned": {
            "2.1.0": {
                "date": "2024-03-01",
                "features": [
                    "增强关系抽取模型",
                    "实现主动学习机制",
                    "改进冲突消解算法",
                ],
                "status": "planning",
            },
            "2.2.0": {
                "date": "2024-06-01",
                "features": [
                    "多语言支持",
                    "实时流处理",
                    "增强可视化界面",
                ],
                "status": "planning",
            },
        },
        "in_progress": {
            "2.0.1": {
                "date": "2024-01-15",
                "features": [
                    "性能优化",
                    "bug修复",
                    "文档完善",
                ],
                "status": "development",
            },
        },
        "completed": {
            "2.0.0": {
                "date": "2024-01-01",
                "features": [
                    "核心系统开发",
                    "基础功能实现",
                    "文档编写",
                ],
                "status": "released",
            },
        },
    }


def print_banner():
    """打印系统横幅"""
    banner = f"""
╔══════════════════════════════════════════════════════════╗
║                {__project_name__} v{__version__}                    ║
║          自主进化的AI驱动新闻分析系统                     ║
║                                                          ║
║  Version: {__version__:48}║
║  Author:  {__author__:48}║
║  License: {__project_license__:48}║
║  Python:  {sys.version.split()[0]:48}║
╚══════════════════════════════════════════════════════════╝
"""
    print(banner)


def export_version_info(output_file=None):
    """导出版本信息"""
    import json
    import yaml
    
    info = get_system_info()
    
    if output_file:
        output_path = Path(output_file)
        if output_path.suffix == '.json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2, ensure_ascii=False)
        elif output_path.suffix in ['.yaml', '.yml']:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(info, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError("输出文件格式必须是 .json 或 .yaml")
    
    return info


if __name__ == "__main__":
    # 测试代码
    print_banner()
    
    print("\n系统信息:")
    info = get_system_info()
    for category, details in info.items():
        print(f"\n{category.upper()}:")
        if isinstance(details, dict):
            for key, value in details.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {details}")
    
    print("\n兼容性检查:")
    compatibility = check_compatibility()
    if compatibility["compatible"]:
        print("  ✅ 系统兼容性检查通过")
    else:
        print("  ❌ 存在兼容性问题:")
        for issue in compatibility["issues"]:
            print(f"    - {issue}")
    
    if compatibility["warnings"]:
        print("  ⚠️  警告:")
        for warning in compatibility["warnings"]:
            print(f"    - {warning}")