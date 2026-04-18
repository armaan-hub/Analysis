"""Tests for FormatFingerprinter — unknown format falls through to full extraction."""
import pytest


@pytest.fixture
def unknown_format_pdf(tmp_path):
    """Creates a PDF that deliberately does NOT match any prebuilt format."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=612.0, height=792.0)
    page.insert_text((72, 700), "Profit and Loss Account", fontsize=12)
    page.insert_text((72, 680), "Balance Sheet", fontsize=12)
    page.insert_text((350, 660), "BDT")
    page.insert_text((380, 640), "50,000")
    pdf_path = tmp_path / "unknown_format.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_unknown_format_returns_none_config(unknown_format_pdf):
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    config, score, source_id = fp.match(unknown_format_pdf)
    assert score < 88, f"Expected score < 88 but got {score}"
    assert config is None
    assert source_id is None


def test_known_format_returns_config(tmp_path):
    import fitz
    from core.format_fingerprinter import FormatFingerprinter
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((72, 750), "Statement of Financial Position", fontsize=12)
    page.insert_text((72, 720), "Statement of Profit and Loss", fontsize=12)
    page.insert_text((72, 690), "Notes to the Financial Statements", fontsize=12)
    page.insert_text((72, 660), "Statement of Cash Flows", fontsize=12)
    page.insert_text((72, 630), "Statement of Changes in Equity", fontsize=12)
    page.insert_text((72, 600), "Independent Auditor's Report", fontsize=12)
    page.insert_text((350, 570), "AED")
    page.insert_text((380, 550), "2023")
    page.insert_text((460, 550), "2022")
    pdf_path = tmp_path / "gcc_format.pdf"
    doc.save(str(pdf_path))
    doc.close()
    fp = FormatFingerprinter()
    config, score, source_id = fp.match(str(pdf_path))
    assert score >= 88, f"Expected score >=88 but got {score}"
    assert config is not None
    assert source_id == "prebuilt-gcc-standard"


def test_match_with_no_library_entries(tmp_path, monkeypatch):
    import fitz
    from core.format_fingerprinter import FormatFingerprinter
    import core.format_fingerprinter as ff_module
    monkeypatch.setattr(ff_module, "PREBUILT_FORMATS", [])
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    pdf_path = tmp_path / "blank.pdf"
    doc.save(str(pdf_path))
    doc.close()
    fp = FormatFingerprinter()
    config, score, source_id = fp.match(str(pdf_path))
    assert config is None
    assert score == 0
    assert source_id is None
