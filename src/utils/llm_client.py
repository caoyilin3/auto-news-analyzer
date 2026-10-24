# src/utils/llm_client.py
"""
DeepSeek / OpenAI 兼容大模型客户端（可选增强模块）

用于在规则提取之外，借助大模型从新闻文本中抽取 (主体, 关系, 客体) 三元组。
未配置 api_key 或调用失败时自动降级，不影响系统运行。
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

import requests


class LLMClient:
    """OpenAI 兼容聊天客户端（默认指向 DeepSeek）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.logger = logging.getLogger(__name__)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.deepseek.com/v1/chat/completions")
        self.model = config.get("model", "deepseek-v4-flash")
        self.timeout = int(config.get("timeout", 60))
        self.enabled = bool(self.api_key) and bool(config.get("enabled", True))
        self.stats = {"calls": 0, "failures": 0, "triples_extracted": 0}

    def chat(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """同步调用聊天接口，失败返回空字符串"""
        if not self.enabled:
            return ""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                },
                timeout=self.timeout,
            )
            self.stats["calls"] += 1
            if resp.status_code != 200:
                self.stats["failures"] += 1
                self.logger.warning(f"LLM 调用失败 HTTP {resp.status_code}: {resp.text[:200]}")
                return ""
            data = resp.json()
            return data["choices"][0]["message"].get("content", "") or ""
        except Exception as e:
            self.stats["failures"] += 1
            self.logger.warning(f"LLM 调用异常: {e}")
            return ""

    def extract_triples(self, text: str) -> List[Dict[str, str]]:
        """
        从新闻文本抽取三元组
        返回 [{"subject":..., "predicate":..., "object":...}, ...]
        """
        if not text or not self.enabled:
            return []

        system = (
            "你是一个金融/科技新闻知识抽取助手。从给定新闻正文中抽取事实三元组，"
            "只输出 JSON 数组，不要任何解释。每个元素形如 "
            '{"subject": "实体", "predicate": "关系动词", "object": "实体/数字"}。'
            "只抽取正文中明确陈述的事实，关系用简短中文动词。"
        )
        prompt = f"新闻正文：\n{text[:3000]}\n\n请输出三元组 JSON 数组："

        content = self.chat(prompt, system=system, max_tokens=1500)
        if not content:
            return []

        triples = self._parse_triples(content)
        self.stats["triples_extracted"] += len(triples)
        return triples

    @staticmethod
    def _parse_triples(content: str) -> List[Dict[str, str]]:
        """从模型输出中鲁棒解析三元组 JSON"""
        # 提取第一个 JSON 数组
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group(0))
        except Exception:
            return []

        result = []
        for it in items:
            if not isinstance(it, dict):
                continue
            s = str(it.get("subject", "")).strip()
            p = str(it.get("predicate", "")).strip()
            o = str(it.get("object", "")).strip()
            if s and p and o:
                result.append({"subject": s, "predicate": p, "object": o})
        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "module": "llm_client",
            "enabled": self.enabled,
            "model": self.model,
            "stats": self.stats,
        }
