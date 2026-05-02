"""Tests for TemplateVerifier verification logic."""
import pytest
from core.template_verifier import TemplateVerifier


@pytest.fixture
def verifier():
    return TemplateVerifier()


def test_verify_page_dimensions_match(verifier):
    """Verification passes when dimensions match within tolerance."""
    config = {
        "page": {"width": 612, "height": 792},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "fonts": {"heading": {"family": "Helvetica-Bold", "size": 12},
                  "body": {"family": "Helvetica", "size": 9}},
        "tables": [],
        "sections": [],
    }
    result = verifier.verify_page_dimensions(config, (612, 792))
    assert result["passed"] is True
    assert result["confidence"] > 0.9


def test_verify_page_dimensions_mismatch(verifier):
    """Verification catches dimension mismatches."""
    config = {"page": {"width": 595, "height": 842}}  # A4 vs US Letter
    result = verifier.verify_page_dimensions(config, (612, 792))
    assert result["passed"] is False
    assert "mismatch" in result["message"].lower()


def test_verify_margins_match(verifier):
    """Margins match check passes when values are within tolerance."""
    config = {"margins": {"top": 72, "bottom": 72, "left": 72, "right": 72}}
    result = verifier.verify_margins(config, {"top": 72, "bottom": 72, "left": 72, "right": 72})
    assert result["passed"] is True
    assert result["confidence"] == 1.0


def test_verify_margins_mismatch(verifier):
    """Margins check catches significant deviations."""
    config = {"margins": {"top": 36, "bottom": 36, "left": 36, "right": 36}}
    result = verifier.verify_margins(config, {"top": 72, "bottom": 72, "left": 72, "right": 72})
    assert result["passed"] is False


def test_verify_fonts_ok(verifier):
    """Font check passes with valid heading and body."""
    config = {
        "fonts": {
            "heading": {"family": "Helvetica-Bold", "size": 12},
            "body": {"family": "Helvetica", "size": 9},
        }
    }
    result = verifier.verify_fonts(config)
    assert result["passed"] is True
    assert result["confidence"] == 1.0


def test_verify_fonts_missing(verifier):
    """Font check fails when fonts are empty."""
    config = {"fonts": {}}
    result = verifier.verify_fonts(config)
    assert result["passed"] is False


def test_verification_report_structure(verifier):
    """Verification report has required keys and structure."""
    config = {
        "page": {"width": 612, "height": 792},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "fonts": {"heading": {"family": "Helvetica-Bold", "size": 12},
                  "body": {"family": "Helvetica", "size": 9}},
        "tables": [],
        "sections": [{"name": "cover", "page": 1}],
    }
    report = verifier.generate_report(config)
    assert "overall_passed" in report
    assert "confidence" in report
    assert "checks" in report
    assert isinstance(report["checks"], list)
    assert len(report["checks"]) == 4  # dimensions, margins, fonts, sections
    assert "summary" in report


def test_report_confidence_range(verifier):
    """Confidence is always between 0 and 1."""
    config = {
        "page": {"width": 100, "height": 100},
        "margins": {},
        "fonts": {},
        "tables": [],
        "sections": [],
    }
    report = verifier.generate_report(config)
    assert 0.0 <= report["confidence"] <= 1.0
    for check in report["checks"]:
        assert 0.0 <= check["confidence"] <= 1.0
