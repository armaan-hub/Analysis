"""Tests for TemplateAnalyzer PDF extraction."""
import pytest
from pathlib import Path

from core.template_analyzer import TemplateAnalyzer


REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)


@pytest.fixture
def analyzer():
    return TemplateAnalyzer()


def test_extract_page_dimensions_fallback(analyzer):
    """Should return fallback config when file not found."""
    config = analyzer.analyze("nonexistent_file.pdf")
    assert "page" in config
    assert config["page"]["width"] > 0
    assert config["page"]["height"] > 0


def test_extract_page_dimensions_from_real_pdf(analyzer):
    """Extract dimensions from reference PDF if available."""
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    
    config = analyzer.analyze(REFERENCE_PDF)
    assert config["page"]["width"] > 0
    assert config["page"]["height"] > 0
    assert config["page"]["unit"] == "points"


def test_config_has_required_keys(analyzer):
    """Config must always have required keys."""
    config = analyzer.analyze("nonexistent.pdf")
    required = ["page", "margins", "fonts", "tables", "sections", "confidence"]
    for key in required:
        assert key in config, f"Missing key: {key}"


def test_fonts_structure(analyzer):
    """Fonts dict must have heading, body, footer keys."""
    config = analyzer.analyze("nonexistent.pdf")
    fonts = config["fonts"]
    for key in ("heading", "body", "footer"):
        assert key in fonts
        assert "size" in fonts[key]
        assert "family" in fonts[key]


def test_analyze_reference_pdf_returns_confident_result(analyzer):
    """When analyzing real PDF, confidence should be > 0."""
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    
    config = analyzer.analyze(REFERENCE_PDF)
    assert config["confidence"] > 0
    assert config["page_count"] > 0
    assert len(config["sections"]) > 0
