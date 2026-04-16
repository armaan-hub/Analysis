"""
Document endpoint tests — upload/list/delete flow.
"""
import io
import pytest


@pytest.mark.asyncio
async def test_upload_txt_document(client):
    content = b"This is a test document about UAE VAT regulations."
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("test_vat.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    # API returns {"document": {...}, "message": "..."}
    doc = data["document"]
    assert doc["original_name"] == "test_vat.txt"
    assert doc["status"] in ("indexed", "processing", "error")


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
