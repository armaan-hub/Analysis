"""Tests for POST /api/documents/scan-and-ingest and POST /api/documents/reindex-all."""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── scan-and-ingest tests ─────────────────────────────────────────────────────

async def test_scan_and_ingest_returns_200(client):
    """POST /api/documents/scan-and-ingest returns 200 with summary."""
    with patch("api.documents.scan_and_ingest_all", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = {"ingested": 5, "skipped": 2, "errors": 0, "error_details": []}
        resp = await client.post("/api/documents/scan-and-ingest")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "ingested" in data
    assert "skipped" in data


async def test_scan_and_ingest_skips_existing(db_session):
    """scan_and_ingest_all() skips docs already in the DB."""
    from api.documents import scan_and_ingest_all
    from db.models import Document as DBDocument

    law_dir = (
        "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com"
        "/My Drive/Study/Armaan/AI Class/Data Science Class"
        "/35. 11-Apr-2026 Agentic AI/data_source_law"
    )
    if not os.path.isdir(law_dir):
        pytest.skip("data_source_law not accessible")

    first_pdf = next(
        (f for f in sorted(os.listdir(law_dir)) if f.lower().endswith(".pdf")),
        None,
    )
    if not first_pdf:
        pytest.skip("No PDF found in data_source_law")

    doc = DBDocument(
        id="existing-doc-01",
        filename=first_pdf,
        original_name=first_pdf,
        file_type="pdf",
        file_size=0,
    )
    db_session.add(doc)
    await db_session.commit()

    # Mock document_processor.process to return [] so non-existing files don't
    # try to open disk files (keeps the test fast and hermetic).
    with patch("api.documents.document_processor.process", new_callable=AsyncMock) as mock_proc, \
         patch("api.documents.rag_engine.ingest_chunks", new_callable=AsyncMock) as mock_ingest:
        mock_proc.return_value = []
        mock_ingest.return_value = 0
        result = await scan_and_ingest_all(db=db_session, skip_existing=True)

    assert result["skipped"] >= 1, f"Expected skipped>=1, got {result}"


async def test_reindex_all_returns_200(client):
    """POST /api/documents/reindex-all returns 200 with chunk count."""
    with patch("api.documents.reindex_all_from_db", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = {"reindexed_chunks": 100, "documents": 10}
        resp = await client.post("/api/documents/reindex-all")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "reindexed_chunks" in data


async def test_reindex_reads_from_document_chunks(db_session):
    """reindex_all_from_db() reads from document_chunks table, not disk."""
    from api.documents import reindex_all_from_db
    from db.models import Document as DBDocument, DocumentChunk as DBDocumentChunk

    doc = DBDocument(
        id="r-doc-01",
        filename="test.pdf",
        original_name="test.pdf",
        file_type="pdf",
        file_size=0,
    )
    db_session.add(doc)
    await db_session.flush()

    for i in range(2):
        db_session.add(DBDocumentChunk(
            id=f"r-chunk-0{i}",
            doc_id="r-doc-01",
            chunk_index=i,
            text=f"Chunk text {i}",
            metadata_json={"category": "law"},
        ))
    await db_session.commit()

    with patch("api.documents.rag_engine.ingest_chunks", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = 2
        result = await reindex_all_from_db(db=db_session)

    assert result["reindexed_chunks"] >= 2
    mock_ingest.assert_called()
