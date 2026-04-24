"""
Document endpoint tests — upload/list/delete flow.
"""
import io
import uuid
import pytest


@pytest.mark.asyncio
async def test_upload_txt_document(client):
    content = b"Random content " + str(uuid.uuid4()).encode() + b" about UAE VAT regulations."
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("test_vat.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    # API returns {"document": {...}, "message": "..."}
    doc = data["document"]
    assert doc["original_name"] == "test_vat.txt"
    assert doc["status"] == "indexed"


@pytest.mark.asyncio
async def test_list_documents_after_upload(client):
    content = b"Corporate tax test document for UAE 9% rate."
    await client.post(
        "/api/documents/upload",
        files={"file": ("corp_tax.txt", io.BytesIO(content), "text/plain")},
    )
    resp = await client.get("/api/documents/")
    assert resp.status_code == 200
    docs = resp.json()
    assert any(d["original_name"] == "corp_tax.txt" for d in docs)


@pytest.mark.asyncio
async def test_delete_document(client):
    content = b"Temporary document to be deleted."
    upload = await client.post(
        "/api/documents/upload",
        files={"file": ("to_delete.txt", io.BytesIO(content), "text/plain")},
    )
    doc_id = upload.json()["document"]["id"]
    resp = await client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    list_resp = await client.get("/api/documents/")
    ids = [d["id"] for d in list_resp.json()]
    assert doc_id not in ids


def test_vector_store_uses_temp_dir_not_real_store():
    """Regression: vector store must NOT be the real backend/vector_store_v2 during tests.

    Spec: docs/superpowers/specs/SKILL.md §3 'Isolated Vector Store'
    Root cause of past corruption: vector_store_v2_backup_corrupted exists because
    tests wrote to the real ChromaDB and a Python version mismatch corrupted it.
    """
    from config import settings
    from pathlib import Path

    real_store = (Path(__file__).parent.parent / "vector_store_v2").resolve()
    test_store = Path(settings.vector_store_dir).resolve()

    assert test_store != real_store, (
        f"Tests are writing to the REAL vector store at {real_store}!\n"
        "This violates the isolation spec (docs/superpowers/specs/SKILL.md §3).\n"
        "Fix: set VECTOR_STORE_DIR env var to a temp dir in conftest.py before app import."
    )
