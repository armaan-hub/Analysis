"""Tests for TemplateStore CRUD operations."""
import pytest
import json

from core.template_store import TemplateStore


@pytest.mark.asyncio
async def test_save_and_load(db_session):
    store = TemplateStore(db_session)
    config = {
        "page": {"width": 612, "height": 792, "unit": "points"},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "fonts": {},
        "tables": [],
        "sections": [],
    }

    tmpl = await store.save(name="Castle Plaza Format", config=config,
                            user_id="user123", status="verified",
                            confidence_score=0.92)
    assert tmpl.id is not None

    loaded = await store.load(tmpl.id)
    assert loaded is not None
    assert loaded.name == "Castle Plaza Format"
    assert loaded.confidence_score == 0.92
    assert json.loads(loaded.config_json) == config


@pytest.mark.asyncio
async def test_list_user_templates(db_session):
    store = TemplateStore(db_session)
    config = {"page": {}, "margins": {}, "fonts": {}, "tables": [], "sections": []}

    await store.save("Format A", config, user_id="userX", status="ready")
    await store.save("Format B", config, user_id="userX", status="ready")
    await store.save("Format C", config, user_id="userY", status="ready")

    result = await store.list_user_templates("userX")
    assert len(result) == 2
    assert all(t.user_id == "userX" for t in result)


@pytest.mark.asyncio
async def test_publish_global(db_session):
    store = TemplateStore(db_session)
    config = {"page": {}, "margins": {}, "fonts": {}, "tables": [], "sections": []}

    tmpl = await store.save("Global IFRS Format", config, user_id="admin123")
    published = await store.publish_global(tmpl.id)
    assert published.is_global is True

    globals_ = await store.list_global_templates()
    assert any(t.id == tmpl.id for t in globals_)


@pytest.mark.asyncio
async def test_delete(db_session):
    store = TemplateStore(db_session)
    config = {"page": {}, "margins": {}, "fonts": {}, "tables": [], "sections": []}

    tmpl = await store.save("Temp Format", config, user_id="user1")
    deleted = await store.delete(tmpl.id)
    assert deleted is True
    assert await store.load(tmpl.id) is None
