"""Test that Document model has summary/key_terms/source columns."""
import pytest
from db.models import Document


@pytest.mark.asyncio
async def test_document_has_new_columns(db_session):
    doc = Document(
        filename="test.pdf",
        original_name="test.pdf",
        file_type="pdf",
        summary="A test summary",
        key_terms=["term1", "term2"],
        source="upload",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    assert doc.summary == "A test summary"
    assert doc.key_terms == ["term1", "term2"]
    assert doc.source == "upload"
