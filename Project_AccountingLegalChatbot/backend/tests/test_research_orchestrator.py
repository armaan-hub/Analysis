"""Tests for the deep research orchestrator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from core.research.event_bus import create_channel, get_channel, emit, remove_channel
from core.research.orchestrator import _plan, _gather_one


@pytest.mark.asyncio
async def test_event_bus_create_and_emit():
    q = create_channel("test-job")
    await emit("test-job", {"phase": "planning"})
    event = await q.get()
    assert event["phase"] == "planning"
    remove_channel("test-job")
    assert get_channel("test-job") is None


@pytest.mark.asyncio
async def test_plan_parses_sub_questions():
    fake = json.dumps({"sub_questions": ["Q1", "Q2", "Q3"]})
    with patch("core.research.orchestrator._llm", new=AsyncMock(return_value=fake)):
        result = await _plan("Tell me about UAE VAT")
    assert result == ["Q1", "Q2", "Q3"]


@pytest.mark.asyncio
async def test_plan_fallback_on_bad_json():
    with patch("core.research.orchestrator._llm", new=AsyncMock(return_value="not json")):
        result = await _plan("original query")
    assert result == ["original query"]


@pytest.mark.asyncio
async def test_gather_one_combines_rag_and_web():
    mock_rag = AsyncMock()
    mock_rag.search = AsyncMock(return_value=[{"text": "RAG result"}])

    with patch("core.research.orchestrator.rag_engine", mock_rag), \
         patch("core.research.orchestrator.search_web", new=AsyncMock(return_value=[{"title": "Web"}])), \
         patch("core.research.orchestrator.build_web_context", return_value="Web context"):
        result = await _gather_one("test query")
    assert "RAG result" in result
    assert "Web context" in result
