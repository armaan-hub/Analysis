"""Tests for API key visibility settings endpoints."""
import json
import os
import pytest
import tempfile
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from main import app


KNOWN_KEYS = [
    "NVIDIA_API_KEY", "NVIDIA_FAST_API_KEY", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY"
]


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Client with isolated settings_keys.json path."""
    keys_file = tmp_path / "settings_keys.json"
    monkeypatch.setenv("SETTINGS_KEYS_FILE", str(keys_file))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestGetKeysVisibility:
    async def test_returns_all_six_keys(self, client):
        resp = await client.get("/api/settings/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        returned_names = [k["name"] for k in data["keys"]]
        for key in KNOWN_KEYS:
            assert key in returned_names

    async def test_default_visibility_is_masked(self, client):
        resp = await client.get("/api/settings/keys")
        for k in resp.json()["keys"]:
            assert k["visibility"] in ("masked", "hidden", "none")

    async def test_each_key_has_required_fields(self, client):
        resp = await client.get("/api/settings/keys")
        for k in resp.json()["keys"]:
            assert "name" in k
            assert "visibility" in k


class TestPutKeyVisibility:
    async def test_update_visibility_to_hidden(self, client):
        resp = await client.put(
            "/api/settings/keys",
            json={"NVIDIA_API_KEY": "hidden"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        keys_map = {k["name"]: k["visibility"] for k in data["keys"]}
        assert keys_map["NVIDIA_API_KEY"] == "hidden"

    async def test_update_persists_across_requests(self, client):
        await client.put("/api/settings/keys", json={"OPENAI_API_KEY": "none"})
        resp = await client.get("/api/settings/keys")
        keys = {k["name"]: k["visibility"] for k in resp.json()["keys"]}
        assert keys["OPENAI_API_KEY"] == "none"

    async def test_invalid_visibility_returns_422(self, client):
        resp = await client.put(
            "/api/settings/keys",
            json={"NVIDIA_API_KEY": "INVALID_VALUE"}
        )
        assert resp.status_code == 422

    async def test_unknown_key_returns_400(self, client):
        resp = await client.put(
            "/api/settings/keys",
            json={"NONEXISTENT_KEY": "masked"}
        )
        assert resp.status_code == 400

    async def test_update_only_affects_target_key(self, client):
        await client.put("/api/settings/keys", json={"NVIDIA_API_KEY": "none"})
        resp = await client.get("/api/settings/keys")
        keys = {k["name"]: k["visibility"] for k in resp.json()["keys"]}
        # Others should remain at default
        assert keys["ANTHROPIC_API_KEY"] in ("masked", "hidden", "none")
        assert keys["NVIDIA_API_KEY"] == "none"
