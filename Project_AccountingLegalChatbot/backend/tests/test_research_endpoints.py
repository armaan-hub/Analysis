"""Tests for research endpoints."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_start_research(client):
    with patch("api.legal_studio.run_deep_research", new=AsyncMock()):
        resp = await client.post(
            "/api/legal-studio/research",
            json={"query": "UAE VAT overview"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_get_research_not_found(client):
    resp = await client.get("/api/legal-studio/research/nonexistent-id")
    assert resp.status_code == 404
