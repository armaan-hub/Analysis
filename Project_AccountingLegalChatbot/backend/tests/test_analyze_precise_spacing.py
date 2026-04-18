"""Tests for TemplateAnalyzer.analyze_precise() — line spacing detection."""
import pytest
from pathlib import Path

REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)

SPACING_KEYS = {"heading_after", "row_height", "section_gap", "subtotal_gap",
                "indent_level_1", "indent_level_2"}


@pytest.fixture
def spaced_pdf(tmp_path):
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    for i in range(25):
        y = 750 - i * 14
        page.insert_text((72, y), f"Row {i + 1}")
        page.insert_text((380, y), f"{(i + 1) * 1000:,}")
    page.insert_text((72, 750 - 25 * 14 - 28), "TOTAL ASSETS")
    pdf_path = tmp_path / "spaced.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_analyze_precise_returns_spacing_key(spaced_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert "spacing" in result


def test_spacing_has_required_sub_keys(spaced_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert set(result["spacing"].keys()) == SPACING_KEYS


def test_row_height_is_positive(spaced_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert result["spacing"]["row_height"] > 0


def test_section_gap_greater_than_row_height(spaced_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert result["spacing"]["section_gap"] >= result["spacing"]["row_height"]


def test_row_height_within_tolerance(spaced_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert abs(result["spacing"]["row_height"] - 14) <= 3, (
        f"row_height={result['spacing']['row_height']}, expected ~14"
    )


def test_indent_levels_positive(spaced_pdf):
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert result["spacing"]["indent_level_1"] > 0
    assert result["spacing"]["indent_level_2"] > 0


def test_spacing_fallback_on_empty_pdf(tmp_path):
    import fitz
    from core.template_analyzer import TemplateAnalyzer
    doc = fitz.open()
    doc.new_page(width=595.28, height=841.89)
    pdf_path = tmp_path / "empty.pdf"
    doc.save(str(pdf_path))
    doc.close()
    result = TemplateAnalyzer().analyze_precise(str(pdf_path))
    assert result["spacing"]["row_height"] > 0


def test_spacing_real_pdf():
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(REFERENCE_PDF)
    assert 5 <= result["spacing"]["row_height"] <= 20
