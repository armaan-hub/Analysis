"""Test that completed research saves a document record."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from db.database import engine, Base, async_session
from db.models import Document


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_save_as_document():
    from core.research.orchestrator import _save_as_document
    await _save_as_document("test-job-123", "UAE VAT overview", "This is a long research report about VAT.")

    async with async_session() as session:
        result = await session.execute(select(Document).where(Document.source == "research"))
        doc = result.scalar_one()

    assert doc.source == "research"
    assert "research_test-job" in doc.filename
    assert doc.file_type == "md"
    assert doc.status == "indexed"
    assert "UAE VAT overview" in doc.original_name or "UAE_VAT" in doc.original_name
