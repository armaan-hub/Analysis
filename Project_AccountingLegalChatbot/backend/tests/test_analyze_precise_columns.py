"""Tests for TemplateAnalyzer.analyze_precise() — column x-position detection."""
import pytest
from pathlib import Path

REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)

COLUMN_KEYS = {"label_col_x", "notes_col_x", "year1_col_x", "year2_col_x", "currency_label_y"}


@pytest.fixture
def two_column_pdf(tmp_path):
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    for y in range(700, 400, -14):
        page.insert_text((72, y), "Some line item")
        page.insert_text((380, y), f"{(y * 100):,}")
        page.insert_text((460, y), f"{(y * 90):,}")
    pdf_path = tmp_path / "two_col.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_analyze_precise_returns_columns_key(two_column_pdf):
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert "columns" in result


def test_columns_has_required_sub_keys(two_column_pdf):
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert set(result["columns"].keys()) == COLUMN_KEYS


def test_columns_are_floats(two_column_pdf):
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    for key in ("year1_col_x", "year2_col_x"):
        assert isinstance(result["columns"][key], float)


def test_year1_col_within_tolerance(two_column_pdf):
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert abs(result["columns"]["year1_col_x"] - 380) <= 10, (
        f"year1_col_x={result['columns']['year1_col_x']}, expected ~380"
    )


def test_year2_col_within_tolerance(two_column_pdf):
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert abs(result["columns"]["year2_col_x"] - 460) <= 10, (
        f"year2_col_x={result['columns']['year2_col_x']}, expected ~460"
    )


def test_columns_fallback_on_sparse_pdf(tmp_path):
    import fitz
    from core.template_analyzer import TemplateAnalyzer
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((72, 700), "Only text, no numbers here")
    pdf_path = tmp_path / "sparse.pdf"
    doc.save(str(pdf_path))
    doc.close()
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(str(pdf_path))
    assert "columns" in result
    assert result["columns"]["year1_col_x"] > 0


def test_analyze_precise_nonexistent_file():
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise("nonexistent.pdf")
    assert "columns" in result


def test_analyze_precise_real_pdf_columns():
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(REFERENCE_PDF)
    cols = result["columns"]
    assert cols["year1_col_x"] > 300
    assert cols["year2_col_x"] > cols["year1_col_x"]
