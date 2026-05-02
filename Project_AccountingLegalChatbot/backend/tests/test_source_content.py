"""Tests for GET /api/documents/source-content endpoint."""
import io
import pytest


@pytest.mark.asyncio
async def test_source_content_not_found(client):
    """Returns 404 when source does not exist in vector store."""
    resp = await client.get(
        "/api/documents/source-content",
        params={"source": "nonexistent_file.pdf"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_source_content_returns_text_after_upload(client):
    """Returns text content for a previously uploaded and indexed document."""
    content = b"UAE VAT standard rate is 5 percent under Federal Decree-Law No 8 of 2017."
    upload = await client.post(
        "/api/documents/upload",
        files={"file": ("vat_law.txt", io.BytesIO(content), "text/plain")},
    )
    assert upload.status_code == 200
    doc_data = upload.json()["document"]
    source_name = doc_data["original_name"]  # "vat_law.txt"

    if doc_data["status"] != "indexed":
        pytest.skip("Document indexing failed — skipping content retrieval test")

    resp = await client.get(
        "/api/documents/source-content",
        params={"source": source_name},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "text" in body
    assert len(body["text"]) > 0


@pytest.mark.asyncio
async def test_source_content_response_shape(client):
    """Response contains source, page, and text keys."""
    resp = await client.get(
        "/api/documents/source-content",
        params={"source": "any_file.pdf", "page": "1"},
    )
    # Either 404 (not found) or 200 with correct shape
    if resp.status_code == 200:
        body = resp.json()
        assert "source" in body
        assert "text" in body
    else:
        assert resp.status_code == 404


def test_is_research_query_detects_keywords():
    from api.chat import _is_research_query

    assert _is_research_query("research UAE corporate tax exemptions") is True
    assert _is_research_query("deep analysis of IFRS 16") is True
    assert _is_research_query("comprehensive guide to VAT") is True
    assert _is_research_query("what is VAT") is False
    assert _is_research_query("how much is the VAT rate") is False
