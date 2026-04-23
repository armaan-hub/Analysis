"""Tests that notebook sources endpoint returns original_name, not raw doc IDs."""
import pytest
from db.models import Conversation, Document


@pytest.mark.asyncio
async def test_notebook_sources_returns_original_name(client, db_session):
    """GET /notebook/{id}/sources must resolve each doc ID to its original_name."""
    # Create a document with a known original_name
    doc = Document(
        id="test-doc-id-001",
        filename="a1b2c3d4_annual_report.pdf",
        original_name="Annual Report 2024.pdf",
        file_type="pdf",
        file_size=12345,
        status="indexed",
    )
    db_session.add(doc)

    # Create a conversation with checked_source_ids pointing at that doc
    conv = Conversation(
        id="test-conv-id-001",
        title="Test Notebook",
        checked_source_ids=["test-doc-id-001"],
    )
    db_session.add(conv)
    await db_session.flush()

    resp = await client.get("/api/legal-studio/notebook/test-conv-id-001/sources")
    assert resp.status_code == 200

    data = resp.json()
    sources = data.get("sources", [])
    assert sources, "Expected at least one source in response"

    first = sources[0]
    assert first["id"] == "test-doc-id-001"
    assert first["name"] == "Annual Report 2024.pdf", (
        f"Expected original_name, got: {first['name']!r}"
    )
    assert "a1b2c3d4" not in first["name"], "name must not contain UUID-prefixed filename"


@pytest.mark.asyncio
async def test_notebook_sources_falls_back_to_id_when_doc_missing(client, db_session):
    """If a doc ID has no matching Document row, fall back to the ID itself as the name."""
    conv = Conversation(
        id="test-conv-id-002",
        title="Test Notebook 2",
        checked_source_ids=["missing-doc-id"],
    )
    db_session.add(conv)
    await db_session.flush()

    resp = await client.get("/api/legal-studio/notebook/test-conv-id-002/sources")
    assert resp.status_code == 200

    data = resp.json()
    sources = data.get("sources", [])
    assert sources, "Expected at least one source entry even for missing doc"
    assert sources[0]["id"] == "missing-doc-id"
    assert sources[0]["name"] == "missing-doc-id"


@pytest.mark.asyncio
async def test_notebook_sources_404_for_unknown_conversation(client):
    resp = await client.get("/api/legal-studio/notebook/does-not-exist/sources")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_notebook_sources_empty_when_no_sources(client, db_session):
    """Endpoint returns empty sources list when conversation has no checked sources."""
    conv = Conversation(
        id="test-conv-id-003",
        title="Empty Notebook",
        checked_source_ids=None,
    )
    db_session.add(conv)
    await db_session.flush()

    resp = await client.get("/api/legal-studio/notebook/test-conv-id-003/sources")
    assert resp.status_code == 200

    data = resp.json()
    assert data.get("sources", []) == []
    assert data.get("source_ids", []) == []
