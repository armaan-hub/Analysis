"""Tests for embedding provider switch endpoint."""
import pytest
from unittest.mock import patch, MagicMock


_VALID_PROVIDERS = ["nvidia", "openai", "ollama"]


class TestGetEmbeddingStatus:
    @pytest.mark.asyncio
    async def test_get_embedding_config_returns_200(self, client):
        """GET /api/documents/embedding-config returns 200 with provider info."""
        r = await client.get("/api/documents/embedding-config")
        assert r.status_code == 200
        data = r.json()
        assert "provider" in data
        assert "model" in data
        assert "dimension" in data


class TestPostEmbeddingSwitch:
    @pytest.mark.asyncio
    async def test_post_embedding_switch_returns_200(self, client, monkeypatch):
        """POST /api/settings/embedding-switch with valid provider returns 200."""
        import api.settings as settings_module
        monkeypatch.setattr(settings_module.settings, "embedding_provider", "nvidia")

        with patch("api.settings._update_env_key"), \
             patch("api.settings.rag_engine", create=True) as mock_rag:
            mock_rag.embedding_provider = MagicMock()
            mock_rag.embedding_provider.provider = "nvidia"
            r = await client.post(
                "/api/settings/embedding-switch",
                json={"provider": "openai"},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["provider"] == "openai"
        assert data["needs_reindex"] is True
        assert "message" in data

    @pytest.mark.asyncio
    async def test_post_embedding_switch_same_provider_no_reindex(self, client, monkeypatch):
        """Switching to same provider returns needs_reindex=False."""
        import api.settings as settings_module
        monkeypatch.setattr(settings_module.settings, "embedding_provider", "openai")

        with patch("api.settings._update_env_key"), \
             patch("api.settings.rag_engine", create=True) as mock_rag:
            mock_rag.embedding_provider = MagicMock()
            mock_rag.embedding_provider.provider = "openai"
            r = await client.post(
                "/api/settings/embedding-switch",
                json={"provider": "openai"},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["provider"] == "openai"
        assert data["needs_reindex"] is False
        assert "Provider unchanged" in data["message"]

    @pytest.mark.asyncio
    async def test_post_embedding_switch_invalid_provider_returns_400(self, client):
        """POST /api/settings/embedding-switch with unknown provider returns 400."""
        with patch("api.settings._update_env_key"):
            r = await client.post(
                "/api/settings/embedding-switch",
                json={"provider": "unknown_provider"},
            )

        assert r.status_code == 400
        assert "unknown_provider" in r.json()["detail"].lower() or "unknown" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_post_embedding_switch_all_valid_providers(self, client, monkeypatch):
        """Each valid provider can be switched to successfully."""
        import api.settings as settings_module

        for provider in _VALID_PROVIDERS:
            monkeypatch.setattr(settings_module.settings, "embedding_provider", "nvidia")
            with patch("api.settings._update_env_key"), \
                 patch("api.settings.rag_engine", create=True) as mock_rag:
                mock_rag.embedding_provider = MagicMock()
                mock_rag.embedding_provider.provider = "nvidia"
                r = await client.post(
                    "/api/settings/embedding-switch",
                    json={"provider": provider},
                )
            assert r.status_code == 200, f"Expected 200 for provider={provider}, got {r.status_code}"
            assert r.json()["provider"] == provider

    @pytest.mark.asyncio
    async def test_post_embedding_switch_env_write_failure_is_non_fatal(self, client, monkeypatch):
        """A failure to write .env does not cause a 500 — warning only."""
        import api.settings as settings_module
        monkeypatch.setattr(settings_module.settings, "embedding_provider", "nvidia")

        with patch("api.settings._update_env_key", side_effect=OSError("disk full")), \
             patch("api.settings.rag_engine", create=True) as mock_rag:
            mock_rag.embedding_provider = MagicMock()
            mock_rag.embedding_provider.provider = "nvidia"
            r = await client.post(
                "/api/settings/embedding-switch",
                json={"provider": "openai"},
            )

        assert r.status_code == 200
        assert r.json()["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_post_embedding_switch_rag_rebind_failure_is_non_fatal(self, client, monkeypatch):
        """A failure to rebind rag_engine does not cause a 500 — warning only."""
        import api.settings as settings_module
        monkeypatch.setattr(settings_module.settings, "embedding_provider", "nvidia")

        with patch("api.settings._update_env_key"), \
             patch("core.rag_engine.rag_engine", create=True, side_effect=ImportError("no rag")):
            r = await client.post(
                "/api/settings/embedding-switch",
                json={"provider": "ollama"},
            )

        assert r.status_code == 200


@pytest.mark.asyncio
async def test_embedding_status_returns_required_fields(client):
    resp = await client.get("/api/settings/embedding-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "status" in data
    assert data["status"] in ("green", "yellow", "red")
    assert "latency_ms" in data
    assert "model" in data
    assert "chunk_count" in data
    assert "available_providers" in data
    assert isinstance(data["available_providers"], list)
    assert len(data["available_providers"]) >= 1
