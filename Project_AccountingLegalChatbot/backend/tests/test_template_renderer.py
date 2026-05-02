"""Tests for template renderer."""
import pytest
from core.templates.renderer import render_template, load_sample_data, _flatten


def test_load_sample_data():
    data = load_sample_data()
    assert data["company"]["name"] == "Sample Trading LLC"
    assert len(data["trial_balance"]) == 8


def test_flatten():
    flat = _flatten({"company": {"name": "Test", "trn": "123"}, "period": "2025"})
    assert flat["company_name"] == "Test"
    assert flat["company_trn"] == "123"
    assert flat["period"] == "2025"


def test_render_simple_template():
    body = "Company: ${company_name}, Period: ${period}"
    result = render_template(body)
    assert "Sample Trading LLC" in result
    assert "2025" in result


def test_render_with_custom_data():
    body = "Hello ${company_name}"
    result = render_template(body, {"company": {"name": "My Corp"}})
    assert "My Corp" in result


def test_render_missing_var_safe():
    body = "Value: ${nonexistent}"
    result = render_template(body)
    assert "${nonexistent}" in result  # safe_substitute preserves unknowns
