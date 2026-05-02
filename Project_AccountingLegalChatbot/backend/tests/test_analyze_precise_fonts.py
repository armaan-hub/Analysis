"""Tests for TemplateAnalyzer.analyze_precise() — role-based font mapping."""
import pytest
from pathlib import Path

REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)


@pytest.fixture
def role_pdf(tmp_path):
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((72, 780), "Statement of Financial Position", fontsize=12)
    for i in range(10):
        page.insert_text((72, 750 - i * 12), f"Line item {i}", fontsize=9)
    page.insert_text((72, 30), "Page 1 of 5", fontsize=7)
    page.insert_text((310, 750), "Note 1", fontsize=8)
    page.insert_text((310, 738), "Note 2", fontsize=8)
    pdf_path = tmp_path / "role_fonts.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_fonts_has_heading_key(role_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "heading" in result["fonts"]


def test_fonts_has_body_key(role_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "body" in result["fonts"]


def test_fonts_has_footer_key(role_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "footer" in result["fonts"]


def test_fonts_has_number_key(role_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "number" in result["fonts"]


def test_fonts_has_note_ref_key(role_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "note_ref" in result["fonts"]


def test_each_font_role_has_size_and_family(role_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    for role in ("heading", "body", "footer", "note_ref"):
        if result["fonts"].get(role):
            assert "size" in result["fonts"][role], f"Missing 'size' in {role}"
            assert "family" in result["fonts"][role], f"Missing 'family' in {role}"


def test_heading_size_larger_than_body(role_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    heading_size = result["fonts"].get("heading", {}).get("size", 0)
    body_size = result["fonts"].get("body", {}).get("size", 0)
    assert heading_size >= body_size


def test_fonts_real_pdf():
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(REFERENCE_PDF)
    for role in ("heading", "body", "footer"):
        assert result["fonts"].get(role, {}).get("size", 0) > 0, f"{role} font size is 0"
