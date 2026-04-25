import json
import pytest
from unittest.mock import patch, AsyncMock

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
    with patch("core.rag_engine.RAGEngine.search", return_value=[]), \
         patch("api.chat.search_web", AsyncMock(return_value=fake_web_results)), \
         patch("core.document_processor.ingest_text", AsyncMock()) as mock_ingest, \
         patch("api.chat._generate_title", new=AsyncMock()):
        
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
        mock_ingest.assert_called_with(expected_text, source="https://fta.gov.ae/vat", source_type="research")
