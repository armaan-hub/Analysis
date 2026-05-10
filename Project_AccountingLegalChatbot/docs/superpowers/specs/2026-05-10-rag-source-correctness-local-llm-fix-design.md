# RAG Source Correctness + Local LLM Hallucination Fix — Design Spec

> **Date:** 2026-05-10
> **Status:** Draft

---

## Problem Statement

Two bugs confirmed from live testing:

1. **Wrong sources shown**: User asks about "E-invoicing" → gets AML/tax evasion/anti-money-laundering sources instead → answer may be correct but sources are completely irrelevant
2. **Local LLM hallucination**: Ollama and LM Studio return completely fabricated answers when using local LLMs, even though the RAG knowledge base contains relevant UAE e-invoicing documents. Cloud NVIDIA LLMs also show wrong sources (but produce correct answers).

---

## Root Cause Hypothesis

**Bug 1 — Wrong Sources:**
- Domain classifier may misclassify "E-invoicing" queries as `commercial` or `general_law` because the classifier prompt lacks explicit e-invoicing examples
- `_build_rag_domain_filter()` then applies a narrow domain filter that excludes actual e-invoicing docs
- RAG search returns irrelevant documents; cross-domain guard can't help if wrong domain was classified

**Bug 2 — Local LLM Hallucination:**
- Local LLM system prompt is too long/complex for 14B-32B parameter models to follow instruction hierarchy
- Context overflow may silently truncate RAG chunks, so model never sees the documents
- `_compute_safe_max_tokens()` may not be correctly accounting for prompt size on local models
- `build_augmented_prompt()` concatenates all RAG chunks into one giant context block — may exceed local model context windows

---

## Scope

This fix is scoped to `backend/` only. Frontend changes not required.

---

## Architecture

### New Diagnostic Endpoint: `/api/debug/rag-inspect`

A diagnostic-only endpoint that bypasses the LLM and shows the entire RAG pipeline decision tree for any query.

**Request:**
```
POST /api/debug/rag-inspect
{
  "query": "What are the UAE e-invoicing requirements?",
  "domain_override": null   // optional: force a specific domain
}
```

**Response:**
```json
{
  "query": "What are the UAE e-invoicing requirements?",
  "effective_domain": "e_invoicing",
  "domain_classifier_confidence": 0.94,
  "domain_classifier_alternatives": [["vat", 0.04], ["peppol", 0.02]],
  "rag_filter_applied": {"domain": {"$in": ["e_invoicing", "peppol", "vat", "general"]}},
  "rag_filter_applied_explanation": "domain=e_invoicing → mapped to doc_domains [e_invoicing, peppol, vat, general]",
  "rag_results_count": 8,
  "top_rag_results": [
    {
      "rank": 1,
      "source_file": "UAE_E-Invoice_Mandate.pdf",
      "domain": "e_invoicing",
      "score": 0.92,
      "combined_score": 0.89,
      "excerpt": "First 200 chars of chunk text..."
    },
    ...
  ],
  "web_search_triggered": false,
  "web_search_reason": null,
  "context_size_estimate_tokens": 1840,
  "context_safe_for_local_llm": true,
  "graph_context_used": false,
  "graph_entities_found": []
}
```

**Implementation:** New file `backend/api/debug.py` with a single endpoint.

---

### Enhanced Debug Logging (no code changes, just logging)

Add structured `logger.info` / `logger.debug` calls at these pipeline points (chat.py):

| Pipeline point | Log fields |
|---|---|
| Domain classification result | `domain`, `confidence`, `alternatives` |
| RAG filter applied | `filter`, `filter_type` ("domain_filtered" \| "broad" \| "doc_scoped") |
| RAG results summary | `count`, `top_domains`, `top_scores`, `top_sources` |
| Broad fallback triggered | `reason`, `broad_score`, `domain_filtered_score` |
| Web search triggered | `reason`, `is_research_query` |
| LLM provider selected | `provider`, `model`, `mode`, `context_size_estimate` |
| Local LLM context warning | `context_estimate`, `max_tokens_requested`, `provider` |

Log level: `INFO` for errors/edge cases, `DEBUG` for routine diagnostics.
When `DEBUG` logging is enabled (via `.env`), the pipeline logs every step.
When `DEBUG` is disabled, only problematic paths are logged at INFO level.

---

### Bug 1 Fix: Robust E-invoicing Domain Classification

**File:** `backend/core/chat/domain_classifier.py`

Three-layer classifier (best match wins):

**Layer 1 — Exact keyword match (confidence 0.9):**
```python
# Before LLM call, check exact keywords
_EXACT_EINVOICING = re.compile(
    r'\b(e-?invoic(e|ing|ed|er|ees?)|electronic\s+invoice|dctce|peppol\s+bis)\b',
    re.IGNORECASE
)
# Also check number patterns from DOMAIN_KEYWORDS
for kw in DOMAIN_KEYWORDS[DomainLabel.E_INVOICING]:
    if _word_boundary_match(kw, lower):
        return ClassifierResult(domain=DomainLabel.E_INVOICING, confidence=0.9, alternatives=[])
```

