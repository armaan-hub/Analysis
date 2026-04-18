"""
Tests for POST /api/templates/upload-reference?fast_learn=true.
Uses conftest.py client fixture (in-memory DB, ASGITransport).
"""
import pytest
from unittest.mock import MagicMock, patch


FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
_VERIFIED_RESULT = {"status": "verified", "confidence": 0.97, "hints": None, "adjusted": False}
_REVIEW_RESULT = {"status": "needs_review", "confidence": 0.72, "hints": [
    {"element": "columns", "message": "Column offset", "options": ["shift left 6pt", "leave as-is"]}
], "adjusted": False}


@pytest.mark.asyncio
async def test_fast_learn_returns_new_response_schema(client):
    """fast_learn=true returns template_id, status, confidence, time_taken_sec, match_source."""
    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        mock_ff = MockFF.return_value
        mock_ff.match.return_value = (None, 50, None)  # No prebuilt match
        mock_ff.fingerprint.return_value = {}

        mock_ta = MockTA.return_value
        mock_ta.analyze_precise.return_value = {
            "page": {"width": 595.28, "height": 841.89}, "margins": {}, "fonts": {},
            "tables": [], "sections": [], "confidence": 0.9,
            "source": "test.pdf", "page_count": 5,
            "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0, "label_col_x": 72.0,
                        "notes_col_x": 310.0, "currency_label_y": 0.0},
            "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                        "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        }

        mock_av = MockAV.return_value
        mock_av.verify.return_value = _VERIFIED_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("audit.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "name": "Test Fast Template", "user_id": "user1"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "template_id" in data
    assert "status" in data
    assert "confidence" in data
    assert "time_taken_sec" in data
    assert "match_source" in data
    assert data["status"] in ("verified", "needs_review")


@pytest.mark.asyncio
async def test_fast_learn_verified_status_returns_null_hints(client):
    """When status=verified, hints is null."""
    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        MockFF.return_value.match.return_value = (None, 40, None)
        MockFF.return_value.fingerprint.return_value = {}
        MockTA.return_value.analyze_precise.return_value = {
            "page": {}, "margins": {}, "fonts": {}, "tables": [], "sections": [],
            "confidence": 0.9, "source": "t.pdf", "page_count": 3,
            "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0,
                        "label_col_x": 72.0, "notes_col_x": 0.0, "currency_label_y": 0.0},
            "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                        "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        }
        MockAV.return_value.verify.return_value = _VERIFIED_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("a.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "user_id": "u1"},
        )

    data = resp.json()
    assert data["hints"] is None


@pytest.mark.asyncio
async def test_fast_learn_needs_review_returns_hints(client):
    """When status=needs_review, hints array is present."""
    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        MockFF.return_value.match.return_value = (None, 30, None)
        MockFF.return_value.fingerprint.return_value = {}
        MockTA.return_value.analyze_precise.return_value = {
            "page": {}, "margins": {}, "fonts": {}, "tables": [], "sections": [],
            "confidence": 0.5, "source": "t.pdf", "page_count": 2,
            "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0,
                        "label_col_x": 72.0, "notes_col_x": 0.0, "currency_label_y": 0.0},
            "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                        "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        }
        MockAV.return_value.verify.return_value = _REVIEW_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("b.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "user_id": "u2"},
        )

    data = resp.json()
    assert data["hints"] is not None
    assert len(data["hints"]) >= 1


@pytest.mark.asyncio
async def test_fast_learn_prebuilt_match_skips_analyze(client):
    """When fingerprint score >=88, analyze_precise() is NOT called."""
    from core.prebuilt_formats import PREBUILT_FORMATS

    cloned_config = PREBUILT_FORMATS[0]["config"]

    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        MockFF.return_value.match.return_value = (cloned_config, 95, "prebuilt-gcc-standard")
        MockFF.return_value.fingerprint.return_value = {}
        MockAV.return_value.verify.return_value = _VERIFIED_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("c.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "user_id": "u3"},
        )

    data = resp.json()
    assert data.get("status_code", resp.status_code) == 200
    assert MockTA.return_value.analyze_precise.call_count == 0
    assert data.get("match_source") == "prebuilt-gcc-standard"
