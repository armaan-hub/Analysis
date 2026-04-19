"""Test that Document model has summary/key_terms/source columns."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from db.database import engine, Base
from db.models import Document


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_document_has_new_columns():
    from db.database import async_session
    async with async_session() as session:
        doc = Document(
            filename="test.pdf",
            original_name="test.pdf",
            file_type="pdf",
            summary="A test summary",
            key_terms=["term1", "term2"],
            source="upload",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        assert doc.summary == "A test summary"
        assert doc.key_terms == ["term1", "term2"]
        assert doc.source == "upload"
