"""Tests verifying chat.py reads LLM params from compute_llm_params()."""
import pytest
from unittest.mock import patch, MagicMock


class TestLlmParamsWiring:
    """Verify chat endpoints use compute_llm_params for LLM configuration."""

    async def test_fast_mode_uses_compute_params(self, client):
        """fast mode must use compute_llm_params, not hardcoded values."""
        with patch("api.chat.compute_llm_params") as mock_params:
            mock_params.return_value = {
                "max_tokens": 1234, "temperature": 0.99,
                "timeout": 5.0, "top_k": 99
            }
            # Just verify compute_llm_params was called — actual chat call may fail LLM
            resp = await client.post("/api/chat/send", json={
                "message": "hello",
                "mode": "fast",
                "stream": True,
            })
            # compute_llm_params should have been called with mode="fast"
            assert mock_params.called
            calls = [str(c) for c in mock_params.call_args_list]
            assert any("fast" in c for c in calls)

    async def test_deep_research_mode_uses_compute_params(self, client):
        """deep_research mode must call compute_llm_params with mode='deep_research'."""
        with patch("api.chat.compute_llm_params") as mock_params:
            mock_params.return_value = {
                "max_tokens": 32768, "temperature": 0.4,
                "timeout": 300.0, "top_k": 20
            }
            resp = await client.post("/api/chat/send", json={
                "message": "complex legal analysis",
                "mode": "deep_research",
                "stream": True,
            })
            assert mock_params.called
            calls = [str(c) for c in mock_params.call_args_list]
            assert any("deep_research" in c for c in calls)

    async def test_no_hardcoded_fast_temperature_ternary(self):
        """Verify no hardcoded ternary chains exist in chat.py source."""
        import inspect, api.chat as chat_module
        source = inspect.getsource(chat_module)
        # Old pattern: settings.fast_temperature if req.mode == "fast" else
        assert "fast_temperature if" not in source
        assert "fast_max_tokens if" not in source
        assert "fast_top_k if" not in source
        assert "fast_top_k" not in source  # catches non-ternary usages too

    async def test_no_hardcoded_deep_temperature_ternary(self):
        """Verify deep_temperature ternary is gone."""
        import inspect, api.chat as chat_module
        source = inspect.getsource(chat_module)
        assert "deep_temperature if" not in source
