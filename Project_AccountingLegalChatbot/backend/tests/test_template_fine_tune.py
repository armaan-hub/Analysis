"""
Integration tests for PUT /api/templates/{template_id} (fine-tune endpoint)
and the update_config store method.
"""
import json
import pytest
from httpx import AsyncClient

from core.template_store import TemplateStore


# ── helpers ──────────────────────────────────────────────────────────────────

_BASE_CONFIG = {
    "page": {"width": 612, "height": 792, "unit": "points"},
    "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
    "fonts": {
        "heading": {"family": "Helvetica", "size": 12},
        "body": {"family": "Helvetica", "size": 9},
        "footer": {"family": "Helvetica", "size": 8},
    },
    "tables": [],
    "sections": [],
    "confidence": 0.8,
    "source": "test.pdf",
    "page_count": 5,
}

_UPDATED_CONFIG = {
    "page": {"width": 595, "height": 842, "unit": "points"},  # A4
    "margins": {"top": 56, "bottom": 56, "left": 56, "right": 56},
    "fonts": {
        "heading": {"family": "Times", "size": 14},
        "body": {"family": "Times", "size": 10},
        "footer": {"family": "Times", "size": 8},
    },
    "tables": [],
    "sections": [],
    "confidence": 0.9,
    "source": "test.pdf",
    "page_count": 5,
}


async def _create_template(db_session, user_id="user1", name="My Template"):
    """Helper: directly persist a template and return it."""
    store = TemplateStore(db_session)
    return await store.save(
        name=name,
        config=_BASE_CONFIG,
        user_id=user_id,
        status="draft",
        confidence_score=0.8,
    )


# ── PUT endpoint tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_nonexistent_template(client: AsyncClient):
    """PUT on missing template returns 404."""
    resp = await client.put(
        "/api/templates/nonexistent-id",
        json={"config": _BASE_CONFIG},
        params={"user_id": "user1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_template_config(client: AsyncClient, db_session):
    """PUT updates config, returns updated status and confidence."""
    tmpl = await _create_template(db_session)

    resp = await client.put(
        f"/api/templates/{tmpl.id}",
        json={"config": _UPDATED_CONFIG},
        params={"user_id": "user1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["template_id"] == tmpl.id
    assert data["message"] == "Template updated"
    assert "status" in data
    assert "confidence" in data


@pytest.mark.asyncio
async def test_update_template_name_change(client: AsyncClient, db_session):
    """PUT with a new name updates the template name."""
    tmpl = await _create_template(db_session, name="OldName")

    resp = await client.put(
        f"/api/templates/{tmpl.id}",
        json={"config": _UPDATED_CONFIG, "name": "NewName"},
        params={"user_id": "user1"},
    )
    assert resp.status_code == 200

    # Verify via GET that the name was persisted
    get_resp = await client.get(f"/api/templates/{tmpl.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "NewName"


@pytest.mark.asyncio
async def test_update_template_config_persisted(client: AsyncClient, db_session):
    """After PUT, GET returns the new config."""
    tmpl = await _create_template(db_session)

    await client.put(
        f"/api/templates/{tmpl.id}",
        json={"config": _UPDATED_CONFIG},
        params={"user_id": "user1"},
    )

    get_resp = await client.get(f"/api/templates/{tmpl.id}")
    assert get_resp.status_code == 200
    stored_config = get_resp.json()["config"]
    assert stored_config["page"]["width"] == 595
    assert stored_config["fonts"]["heading"]["family"] == "Times"


@pytest.mark.asyncio
async def test_update_template_wrong_user(client: AsyncClient, db_session):
    """PUT by a different user returns 403."""
    tmpl = await _create_template(db_session, user_id="owner")

    resp = await client.put(
        f"/api/templates/{tmpl.id}",
        json={"config": _UPDATED_CONFIG},
        params={"user_id": "intruder"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_template_missing_config_field(client: AsyncClient, db_session):
    """PUT without config key returns 400."""
    tmpl = await _create_template(db_session)

    resp = await client.put(
        f"/api/templates/{tmpl.id}",
        json={"name": "OnlyName"},
        params={"user_id": "user1"},
    )
    assert resp.status_code == 400


# ── update_config store method tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_config_store_method(db_session):
    """update_config directly updates the DB record."""
    store = TemplateStore(db_session)
    tmpl = await store.save(
        name="Before",
        config=_BASE_CONFIG,
        user_id="u1",
        status="draft",
        confidence_score=0.5,
    )

    await store.update_config(
        template_id=tmpl.id,
        config=_UPDATED_CONFIG,
        name="After",
        status="verified",
        confidence_score=0.95,
        verification_report=json.dumps({"overall_passed": True}),
    )

    reloaded = await store.load(tmpl.id)
    assert reloaded.name == "After"
    assert reloaded.status == "verified"
    assert reloaded.confidence_score == 0.95
    assert json.loads(reloaded.config_json)["page"]["width"] == 595
    assert reloaded.verification_report is not None


@pytest.mark.asyncio
async def test_update_config_without_verification_report(db_session):
    """update_config works with verification_report=None."""
    store = TemplateStore(db_session)
    tmpl = await store.save(
        name="Test",
        config=_BASE_CONFIG,
        user_id="u2",
    )

    await store.update_config(
        template_id=tmpl.id,
        config=_UPDATED_CONFIG,
        name="Test",
        status="needs_review",
        confidence_score=0.6,
    )

    reloaded = await store.load(tmpl.id)
    assert reloaded.status == "needs_review"
