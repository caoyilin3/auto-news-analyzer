"""
AutoNewsAnalyzer - 自主进化的AI驱动新闻分析系统

核心模块：
- data_acquisition: 数据采集层
- credibility: 可信度评估层  
- knowledge: 知识管理层
- evolution: 自主进化层
- memory: 记忆管理层
- interfaces: 接口层
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from .version import __version__, __author__, __project_license__ as __license__
from .core import SystemEngine, Orchestrator
from .data_acquisition import DataAcquisitionManager
from .credibility import CredibilityEvaluator
from .knowledge import KnowledgeManager
from .evolution import EvolutionManager
from .memory import MemoryManager

# 设置模块级别的logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    # 版本信息
    '__version__',
    '__author__',
    '__license__',
    
    # 核心组件
    'SystemEngine',
    'Orchestrator',
    
    # 功能模块
    'DataAcquisitionManager',
    'CredibilityEvaluator',
    'KnowledgeManager',
    'EvolutionManager',
    'MemoryManager',
    
    # 工具函数
    'initialize_system',
    'get_system_info',
    'setup_logging',
]


class AutoNewsAnalyzer:
    """AutoNewsAnalyzer 主类 - 统一入口"""
    
    def __init__(self, config_path=None, env="development"):
        """
        初始化系统
        
        Args:
            config_path: 配置文件路径
            env: 环境类型 (development, production, testing)
        """
        self.version = __version__
        self.env = env
        self.config_path = config_path
        self.components = {}
        self.logger = logging.getLogger(__name__)
        
    def initialize(self):
        """初始化所有组件"""
        self.logger.info(f"初始化 AutoNewsAnalyzer v{self.version}...")
        
        # 这里会初始化所有核心组件
        # 具体实现会在各模块中完成
        
        self.logger.info("系统初始化完成")
        return True
    
    def run(self, cycles=1):
        """运行指定次数的分析周期"""
        results = []
        
        for i in range(cycles):
            self.logger.info(f"开始第 {i+1}/{cycles} 个分析周期...")
            result = self._run_single_cycle()
            results.append(result)
            
            if not result.get("success", False):
                self.logger.error(f"第 {i+1} 个周期失败")
                break
        
        return results
    
    def _run_single_cycle(self):
        """运行单个分析周期"""
        # 这里会实现完整的工作流
        # 数据采集 -> 可信度评估 -> 知识提取 -> 进化学习 -> 记忆管理
        
        return {
            "status": "completed",
            "success": True,
            "timestamp": "2024-01-01T00:00:00",
            "duration": 0.0,
            "results": {}
        }
    
    def shutdown(self):
        """优雅关闭系统"""
        self.logger.info("关闭系统...")
        
        for name, component in self.components.items():
            if hasattr(component, 'shutdown'):
                component.shutdown()
                self.logger.debug(f"已关闭组件: {name}")
        
        self.logger.info("系统关闭完成")


def initialize_system(config_path=None, env="development"):
    """
    初始化系统
    
    Args:
        config_path: 配置文件路径
        env: 环境类型
        
    Returns:
        AutoNewsAnalyzer: 系统实例
    """
    system = AutoNewsAnalyzer(config_path, env)
    system.initialize()
    return system


def get_system_info():
    """获取系统信息"""
    from .core.state_manager import SystemStateManager
    
    return {
        "system": {
            "name": "AutoNewsAnalyzer",
            "version": __version__,
            "author": __author__,
            "license": __license__,
            "python_version": sys.version,
            "platform": sys.platform,
        },
        "modules": {
            "data_acquisition": True,
            "credibility": True,
            "knowledge": True,
            "evolution": True,
            "memory": True,
            "interfaces": True,
        }
    }


def setup_logging(level=logging.INFO, log_file=None):
    """
    设置日志系统
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
    """
    # 创建formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # 配置logger
    logger = logging.getLogger('autonews')
    logger.setLevel(level)
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，添加文件handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    return logger


# 定义模块级别的变量
__author__ = "AutoNewsAnalyzer Team"
__license__ = "MIT"
__copyright__ = f"Copyright 2023 {__author__}"


# 当模块被导入时执行的代码
if __name__ == "__main__":
    # 如果直接运行这个模块，显示系统信息
    info = get_system_info()
    print(f"AutoNewsAnalyzer v{info['system']['version']}")
    print(f"Author: {info['system']['author']}")
    print(f"License: {info['system']['license']}")
    print(f"Python: {info['system']['python_version']}")
    print(f"Platform: {info['system']['platform']}")