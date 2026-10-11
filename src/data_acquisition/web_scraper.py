# src/data_acquisition/web_scraper.py
"""
网页抓取器 - 专门处理网页内容抓取
"""
import asyncio
from typing import Dict, Any, List, Optional
import logging
from bs4 import BeautifulSoup

from .base_crawler import BaseCrawler


class WebScraper(BaseCrawler):
    """网页抓取器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("web_scraper", config)
        
        # 解析配置
        self.extractors = config.get('extractors', {})
        self.content_selectors = config.get('content_selectors', [])
        self.max_content_length = config.get('max_content_length', 10000)
        
        # 缓存已访问页面
        self.visited_pages = set()
        self.max_cache_size = 1000
    
    async def fetch(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取网页数据
        
        Args:
            limit: 最大获取数量
            
        Returns:
            数据列表
        """
        self.logger.info(f"开始网页抓取，目标数量: {limit}")
        
        urls = self.config.get('urls', [])
        if not urls:
            self.logger.warning("未配置抓取URL")
            return []
        
        all_articles = []
        
        for url in urls[:limit]:
            try:
                # 检查是否已访问
                if url in self.visited_pages:
                    self.logger.debug(f"跳过已访问页面: {url}")
                    continue
                
                self.logger.debug(f"抓取网页: {url}")
                article = await self._scrape_webpage(url)
                
                if article:
                    all_articles.append(article)
                    self.visited_pages.add(url)
                    
                    # 限制缓存大小
                    if len(self.visited_pages) > self.max_cache_size:
                        self.visited_pages.pop()
                
                # 如果达到限制，提前返回
                if len(all_articles) >= limit:
                    break
                    
            except Exception as e:
                self.logger.error(f"抓取网页 {url} 失败: {e}")
        
        # 更新统计
        self.stats['total_articles'] += len(all_articles)
        
        self.logger.info(f"网页抓取完成，共获取 {len(all_articles)} 篇文章")
        
        return all_articles
    
    async def _scrape_webpage(self, url: str) -> Optional[Dict[str, Any]]:
        """抓取单个网页"""
        try:
            # 获取HTML内容
            html_content = await self._fetch_url(url)
            if not html_content:
                return None
            
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取元数据
            metadata = self._extract_metadata(soup, url)
            
            # 提取主要内容
            content = self._extract_main_content(soup)
            
            if not content:
                self.logger.warning(f"无法提取页面内容: {url}")
                return None
            
            # 清理内容
            cleaned_content = self._clean_content(content)
            
            # 构建文章对象
            article = {
                'id': f"web_{hash(url) % 1000000:06d}",
                'title': metadata.get('title', 'No Title'),
                'content': cleaned_content[:self.max_content_length],
                'url': url,
                'source': 'web',
                'published_at': metadata.get('published_at', ''),
                'author': metadata.get('author', ''),
                'category': metadata.get('category', ''),
                'language': metadata.get('language', 'en'),
                'word_count': len(cleaned_content.split()),
                'scraped_at': self.stats['start_time'].isoformat()
            }
            
            return article
            
        except Exception as e:
            self.logger.error(f"解析网页 {url} 失败: {e}")
            return None
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """提取页面元数据"""
        metadata = {
            'url': url,
            'title': '',
            'author': '',
            'published_at': '',
            'category': '',
            'language': 'en'
        }
        
        # 提取标题
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.text.strip()
        
        # 提取meta描述
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            metadata['description'] = meta_desc['content']
        
        # 尝试从常见位置提取作者
        author_selectors = [
            'meta[name="author"]',
            '.author', '[class*="author"]',
            '[itemprop="author"]',
            'meta[property="article:author"]'
        ]
        
        for selector in author_selectors:
            try:
                author_elem = soup.select_one(selector)
                if author_elem:
                    if author_elem.name == 'meta':
                        author = author_elem.get('content', '')
                    else:
                        author = author_elem.text.strip()
                    if author:
                        metadata['author'] = author
                        break
            except:
                continue
        
        # 尝试提取发布时间
        time_selectors = [
            'time', '[datetime]',
            'meta[property="article:published_time"]',
            '[itemprop="datePublished"]'
        ]
        
        for selector in time_selectors:
            try:
                time_elem = soup.select_one(selector)
                if time_elem:
                    if time_elem.name == 'meta':
                        published_at = time_elem.get('content', '')
                    elif time_elem.get('datetime'):
                        published_at = time_elem['datetime']
                    else:
                        published_at = time_elem.text.strip()
                    if published_at:
                        metadata['published_at'] = published_at
                        break
            except:
                continue
        
        # 提取分类/标签
        category_selectors = [
            '.category', '.tags', '[rel="tag"]',
            'meta[property="article:section"]'
        ]
        
        for selector in category_selectors:
            try:
                cat_elem = soup.select(selector)
                if cat_elem:
                    categories = [elem.text.strip() for elem in cat_elem[:3]]
                    if categories:
                        metadata['category'] = ', '.join(categories)
                        break
            except:
                continue
        
        return metadata
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """提取主要内容"""
        # 首先尝试使用配置的选择器
        for selector in self.content_selectors:
            try:
                content_elem = soup.select_one(selector)
                if content_elem:
                    return content_elem.get_text(separator='\n', strip=True)
            except:
                continue
        
        # 通用内容提取策略
        # 1. 查找最大的文本块
        paragraphs = soup.find_all('p')
        if paragraphs:
            # 计算每个段落及其上下文的总文本长度
            para_scores = []
            for i, para in enumerate(paragraphs):
                if len(para.text.strip()) < 50:  # 跳过太短的段落
                    continue
                    
                # 计算段落分数：自身长度 + 周围段落长度
                score = len(para.text)
                
                # 检查前两个段落
                for j in range(max(0, i-2), i):
                    if j < len(paragraphs):
                        score += len(paragraphs[j].text) * 0.5
                
                # 检查后两个段落
                for j in range(i+1, min(len(paragraphs), i+3)):
                    score += len(paragraphs[j].text) * 0.5
                
                para_scores.append((score, para))
            
            if para_scores:
                # 选择分数最高的段落
                para_scores.sort(key=lambda x: x[0], reverse=True)
                main_paragraphs = []
                
                # 取前10个最高分的段落
                for score, para in para_scores[:10]:
                    if score > para_scores[0][0] * 0.3:  # 至少是最高分的30%
                        main_paragraphs.append(para.text.strip())
                
                return '\n\n'.join(main_paragraphs)
        
        # 2. 尝试提取article标签内容
        article = soup.find('article')
        if article:
            return article.get_text(separator='\n', strip=True)
        
        # 3. 尝试提取main标签内容
        main = soup.find('main')
        if main:
            return main.get_text(separator='\n', strip=True)
        
        # 4. 最后尝试body标签
        body = soup.find('body')
        if body:
            # 移除脚本和样式
            for script in body.find_all(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()
            return body.get_text(separator='\n', strip=True)
        
        return ''
    
    def _clean_content(self, content: str) -> str:
        """清理内容"""
        import re
        
        # 移除多余空白字符
        content = re.sub(r'\s+', ' ', content)
        
        # 移除重复的换行符
        content = re.sub(r'\n\s*\n+', '\n\n', content)
        
        # 移除常见的广告文本
        ads_patterns = [
            r'sponsored\s+by.*',
            r'advertisement.*',
            r'click\s+here.*',
            r'sign\s+up.*',
            r'subscribe.*',
            r'follow\s+us.*'
        ]
        
        for pattern in ads_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # 移除短行（可能是导航或页脚）
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 30:  # 至少30个字符
                cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
        
        return content.strip()
    
    def get_visited_pages(self) -> List[str]:
        """获取已访问页面列表"""
        return list(self.visited_pages)
    
    async def clear_cache(self):
        """清空缓存"""
        self.visited_pages.clear()
        self.logger.info("网页缓存已清空")