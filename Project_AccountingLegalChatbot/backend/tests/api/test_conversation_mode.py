import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_new_conversation_defaults_to_fast_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/chat/conversations", json={"title": "t"})
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]
        r2 = await client.get(f"/api/chat/conversations/{cid}")
        assert r2.status_code == 200
        assert r2.json()["mode"] == "fast"


@pytest.mark.asyncio
async def test_list_includes_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/chat/conversations", json={"title": "t2"})
        cid = r.json()["id"]
        r2 = await client.get("/api/chat/conversations")
        assert r2.status_code == 200
        item = next(x for x in r2.json() if x["id"] == cid)
        assert item["mode"] == "fast"


@pytest.mark.asyncio
async def test_patch_mode_updates_and_persists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/chat/conversations", json={"title": "t3"})
        cid = r.json()["id"]
        r2 = await client.patch(f"/api/chat/conversations/{cid}", json={"mode": "analyst"})
        assert r2.status_code == 200
        assert r2.json()["mode"] == "analyst"
        r3 = await client.get(f"/api/chat/conversations/{cid}")
        assert r3.json()["mode"] == "analyst"


@pytest.mark.asyncio
async def test_patch_mode_rejects_invalid_value():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/chat/conversations", json={"title": "t4"})
        cid = r.json()["id"]
        r2 = await client.patch(f"/api/chat/conversations/{cid}", json={"mode": "garbage"})
        assert r2.status_code == 422
