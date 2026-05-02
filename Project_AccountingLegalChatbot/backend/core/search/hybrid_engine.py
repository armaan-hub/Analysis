"""Hybrid search: vector over-fetch + keyword re-ranking."""

from __future__ import annotations

import re

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False

_VECTOR_WEIGHT = 0.7
_KEYWORD_WEIGHT = 0.3


def _word_in_text(word: str, text: str) -> bool:
    """Return True only if *word* appears as a whole word in *text*."""
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text))


def _keyword_score(query: str, text: str) -> float:
    """Score how well *text* matches *query* using keyword signals.

    Signals (highest wins):
      1. Exact phrase match → 1.0
      2. All query words present → 0.8
      3. Fuzzy token-set ratio (rapidfuzz) → scaled 0.0–0.7
    """
    if not query or not text:
        return 0.0
    q_lower = query.lower()
    t_lower = text.lower()
    q_words = [w for w in q_lower.split() if len(w) > 2]

    if q_words and _word_in_text(q_lower, t_lower):
        return 1.0
    if q_words and all(_word_in_text(w, t_lower) for w in q_words):
        return 0.8
    if _RAPIDFUZZ_AVAILABLE:
        ratio = _fuzz.token_set_ratio(q_lower, t_lower) / 100.0
        return min(ratio * 0.7, 0.7)
    return 0.0


def blend_results(
    query: str,
    results: list[dict],
    *,
    vector_weight: float = _VECTOR_WEIGHT,
    keyword_weight: float = _KEYWORD_WEIGHT,
) -> list[dict]:
    """Re-rank *results* by blending vector score with keyword score.

    Each result dict is expected to have:
      - "score": float  (vector similarity, higher = better)
      - "text": str     (chunk text used for keyword matching)

    Adds "hybrid_score" key; sorts descending. Does not mutate input.
    """
    if not results:
        return []
    scored = []
    for r in results:
        out = dict(r)
        out["hybrid_score"] = (
            vector_weight * float(r.get("score", 0.0))
            + keyword_weight * _keyword_score(query, r.get("text", ""))
        )
        scored.append(out)
    scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return scored
