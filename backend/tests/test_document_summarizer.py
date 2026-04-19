"""Tests for document summarizer module."""
import json
import pytest
from unittest.mock import patch, AsyncMock
from core.documents.summarizer import summarize_document_text


@pytest.mark.asyncio
async def test_summarize_parses_valid_json():
    fake = json.dumps({"summary": "A brief about UAE VAT.", "key_terms": ["VAT", "UAE", "tax", "compliance", "filing"]})
    with patch("core.documents.summarizer._llm_complete", new=AsyncMock(return_value=fake)):
        r = await summarize_document_text("long text about UAE VAT...")
    assert r.summary == "A brief about UAE VAT."
    assert r.key_terms == ["VAT", "UAE", "tax", "compliance", "filing"]


@pytest.mark.asyncio
async def test_summarize_handles_markdown_fenced_json():
    fake = '```json\n{"summary": "test", "key_terms": ["a", "b", "c", "d", "e"]}\n```'
    with patch("core.documents.summarizer._llm_complete", new=AsyncMock(return_value=fake)):
        r = await summarize_document_text("text")
    assert r.summary == "test"
    assert len(r.key_terms) == 5


@pytest.mark.asyncio
async def test_summarize_fallback_on_bad_json():
    with patch("core.documents.summarizer._llm_complete", new=AsyncMock(return_value="not json")):
        r = await summarize_document_text("text")
    assert r.summary == "Summary unavailable."
    assert r.key_terms == []
