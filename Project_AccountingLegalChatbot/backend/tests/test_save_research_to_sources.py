"""Test that completed research saves a document record."""
import pytest
from contextlib import asynccontextmanager
from unittest.mock import patch
from sqlalchemy import select
from db.models import Document


@pytest.mark.asyncio
async def test_save_as_document(db_session):
    from core.research.orchestrator import _save_as_document

    @asynccontextmanager
    async def _mock_session():
        yield db_session

    with patch("core.research.orchestrator.async_session", _mock_session):
        await _save_as_document("test-job-123", "UAE VAT overview", "This is a long research report about VAT.")

    result = await db_session.execute(select(Document).where(Document.source == "research"))
    doc = result.scalar_one()

    assert doc.source == "research"
    assert "research_test-job" in doc.filename
    assert doc.file_type == "md"
    assert doc.status == "indexed"
    assert "UAE VAT overview" in doc.original_name or "UAE_VAT" in doc.original_name
