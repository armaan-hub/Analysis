# RAG Domain Adaptive Retrieval — Design Spec
**Date:** 2026-04-28  
**Status:** Approved  
**Topic:** Fix wrong RAG sources for wills/estate/general-law queries

---

## Problem

When a user asks "Draft Wills for 10 Million Estate and Properties", the chatbot returns irrelevant sources (e.g., `VATP035 - Criteria Pieces and Parts Electronic Devices`) with low scores (0.649–0.672) instead of the correct UAE Civil Transactions Law and Family Company Law documents.

**Root causes:**

1. **Domain misclassification** — The LLM domain classifier sees "estate" and "properties" and maps to `vat` (because UAE real estate has VAT implications). There are no wills/inheritance examples in the classifier prompt.
2. **Hard domain filter applied** — Once classified as `vat`, the RAG filter `{"domain": "vat"}` restricts search to VAT documents only.
3. **Low min_score (0.30)** — Noise documents with marginal similarity pass through, appearing as "sources."
4. **No fallback mechanism** — When domain-filtered results are poor, the system does not retry with a broader search.

---

## Design

### Architecture: Smart Adaptive Retrieval

```
Query
  └─► Domain Classifier (LLM + keyword fallback)
        ├─ If "general_law" → no domain filter → search all law+finance docs
        └─ If specific domain (vat, ct, ...) → apply domain filter
              └─► RAG Search with filter
                    ├─ top score ≥ 0.65 → use results ✅
                    └─ top score < 0.65 → FALLBACK: retry without domain filter
                          └─► RAG Search (broad: all law+finance)
                                └─► Return best results
```

---

## Changes

### 1. `backend/core/chat/prompts/domain_classifier.md`
Add three examples anchoring wills/estate/inheritance to `general_law`:

```
Q: "Draft a will for a 10 million estate and properties"
A: {"domain": "general_law", "confidence": 0.92, "alternatives": [["commercial", 0.05]]}

Q: "UAE inheritance law for expatriate with property in Dubai"
A: {"domain": "general_law", "confidence": 0.93, "alternatives": [["commercial", 0.04]]}

Q: "How to register a DIFC will for estate worth 5 million dirhams"
A: {"domain": "general_law", "confidence": 0.91, "alternatives": [["commercial", 0.06]]}
```

**Why:** The LLM domain classifier has no wills/inheritance examples. Adding them prevents "estate" and "properties" from being misclassified as `vat`.

---

### 2. `backend/core/chat/domain_classifier.py`
Add `general_law` keywords to `_DOMAIN_KEYWORDS` **before** any ambiguous terms:

```python
"general_law": [
    "wills", "will and testament", "inheritance", "inherit",
    "probate", "testator", "beneficiary", "estate planning",
    "succession", "guardian appointment",
],
```

Insert these before the VAT check in `_FLAT_KEYWORDS_SORTED` (longest-first sort handles priority automatically via the sort key).

**Why:** Provides a keyword-based safety net when the LLM classifier fails or is bypassed.

---

### 3. `backend/api/chat.py`
Add a **broad-search fallback** after the domain-filtered RAG search:

```python
# Adaptive fallback: if domain-filtered results are poor, retry without domain filter
_BROAD_FALLBACK_THRESHOLD = 0.65

if (_rag_filter and _search_results and
        max(r.get("score", 0) for r in _search_results) < _BROAD_FALLBACK_THRESHOLD):
    logger.info("RAG domain-filtered results below threshold (%.3f) — retrying with broad search",
                max(r.get("score", 0) for r in _search_results))
    _broad_filter = {"category": {"$in": ["law", "finance"]}}
    try:
        _broad_results = await rag_engine.search(
            req.message,
            top_k=settings.fast_top_k if req.mode == "fast" else settings.top_k_results,
            filter=_broad_filter,
            min_score=settings.rag_min_score,
        )
        if _broad_results and max(r.get("score", 0) for r in _broad_results) > max(r.get("score", 0) for r in _search_results):
            _search_results = _broad_results
            logger.info("Broad fallback improved results — now using %d results", len(_search_results))
    except Exception as _fallback_exc:
        logger.warning("Broad fallback search failed (non-fatal): %s", _fallback_exc)
```

Apply this fallback in both the streaming (`generate()`) and non-streaming paths.

**Why:** Self-corrects when classifier is wrong. Even if `vat` is misclassified, if VAT results score < 0.65, the system retries with all law/finance docs and cites the correct ones.

---

### 4. `chat_history_viewer.py`
Add `⚠️ low-confidence` label for sources with score < 0.65:

```python
score_str = f"  score={score:.3f}" if score is not None else ""
if score is not None and score < 0.65:
    score_str += "  ⚠️ low-confidence"
```

**Why:** Transparency — users and developers can immediately see when sources are weakly matched.

---

## What the fix delivers

| Query | Before | After |
|---|---|---|
| "Draft Wills for 10M Estate" | 15 VAT + Electronic Device sources (score 0.649–0.672) | UAE Civil Transactions Law, Family Company Law (score 0.75+) |
| "Inheritance law UAE expatriate" | Routed to vat → wrong | Routed to general_law → correct law docs |
| Clear VAT query ("How do I file VAT?") | No change | No change |

---

## Constraints

- No structural changes to RAG engine or embedding pipeline
- No new API endpoints
- Tests for `rag_min_score = 0.30` must continue to pass (we are NOT changing min_score globally)
- The fallback only triggers when domain filter was applied AND results are poor — it cannot cause regressions on well-matched queries

---

## Testing

- Unit test: `domain_classifier` returns `general_law` for "Draft Wills" query
- Unit test: fallback logic triggers when mock results score < 0.65
- Manual smoke test: ask chatbot "Draft Wills for 10 Million Estate" → verify sources are from Civil Transactions Law / Family Company Law
