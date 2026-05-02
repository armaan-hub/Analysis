"""Test that upload triggers auto-summary."""
import pytest
from unittest.mock import patch, AsyncMock
import io


@pytest.mark.asyncio
async def test_upload_triggers_summary(client):
    from core.documents.summarizer import DocSummary
    fake_summary = DocSummary(summary="Brief about test", key_terms=["test", "doc"])

    with patch("core.document_processor.document_processor.is_supported", return_value=True), \
         patch("core.document_processor.document_processor.process", new=AsyncMock(
             return_value=[{"text": "some content"}]
         )), \
         patch("core.rag_engine.rag_engine.ingest_chunks", new=AsyncMock(return_value=1)), \
         patch("api.documents.summarize_document_text", new=AsyncMock(return_value=fake_summary)):

        files = {"file": ("test.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")}
        resp = await client.post("/api/documents/upload", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["summary"] == "Brief about test"
    assert data["document"]["key_terms"] == ["test", "doc"]