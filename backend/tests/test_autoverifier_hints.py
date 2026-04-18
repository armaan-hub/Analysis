"""Tests for AutoVerifier — <85% score returns StructuredHints."""
import pytest
import numpy as np
from PIL import Image


def _make_image(value: int, size=(600, 500)) -> Image.Image:
    arr = np.full(size, value, dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def test_hints_returned_when_score_below_85(monkeypatch):
    from core.auto_verifier import AutoVerifier
    ref_img = _make_image(0)
    test_img = _make_image(255)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)
    result = verifier.verify({}, "fake.pdf")
    assert result["status"] == "needs_review"
    assert result["hints"] is not None
    assert len(result["hints"]) >= 1


def test_hints_have_required_keys(monkeypatch):
    from core.auto_verifier import AutoVerifier
    ref_img = _make_image(0)
    test_img = _make_image(255)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)
    result = verifier.verify({}, "fake.pdf")
    for hint in result["hints"]:
        assert "element" in hint
        assert "message" in hint
        assert "options" in hint
        assert isinstance(hint["options"], list)
        assert len(hint["options"]) == 2


def test_hints_options_are_non_empty_strings(monkeypatch):
    from core.auto_verifier import AutoVerifier
    ref_img = _make_image(0)
    test_img = _make_image(255)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)
    result = verifier.verify({}, "fake.pdf")
    for hint in result["hints"]:
        for option in hint["options"]:
            assert isinstance(option, str) and len(option) > 0


def test_generate_hints_returns_fallback_when_no_bad_bands():
    from core.auto_verifier import AutoVerifier
    same = _make_image(128)
    verifier = AutoVerifier()
    hints = verifier._generate_hints({}, same, same, 0.80)
    assert len(hints) >= 1


def test_pdf_open_failure_returns_needs_review():
    from core.auto_verifier import AutoVerifier
    verifier = AutoVerifier()
    result = verifier.verify({}, "totally_nonexistent_file.pdf")
    assert result["status"] == "needs_review"
    assert result["confidence"] == 0.75
    assert result["hints"] is None
