"""
日志配置模块
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(name: str, level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径（可选）
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定了日志文件）
    if log_file:
        # 确保日志目录存在
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 防止日志传递给父记录器
    logger.propagate = False
    
    return logger


class EvidenceLogger:
    """证据日志记录器"""
    
    def __init__(self, collector):
        self.collector = collector
        self.logger = setup_logger("EvidenceLogger")
    
    def log_evolution(self, **kwargs):
        """记录进化证据"""
        self.logger.info(f"Evolution evidence recorded: {kwargs.get('decision', 'unknown')}")
        return self.collector.log_evolution(**kwargs)
    
    def log_decision(self, **kwargs):
        """记录决策证据"""
        self.logger.info(f"Decision evidence recorded: {kwargs.get('decision_point', 'unknown')}")
        return self.collector.log_decision(**kwargs)
    
    def log_knowledge(self, **kwargs):
        """记录知识证据"""
        self.logger.info(f"Knowledge evidence recorded: {kwargs.get('entity', 'unknown')}")
        return self.collector.log_knowledge(**kwargs)
    
    def log_performance(self, **kwargs):
        """记录性能证据"""
        self.logger.info(f"Performance evidence recorded: {kwargs.get('metric_name', 'unknown')}")
        return self.collector.log_performance(**kwargs)