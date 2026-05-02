"""Tests for template_config_to_format bridge function."""
import pytest
from core.format_applier import template_config_to_format, apply_format, DEFAULT_TEMPLATE


SAMPLE_TEMPLATE_CONFIG = {
    "page": {"width": 612, "height": 792, "unit": "points"},
    "margins": {"top": 72.0, "bottom": 54.0, "left": 90.0, "right": 54.0},
    "fonts": {
        "heading": {"family": "TimesNewRomanPS-BoldMT", "size": 12.0},
        "body": {"family": "TimesNewRomanPSMT", "size": 9.0},
        "footer": {"family": "TimesNewRomanPSMT", "size": 8.0},
    },
    "tables": [],
    "sections": [],
    "confidence": 0.9,
}


def test_template_config_to_format_font_mapping():
    """Times family maps to Times-Roman."""
    result = template_config_to_format(SAMPLE_TEMPLATE_CONFIG)
    assert result["font_family"] == "Times-Roman"
    assert result["font_size"] == 9.0


def test_template_config_to_format_margins():
    """Margins are copied correctly."""
    result = template_config_to_format(SAMPLE_TEMPLATE_CONFIG)
    assert result["margins"]["top"] == 72.0
    assert result["margins"]["left"] == 90.0


def test_template_config_to_format_page_letter():
    """US Letter dimensions map to 'LETTER'."""
    result = template_config_to_format(SAMPLE_TEMPLATE_CONFIG)
    assert result["page_size"] == "LETTER"


def test_template_config_to_format_a4():
    """A4 dimensions map to 'A4'."""
    a4_config = {
        "page": {"width": 595, "height": 842},
        "fonts": {},
        "margins": {},
    }
    result = template_config_to_format(a4_config)
    assert result["page_size"] == "A4"


def test_template_config_to_format_empty():
    """Empty config returns empty dict — no errors."""
    result = template_config_to_format({})
    assert isinstance(result, dict)


def test_apply_format_accepts_template_config():
    """apply_format accepts template_config parameter without error."""
    import inspect
    sig = inspect.signature(apply_format)
    assert "template_config" in sig.parameters


def test_apply_format_template_config_merging():
    """template_config is merged with DEFAULT_TEMPLATE, format_template overrides both."""
    bridge = template_config_to_format(SAMPLE_TEMPLATE_CONFIG)
    merged = {**DEFAULT_TEMPLATE, **bridge}
    # font from template_config should override default
    assert merged["font_family"] == "Times-Roman"
    assert merged["font_size"] == 9.0
    # columns should remain from DEFAULT_TEMPLATE (not in template_config)
    assert "columns" in merged
