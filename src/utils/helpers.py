"""
helpers.py - 通用辅助函数
为整个系统提供各种通用工具和辅助功能
"""

import os
import sys
import json
import yaml
import hashlib
import logging
import random
import string
import time
import re
import inspect
import traceback
import pickle
import base64
import csv
import zipfile
import tarfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, is_dataclass
from enum import Enum
from contextlib import contextmanager
from functools import wraps, lru_cache
from collections import defaultdict, OrderedDict
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
from threading import Lock, RLock
from copy import deepcopy
import math
import statistics
import uuid

# 类型变量
T = TypeVar('T')
R = TypeVar('R')


class Singleton(type):
    """单例元类"""
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Timer:
    """计时器类"""
    
    def __init__(self, name: str = "Timer", logger: Optional[logging.Logger] = None):
        """
        初始化计时器
        
        Args:
            name: 计时器名称
            logger: 日志记录器
        """
        self.name = name
        self.logger = logger or logging.getLogger(__name__)
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        """进入上下文"""
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        self.end_time = time.perf_counter()
        elapsed = self.end_time - self.start_time
        
        if exc_type:
            self.logger.error(f"{self.name} 执行出错: {exc_val}")
        else:
            self.logger.debug(f"{self.name} 耗时: {elapsed:.4f} 秒")
    
    def start(self):
        """开始计时"""
        self.start_time = time.perf_counter()
        return self
    
    def stop(self) -> float:
        """停止计时并返回耗时"""
        if self.start_time is None:
            raise RuntimeError("计时器尚未开始")
        
        self.end_time = time.perf_counter()
        elapsed = self.end_time - self.start_time
        return elapsed
    
    def elapsed(self) -> float:
        """获取已用时间"""
        if self.start_time is None:
            return 0.0
        
        current = time.perf_counter()
        return current - self.start_time


@contextmanager
def timer_context(name: str = "操作", logger: Optional[logging.Logger] = None):
    """
    计时器上下文管理器
    
    Args:
        name: 操作名称
        logger: 日志记录器
    """
    timer = Timer(name, logger)
    timer.start()
    try:
        yield timer
    finally:
        elapsed = timer.stop()
        log_func = logger.info if logger else print
        log_func(f"{name} 完成，耗时: {elapsed:.4f} 秒")


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0,
          exceptions: Tuple = (Exception,), logger: Optional[logging.Logger] = None):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟时间(秒)
        backoff: 退避系数
        exceptions: 捕获的异常类型
        logger: 日志记录器
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        break
                    
                    wait_time = current_delay * (backoff ** (attempt - 1))
                    log_msg = (f"{func.__name__} 第 {attempt} 次尝试失败: {e}. "
                              f"{wait_time:.1f} 秒后重试...")
                    
                    if logger:
                        logger.warning(log_msg)
                    else:
                        print(log_msg)
                    
                    time.sleep(wait_time)
            
            # 所有尝试都失败
            error_msg = f"{func.__name__} 在 {max_attempts} 次尝试后失败"
            if logger:
                logger.error(f"{error_msg}: {last_exception}")
            else:
                print(f"{error_msg}: {last_exception}")
            
            raise last_exception
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        break
                    
                    wait_time = current_delay * (backoff ** (attempt - 1))
                    log_msg = (f"{func.__name__} 第 {attempt} 次尝试失败: {e}. "
                              f"{wait_time:.1f} 秒后重试...")
                    
                    if logger:
                        logger.warning(log_msg)
                    else:
                        print(log_msg)
                    
                    await asyncio.sleep(wait_time)
            
            # 所有尝试都失败
            error_msg = f"{func.__name__} 在 {max_attempts} 次尝试后失败"
            if logger:
                logger.error(f"{error_msg}: {last_exception}")
            else:
                print(f"{error_msg}: {last_exception}")
            
            raise last_exception
        
        return async_wrapper if inspect.iscoroutinefunction(func) else wrapper
    return decorator


