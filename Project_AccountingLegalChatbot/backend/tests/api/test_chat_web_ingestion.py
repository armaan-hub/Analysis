import json
import pytest
from unittest.mock import patch, AsyncMock

async def _fake_chat_stream(*args, **kwargs):
    """Yield a minimal non-empty LLM response so the ingest guard isn't triggered."""
    yield "The VAT rate in UAE is 5%."

@pytest.mark.asyncio
async def test_chat_auto_ingests_web_results(client):
    """
    When a chat request triggers a web search, the results should be 
    automatically ingested into the vector store.
    """
    # Request payload
    payload = {
        "message": "What is the VAT rate in UAE?",
        "mode": "fast",
        "provider": "nvidia",
        "stream": True
    }

    # Fake web results
    fake_web_results = [
        {"title": "VAT Law", "href": "https://fta.gov.ae/vat", "body": "VAT is 5%"}
    ]

    # Mock RAG to return empty results (to trigger web search)
    # Mock search_web in api.chat (where it is used)
    # Mock ingest_text in core.document_processor
    # Mock chat_stream so we get a real (non-empty) response without calling the LLM API
    with patch("core.rag_engine.RAGEngine.search", return_value=[]), \
         patch("api.chat.search_web", AsyncMock(return_value=fake_web_results)), \
         patch("core.document_processor.ingest_text", AsyncMock()) as mock_ingest, \
         patch("api.chat._generate_title", new=AsyncMock()), \
         patch("core.llm_manager.NvidiaProvider.chat_stream", side_effect=_fake_chat_stream):
        
        # Send request (SSE stream)
        resp = await client.post("/api/chat/send", json=payload)
        assert resp.status_code == 200
        
        # Consume stream to ensure processing completes
        async for _ in resp.aiter_lines():
            pass

        # Verify that ingest_text was called for the web result
        assert mock_ingest.called, "ingest_text should be called for web results"
        
        # The text format in api/chat.py is f"{s.get('source')}\n\n{s.get('excerpt')}"
        expected_text = "https://fta.gov.ae/vat\n\nVAT is 5%"
        mock_ingest.assert_called_with(expected_text, source="https://fta.gov.ae/vat", source_type="research", category="law")

@pytest.mark.asyncio
async def test_chat_uses_compute_safe_max_tokens(client):
    """chat.py must call compute_safe_max_tokens() with the correct arguments."""
    from unittest.mock import patch, AsyncMock

    async def _fake_stream(*args, **kwargs):
        yield "Budget test response"

    call_args_captured = {}

    def _spy_compute(self, messages, requested_max=None):
        call_args_captured["messages"] = messages
        call_args_captured["requested_max"] = requested_max
        call_args_captured["call_count"] = call_args_captured.get("call_count", 0) + 1
        return 1024

    with patch("core.rag_engine.RAGEngine.search", return_value=[]), \
         patch("api.chat._generate_title", new=AsyncMock()), \
         patch("core.llm_manager.BaseLLMProvider.compute_safe_max_tokens", _spy_compute), \
         patch("core.llm_manager.NvidiaProvider.chat_stream", _fake_stream):
        response = await client.post(
            "/api/chat/send",
            json={
                "message": "test adaptive budget",
                "mode": "fast",
                "provider": "nvidia",
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert call_args_captured.get("call_count", 0) == 1, \
        f"compute_safe_max_tokens should be called exactly once, got {call_args_captured.get('call_count', 0)}"
    assert isinstance(call_args_captured.get("messages"), list), \
        "messages argument must be a list"
    assert len(call_args_captured.get("messages", [])) > 0, \
        "messages argument must not be empty"
    from config import settings
    assert call_args_captured.get("requested_max") == settings.fast_max_tokens, \
        f"fast mode must pass fast_max_tokens ({settings.fast_max_tokens}), got {call_args_captured.get('requested_max')}"
