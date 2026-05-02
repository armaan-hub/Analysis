"""Tests for AutoVerifier — pixel_similarity() and the >=95% verified path."""
import pytest
import numpy as np
from PIL import Image


def _gray_image(value: int, size=(200, 300)) -> Image.Image:
    arr = np.full(size, value, dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def test_pixel_similarity_identical_images():
    from core.auto_verifier import AutoVerifier
    img = _gray_image(128)
    result = AutoVerifier.pixel_similarity(img, img)
    assert result == 1.0


def test_pixel_similarity_opposite_images():
    from core.auto_verifier import AutoVerifier
    black = _gray_image(0)
    white = _gray_image(255)
    result = AutoVerifier.pixel_similarity(black, white)
    assert result == 0.0


def test_pixel_similarity_half_different():
    from core.auto_verifier import AutoVerifier
    black = _gray_image(0)
    mid = _gray_image(128)
    result = AutoVerifier.pixel_similarity(black, mid)
    assert 0.45 <= result <= 0.55


def test_pixel_similarity_different_sizes():
    from core.auto_verifier import AutoVerifier
    img_a = _gray_image(100, size=(100, 100))
    img_b = _gray_image(100, size=(200, 200))
    result = AutoVerifier.pixel_similarity(img_a, img_b)
    assert result > 0.99


def test_verify_returns_verified_when_images_identical(monkeypatch):
    from core.auto_verifier import AutoVerifier
    identical = _gray_image(100)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: identical)
    monkeypatch.setattr(verifier, "_render_test_page", lambda config: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: identical)
    config = {
        "page": {"width": 595.28, "height": 841.89},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0, "label_col_x": 72.0,
                    "notes_col_x": 310.0, "currency_label_y": 0.0},
        "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                    "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        "fonts": {"body": {"family": "Helvetica", "size": 9},
                  "heading": {"family": "Helvetica-Bold", "size": 12}},
    }
    result = verifier.verify(config, "fake.pdf")
    assert result["status"] == "verified"
    assert result["confidence"] >= 0.95
    assert result["hints"] is None
    assert result["adjusted"] is False


def test_verify_returns_dict_with_required_keys(monkeypatch):
    from core.auto_verifier import AutoVerifier
    identical = _gray_image(200)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: identical)
    monkeypatch.setattr(verifier, "_render_test_page", lambda config: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: identical)
    result = verifier.verify({}, "fake.pdf")
    for key in ("status", "confidence", "hints", "adjusted"):
        assert key in result, f"Missing key: {key}"


def test_verify_render_failure_returns_needs_review(monkeypatch):
    from core.auto_verifier import AutoVerifier
    def bad_render(config):
        raise RuntimeError("ReportLab failed")
    identical = _gray_image(100)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: identical)
    monkeypatch.setattr(verifier, "_render_test_page", bad_render)
    result = verifier.verify({}, "fake.pdf")
    assert result["status"] == "needs_review"
    assert result["confidence"] == 0.75
