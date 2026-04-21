import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_detect_returns_schema():
    """POST /api/reports/detect must return entity_name, period_end, confidence."""
    with patch("api.reports.rag_engine") as mock_rag, \
         patch("api.reports.get_llm_provider") as mock_llm_factory:

        mock_rag.search = AsyncMock(return_value=[
            {"text": "ABC Trading LLC annual report for year ended 31 December 2024",
             "metadata": {"source": "financial_report.pdf", "page": 1}, "score": 0.92}
        ])

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(
            content='{"entity_name": "ABC Trading LLC", "period_end": "31 Dec 2024"}'
        ))
        mock_llm_factory.return_value = mock_llm

        r = client.post(
            "/api/reports/detect",
            json={"report_type": "audit", "selected_doc_ids": ["doc-1"]}
        )

    assert r.status_code == 200
    data = r.json()
    assert "entity_name" in data
    assert "period_end" in data
    assert data["confidence"] in ("high", "low", "none")


def test_detect_returns_none_confidence_when_no_docs():
    """When no docs are selected, confidence must be 'none'."""
    with patch("api.reports.rag_engine") as mock_rag, \
         patch("api.reports.get_llm_provider") as mock_llm_factory:

        mock_rag.search = AsyncMock(return_value=[])
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(content='{}'))
        mock_llm_factory.return_value = mock_llm

        r = client.post(
            "/api/reports/detect",
            json={"report_type": "audit", "selected_doc_ids": []}
        )

    assert r.status_code == 200
    assert r.json()["confidence"] == "none"
