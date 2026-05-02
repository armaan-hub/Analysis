"""Tests for the route_prompt function."""
import pytest
from core.prompt_router import route_prompt, FEW_SHOT_EXAMPLES
from core.chat.domain_classifier import DomainLabel


def test_route_vat_returns_vat_prompt():
    p = route_prompt(DomainLabel.VAT)
    assert "vat" in p.lower() or "value-added tax" in p.lower() or "VAT" in p


def test_route_general_law_returns_general_law_prompt():
    p = route_prompt(DomainLabel.GENERAL_LAW)
    assert p  # non-empty
    assert "accounting" in p.lower() or "law" in p.lower() or "legal" in p.lower()


def test_route_all_labels_have_prompts():
    for label in DomainLabel:
        p = route_prompt(label)
        assert isinstance(p, str) and len(p) > 50, f"Missing or short prompt for {label}"


def test_router_requires_enum_not_string():
    with pytest.raises((TypeError, ValueError, KeyError)):
        route_prompt("unknown_string")  # type: ignore[arg-type]


def test_vat_prompt_contains_commercial_property_guidance():
    """VAT prompt must cover non-registered-person hotel-apartment sale workflow."""
    p = route_prompt(DomainLabel.VAT)
    assert "commercial property" in p.lower(), "VAT prompt missing 'commercial property'"
    assert "Payment of VAT on Commercial Property Sale" in p, (
        "VAT prompt missing FTA portal service name"
    )
    assert "non-registered" in p.lower(), "VAT prompt missing non-registered-person case"
    assert "tax.gov.ae" in p.lower(), "VAT prompt missing FTA portal URL (tax.gov.ae)"


def test_vat_few_shot_example_covers_hotel_apartment():
    """VAT few-shot example must mention hotel apartment and FTA portal steps."""
    ex = FEW_SHOT_EXAMPLES.get("vat", "")
    assert "hotel apartment" in ex.lower(), "VAT few-shot missing hotel apartment scenario"
    assert "tax.gov.ae" in ex.lower(), (
        "VAT few-shot missing FTA portal URL (tax.gov.ae)"
    )
    assert "title deed" in ex.lower() or "oqood" in ex.lower(), (
        "VAT few-shot missing document list"
    )
