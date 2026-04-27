"""Hybrid search: vector over-fetch + keyword re-ranking."""

from __future__ import annotations

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False

_VECTOR_WEIGHT = 0.7
_KEYWORD_WEIGHT = 0.3


def _keyword_score(query: str, text: str) -> float:
    """Score how well *text* matches *query* using keyword signals.

    Combines three signals:
      1. Exact phrase presence  → 1.0
      2. All query words present → 0.8
      3. Fuzzy token-set ratio  → 0.0-1.0 (scaled to 0.0-0.7, only if rapidfuzz available)
    Returns the highest signal found, clamped to [0.0, 1.0].
    """
    if not query or not text:
        return 0.0
    q_lower = query.lower()
    t_lower = text.lower()

    # Signal 1: exact phrase
    if q_lower in t_lower:
        return 1.0

    # Signal 2: all keywords present
    q_words = [w for w in q_lower.split() if len(w) > 2]
    if q_words and all(w in t_lower for w in q_words):
        return 0.8

    # Signal 3: fuzzy (rapidfuzz)
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

    The function adds a "hybrid_score" key and sorts descending.
    Original score is preserved unchanged.
    """
    if not results:
        return results

    for r in results:
        vec_score = float(r.get("score", 0.0))
        kw_score = _keyword_score(query, r.get("text", ""))
        r["hybrid_score"] = vector_weight * vec_score + keyword_weight * kw_score

    results.sort(key=lambda r: r["hybrid_score"], reverse=True)
    return results