**Layer 2 — Enhanced fuzzy match (confidence 0.75):**
Keep existing difflib fuzzy match but lower the length-ratio threshold from 0.75 → 0.65 for e-invoicing keywords specifically.

**Layer 3 — LLM fallback:**
Existing `_llm_complete()` call. Unchanged.

This ensures "e-invoicing", "electronic invoice", "dctce" etc. are caught at Layer 1 with high confidence even if the LLM classifier misfires.

---

### Bug 2 Fix: Local LLM Context Safety

**Problem:** Local LLMs (14B-32B) have smaller context windows and weaker instruction following. The current pipeline sends the entire system prompt + all RAG chunks + conversation history — this can overflow context or confuse smaller models.

**Fix 1 — Aggressive context truncation for local models:**

In `get_llm_provider()` (`llm_manager.py`), when provider is "ollama" or "lmstudio" / "local", compute a safe max context budget:

```python
_LOCAL_MAX_CONTEXT = {
    "ollama":    6_000,   # Conservative: 14B models often have 8K-32K windows, but vLLM may report larger
    "lmstudio":  8_000,
    "local":     8_000,
}
```

When building `_msgs` in chat.py, if provider is local, truncate RAG chunks to top 3 (instead of all), and cap conversation history at 4 messages.

**Fix 2 — Simplify system prompt for local models:**

Create a stripped-down system prompt variant for local LLMs (`_LOCAL_SYSTEM_SUFFIX`). Remove verbose formatting instructions, reduce examples, keep only the core instruction: "Answer using ONLY the provided documents."

**Fix 3 — Ensure RAG context always included:**

For local LLMs, after truncation, verify at minimum the top 2 RAG chunks are included. If no RAG results exist, do NOT fall back to web search for local models — instead return a "no documents found" response with the disclaimer.

**Fix 4 — Local LLM context overflow detection:**

In `compute_safe_max_tokens()`, add provider-specific logic:
- For NVIDIA/OpenAI/claude: use existing `_MIN_RESPONSE_TOKENS = 512`
- For local models: use `_MIN_RESPONSE_TOKENS = 256` (smaller models need less headroom)
- If estimated context > local max context, truncate RAG chunks before calling LLM

---

### Bug 1 Fix (secondary): RAG Domain Mapping Expansion

**File:** `backend/api/chat.py` — `_DOMAIN_TO_DOC_DOMAINS`

If e-invoicing domain is detected but RAG returns 0 results, try an expanded fallback:

```python
# After domain-filtered search returns 0 results
if domain_classified == "e_invoicing" and search_results == []:
    # Retry with broader doc domains
    expanded_filter = {"domain": {"$in": ["e_invoicing", "peppol", "vat", "corporate_tax", "general"]}}
    search_results = await _hybrid_retriever.retrieve(query, top_k, expanded_filter)
```

---

## File Map

| File | Action |
|---|---|
| `backend/api/debug.py` | Create — `/api/debug/rag-inspect` endpoint |
| `backend/api/chat.py` | Modify — add debug logging at pipeline points |
| `backend/core/chat/domain_classifier.py` | Modify — add Layer 1 exact keyword match for e-invoicing |
| `backend/core/llm_manager.py` | Modify — `get_llm_provider()` add local model context warnings |
| `backend/core/rag_engine.py` | Modify — `compute_safe_max_tokens()` add local model variant |
| `backend/config.py` | Modify — add `_LOCAL_MAX_CONTEXT` constants |

---

## Testing

### Unit Tests
- `backend/tests/api/test_debug_endpoint.py` — test rag-inspect endpoint
- `backend/tests/test_domain_classifier.py` — test Layer 1 e-invoicing keyword matching
- `backend/tests/test_local_llm_context.py` — test context truncation for local providers

### Manual Testing
1. Start backend, call `curl -X POST http://localhost:8002/api/debug/rag-inspect -d '{"query":"e-invoicing UAE requirements"}'`
2. Verify domain is classified as `e_invoicing`, rag_filter includes e_invoicing docs
3. Test via UI with NVIDIA — verify correct e-invoicing sources shown
4. Test via UI with Ollama — verify RAG context is used (not hallucinated)
5. Test via UI with LM Studio — same as Ollama

---

## Success Criteria

1. `curl /api/debug/rag-inspect` with "e-invoicing" query returns domain=e_invoicing with confidence ≥ 0.9
2. E-invoicing query via UI with NVIDIA returns UAE e-invoicing document sources (not AML/tax evasion)
3. E-invoicing query via UI with Ollama returns correct answer AND cites actual RAG sources (no hallucination)
4. E-invoicing query via UI with LM Studio returns correct answer AND cites actual RAG sources (no hallucination)
5. Full test suite passes: `python -m pytest tests/ -q`
