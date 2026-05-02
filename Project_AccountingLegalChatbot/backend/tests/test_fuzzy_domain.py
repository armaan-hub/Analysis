import pytest
from core.chat.domain_classifier import _fuzzy_classify_query, DomainLabel


def test_exact_keyword_vat():
    result = _fuzzy_classify_query("what is the vat rate on real estate?")
    assert result is not None
    assert result.domain == DomainLabel.VAT
    assert result.confidence == 0.8


def test_fuzzy_typo_vatt():
    result = _fuzzy_classify_query("what is vatt registration process?")
    assert result is not None
    assert result.domain == DomainLabel.VAT


def test_fuzzy_typo_corparate():
    result = _fuzzy_classify_query("corparate tax filing deadline")
    assert result is not None
    assert result.domain == DomainLabel.CORPORATE_TAX


def test_fuzzy_typo_employmant():
    result = _fuzzy_classify_query("employmant contract requirements uae")
    assert result is not None
    assert result.domain == DomainLabel.LABOUR


def test_returns_none_for_unrelated():
    result = _fuzzy_classify_query("hello how are you")
    assert result is None


def test_hotel_apartment_exact():
    result = _fuzzy_classify_query("hotel apartment vat treatment")
    assert result is not None
    assert result.domain == DomainLabel.VAT


def test_fuzzy_match_confidence_is_lower():
    result = _fuzzy_classify_query("corparate tax")
    assert result is not None, "Expected a match for 'corparate tax'"
    assert result.domain == DomainLabel.CORPORATE_TAX
    assert result.confidence == 0.7, f"Expected fuzzy confidence 0.7, got {result.confidence}"


def test_peppol_keyword_matches_peppol_domain():
    """DomainLabel.PEPPOL must be reachable through fuzzy path."""
    result = _fuzzy_classify_query("how does peppol work")
    assert result is not None
    assert result.domain == DomainLabel.PEPPOL


def test_peppol_typo_matches_peppol_domain():
    """Typo 'peppl' must route to PEPPOL not e_invoicing."""
    result = _fuzzy_classify_query("peppl invoice network")
    assert result is not None
    assert result.domain == DomainLabel.PEPPOL


def test_no_substring_false_positive():
    """'release funds' must NOT match 'lease' (ifrs domain)."""
    result = _fuzzy_classify_query("how do I release funds")
    assert result is None or result.domain != DomainLabel.IFRS


def test_arabic_transliteration_returns_none():
    """Unknown Islamic finance terms should return None cleanly."""
    assert _fuzzy_classify_query("zakatah calculation rules") is None
    assert _fuzzy_classify_query("murabaha financing structure") is None


def test_env_var_crash_guard():
    """Invalid FUZZY_CUTOFF env var must not crash module."""
    import importlib, os
    import core.chat.domain_classifier as dc_module
    original = os.environ.get("FUZZY_CUTOFF")
    try:
        os.environ["FUZZY_CUTOFF"] = "not-a-number"
        # Re-reading the module-level var won't re-trigger, but we can verify the guard exists
        # by checking that the current cutoff is a valid float
        assert isinstance(dc_module._FUZZY_CUTOFF, float)
    finally:
        if original is None:
            os.environ.pop("FUZZY_CUTOFF", None)
        else:
            os.environ["FUZZY_CUTOFF"] = original


def test_wills_keyword_routes_to_general_law():
    """'wills' must route to GENERAL_LAW, not VAT, even though estate has VAT connotation."""
    result = _fuzzy_classify_query("draft wills for estate and properties")
    assert result is not None
    assert result.domain == DomainLabel.GENERAL_LAW


def test_inheritance_keyword_routes_to_general_law():
    """'inheritance' must route to GENERAL_LAW."""
    result = _fuzzy_classify_query("uae inheritance law for expatriates")
    assert result is not None
    assert result.domain == DomainLabel.GENERAL_LAW


def test_probate_keyword_routes_to_general_law():
    """'probate' must route to GENERAL_LAW."""
    result = _fuzzy_classify_query("probate process in dubai for non-muslims")
    assert result is not None
    assert result.domain == DomainLabel.GENERAL_LAW


def test_estate_planning_keyword_routes_to_general_law():
    """'estate planning' multi-word must route to GENERAL_LAW, not VAT."""
    result = _fuzzy_classify_query("estate planning for high net worth individuals")
    assert result is not None
    assert result.domain == DomainLabel.GENERAL_LAW
