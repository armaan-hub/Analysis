"""
Integration tests for /api/templates routes.
Uses the existing conftest.py fixtures (client, db_session).
"""
import pytest
from core.template_store import TemplateStore

_MINIMAL_CONFIG = {
    "page": {"width": 612, "height": 792, "unit": "points"},
    "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
    "fonts": {},
    "tables": [],
    "sections": [],
}


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


# ── Feedback endpoint tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feedback_correct_increases_confidence(client, db_session):
    """Happy path: 'correct' feedback → 200 with new_confidence field."""
    store = TemplateStore(db_session)
    tmpl = await store.save(
        name="Feedback Test Template",
        config=_MINIMAL_CONFIG,
        user_id="user_fb",
        status="needs_review",
        confidence_score=0.5,
    )

    resp = await client.post(
        f"/api/templates/{tmpl.id}/feedback",
        json={"feedback_type": "correct", "user_id": "user_fb"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "new_confidence" in data
    assert data["new_confidence"] > 0.5


@pytest.mark.asyncio
async def test_feedback_invalid_type_returns_400(client, db_session):
    """Invalid feedback_type → 400."""
    store = TemplateStore(db_session)
    tmpl = await store.save(
        name="Feedback 400 Test",
        config=_MINIMAL_CONFIG,
        user_id="user_fb2",
        status="needs_review",
        confidence_score=0.5,
    )

    resp = await client.post(
        f"/api/templates/{tmpl.id}/feedback",
        json={"feedback_type": "excellent"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_feedback_nonexistent_template_returns_404(client):
    """Feedback on non-existent template → 404."""
    resp = await client.post(
        "/api/templates/nonexistent-template-xyz/feedback",
        json={"feedback_type": "correct"},
    )
    assert resp.status_code == 404


# ── Phase 2D: Confidence calibration / retraining tests ──────────────────────

@pytest.mark.asyncio
async def test_confidence_history_empty_feedback(client, db_session):
    from core.template_store import TemplateStore
    store = TemplateStore(db_session)
    tmpl = await store.save(
        user_id="user-p2d",
        name="P2D Calibration Test",
        config={"page": {"width": 595, "height": 842, "unit": "points"}, "margins": {}, "fonts": {}, "tables": [], "sections": []},
        status="verified",
        confidence_score=0.75,
    )
    resp = await client.get(f"/api/templates/{tmpl.id}/confidence-history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["feedback_count"] == 0
    assert data["current_confidence"] == pytest.approx(0.75, abs=0.01)
    assert data["calibration_summary"]["method"] == "none"


@pytest.mark.asyncio
async def test_retrain_single_template_no_feedback(client, db_session):
    from core.template_store import TemplateStore
    store = TemplateStore(db_session)
    tmpl = await store.save(
        user_id="user-p2d2",
        name="Retrain No Feedback",
        config={"page": {"width": 595, "height": 842, "unit": "points"}, "margins": {}, "fonts": {}, "tables": [], "sections": []},
        status="verified",
        confidence_score=0.75,
    )
    resp = await client.post(f"/api/templates/{tmpl.id}/retrain")
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "skipped"
    assert data["reason"] == "no_feedback"


@pytest.mark.asyncio
async def test_retrain_single_template_with_feedback(client, db_session):
    from core.template_store import TemplateStore
    store = TemplateStore(db_session)
    tmpl = await store.save(
        user_id="user-p2d3",
        name="Retrain With Feedback",
        config={"page": {"width": 595, "height": 842, "unit": "points"}, "margins": {}, "fonts": {}, "tables": [], "sections": []},
        status="verified",
        confidence_score=0.7,
    )
    # Submit 2 accurate feedbacks (normalized to "correct" by the API)
    await client.post(f"/api/templates/{tmpl.id}/feedback", json={"feedback_type": "accurate"})
    await client.post(f"/api/templates/{tmpl.id}/feedback", json={"feedback_type": "accurate"})

    resp = await client.post(f"/api/templates/{tmpl.id}/retrain")
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "retrained"
    assert data["new_confidence"] >= data["old_confidence"]


@pytest.mark.asyncio
async def test_retrain_all_endpoint(client, db_session):
    resp = await client.post("/api/templates/retrain")
    assert resp.status_code == 200
    data = resp.json()
    assert "retrained" in data
    assert "results" in data


@pytest.mark.asyncio
async def test_confidence_history_not_found(client):
    resp = await client.get("/api/templates/nonexistent-xyz/confidence-history")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retrain_single_not_found(client):
    resp = await client.post("/api/templates/nonexistent-xyz/retrain")
    assert resp.status_code == 404


# ── Prebuilt format tests (Phase 2C) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_prebuilt_formats_all(client):
    resp = await client.get("/api/templates/prebuilt")
    assert resp.status_code == 200
    data = resp.json()
    formats = data.get("formats", data) if isinstance(data, dict) else data
    assert len(formats) >= 6  # 3 original + 3 new


@pytest.mark.asyncio
async def test_list_prebuilt_formats_ifrs_filter(client):
    resp = await client.get("/api/templates/prebuilt?format_family=IFRS")
    assert resp.status_code == 200
    data = resp.json()
    formats = data.get("formats", data) if isinstance(data, dict) else data
    assert all(f["format_family"] == "IFRS" for f in formats)
    assert len(formats) >= 2  # IFRS Standard + UK FRS 102 + GCC Standard (min 2)


@pytest.mark.asyncio
async def test_list_prebuilt_formats_local_tax_filter(client):
    resp = await client.get("/api/templates/prebuilt?format_family=local-tax")
    assert resp.status_code == 200
    data = resp.json()
    formats = data.get("formats", data) if isinstance(data, dict) else data
    assert len(formats) >= 2  # UAE + Saudi ZATCA


@pytest.mark.asyncio
async def test_apply_new_prebuilt_uk_frs102(client, db_session):
    resp = await client.post(
        "/api/templates/prebuilt/prebuilt-uk-frs102/apply?user_id=test-user-2c"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["format_family"] == "IFRS"
    assert data["format_variant"] == "UK FRS 102"


@pytest.mark.asyncio
async def test_apply_new_prebuilt_saudi_zatca(client, db_session):
    resp = await client.post(
        "/api/templates/prebuilt/prebuilt-saudi-zatca/apply?user_id=test-user-2c"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["format_family"] == "local-tax"


@pytest.mark.asyncio
async def test_apply_new_prebuilt_gcc(client, db_session):
    resp = await client.post(
        "/api/templates/prebuilt/prebuilt-gcc-standard/apply?user_id=test-user-2c"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["format_family"] == "IFRS"
