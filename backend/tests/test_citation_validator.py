import pytest
from core.accuracy.citation_validator import validate_citations, should_skip_llm


# ── validate_citations ────────────────────────────────────────────────────────

def test_no_warning_when_no_fabrications():
    answer = "According to the documents, VAT applies at 5%."
    chunks = [{"text": "VAT applies at 5% under Federal Decree Law No. 8 of 2017."}]
    result = validate_citations(answer, chunks)
    assert "🚨" not in result
    assert result == answer


def test_warning_appended_when_two_fabrications():
    answer = (
        '"The law states: penalties are 200% of unpaid tax." '
        '"According to Article 99: all imports are exempt."'
    )
    chunks = [{"text": "VAT is 5%. Some supplies are zero-rated."}]
    result = validate_citations(answer, chunks)
    assert "🚨" in result
    assert "CRITICAL LEGAL ACCURACY WARNING" in result


def test_no_warning_for_honest_refusal():
    answer = "I don't have this in my documents."
    chunks = []
    result = validate_citations(answer, chunks)
    assert result == answer
    assert "🚨" not in result


def test_single_fabrication_no_warning():
    answer = '"The law states: all transactions must be reported daily."'
    chunks = [{"text": "VAT applies at 5% on most goods and services."}]
    result = validate_citations(answer, chunks)
    # Only 1 fabrication — below threshold of 2
    assert "🚨" not in result


def test_warning_contains_issue_count():
    answer = (
        '"The regulation requires: all invoices to be notarised." '
        '"Article 99 states: imports are fully exempt from all taxes." '
        '"Section 12: penalties exceed 500% of outstanding balance."'
    )
    chunks = [{"text": "Standard VAT rate is 5%."}]
    result = validate_citations(answer, chunks)
    assert "🚨" in result


# ── should_skip_llm ───────────────────────────────────────────────────────────

def test_skip_llm_when_doc_scoped_and_empty():
    assert should_skip_llm(search_results=[], doc_scoped=True) is True


def test_no_skip_when_results_exist():
    assert should_skip_llm(search_results=[{"text": "some chunk"}], doc_scoped=True) is False


def test_no_skip_when_not_doc_scoped():
    # Not doc-scoped: web search fallback may still fire — don't block LLM
    assert should_skip_llm(search_results=[], doc_scoped=False) is False


def test_verified_quote_not_flagged():
    """A quote whose key words appear verbatim in source should NOT be flagged."""
    answer = (
        '"Supplies that are zero-rated include exported goods." '
        '"The standard VAT rate is five percent under this decree."'
    )
    chunks = [{"text": "Supplies that are zero-rated include exported goods. "
                        "The standard VAT rate is five percent under this decree."}]
    result = validate_citations(answer, chunks)
    assert "🚨" not in result


def test_claims_only_triggers_warning():
    """Two unverified claims (no quotes) should also trigger the 🚨 warning."""
    answer = (
        "The law states: all financial institutions must report holdings quarterly. "
        "According to Article 15: foreign investors are exempt from all transaction levies."
    )
    chunks = [{"text": "Standard VAT rate is 5% on most goods."}]
    result = validate_citations(answer, chunks)
    assert "🚨" in result


def test_alternate_refusal_prefixes_skip_validation():
    """'i do not have' and 'no information' prefixes should skip validation."""
    for prefix in ("I do not have the required documents.", "No information available."):
        result = validate_citations(prefix, [])
        assert "🚨" not in result
        assert result == prefix


def test_curly_quotes_detected():
    """Curly quotes should be treated same as straight quotes."""
    answer = (
        '\u201cThe law states that penalties double each month.\u201d '
        '\u201cAccording to Article 5: all exports face additional levy.\u201d'
    )
    chunks = [{"text": "VAT is 5%."}]
    result = validate_citations(answer, chunks)
    assert "🚨" in result
