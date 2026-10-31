"""LLM 客户端失败可见性测试（防止"显示已启用但静默降级"）"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.knowledge.manager import KnowledgeManager
from src.utils import llm_client as llm_module


class _FakeResponse:
    status_code = 401
    text = '{"error":{"message":"Authentication Fails"}}'

    def json(self):
        return {}


def test_llm_client_records_last_error(monkeypatch):
    monkeypatch.setattr(llm_module.requests, "post", lambda *a, **k: _FakeResponse())
    client = llm_module.LLMClient({"api_key": "sk-test", "enabled": True})

    assert client.chat("hi") == ""
    assert client.stats["failures"] == 1
    assert "401" in client.last_error
    assert client.get_status()["last_error"] == client.last_error


class _FakeLLM:
    enabled = True
    model = "fake"
    last_error = "HTTP 401: invalid key"
    stats = {"calls": 3, "failures": 1, "triples_extracted": 1}

    def extract_triples(self, text):
        return [{"subject": "A", "predicate": "属于", "object": "B"}]

    def get_status(self):
        return {"enabled": True, "model": "fake", "stats": self.stats}


def test_knowledge_manager_exposes_llm_failures():
    manager = KnowledgeManager({"llm": {"api_key": "dummy"}})
    manager.llm_client = _FakeLLM()
    result = asyncio.run(manager.extract_knowledge(
        {"articles": [{"id": "a1", "title": "t", "content": "A 属于 B。"}]}
    ))
    assert result["llm_calls"] == 3
    assert result["llm_failures"] == 1
    assert "401" in result["llm_last_error"]
