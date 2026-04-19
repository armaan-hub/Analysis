"""Tests for the route_prompt function."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.prompt_router import route_prompt
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
