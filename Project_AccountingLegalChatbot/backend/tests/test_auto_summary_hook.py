"""Test that upload triggers auto-summary."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from db.database import engine, Base
import io


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_upload_triggers_summary():
    from core.documents.summarizer import DocSummary
    fake_summary = DocSummary(summary="Brief about test", key_terms=["test", "doc"])

    with patch("core.document_processor.document_processor.is_supported", return_value=True), \
         patch("core.document_processor.document_processor.process", new=AsyncMock(
             return_value=[{"text": "some content"}]
         )), \
         patch("core.rag_engine.rag_engine.ingest_chunks", new=AsyncMock(return_value=1)), \
         patch("api.documents.summarize_document_text", new=AsyncMock(return_value=fake_summary)):

        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            files = {"file": ("test.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")}
            resp = await client.post("/api/documents/upload", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert data["document"]["summary"] == "Brief about test"
        assert data["document"]["key_terms"] == ["test", "doc"]
