"""Tests for markdown → Word/PDF/Excel conversion."""
import pytest
from core.export_converter import to_word, to_pdf, to_excel


SAMPLE_MARKDOWN = """# UAE VAT Summary

This document covers the key points of UAE VAT regulations.

## Key Rates

| Supply Type | Rate |
|-------------|------|
| Standard | 5% |
| Zero-rated | 0% |
| Exempt | N/A |

## Filing Deadlines

Quarterly filers must submit by the **28th day** after the quarter ends.

- Q1: April 28
- Q2: July 28
- Q3: October 28
- Q4: January 28
"""


def test_to_word_returns_bytes():
    result = to_word(SAMPLE_MARKDOWN)
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:2] == b'PK'


def test_to_word_contains_heading():
    import io
    from docx import Document
    result = to_word(SAMPLE_MARKDOWN)
    doc = Document(io.BytesIO(result))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "UAE VAT Summary" in all_text
    assert "Key Rates" in all_text


def test_to_excel_returns_bytes_when_table_present():
    result = to_excel(SAMPLE_MARKDOWN)
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:2] == b'PK'


def test_to_excel_returns_empty_bytes_when_no_table():
    no_table_md = "# Title\n\nJust some text with no table here."
    result = to_excel(no_table_md)
    assert result == b""


def test_to_pdf_returns_bytes():
    result = to_pdf(SAMPLE_MARKDOWN)
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:4] == b'%PDF'