def validate_environment() -> Dict[str, Any]:
    """
    验证运行环境
    
    Returns:
        环境验证结果
    """
    result = {
        "valid": True,
        "message": "环境验证通过",
        "details": {},
        "warnings": [],
        "errors": []
    }
    
    try:
        # 检查Python版本
        python_version = sys.version_info
        result["details"]["python_version"] = f"{python_version.major}.{python_version.minor}.{python_version.micro}"
        
        if python_version < (3, 8):
            result["valid"] = False
            result["errors"].append("Python版本需要3.8或更高")
        
        # 检查必要目录
        required_dirs = ["config", "src", "data"]
        for dir_name in required_dirs:
            if not Path(dir_name).exists():
                result["warnings"].append(f"目录 '{dir_name}' 不存在")
        
        # 检查环境变量
        env_vars_to_check = ["ENVIRONMENT", "LOG_LEVEL"]
        for var in env_vars_to_check:
            if var not in os.environ:
                result["warnings"].append(f"环境变量 '{var}' 未设置")
        
        # 检查依赖
        required_packages = ["numpy", "pandas", "requests", "aiohttp", "pydantic"]
        for package in required_packages:
            try:
                __import__(package)
                result["details"][f"package_{package}"] = True
            except ImportError:
                result["warnings"].append(f"缺少依赖包: {package}")
        
        # 检查磁盘空间
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            result["details"]["disk_space_mb"] = free // (2**20)
            
            if free < 100 * 2**20:  # 小于100MB
                result["warnings"].append("磁盘空间不足 (少于100MB)")
        except:
            pass
        
        # 更新结果消息
        if result["errors"]:
            result["valid"] = False
            result["message"] = f"环境验证失败: {', '.join(result['errors'][:3])}"
        elif result["warnings"]:
            result["message"] = f"环境验证通过，但有警告: {', '.join(result['warnings'][:3])}"
        
    except Exception as e:
        result["valid"] = False
        result["message"] = f"环境验证过程中出错: {e}"
        result["errors"].append(str(e))
    
    return result


def create_project_structure(base_path: Union[str, Path]) -> bool:
    """
    创建项目目录结构
    
    Args:
        base_path: 基础路径
        
    Returns:
        是否成功
    """
    try:
        base_path = Path(base_path)
        
        directories = [
            base_path / "config",
            base_path / "src",
            base_path / "src/core",
            base_path / "src/utils",
            base_path / "src/evolution",
            base_path / "src/knowledge",
            base_path / "data",
            base_path / "data/logs",
            base_path / "data/cache",
            base_path / "data/models",
            base_path / "tests",
            base_path / "docs",
            base_path / "scripts"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            # 创建 .gitkeep 文件
            (directory / ".gitkeep").touch(exist_ok=True)
        
        # 创建 __init__.py 文件
        init_files = [
            base_path / "src" / "__init__.py",
            base_path / "src/core" / "__init__.py",
            base_path / "src/utils" / "__init__.py",
            base_path / "src/evolution" / "__init__.py",
            base_path / "src/knowledge" / "__init__.py",
            base_path / "tests" / "__init__.py",
        ]
        
        for init_file in init_files:
            if not init_file.exists():
                init_file.write_text('"""模块初始化"""\n')
        
        return True
        
    except Exception as e:
        logging.error(f"创建项目结构失败: {e}")
        return False


def load_config_file(filepath: Union[str, Path], file_type: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        filepath: 文件路径
        file_type: 文件类型 (yaml, json, env)，自动检测
        
    Returns:
        配置字典
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"配置文件不存在: {filepath}")
    
    # 自动检测文件类型
    if file_type is None:
        suffix = filepath.suffix.lower()
        if suffix in ['.yaml', '.yml']:
            file_type = 'yaml'
        elif suffix == '.json':
            file_type = 'json'
        elif suffix == '.env':
            file_type = 'env'
        else:
            # 尝试根据内容判断
            content = filepath.read_text(encoding='utf-8')[:100]
            if content.strip().startswith('{') or content.strip().startswith('['):
                file_type = 'json'
            elif ':' in content and '\n' in content:
                file_type = 'yaml'
            else:
                file_type = 'env'
    
    try:
        if file_type == 'yaml':
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        elif file_type == 'json':
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        elif file_type == 'env':
            config = {}
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
            return config
        
        else:
            raise ValueError(f"不支持的配置文件类型: {file_type}")
            
    except Exception as e:
        raise RuntimeError(f"加载配置文件失败: {filepath} - {e}")


def save_config_file(config: Dict[str, Any], filepath: Union[str, Path], 
                     file_type: str = 'yaml', indent: int = 2) -> bool:
    """
    保存配置文件
    
    Args:
        config: 配置字典
        filepath: 文件路径
        file_type: 文件类型 (yaml, json)
        indent: 缩进空格数
        
    Returns:
        是否成功
    """
    try:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if file_type == 'yaml':
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, indent=indent,
                         allow_unicode=True)
        
        elif file_type == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=indent)
        
        else:
            raise ValueError(f"不支持的配置文件类型: {file_type}")
        
        return True
        
    except Exception as e:
        logging.error(f"保存配置文件失败: {filepath} - {e}")
        return False


