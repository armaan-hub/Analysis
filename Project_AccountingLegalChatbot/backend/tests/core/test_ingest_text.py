import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_ingest_text_calls_ingest_chunks():
    """ingest_text should create a DocumentChunk and store it via rag_engine.ingest_chunks."""
    from core.document_processor import ingest_text

    with patch("core.rag_engine.rag_engine.ingest_chunks", new_callable=AsyncMock) as mock_ingest:
        await ingest_text("Some research content", source="https://example.com", source_type="research")
        mock_ingest.assert_called_once()
        chunks = mock_ingest.call_args[0][0]
        assert len(chunks) == 1
        assert "Some research content" in chunks[0].text
        assert chunks[0].metadata["source"] == "https://example.com"
        assert chunks[0].metadata["source_type"] == "research"


@pytest.mark.asyncio
async def test_ingest_text_uses_text_hash_when_no_source():
    """ingest_text should derive doc_id from text when source is None."""
    from core.document_processor import ingest_text

    with patch("core.rag_engine.rag_engine.ingest_chunks", new_callable=AsyncMock) as mock_ingest:
        await ingest_text("No source text here")
        mock_ingest.assert_called_once()
        doc_id = mock_ingest.call_args.kwargs["doc_id"]
        assert doc_id.startswith("research_")


@pytest.mark.asyncio
async def test_ingest_text_truncates_long_text():
    """ingest_text should truncate text to 8000 chars before storing."""
    from core.document_processor import ingest_text

    long_text = "x" * 10_000

    with patch("core.rag_engine.rag_engine.ingest_chunks", new_callable=AsyncMock) as mock_ingest:
        await ingest_text(long_text, source="http://example.com")
        chunks = mock_ingest.call_args[0][0]
        assert len(chunks[0].text) <= 8000

