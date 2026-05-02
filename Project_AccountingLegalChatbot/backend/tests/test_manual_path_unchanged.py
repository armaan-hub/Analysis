"""
Tests that fast_learn=false (default) preserves the existing job-based workflow exactly.
"""
import pytest


FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"


@pytest.mark.asyncio
async def test_upload_without_fast_learn_returns_job_id(client):
    """Default upload (fast_learn=false) still returns job_id and pending status."""
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("manual.pdf", FAKE_PDF, "application/pdf")},
        params={"name": "Manual Template", "user_id": "user_manual"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert "message" in data


@pytest.mark.asyncio
async def test_upload_fast_learn_false_returns_job_id(client):
    """Explicit fast_learn=false still returns job_id and pending status."""
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("manual2.pdf", FAKE_PDF, "application/pdf")},
        params={"fast_learn": "false", "user_id": "user_manual2"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_manual_path_job_trackable(client):
    """A job created without fast_learn can be tracked via /status/{job_id}."""
    upload_resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("track.pdf", FAKE_PDF, "application/pdf")},
        params={"user_id": "tracker"},
    )
    job_id = upload_resp.json()["job_id"]

    status_resp = await client.get(f"/api/templates/status/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["job_id"] == job_id


@pytest.mark.asyncio
async def test_non_pdf_still_returns_400(client):
    """Non-PDF upload still returns 400 regardless of fast_learn."""
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("bad.txt", b"not a pdf", "text/plain")},
        params={"fast_learn": "true"},
    )
    assert resp.status_code == 400