def generate_unique_id(prefix: str = "", length: int = 8) -> str:
    """
    生成唯一ID
    
    Args:
        prefix: 前缀
        length: 随机部分长度
        
    Returns:
        唯一ID字符串
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    if prefix:
        return f"{prefix}_{timestamp}_{random_str}"
    else:
        return f"{timestamp}_{random_str}"


def calculate_md5(data: Union[str, bytes], encoding: str = 'utf-8') -> str:
    """
    计算MD5哈希值
    
    Args:
        data: 输入数据
        encoding: 字符串编码
        
    Returns:
        MD5哈希字符串
    """
    if isinstance(data, str):
        data = data.encode(encoding)
    
    return hashlib.md5(data).hexdigest()


def calculate_sha256(data: Union[str, bytes], encoding: str = 'utf-8') -> str:
    """
    计算SHA256哈希值
    
    Args:
        data: 输入数据
        encoding: 字符串编码
        
    Returns:
        SHA256哈希字符串
    """
    if isinstance(data, str):
        data = data.encode(encoding)
    
    return hashlib.sha256(data).hexdigest()


def format_bytes(size: int) -> str:
    """
    格式化字节大小
    
    Args:
        size: 字节大小
        
    Returns:
        格式化字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    格式化时间间隔
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化字符串
    """
    if seconds < 60:
        return f"{seconds:.2f}秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}分{secs:.1f}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}小时{minutes}分{secs:.1f}秒"


def parse_duration(duration_str: str) -> float:
    """
    解析时间间隔字符串
    
    Args:
        duration_str: 时间间隔字符串 (如: "1h30m", "90s", "2.5h")
        
    Returns:
        秒数
    """
    pattern = r'(\d+(?:\.\d+)?)\s*([dhms])'
    matches = re.findall(pattern, duration_str.lower())
    
    if not matches:
        try:
            return float(duration_str)
        except ValueError:
            raise ValueError(f"无法解析时间间隔: {duration_str}")
    
    total_seconds = 0
    multipliers = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
    
    for value, unit in matches:
        total_seconds += float(value) * multipliers[unit]
    
    return total_seconds


def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """
    将列表分割成块
    
    Args:
        lst: 输入列表
        chunk_size: 块大小
        
    Returns:
        块列表
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_list(nested_list: List[Any]) -> List[Any]:
    """
    展平嵌套列表
    
    Args:
        nested_list: 嵌套列表
        
    Returns:
        展平后的列表
    """
    result = []
    for item in nested_list:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    return result


