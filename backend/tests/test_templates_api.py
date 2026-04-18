"""
Integration tests for /api/templates routes.
Uses the existing conftest.py fixtures (client, db_session).
"""
import pytest


@pytest.mark.asyncio
async def test_upload_reference_invalid_file(client):
    """Uploading non-PDF returns 400."""
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_reference_pdf(client):
    """Uploading a PDF returns job_id and pending status."""
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("test_audit.pdf", fake_pdf, "application/pdf")},
        params={"name": "Test Template", "user_id": "user1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_status_not_found(client):
    """Getting status for non-existent job returns 404."""
    resp = await client.get("/api/templates/status/nonexistent-job-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_status_after_upload(client):
    """After upload, status endpoint returns job details."""
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    upload_resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("status_test.pdf", fake_pdf, "application/pdf")},
        params={"user_id": "user2"},
    )
    job_id = upload_resp.json()["job_id"]

    status_resp = await client.get(f"/api/templates/status/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "processing", "verified", "needs_review", "failed")


@pytest.mark.asyncio
async def test_list_templates_empty(client):
    """Listing templates for new user returns empty list."""
    resp = await client.get("/api/templates/list", params={"user_id": "brand_new_user_xyz"})
    assert resp.status_code == 200
    assert resp.json()["templates"] == []


@pytest.mark.asyncio
async def test_list_global_templates(client):
    """Global library endpoint returns list (possibly empty)."""
    resp = await client.get("/api/templates/library")
    assert resp.status_code == 200
    assert "templates" in resp.json()


@pytest.mark.asyncio
async def test_get_template_not_found(client):
    """Getting a non-existent template returns 404."""
    resp = await client.get("/api/templates/nonexistent-template-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_template_not_found(client):
    """Deleting non-existent template returns 404."""
    resp = await client.delete(
        "/api/templates/nonexistent-id",
        params={"user_id": "user1"},
    )
    assert resp.status_code == 404
