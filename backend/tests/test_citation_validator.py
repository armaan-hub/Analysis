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
