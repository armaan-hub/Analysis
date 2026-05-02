"""
Tests for account_placement_engine.place_accounts_with_template().
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.account_placement_engine import place_accounts_with_template


# ── Helpers ───────────────────────────────────────────────────────────────────

SAMPLE_TEMPLATE = {
    "account_grouping": {
        "Non-Current Assets": [
            {"account_name": "Property, Plant & Equipment", "account_code": None, "indent_level": 1, "is_subtotal": False, "is_total": False},
            {"account_name": "Building", "account_code": None, "indent_level": 2, "is_subtotal": False, "is_total": False},
        ],
        "Current Assets": [
            {"account_name": "Trade Receivables", "account_code": None, "indent_level": 1, "is_subtotal": False, "is_total": False},
            {"account_name": "Cash and Bank", "account_code": None, "indent_level": 1, "is_subtotal": False, "is_total": False},
        ],
        "Current Liabilities": [
            {"account_name": "Trade Payables", "account_code": None, "indent_level": 1, "is_subtotal": False, "is_total": False},
        ],
    }
}


def _make_account(name: str, category: str = "assets") -> dict:
    return {
        "account_name": name,
        "account_code": None,
        "debit": 100.0,
        "credit": 0.0,
        "net": 100.0,
        "category": category,
    }


def _mock_llm_provider(content: str):
    """Return a patched context manager that stubs get_llm_provider."""
    mock_response = MagicMock()
    mock_response.content = content

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(return_value=mock_response)

    return patch(
        "core.account_placement_engine.get_llm_provider",
        return_value=mock_provider,
    )


def _mock_llm_failure():
    """Return a patched context manager where LLM always raises."""
    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    return patch(
        "core.account_placement_engine.get_llm_provider",
        return_value=mock_provider,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_template_match():
    """Account that exists in the template is matched at 0.95 confidence."""
    accounts = [_make_account("Trade Receivables")]
    with _mock_llm_failure():
        result = await place_accounts_with_template(accounts, SAMPLE_TEMPLATE)

    assert len(result) == 1
    r = result[0]
    assert r["section"] == "Current Assets"
    assert r["confidence"] == 0.95
    assert r["placement_method"] == "template_match"
    assert r["needs_review"] is False


@pytest.mark.asyncio
async def test_template_match_normalisation():
    """Matching is case-insensitive and ignores special chars."""
    accounts = [_make_account("  trade  receivables ")]
    with _mock_llm_failure():
        result = await place_accounts_with_template(accounts, SAMPLE_TEMPLATE)

    assert result[0]["placement_method"] == "template_match"
    assert result[0]["confidence"] == 0.95


@pytest.mark.asyncio
async def test_fuzzy_match():
    """Slightly different name (e.g. 'Cash at Bank' vs 'Cash and Bank') → fuzzy match."""
    accounts = [_make_account("Cash at Bank")]
    with _mock_llm_failure():
        result = await place_accounts_with_template(accounts, SAMPLE_TEMPLATE)

    r = result[0]
    assert r["section"] == "Current Assets"
    assert r["confidence"] == 0.85
    assert r["placement_method"] == "fuzzy_match"
    assert r["needs_review"] is False


@pytest.mark.asyncio
async def test_llm_classification():
    """Account not in template → LLM classifies it."""
    accounts = [_make_account("Goodwill", category="assets")]
    llm_json = '{"section": "Non-Current Assets", "indent_level": 1, "confidence": 0.88, "reasoning": "Intangible asset"}'

    with _mock_llm_provider(llm_json):
        result = await place_accounts_with_template(accounts, SAMPLE_TEMPLATE)

    r = result[0]
    assert r["section"] == "Non-Current Assets"
    assert r["confidence"] == 0.88
    assert r["placement_method"] == "llm_classification"
    assert r["needs_review"] is False


@pytest.mark.asyncio
async def test_unmatched_account_flagged():
    """Account not in template and LLM fails → keyword fallback, flagged for review."""
    accounts = [_make_account("Mysterious Account XYZ", category="other")]

    with _mock_llm_failure():
        result = await place_accounts_with_template(accounts, SAMPLE_TEMPLATE)

    r = result[0]
    assert r["placement_method"] == "keyword_fallback"
    assert r["confidence"] == 0.50
    assert r["needs_review"] is True


@pytest.mark.asyncio
async def test_empty_template():
    """Empty template → all accounts end up in fallback and flagged for review."""
    accounts = [_make_account("Trade Receivables")]
    empty_template: dict = {"account_grouping": {}}

    with _mock_llm_failure():
        result = await place_accounts_with_template(accounts, empty_template)

    assert len(result) == 1
    assert result[0]["needs_review"] is True
    assert result[0]["confidence"] < 0.80


@pytest.mark.asyncio
async def test_empty_accounts():
    """Empty accounts list → returns empty list."""
    result = await place_accounts_with_template([], SAMPLE_TEMPLATE)
    assert result == []


@pytest.mark.asyncio
async def test_confidence_threshold():
    """Accounts with confidence < 0.80 have needs_review=True, others False."""
    accounts = [
        _make_account("Trade Receivables"),           # will template match → 0.95
        _make_account("Unknown Thing", "other"),      # will fallback → 0.50
    ]

    with _mock_llm_failure():
        result = await place_accounts_with_template(accounts, SAMPLE_TEMPLATE)

    high = next(r for r in result if r["account_name"] == "Trade Receivables")
    low = next(r for r in result if r["account_name"] == "Unknown Thing")

    assert high["needs_review"] is False
    assert high["confidence"] >= 0.80

    assert low["needs_review"] is True
    assert low["confidence"] < 0.80


@pytest.mark.asyncio
async def test_missing_account_grouping_key():
    """Template without 'account_grouping' key → treated as empty template."""
    accounts = [_make_account("Cash and Bank")]

    with _mock_llm_failure():
        result = await place_accounts_with_template(accounts, {})

    assert len(result) == 1
    assert result[0]["needs_review"] is True


def test_group_tb_for_ifrs_produces_correct_structure():
    from core.agents.trial_balance_classifier import group_tb_for_ifrs

    tb_data = [
        {"account": "Cash in Hand", "mappedTo": "Current Assets", "amount": 10000},
        {"account": "Bank Account", "mappedTo": "Current Assets", "amount": 50000},
        {"account": "Fixed Assets", "mappedTo": "Non-Current Assets", "amount": 200000},
        {"account": "Sundry Creditors", "mappedTo": "Current Liabilities", "amount": -30000},
        {"account": "Capital Account", "mappedTo": "Equity", "amount": -100000},
        {"account": "Commission Revenue", "mappedTo": "Revenue", "amount": -500000},
        {"account": "Salary Expense", "mappedTo": "Operating Expenses", "amount": 80000},
    ]

    grouped = group_tb_for_ifrs(tb_data)

    assert "current_assets" in grouped
    assert "non_current_assets" in grouped
    assert "current_liabilities" in grouped
    assert "equity" in grouped
    assert "revenue" in grouped
    assert "operating_expenses" in grouped

    assert grouped["current_assets"]["total"] == 60000
    assert grouped["non_current_assets"]["total"] == 200000
    assert abs(grouped["current_liabilities"]["total"]) == 30000

    assert len(grouped["current_assets"]["rows"]) == 2