def dict_merge(dict1: Dict, dict2: Dict, overwrite: bool = True) -> Dict:
    """
    合并两个字典
    
    Args:
        dict1: 第一个字典
        dict2: 第二个字典
        overwrite: 是否覆盖已有键
        
    Returns:
        合并后的字典
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = dict_merge(result[key], value, overwrite)
        else:
            if overwrite or key not in result:
                result[key] = value
    
    return result


def dict_filter(dictionary: Dict[str, Any], keys: List[str], 
                include: bool = True) -> Dict[str, Any]:
    """
    过滤字典键
    
    Args:
        dictionary: 输入字典
        keys: 键列表
        include: True包含这些键，False排除这些键
        
    Returns:
        过滤后的字典
    """
    if include:
        return {k: v for k, v in dictionary.items() if k in keys}
    else:
        return {k: v for k, v in dictionary.items() if k not in keys}


def dict_get_nested(dictionary: Dict[str, Any], key_path: str, 
                    default: Any = None, delimiter: str = '.') -> Any:
    """
    获取嵌套字典中的值
    
    Args:
        dictionary: 输入字典
        key_path: 键路径 (如: "a.b.c")
        default: 默认值
        delimiter: 分隔符
        
    Returns:
        值或默认值
    """
    keys = key_path.split(delimiter)
    current = dictionary
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current


def dict_set_nested(dictionary: Dict[str, Any], key_path: str, 
                    value: Any, delimiter: str = '.') -> Dict[str, Any]:
    """
    设置嵌套字典中的值
    
    Args:
        dictionary: 输入字典
        key_path: 键路径 (如: "a.b.c")
        value: 要设置的值
        delimiter: 分隔符
        
    Returns:
        更新后的字典
    """
    keys = key_path.split(delimiter)
    current = dictionary
    
    for i, key in enumerate(keys[:-1]):
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value
    return dictionary


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    安全的JSON解析
    
    Args:
        json_str: JSON字符串
        default: 解析失败时的默认值
        
    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_eval(expr: str, context: Optional[Dict] = None, 
              default: Any = None) -> Any:
    """
    安全地计算表达式
    
    Args:
        expr: 表达式字符串
        context: 上下文变量
        default: 计算失败时的默认值
        
    Returns:
        计算结果或默认值
    """
    try:
        # 限制可用的内置函数
        safe_builtins = {
            'abs': abs, 'all': all, 'any': any, 'bool': bool,
            'chr': chr, 'divmod': divmod, 'float': float,
            'int': int, 'len': len, 'max': max, 'min': min,
            'ord': ord, 'pow': pow, 'round': round, 'str': str,
            'sum': sum, 'tuple': tuple, 'list': list, 'dict': dict,
            'set': set, 'range': range, 'enumerate': enumerate,
            'zip': zip, 'sorted': sorted, 'reversed': reversed
        }
        
        # 创建安全的locals和globals
        local_context = {'__builtins__': safe_builtins}
        if context:
            local_context.update(context)
        
        return eval(expr, {'__builtins__': {}}, local_context)
    except Exception:
        return default


def clean_text(text: str, remove_html: bool = True, 
               remove_urls: bool = True, remove_emails: bool = True,
               remove_special: bool = True, normalize_whitespace: bool = True) -> str:
    """
    清理文本
    
    Args:
        text: 输入文本
        remove_html: 是否移除HTML标签
        remove_urls: 是否移除URL
        remove_emails: 是否移除邮箱
        remove_special: 是否移除特殊字符
        normalize_whitespace: 是否规范化空白字符
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    result = text
    
    # 移除HTML标签
    if remove_html:
        result = re.sub(r'<[^>]+>', ' ', result)
    
    # 移除URL
    if remove_urls:
        result = re.sub(r'https?://\S+|www\.\S+', ' ', result)
    
    # 移除邮箱
    if remove_emails:
        result = re.sub(r'\S+@\S+', ' ', result)
    
    # 移除特殊字符
    if remove_special:
        result = re.sub(r'[^\w\u4e00-\u9fa5\s.,!?;:()\-\'\"]', ' ', result)
    
    # 规范化空白字符
    if normalize_whitespace:
        result = re.sub(r'\s+', ' ', result).strip()
    
    return result


