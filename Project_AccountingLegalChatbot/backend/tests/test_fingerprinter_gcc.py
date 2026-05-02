"""Tests for FormatFingerprinter — fingerprint extraction and GCC matching."""
import pytest
from pathlib import Path


REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)

FINGERPRINT_KEYS = {"page_size", "currency", "section_count", "has_notes", "col_count", "format_family"}


@pytest.fixture
def minimal_a4_aed_pdf(tmp_path):
    """In-memory A4 PDF with AED currency and IFRS section headings."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((72, 750), "Statement of Financial Position", fontsize=12)
    page.insert_text((72, 720), "Statement of Profit and Loss", fontsize=12)
    page.insert_text((72, 690), "Notes to the Financial Statements", fontsize=12)
    page.insert_text((350, 660), "AED")
    page.insert_text((380, 640), "1,234,567")
    page.insert_text((460, 640), "987,654")
    page.insert_text((380, 620), "2023")
    page.insert_text((460, 620), "2022")
    pdf_path = tmp_path / "test_gcc_audit.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_fingerprint_returns_required_keys(minimal_a4_aed_pdf):
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert set(result.keys()) == FINGERPRINT_KEYS


def test_fingerprint_detects_a4(minimal_a4_aed_pdf):
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["page_size"] == "A4"


def test_fingerprint_detects_aed(minimal_a4_aed_pdf):
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["currency"] == "AED"


def test_fingerprint_detects_sections(minimal_a4_aed_pdf):
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["section_count"] >= 2


def test_fingerprint_detects_has_notes(minimal_a4_aed_pdf):
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["has_notes"] is True


def test_fingerprint_detects_col_count(minimal_a4_aed_pdf):
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["col_count"] in (2, 3)


def test_score_exact_match():
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    fingerprint = {
        "page_size": "A4", "currency": "AED", "format_family": "IFRS",
        "section_count": 6, "col_count": 3, "has_notes": True,
    }
    assert fp._score(fingerprint, fingerprint) == 100


def test_score_no_match():
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    a = {"page_size": "A4", "currency": "AED", "format_family": "IFRS",
         "section_count": 6, "col_count": 3, "has_notes": True}
    b = {"page_size": "US_LETTER", "currency": "USD", "format_family": "GAAP",
         "section_count": 20, "col_count": 2, "has_notes": False}
    assert fp._score(a, b) == 0


def test_fingerprint_missing_pdf():
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint("nonexistent_file.pdf")
    assert set(result.keys()) == FINGERPRINT_KEYS
    assert result["page_size"] == "CUSTOM"


def test_fingerprint_real_pdf_gcc():
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    _, score, source_id = fp.match(REFERENCE_PDF)
    assert score >= 88, f"Expected >=88 but got {score}"
    assert source_id == "prebuilt-gcc-standard"
