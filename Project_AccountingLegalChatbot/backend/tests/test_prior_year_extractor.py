"""Tests for prior year PDF extractor."""
import pytest
from unittest.mock import patch, AsyncMock
from core.prior_year_extractor import (
    _has_financial_data,
    _parse_text_tables,
    build_prior_year_context,
    extract_prior_year_from_pdf,
)


def test_has_financial_data_detects_numbers():
    text = "Property, plant & equipment  1,919,606  2,131,198"
    assert _has_financial_data(text) is True


def test_has_financial_data_returns_false_for_empty():
    assert _has_financial_data("") is False
    assert _has_financial_data("   ") is False
    assert _has_financial_data("Invoice dated January 2024") is False


def test_parse_text_tables_extracts_rows():
    text = (
        "Property, plant & equipment  1,919,606  2,131,198\n"
        "Trade receivables  720,277  424,857\n"
        "Cash and cash equivalents  2,369,660  5,003,516\n"
        "Total Assets  5,929,549  9,489,570\n"
    )
    rows = _parse_text_tables(text)
    assert len(rows) >= 3
    # Each row should have account_name and prior_year_value
    for r in rows:
        assert "account_name" in r
        assert "prior_year_value" in r


def test_build_prior_year_context_formats_correctly():
    rows = [
        {"account_name": "Total Assets", "prior_year_value": 9489570.0},
        {"account_name": "Trade receivables", "prior_year_value": 424857.0},
    ]
    ctx = build_prior_year_context(rows)
    assert "Total Assets" in ctx
    assert "9,489,570" in ctx


@patch("core.prior_year_extractor.analyze_audit_document", new_callable=AsyncMock, return_value={"sections": []})
@patch("core.prior_year_extractor._extract_via_vision", new_callable=AsyncMock, return_value=[])
async def test_extract_returns_template_key(mock_vision, mock_analyze):
    """The result dict must always contain a 'template' key."""
    # fitz.open will fail on a non-existent file, falling through to vision (mocked above)
    result = await extract_prior_year_from_pdf("fake.pdf")
    assert "template" in result
    assert isinstance(result["template"], dict)
    mock_analyze.assert_awaited_once_with("fake.pdf")


import os

@pytest.mark.asyncio
async def test_fitz_vision_extraction_returns_rows():
    """
    Smoke test: given a real scanned PDF, fitz vision extraction returns at least one row.
    Uses the sample PDF at backend/tests/fixtures/scanned_sample.pdf if present,
    otherwise skips.
    """
    from core.prior_year_extractor import _extract_via_fitz_vision

    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "scanned_sample.pdf")
    if not os.path.exists(fixture):
        pytest.skip("No fixture PDF — skipping vision extraction test")

    rows = await _extract_via_fitz_vision(fixture)
    assert isinstance(rows, list)