def truncate_text(text: str, max_length: int = 100, 
                  suffix: str = "...", preserve_words: bool = True) -> str:
    """
    截断文本
    
    Args:
        text: 输入文本
        max_length: 最大长度
        suffix: 后缀
        preserve_words: 是否尽量保持单词完整
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    if preserve_words:
        # 在单词边界处截断
        truncated = text[:max_length]
        if max_length < len(text) and text[max_length] not in [' ', '\t', '\n']:
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.5:  # 不要太靠前
                truncated = truncated[:last_space]
        return truncated + suffix
    else:
        return text[:max_length] + suffix


def extract_keywords(text: str, top_n: int = 10, 
                     language: str = "zh") -> List[str]:
    """
    提取关键词
    
    Args:
        text: 输入文本
        top_n: 提取的关键词数量
        language: 语言
        
    Returns:
        关键词列表
    """
    # 移除停用词（简化的中文停用词列表）
    stopwords_zh = {
        '的', '了', '在', '是', '我', '有', '和', '就',
        '不', '人', '都', '一', '一个', '上', '也', '很',
        '到', '说', '要', '去', '你', '会', '着', '没有',
        '看', '好', '自己', '这', '那', '她', '他', '它'
    }
    
    stopwords_en = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
        'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was',
        'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'shall', 'should',
        'can', 'could', 'may', 'might', 'must', 'i', 'you',
        'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
        'us', 'them', 'my', 'your', 'his', 'her', 'its',
        'our', 'their', 'this', 'that', 'these', 'those'
    }
    
    stopwords = stopwords_zh if language == "zh" else stopwords_en
    
    # 分词（简化的分词逻辑）
    words = re.findall(r'[\u4e00-\u9fa5]+|\w+', text.lower())
    
    # 移除停用词和短词
    words = [word for word in words 
             if word not in stopwords and len(word) > 1]
    
    # 统计词频
    word_counts = defaultdict(int)
    for word in words:
        word_counts[word] += 1
    
    # 按频率排序
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 返回前N个关键词
    return [word for word, count in sorted_words[:top_n]]


def calculate_text_similarity(text1: str, text2: str, 
                             method: str = "jaccard") -> float:
    """
    计算文本相似度
    
    Args:
        text1: 文本1
        text2: 文本2
        method: 计算方法 ("jaccard", "cosine", "levenshtein")
        
    Returns:
        相似度 (0-1)
    """
    if not text1 or not text2:
        return 0.0
    
    if method == "jaccard":
        # Jaccard相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    elif method == "cosine":
        # 简化的余弦相似度
        words1 = text1.lower().split()
        words2 = text2.lower().split()
        
        all_words = set(words1 + words2)
        
        vec1 = [words1.count(word) for word in all_words]
        vec2 = [words2.count(word) for word in all_words]
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        return dot_product / (norm1 * norm2) if norm1 * norm2 > 0 else 0.0
    
    elif method == "levenshtein":
        # Levenshtein距离归一化
        n, m = len(text1), len(text2)
        
        if n > m:
            text1, text2 = text2, text1
            n, m = m, n
        
        current_row = range(n + 1)
        for i in range(1, m + 1):
            previous_row = current_row
            current_row = [i] + [0] * n
            for j in range(1, n + 1):
                add = previous_row[j] + 1
                delete = current_row[j - 1] + 1
                change = previous_row[j - 1]
                if text1[j - 1] != text2[i - 1]:
                    change += 1
                current_row[j] = min(add, delete, change)
        
        distance = current_row[n]
        max_len = max(len(text1), len(text2))
        
        return 1 - (distance / max_len) if max_len > 0 else 1.0
    
    else:
        raise ValueError(f"未知的相似度计算方法: {method}")


def async_to_sync(async_func):
    """将异步函数转换为同步函数"""
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


def sync_to_async(sync_func, executor: Optional[ThreadPoolExecutor] = None):
    """将同步函数转换为异步函数"""
    @wraps(sync_func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            executor, 
            lambda: sync_func(*args, **kwargs)
        )
    return wrapper


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, calls: int, period: float):
        """
        初始化速率限制器
        
        Args:
            calls: 时间段内的调用次数
            period: 时间段(秒)
        """
        self.calls = calls
        self.period = period
        self.timestamps = []
        self.lock = Lock()
    
    def wait(self) -> bool:
        """
        等待直到可以调用
        
        Returns:
            是否成功获取调用权限
        """
        with self.lock:
            now = time.time()
            
            # 移除过期的时间戳
            self.timestamps = [t for t in self.timestamps 
                              if now - t <= self.period]
            
            if len(self.timestamps) < self.calls:
                self.timestamps.append(now)
                return True
            else:
                # 计算需要等待的时间
                oldest = self.timestamps[0]
                wait_time = oldest + self.period - now
                if wait_time > 0:
                    time.sleep(wait_time)
                    self.timestamps.append(time.time())
                    return True
                return False
    
    async def async_wait(self) -> bool:
        """异步等待"""
        with self.lock:
            now = time.time()
            
            # 移除过期的时间戳
            self.timestamps = [t for t in self.timestamps 
                              if now - t <= self.period]
            
            if len(self.timestamps) < self.calls:
                self.timestamps.append(now)
                return True
            else:
                # 计算需要等待的时间
                oldest = self.timestamps[0]
                wait_time = oldest + self.period - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    self.timestamps.append(time.time())
                    return True
                return False


class LRUCache(Generic[T, R]):
    """LRU缓存"""
    
    def __init__(self, max_size: int = 100):
        """
        初始化LRU缓存
        
        Args:
            max_size: 最大缓存大小
        """
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = Lock()
    
    def get(self, key: T) -> Optional[R]:
        """
        获取缓存值
        
        Args:
            key: 键
            
        Returns:
            值，不存在则返回None
        """
        with self.lock:
            if key in self.cache:
                # 移动到最近使用的位置
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
            return None
    
    def set(self, key: T, value: R):
        """
        设置缓存值
        
        Args:
            key: 键
            value: 值
        """
        with self.lock:
            if key in self.cache:
                # 移除旧值
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # 移除最久未使用的项
                self.cache.popitem(last=False)
            
            self.cache[key] = value
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        with self.lock:
            return len(self.cache)
    
    def keys(self) -> List[T]:
        """获取所有键"""
        with self.lock:
            return list(self.cache.keys())


def backup_file(filepath: Union[str, Path], max_backups: int = 5) -> bool:
    """
    备份文件
    
    Args:
        filepath: 文件路径
        max_backups: 最大备份数量
        
    Returns:
        是否成功
    """
    try:
        filepath = Path(filepath)
        
        if not filepath.exists():
            return False
        
        # 创建备份目录
        backup_dir = filepath.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filepath.stem}_{timestamp}{filepath.suffix}"
        backup_path = backup_dir / backup_name
        
        # 复制文件
        shutil.copy2(filepath, backup_path)
        
        # 清理旧的备份
        backup_files = sorted(backup_dir.glob(f"{filepath.stem}_*{filepath.suffix}"))
        if len(backup_files) > max_backups:
            for old_backup in backup_files[:-max_backups]:
                old_backup.unlink()
        
        return True
        
    except Exception as e:
        logging.error(f"备份文件失败: {filepath} - {e}")
        return False


def compress_directory(source_dir: Union[str, Path], 
                       output_path: Union[str, Path],
                       compression: str = 'zip') -> bool:
    """
    压缩目录
    
    Args:
        source_dir: 源目录
        output_path: 输出路径
        compression: 压缩格式 ('zip', 'tar', 'tar.gz')
        
    Returns:
        是否成功
    """
    try:
        source_dir = Path(source_dir)
        output_path = Path(output_path)
        
        if not source_dir.exists():
            return False
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if compression == 'zip':
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in source_dir.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(source_dir)
                        zipf.write(file, arcname)
        
        elif compression in ['tar', 'tar.gz']:
            mode = 'w:gz' if compression == 'tar.gz' else 'w'
            with tarfile.open(output_path, mode) as tar:
                tar.add(source_dir, arcname=source_dir.name)
        
        else:
            raise ValueError(f"不支持的压缩格式: {compression}")
        
        return True
        
    except Exception as e:
        logging.error(f"压缩目录失败: {source_dir} - {e}")
        return False


def extract_archive(archive_path: Union[str, Path], 
                    extract_dir: Union[str, Path]) -> bool:
    """
    解压归档文件
    
    Args:
        archive_path: 归档文件路径
        extract_dir: 解压目录
        
    Returns:
        是否成功
    """
    try:
        archive_path = Path(archive_path)
        extract_dir = Path(extract_dir)
        
        if not archive_path.exists():
            return False
        
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                zipf.extractall(extract_dir)
        
        elif archive_path.suffix in ['.tar', '.gz', '.bz2', '.xz']:
            with tarfile.open(archive_path, 'r:*') as tar:
                tar.extractall(extract_dir)
        
        else:
            raise ValueError(f"不支持的归档格式: {archive_path.suffix}")
        
        return True
        
    except Exception as e:
        logging.error(f"解压归档文件失败: {archive_path} - {e}")
        return False


def find_files(directory: Union[str, Path], 
               pattern: str = "*", 
               recursive: bool = True) -> List[Path]:
    """
    查找文件
    
    Args:
        directory: 目录
        pattern: 文件模式 (支持通配符)
        recursive: 是否递归查找
        
    Returns:
        文件路径列表
    """
    directory = Path(directory)
    
    if not directory.exists():
        return []
    
    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))


def human_readable_time(timestamp: Union[float, int, datetime]) -> str:
    """
    将时间戳转换为人类可读格式
    
    Args:
        timestamp: 时间戳或datetime对象
        
    Returns:
        人类可读的时间字符串
    """
    if isinstance(timestamp, datetime):
        dt = timestamp
    else:
        dt = datetime.fromtimestamp(timestamp)
    
    now = datetime.now()
    diff = now - dt
    
    if diff.days == 0:
        if diff.seconds < 60:
            return "刚刚"
        elif diff.seconds < 3600:
            minutes = diff.seconds // 60
            return f"{minutes}分钟前"
        else:
            hours = diff.seconds // 3600
            return f"{hours}小时前"
    elif diff.days == 1:
        return "昨天"
    elif diff.days < 7:
        return f"{diff.days}天前"
    elif diff.days < 30:
        weeks = diff.days // 7
        return f"{weeks}周前"
    elif diff.days < 365:
        months = diff.days // 30
        return f"{months}个月前"
    else:
        years = diff.days // 365
        return f"{years}年前"


def get_system_info() -> Dict[str, Any]:
    """
    获取系统信息
    
    Returns:
        系统信息字典
    """
    import platform
    import psutil
    
    info = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.architecture(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "hostname": platform.node(),
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available,
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/')._asdict() if hasattr(psutil, 'disk_usage') else {},
        "boot_time": psutil.boot_time(),
        "users": [user._asdict() for user in psutil.users()] if hasattr(psutil, 'users') else [],
        "timestamp": datetime.now().isoformat()
    }
    
    return info


def profile_function(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    分析函数性能
    
    Args:
        func: 要分析的函数
        *args: 函数参数
        **kwargs: 函数关键字参数
        
    Returns:
        性能分析结果
    """
    import cProfile
    import pstats
    import io
    
    pr = cProfile.Profile()
    pr.enable()
    
    try:
        result = func(*args, **kwargs)
    finally:
        pr.disable()
    
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # 打印前20行
    
    profile_output = s.getvalue()
    
    return {
        "result": result,
        "profile_output": profile_output,
        "function_name": func.__name__,
        "called_with": {"args": args, "kwargs": kwargs}
    }


# 导出常用函数
__all__ = [
    "Singleton",
    "Timer",
    "timer_context",
    "retry",
    "validate_environment",
    "create_project_structure",
    "load_config_file",
    "save_config_file",
    "generate_unique_id",
    "calculate_md5",
    "calculate_sha256",
    "format_bytes",
    "format_duration",
    "parse_duration",
    "chunk_list",
    "flatten_list",
    "dict_merge",
    "dict_filter",
    "dict_get_nested",
    "dict_set_nested",
    "safe_json_loads",
    "safe_eval",
    "clean_text",
    "truncate_text",
    "extract_keywords",
    "calculate_text_similarity",
    "async_to_sync",
    "sync_to_async",
    "RateLimiter",
    "LRUCache",
    "backup_file",
    "compress_directory",
    "extract_archive",
    "find_files",
    "human_readable_time",
    "get_system_info",
    "profile_function"
]