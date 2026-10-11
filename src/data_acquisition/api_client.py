# src/data_acquisition/api_client.py
"""
API客户端 - 通过API获取数据
"""
import asyncio
from typing import Dict, Any, List, Optional
import logging
import aiohttp

from .base_crawler import BaseCrawler


class APIClient(BaseCrawler):
    """API客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("api_client", config)
        
        # API配置
        self.api_key = config.get('api_key', '')
        self.endpoints = config.get('endpoints', {})
        self.default_params = config.get('default_params', {})
        
        # 缓存API响应
        self.response_cache = {}
        self.cache_ttl = config.get('cache_ttl', 3600)  # 1小时
    
    async def fetch(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        通过API获取数据
        
        Args:
            limit: 最大获取数量
            
        Returns:
            数据列表
        """
        self.logger.info(f"开始API数据获取，目标数量: {limit}")
        
        # 获取配置的API端点
        endpoints = self._get_active_endpoints()
        if not endpoints:
            self.logger.warning("未配置API端点")
            return []
        
        all_articles = []
        
        for endpoint_name, endpoint_config in endpoints.items():
            try:
                self.logger.debug(f"调用API端点: {endpoint_name}")
                
                articles = await self._call_api_endpoint(
                    endpoint_name, endpoint_config, limit
                )
                
                if articles:
                    all_articles.extend(articles)
                    self.logger.debug(f"从 {endpoint_name} 获取了 {len(articles)} 篇文章")
                    
                    # 如果达到限制，提前返回
                    if len(all_articles) >= limit:
                        all_articles = all_articles[:limit]
                        break
                        
            except Exception as e:
                self.logger.error(f"API调用 {endpoint_name} 失败: {e}")
        
        # 更新统计
        self.stats['total_articles'] += len(all_articles)
        
        self.logger.info(f"API数据获取完成，共获取 {len(all_articles)} 篇文章")
        
        return all_articles
    
    def _get_active_endpoints(self) -> Dict[str, Dict]:
        """获取活跃的API端点"""
        active_endpoints = {}
        
        for name, config in self.endpoints.items():
            if config.get('enabled', True):
                active_endpoints[name] = config
        
        return active_endpoints
    
    async def _call_api_endpoint(self, endpoint_name: str, 
                                endpoint_config: Dict[str, Any],
                                limit: int) -> List[Dict[str, Any]]:
        """调用API端点"""
        url = endpoint_config.get('url', '')
        method = endpoint_config.get('method', 'GET').upper()
        params = {**self.default_params, **endpoint_config.get('params', {})}
        headers = endpoint_config.get('headers', {})
        
        # 添加API密钥
        if self.api_key and 'api_key' not in params:
            if 'auth_type' in endpoint_config:
                auth_type = endpoint_config['auth_type']
                if auth_type == 'query':
                    params['api_key'] = self.api_key
                elif auth_type == 'header':
                    headers['Authorization'] = f"Bearer {self.api_key}"
                elif auth_type == 'x-api-key':
                    headers['X-API-Key'] = self.api_key
        
        # 检查缓存
        cache_key = self._generate_cache_key(endpoint_name, params)
        if cache_key in self.response_cache:
            cached_data = self.response_cache[cache_key]
            if self._is_cache_valid(cached_data):
                self.logger.debug(f"使用缓存数据: {endpoint_name}")
                return self._parse_api_response(cached_data['data'], endpoint_config)
        
        try:
            # 准备请求数据
            request_data = None
            if method in ['POST', 'PUT', 'PATCH']:
                request_data = endpoint_config.get('data', {})
            
            # 发送请求
            response = await self._fetch_url(
                url, method=method, params=params, data=request_data
            )
            
            if not response:
                return []
            
            # 缓存响应
            self.response_cache[cache_key] = {
                'data': response,
                'timestamp': asyncio.get_event_loop().time(),
                'endpoint': endpoint_name
            }
            
            # 限制缓存大小
            if len(self.response_cache) > 100:
                # 移除最旧的缓存项
                oldest_key = min(self.response_cache.keys(), 
                               key=lambda k: self.response_cache[k]['timestamp'])
                del self.response_cache[oldest_key]
            
            # 解析响应
            articles = self._parse_api_response(response, endpoint_config)
            
            # 限制返回数量
            if limit > 0:
                articles = articles[:limit]
            
            return articles
            
        except Exception as e:
            self.logger.error(f"API调用失败 {endpoint_name}: {e}")
            return []
    
    def _generate_cache_key(self, endpoint_name: str, params: Dict) -> str:
        """生成缓存键"""
        import hashlib
        import json
        
        params_str = json.dumps(params, sort_keys=True)
        key_str = f"{endpoint_name}:{params_str}"
        return hashlib.md5(key_str.encode()).hexdigest()[:12]
    
    def _is_cache_valid(self, cached_data: Dict) -> bool:
        """检查缓存是否有效"""
        current_time = asyncio.get_event_loop().time()
        cache_age = current_time - cached_data['timestamp']
        return cache_age < self.cache_ttl
    
    def _parse_api_response(self, response: str, 
                           endpoint_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析API响应"""
        parser_type = endpoint_config.get('parser', 'json')
        
        try:
            if parser_type == 'json':
                return self._parse_json_response(response, endpoint_config)
            elif parser_type == 'xml':
                return self._parse_xml_response(response, endpoint_config)
            elif parser_type == 'rss':
                return self._parse_rss_response(response, endpoint_config)
            else:
                self.logger.warning(f"未知的解析器类型: {parser_type}")
                return []
                
        except Exception as e:
            self.logger.error(f"解析API响应失败: {e}")
            return []
    
    def _parse_json_response(self, response: str, 
                            endpoint_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析JSON响应"""
        import json
        
        data = json.loads(response)
        articles = []
        
        # 获取数据路径
        data_path = endpoint_config.get('data_path', '')
        if data_path:
            # 支持嵌套路径，如 'results.articles'
            parts = data_path.split('.')
            current = data
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif isinstance(current, list) and part.isdigit():
                    current = current[int(part)]
                else:
                    self.logger.warning(f"数据路径 {data_path} 无效")
                    return []
            items = current if isinstance(current, list) else [current]
        else:
            items = data if isinstance(data, list) else [data]
        
        # 映射字段
        field_mapping = endpoint_config.get('field_mapping', {
            'title': 'title',
            'content': 'content',
            'url': 'url',
            'published_at': 'published_at',
            'author': 'author'
        })
        
        for item in items:
            try:
                article = {}
                
                for field, source_field in field_mapping.items():
                    if isinstance(source_field, str):
                        # 直接映射
                        if source_field in item:
                            article[field] = item[source_field]
                    elif callable(source_field):
                        # 使用函数计算
                        article[field] = source_field(item)
                
                # 确保必要字段存在
                if 'title' not in article or not article['title']:
                    article['title'] = f"API Article {len(articles)+1}"
                
                if 'content' not in article or not article['content']:
                    article['content'] = article.get('description', '') or article.get('summary', '')
                
                if 'url' not in article or not article['url']:
                    article['url'] = endpoint_config.get('url', '')
                
                if 'published_at' not in article or not article['published_at']:
                    article['published_at'] = self.stats['start_time'].isoformat()
                
                if 'author' not in article or not article['author']:
                    article['author'] = 'Unknown'
                
                # 添加源信息
                article['source'] = endpoint_config.get('name', 'api')
                article['api_endpoint'] = endpoint_config.get('url', '')
                article['retrieved_at'] = self.stats['start_time'].isoformat()
                
                articles.append(article)
                
            except Exception as e:
                self.logger.error(f"解析API项失败: {e}")
                continue
        
        return articles
    
    def _parse_xml_response(self, response: str, 
                           endpoint_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析XML响应"""
        # 简化的XML解析
        import re
        
        articles = []
        
        # 假设XML中有<item>或<entry>元素
        item_pattern = r'<(?:item|entry)>(.*?)</(?:item|entry)>'
        items = re.findall(item_pattern, response, re.DOTALL)
        
        for item_content in items:
            try:
                # 提取标题
                title_match = re.search(r'<title[^>]*>(.*?)</title>', item_content)
                title = title_match.group(1) if title_match else f"XML Item {len(articles)+1}"
                
                # 提取内容
                content_match = re.search(r'<(?:content|description|summary)[^>]*>(.*?)</(?:content|description|summary)>', item_content)
                content = content_match.group(1) if content_match else ''
                
                # 提取链接
                link_match = re.search(r'<link[^>]*>(.*?)</link>', item_content)
                if not link_match:
                    link_match = re.search(r'<link[^>]+href="([^"]+)"', item_content)
                url = link_match.group(1) if link_match else ''
                
                # 提取发布时间
                date_match = re.search(r'<(?:pubDate|published|date)[^>]*>(.*?)</(?:pubDate|published|date)>', item_content)
                published_at = date_match.group(1) if date_match else self.stats['start_time'].isoformat()
                
                # 提取作者
                author_match = re.search(r'<author[^>]*>(.*?)</author>', item_content)
                author = author_match.group(1) if author_match else 'Unknown'
                
                article = {
                    'title': title,
                    'content': content,
                    'url': url,
                    'published_at': published_at,
                    'author': author,
                    'source': 'xml_api',
                    'api_endpoint': endpoint_config.get('url', ''),
                    'retrieved_at': self.stats['start_time'].isoformat()
                }
                
                articles.append(article)
                
            except Exception as e:
                self.logger.error(f"解析XML项失败: {e}")
                continue
        
        return articles
    
    def _parse_rss_response(self, response: str, 
                           endpoint_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析RSS响应"""
        # RSS是特殊的XML格式
        return self._parse_xml_response(response, endpoint_config)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            'cache_size': len(self.response_cache),
            'cache_ttl': self.cache_ttl,
            'endpoints_configured': len(self.endpoints),
            'endpoints_active': len(self._get_active_endpoints())
        }
    
    async def clear_cache(self):
        """清空缓存"""
        self.response_cache.clear()
        self.logger.info("API缓存已清空")