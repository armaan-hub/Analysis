"""
Citation Validator — anti-hallucination guard for LLM answers.

validate_citations(): scans for unverified quotes/claims, appends 🚨 warning if 2+ found.
should_skip_llm(): returns True when doc-scoped RAG returned no results (honest refusal).
"""

import re

_NO_VALIDATE_PREFIXES = ("i don't have", "i do not have", "no information")
_FABRICATION_THRESHOLD = 2
_NO_CONTEXT_MESSAGE = "I don't have this in my documents."

# Patterns that indicate an unsourced claim about the law
_CLAIM_PATTERNS = [
    r'the (?:law|regulation|act|decree|rule) (?:states?|says?|provides?|requires?|mandates?)[:\s]+([^.]{30,})',
    r'according to (?:article|section|clause|paragraph)\s+[\w\d]+[:\s]+([^.]{30,})',
]


def _words_in_text(words: list[str], text: str) -> bool:
    """Return True if any substantive word (len > 3) from words appears in text."""
    return any(w in text for w in words if len(w) > 3)


def validate_citations(answer: str, chunks: list[dict]) -> str:
    """Validate LLM answer against source chunks.

    Appends 🚨 warning block if 2 or more potential fabrications are detected.
    Returns the answer unchanged if confidence is acceptable.
    """
    # Skip validation for honest refusals
    lower = answer.lower().strip()
    if any(lower.startswith(p) for p in _NO_VALIDATE_PREFIXES):
        return answer

    combined = " ".join(c.get("text", "") for c in chunks).lower()

    unverified_quotes = 0
    unverified_claims = 0

    # Check quoted text (straight and curly quotes) and track their spans
    quoted_spans = []
    for match in re.finditer(r'["\u201c\u201d]([^"\u201c\u201d]{10,})["\u201c\u201d]', answer):
        quote = match.group(1)
        words = quote.lower().split()[:5]
        if not _words_in_text(words, combined):
            unverified_quotes += 1
            quoted_spans.append((match.start(), match.end()))

    # Check claim patterns (skip if inside unverified quotes to avoid double-counting)
    for pattern in _CLAIM_PATTERNS:
        for match in re.finditer(pattern, answer, re.IGNORECASE):
            # Skip if this claim is inside an unverified quote
            match_start, match_end = match.start(), match.end()
            is_in_quote = any(q_start <= match_start < q_end for q_start, q_end in quoted_spans)
            if is_in_quote:
                continue
            
            claim_words = match.group(1).lower().split()[:6]
            if not _words_in_text(claim_words, combined):
                unverified_claims += 1

    total = unverified_quotes + unverified_claims
    if total >= _FABRICATION_THRESHOLD:
        warning = (
            f"\n\n🚨 **CRITICAL LEGAL ACCURACY WARNING:**\n"
            f"Found {total} potential issue(s):\n"
            f"• {unverified_quotes} unverified quote(s)\n"
            f"• {unverified_claims} unverified claim(s)\n"
            f"Please verify with official documents before using for compliance."
        )
        return answer + warning

    return answer


def should_skip_llm(search_results: list, doc_scoped: bool) -> bool:
    """Return True when LLM should NOT be called.

    Fires only for doc-scoped queries (user explicitly selected documents)
    that return zero RAG chunks — honest refusal is better than hallucination.
    """
    return doc_scoped and len(search_results) == 0
