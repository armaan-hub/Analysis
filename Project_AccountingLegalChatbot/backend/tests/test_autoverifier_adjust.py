"""Tests for AutoVerifier — 85-95% score triggers auto-adjust pass."""
import pytest
import numpy as np
from PIL import Image


def _make_image(value: int, size=(600, 500)) -> Image.Image:
    arr = np.full(size, value, dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def test_auto_adjust_triggers_on_mid_score(monkeypatch):
    from core.auto_verifier import AutoVerifier
    ref_img = _make_image(0, size=(600, 500))
    test_arr_1 = np.zeros((600, 500), dtype=np.uint8)
    test_arr_1[:60, :] = 255
    test_img_1 = Image.fromarray(test_arr_1, mode="L")
    test_img_2 = _make_image(0, size=(600, 500))
    call_count = [0]

    def fake_render(config):
        return b"fake"

    def fake_bytes_to_image(b):
        call_count[0] += 1
        return test_img_1 if call_count[0] == 1 else test_img_2

    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", fake_render)
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", fake_bytes_to_image)

    config = {
        "page": {"width": 595.28, "height": 841.89},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0, "label_col_x": 72.0,
                    "notes_col_x": 0.0, "currency_label_y": 0.0},
        "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                    "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        "fonts": {},
    }
    result = verifier.verify(config, "fake.pdf")
    assert result["status"] == "verified"
    assert result["adjusted"] is True
    assert result["confidence"] >= 0.95
    assert call_count[0] == 2


def test_auto_adjust_falls_through_to_hints_if_still_failing(monkeypatch):
    from core.auto_verifier import AutoVerifier
    ref_img = _make_image(0, size=(600, 500))
    test_arr = np.zeros((600, 500), dtype=np.uint8)
    test_arr[:60, :] = 255
    test_img = Image.fromarray(test_arr, mode="L")
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)
    config = {"page": {}, "margins": {}, "columns": {}, "spacing": {}, "fonts": {}}
    result = verifier.verify(config, "fake.pdf")
    assert result["status"] == "needs_review"
    assert result["hints"] is not None


def test_auto_adjust_modifies_config_for_worst_band():
    from core.auto_verifier import AutoVerifier
    ref_arr = np.zeros((600, 500), dtype=np.uint8)
    test_arr = np.zeros((600, 500), dtype=np.uint8)
    test_arr[:100, :] = 255
    ref_img = Image.fromarray(ref_arr, mode="L")
    test_img = Image.fromarray(test_arr, mode="L")
    original_config = {
        "margins": {"top": 72}, "columns": {"year1_col_x": 380.0},
        "spacing": {"row_height": 14.0},
    }
    verifier = AutoVerifier()
    adj = verifier._auto_adjust(original_config, ref_img, test_img)
    assert adj["margins"]["top"] > original_config["margins"]["top"]
    assert adj["columns"]["year1_col_x"] == 380.0
    assert adj["spacing"]["row_height"] == 14.0
