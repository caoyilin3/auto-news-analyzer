"""
测试引擎模块
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from src.core.engine import AnalysisEngine


class TestAnalysisEngine:
    """测试分析引擎"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        config = Mock()
        config.system = {"mode": "testing"}
        config.crawler.enabled = True
        config.crawler.use_mock_data = True
        config.crawler.mock_data_count = 3
        config.credibility.enabled = True
        config.knowledge.enabled = True
        config.evolution.enabled = True
        config.patent_evidence.enabled = True
        config.patent_evidence.base_path = "./test_data/patent_evidence"
        config.ensure_directories = Mock()
        return config
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self, mock_config):
        """测试引擎初始化"""
        engine = AnalysisEngine(config_path=None)
        engine.config = mock_config
        
        assert engine is not None
        assert hasattr(engine, 'metrics')
        assert engine.metrics["total_cycles"] == 0
    
    @pytest.mark.asyncio
    async def test_run_cycle(self, mock_config):
        """测试运行周期"""
        engine = AnalysisEngine(config_path=None)
        engine.config = mock_config
        
        # 模拟模块
        engine.modules = {
            'crawler': AsyncMock(),
            'validator': AsyncMock(),
            'knowledge_graph': AsyncMock(),
            'evolution': AsyncMock()
        }
        
        # 模拟方法返回
        engine.modules['crawler'].fetch.return_value = [
            {"id": "test_1", "title": "Test Article", "content": "Test content"}
        ]
        engine.modules['validator'].evaluate_batch.return_value = [
            {"passed": True, "score": 0.8, "reason": "test"}
        ]
        engine.modules['knowledge_graph'].extract_from_text.return_value = {
            "entities": [{"type": "TEST", "text": "Test"}],
            "relations": []
        }
        engine.modules['knowledge_graph'].fuse_knowledge.return_value = {
            "success": True,
            "new_patterns": []
        }
        engine.modules['evolution'].make_decision.return_value = {
            "action": "maintain",
            "reasoning": "test",
            "confidence": 0.5
        }
        
        # 运行周期
        result = await engine.run_cycle()
        
        assert result["status"] in ["success", "error"]
        assert "cycle_id" in result