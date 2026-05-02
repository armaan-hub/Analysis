"""Tests for auditor agent module."""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from core.chat.auditor_agent import run_audit


@pytest.mark.asyncio
async def test_audit_returns_expected_shape():
    fake_response = json.dumps({
        "risk_flags": [{"severity": "high", "document": "d1", "finding": "Missing disclosure"}],
        "anomalies": [],
        "compliance_gaps": [{"severity": "medium", "document": "d1", "finding": "No AML policy"}],
        "summary": "One high-risk flag found.",
    })

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=MagicMock(content=fake_response))

    mock_rag = AsyncMock()
    mock_rag.search = AsyncMock(return_value=[{"text": "some document content", "metadata": {}}])

    with patch("core.chat.auditor_agent.get_llm_provider", return_value=mock_llm), \
         patch("core.chat.auditor_agent.rag_engine", mock_rag):
        out = await run_audit(document_ids=["d1"])

    assert "risk_flags" in out and "summary" in out
    assert isinstance(out["risk_flags"], list)
    assert len(out["risk_flags"]) == 1
    assert out["risk_flags"][0]["severity"] == "high"


@pytest.mark.asyncio
async def test_audit_empty_docs():
    out = await run_audit(document_ids=[])
    assert out["summary"] == "No documents selected."
    assert out["risk_flags"] == []
