"""Tests for template preview endpoints."""
import json
import pytest
from core.template_store import TemplateStore


_TEMPLATE_BODY = "Company: ${company_name}\nPeriod: ${period}"
_PREVIEW_CONFIG = {
    "page": {"width": 612, "height": 792, "unit": "points"},
    "body": _TEMPLATE_BODY,
}


async def _seed_template(db_session) -> str:
    """Insert a test template with a body and return its id."""
    store = TemplateStore(db_session)
    tpl = await store.save(name="Preview Test", config=_PREVIEW_CONFIG, user_id="u1")
    return tpl.id


@pytest.mark.asyncio
async def test_preview_template_get(client, db_session):
    tpl_id = await _seed_template(db_session)
    resp = await client.get(f"/api/templates/{tpl_id}/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert "Sample Trading LLC" in data["rendered"]
    assert "structure" in data
    assert "sample_data" in data
    assert data["template_id"] == tpl_id


@pytest.mark.asyncio
async def test_preview_template_not_found(client):
    resp = await client.get("/api/templates/nonexistent-id/preview")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preview_template_no_body(client, db_session):
    """Template exists but config has no body → 400."""
    store = TemplateStore(db_session)
    tpl = await store.save(name="No Body", config={"page": {}}, user_id="u1")
    resp = await client.get(f"/api/templates/{tpl.id}/preview")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_preview_template_post_custom_data(client, db_session):
    tpl_id = await _seed_template(db_session)
    resp = await client.post(
        f"/api/templates/{tpl_id}/preview",
        json={"company": {"name": "My Corp"}, "period": "2024"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "My Corp" in body["rendered"]
    assert "2024" in body["rendered"]
    assert body["template_id"] == tpl_id


@pytest.mark.asyncio
async def test_preview_post_not_found(client):
    resp = await client.post(
        "/api/templates/nonexistent-id/preview",
        json={"company": {"name": "X"}},
    )
    assert resp.status_code == 404
