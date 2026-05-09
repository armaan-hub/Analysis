import pytest
import json
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_llm_manager_translate_returns_string():
    from core.llm_manager import LLMManager
    mgr = LLMManager.__new__(LLMManager)
    mgr._provider = MagicMock()
    async def _chat(messages, temperature=0.1, max_tokens=None, **kw):
        from core.llm_manager import LLMResponse
        return LLMResponse(content="The Arabic text here", model="test-model", usage={})
    mgr._provider.chat = _chat
    result = await mgr.translate("النص العربي هنا", src="ar", tgt="en")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_llm_manager_translate_uses_legal_system_prompt():
    from core.llm_manager import LLMManager
    mgr = LLMManager.__new__(LLMManager)
    captured = []
    async def _capture_chat(messages, **kw):
        captured.extend(messages)
        from core.llm_manager import LLMResponse
        return LLMResponse(content="translated", model="m", usage={})
    mgr._provider = MagicMock()
    mgr._provider.chat = _capture_chat
    await mgr.translate("نص", src="ar", tgt="en")
    system_msg = next((m for m in captured if m.get("role") == "system"), None)
    assert system_msg is not None
    assert "legal" in system_msg["content"].lower()
