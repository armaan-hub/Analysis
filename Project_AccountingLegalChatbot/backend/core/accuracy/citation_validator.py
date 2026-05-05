"""
Citation Validator — anti-hallucination guard for LLM answers.

validate_citations(): scans for unverified quotes/claims, appends 🚨 warning if 2+ found.
should_skip_llm(): returns True when doc-scoped RAG returned no results (honest refusal).
"""

import re

_NO_VALIDATE_PREFIXES = ("i don't have", "i do not have", "no information")
_FABRICATION_THRESHOLD = 2

# Capture only substantial claim text (≥30 chars) to avoid matching
# short, benign phrases like "The act states: see above."
_CLAIM_PATTERNS = [
    r'the (?:law|regulation|act|decree|rule) (?:states?|says?|provides?|requires?|mandates?)[:\s]+([^.]{30,})',
    r'according to (?:article|section|clause|paragraph)\s+[\w\d]+[:\s]+([^.]{30,})',
]


def _is_grounded(words: list[str], text: str, min_hits: int = 2) -> bool:
    """Return True only if at least min_hits substantive words (len>3) appear
    as whole words in text. Requires min_hits=2 to reduce false passes on
    shared legal vocabulary like 'rate', 'rule', 'code'."""
    hits = sum(
        1 for w in words
        if len(w) > 3 and re.search(r'\b' + re.escape(w) + r'\b', text)
    )
    return hits >= min_hits


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

    # Track ALL quoted spans to prevent claim patterns from double-firing
    all_quoted_spans: list[tuple[int, int]] = []

    # Check quoted text (straight and curly quotes)
    for match in re.finditer(r'["\u201c\u201d]([^"\u201c\u201d]{10,})["\u201c\u201d]', answer):
        all_quoted_spans.append((match.start(), match.end()))
        quote = match.group(1)
        words = quote.lower().split()[:8]
        if not _is_grounded(words, combined):
            unverified_quotes += 1

    # Check claim patterns — skip if the match falls inside a quoted span
    for pattern in _CLAIM_PATTERNS:
        for m in re.finditer(pattern, answer, re.IGNORECASE):
            match_start = m.start()
            is_in_quote = any(q_start <= match_start < q_end for q_start, q_end in all_quoted_spans)
            if is_in_quote:
                continue
            claim_words = m.group(1).lower().split()[:8]
            if not _is_grounded(claim_words, combined):
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


def strip_hallucinated_urls(answer: str, allowed_urls: set[str]) -> str:
    """Replace markdown hyperlinks whose URLs are NOT in allowed_urls with plain text.

    Keeps the link label so the answer remains readable; only removes the URL
    when the LLM invented a link that was not in the supplied source list.
    """
    if not allowed_urls:
        return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', answer)

    def _replace(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        return m.group(0) if url in allowed_urls else label

    return re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', _replace, answer)


def should_skip_llm(search_results: list, doc_scoped: bool) -> bool:
    """Return True when LLM should NOT be called.

    Fires only for doc-scoped queries (user explicitly selected documents)
    that return zero RAG chunks — honest refusal is better than hallucination.
    """
    return doc_scoped and len(search_results) == 0
