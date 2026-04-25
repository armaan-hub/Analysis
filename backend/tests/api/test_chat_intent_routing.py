import pytest
from unittest.mock import patch, AsyncMock
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_classifier(domain=DomainLabel.VAT):
    return ClassifierResult(domain=domain, confidence=0.95, alternatives=[])


@pytest.mark.asyncio
async def test_intent_directive_is_appended(client):
    captured = {}

    async def fake_chat(messages, **kw):
        content = messages[0].get("content", "") if messages else ""
        if "Classify the user" in content:
            from types import SimpleNamespace
            return SimpleNamespace(content='{"output_type":"list","topic":"VAT exempt items"}')
        # Final LLM call — capture messages so we can assert on the system prompt
        captured["messages"] = messages
        return LLMResponse(
            content="The list is: item1, item2",
            tokens_used=10,
            provider="test",
            model="test-model",
        )

    mock_llm = AsyncMock()
    mock_llm.chat = fake_chat

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier())),
        patch("api.chat.get_llm_provider", return_value=mock_llm),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        r = await client.post("/api/chat/send", json={
            "message": "Give me a list of VAT exempt items",
            "mode": "fast",
            "use_rag": False,
            "stream": False,
        })

    assert r.status_code == 200
    msgs = captured.get("messages") or []
    sys_content = next((m["content"] for m in msgs if m["role"] == "system"), "")
    assert "USER INTENT" in sys_content
    assert "list" in sys_content
