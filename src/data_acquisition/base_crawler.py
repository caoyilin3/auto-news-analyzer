# src/data_acquisition/base_crawler.py
"""
爬虫基类 - 定义所有爬虫的通用接口和功能
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import urlparse
import aiohttp
import backoff


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"crawler.{name}")
        
        # HTTP客户端配置
        self.timeout = config.get('timeout', 30)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.user_agent = config.get('user_agent', 'AutoNewsAnalyzer/2.0')
        
        # 速率限制
        self.rate_limit_per_source = config.get('rate_limit_per_source', 1.0)
        self.request_times = {}
        
        # 会话管理
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_articles': 0,
            'start_time': datetime.now()
        }
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def initialize(self):
        """初始化爬虫"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(limit=10)
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': self.user_agent}
            )
        
        self.logger.info(f"爬虫 {self.name} 初始化完成")
        return self
    
    @abstractmethod
    async def fetch(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取数据
        
        Args:
            limit: 最大获取数量
            
        Returns:
            数据列表
        """
        pass
    
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3
    )
    async def _fetch_url(self, url: str, method: str = 'GET', 
                        params: Optional[Dict] = None, 
                        data: Optional[Dict] = None) -> Optional[str]:
        """
        获取URL内容
        
        Args:
            url: 目标URL
            method: HTTP方法
            params: 查询参数
            data: 请求数据
            
        Returns:
            响应文本，失败返回None
        """
        if not self.session:
            raise RuntimeError("爬虫未初始化")
        
        # 遵守robots.txt
        if self.config.get('respect_robots_txt', True):
            if not await self._check_robots_allowed(url):
                self.logger.warning(f"被robots.txt禁止访问: {url}")
                return None
        
        # 速率限制
        domain = urlparse(url).netloc
        await self._rate_limit(domain)
        
        try:
            async with self.session.request(method, url, params=params, 
                                          data=data) as response:
                self.stats['total_requests'] += 1
                
                if response.status == 200:
                    self.stats['successful_requests'] += 1
                    text = await response.text()
                    self.logger.debug(f"成功获取 {url}, 长度: {len(text)}")
                    return text
                else:
                    self.stats['failed_requests'] += 1
                    self.logger.warning(f"请求失败 {url}: {response.status}")
                    return None
                    
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.stats['failed_requests'] += 1
            self.logger.error(f"请求异常 {url}: {e}")
            raise
    
    async def _check_robots_allowed(self, url: str) -> bool:
        """检查robots.txt是否允许访问"""
        # 简化的robots.txt检查
        # 生产环境应使用专门的robots.txt解析器
        domain = urlparse(url).netloc
        robots_url = f"https://{domain}/robots.txt"
        
        try:
            async with self.session.get(robots_url) as response:
                if response.status == 200:
                    robots_content = await response.text()
                    # 简单检查 - 实际应使用robots.txt解析库
                    if "Disallow: /" in robots_content:
                        return False
        except:
            # 如果无法获取robots.txt，默认允许访问
            pass
        
        return True
    
    async def _rate_limit(self, domain: str):
        """速率限制"""
        current_time = datetime.now()
        
        if domain in self.request_times:
            last_request = self.request_times[domain]
            time_since = (current_time - last_request).total_seconds()
            
            if time_since < 1.0 / self.rate_limit_per_source:
                wait_time = (1.0 / self.rate_limit_per_source) - time_since
                self.logger.debug(f"速率限制，等待 {wait_time:.2f}秒")
                await asyncio.sleep(wait_time)
        
        self.request_times[domain] = current_time
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = datetime.now() - self.stats['start_time']
        
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'success_rate': (
                self.stats['successful_requests'] / max(1, self.stats['total_requests']) * 100
            ),
            'name': self.name,
            'config': {
                'timeout': self.timeout,
                'retry_attempts': self.retry_attempts,
                'rate_limit': self.rate_limit_per_source
            }
        }
    
    async def close(self):
        """关闭爬虫"""
        if self.session:
            await self.session.close()
            self.session = None
        
        self.logger.info(f"爬虫 {self.name} 已关闭")