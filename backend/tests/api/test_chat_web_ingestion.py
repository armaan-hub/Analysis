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
    """chat.py must call compute_safe_max_tokens() — not raw settings.max_tokens."""
    from unittest.mock import patch

    async def _fake_stream(*args, **kwargs):
        yield "Budget test response"

    call_count = {"n": 0}

    def _spy_compute(self, messages, requested_max=None):
        call_count["n"] += 1
        return 1024

    with patch(
        "core.llm_manager.BaseLLMProvider.compute_safe_max_tokens",
        _spy_compute,
    ), patch(
        "core.llm_manager.NvidiaProvider.chat_stream",
        _fake_stream,
    ):
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
    assert call_count["n"] >= 1, "compute_safe_max_tokens was not called"
