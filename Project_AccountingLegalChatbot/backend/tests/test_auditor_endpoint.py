"""Tests for the auditor endpoint."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_auditor_endpoint_returns_result(client):
    fake_result = {
        "risk_flags": [{"severity": "high", "document": "d1", "finding": "Missing info"}],
        "anomalies": [],
        "compliance_gaps": [],
        "summary": "One risk found.",
    }
    with patch("api.legal_studio.run_audit", new=AsyncMock(return_value=fake_result)):
        resp = await client.post("/api/legal-studio/auditor", json={"document_ids": ["d1"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["risk_flags"]) == 1
    assert data["summary"] == "One risk found."


@pytest.mark.asyncio
async def test_auditor_endpoint_empty_docs(client):
    fake_result = {
        "risk_flags": [],
        "anomalies": [],
        "compliance_gaps": [],
        "summary": "No documents selected.",
    }
    with patch("api.legal_studio.run_audit", new=AsyncMock(return_value=fake_result)):
        resp = await client.post("/api/legal-studio/auditor", json={"document_ids": []})
    assert resp.status_code == 200
    assert resp.json()["summary"] == "No documents selected."
