# Design: Chat History Viewer Fix + Cross-Domain Source Quality

**Date:** 2026-05-07  
**Status:** Approved  
**Scope:** `chat_history_viewer.py` DB path detection, backend cross-domain RAG source suppression, viewer display enhancements, tokens_used investigation

---

## Problem Statement

Three interconnected bugs degrade the chatbot's quality and the history viewer's usability:

1. **Viewer cannot find the database** — `chat_history_viewer.py` resolves its DB path relative to its own file location (GoogleDrive folder), but the live backend and database live at `~/chatbot_local/`. Result: `[ERROR] Database not found`.

2. **Cross-domain source hallucination** — When a domain-specific RAG search (e.g., `corporate_tax`) returns low-scoring results (below `_BROAD_FALLBACK_THRESHOLD = 0.39`), a broad-fallback search runs without domain filter. This broad search returns documents from a completely different domain (e.g., 15 VAT real estate PDFs for a corporate tax query). These wrong-domain sources get attached to the response. The LLM receives irrelevant context, produces a short generic answer, and the user sees misleading sources.

3. **Short/truncated LLM answers** — Directly caused by Bug 2. When the LLM is given irrelevant context, it cannot produce a comprehensive domain answer. Once the sources are cleared (Bug 2 fixed), web search kicks in and provides real context.

**Domains affected by Bug 2:** corporate_tax, vat, ifrs, labour, commercial, e_invoicing, peppol — every domain with an entry in `_DOMAIN_TO_DOC_DOMAINS`. Also affects FTA and audit-related queries.

---

## Fix 1: `chat_history_viewer.py` — DB Path Auto-Detection

### Root Cause

```python
_SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = _SCRIPT_DIR / "backend" / "data" / "chatbot.db"
```

When the script is run from the GoogleDrive copy, this resolves to a path where no database exists. The live database is at `~/chatbot_local/Project_AccountingLegalChatbot/backend/data/chatbot.db`.

### Solution

Replace the hardcoded relative assignment with a `_find_db_path()` function that searches in order:

1. `CHATBOT_DB_PATH` environment variable (explicit user override)
2. `~/chatbot_local/Project_AccountingLegalChatbot/backend/data/chatbot.db` (active runtime — checked first)
3. `<script_dir>/backend/data/chatbot.db` (original relative path — legacy fallback)
4. `<script_dir>/../backend/data/chatbot.db` (alternate layout)

Returns the first path that exists. If none found, `get_connection()` prints a clear error listing all searched paths and exits.

---

## Fix 2: `backend/api/chat.py` — Cross-Domain Source Suppression

### Root Cause

The broad-fallback block (lines 599–647) replaces domain-filtered results with all-domain results when the filtered scores are too low. There is no check whether the broad results actually belong to the queried domain.

The existing `_GENERAL_LAW_MIN_RELEVANCE_SCORE` guard only covers `general_law`/`general` queries. All other specific domains (corporate_tax, ifrs, labour, etc.) have no protection.

### Solution

Immediately after the broad fallback sets `_search_results = _broad_results`, add a cross-domain guard:

```python
# Cross-domain contamination guard (applies to all domain-specific queries)
_queried_doc_domains = set(_DOMAIN_TO_DOC_DOMAINS.get(_cls.domain.value, []))
if _queried_doc_domains and _search_results:
    _domain_matching = [
        r for r in _search_results
        if r.get("metadata", {}).get("domain") in _queried_doc_domains
    ]
    if not _domain_matching:
        logger.info(
            "Cross-domain suppression: cleared %d broad-fallback results "
            "(domains: %s) for %s query — none matched queried domains %s",
            len(_search_results),
            {r.get("metadata", {}).get("domain") for r in _search_results},
            _cls.domain.value,
            _queried_doc_domains,
        )
        _search_results = []
    elif len(_domain_matching) < len(_search_results):
        logger.info(
            "Cross-domain partial filter: kept %d/%d broad-fallback results "
            "matching %s domain",
            len(_domain_matching), len(_search_results), _cls.domain.value,
        )
        _search_results = _domain_matching
```

### Effect Flow (corporate tax example)

```
User: "tell me corporate tax"
  → Domain classifier: corporate_tax (confidence 0.8)
  → RAG (corporate_tax filter): top score < 0.39
  → Broad fallback: finds 15 VAT real-estate docs (score 0.67)
  → [NEW] Cross-domain guard: VAT ∉ {corporate_tax} → _search_results = []
  → _search_results empty, not doc-scoped → web search triggers
  → LLM gets real corporate tax web context → comprehensive answer + correct sources
```

Applies to: corporate_tax, vat, ifrs, labour, commercial, e_invoicing, peppol, and any future domain added to `_DOMAIN_TO_DOC_DOMAINS`.

---

## Fix 3: `chat_history_viewer.py` — Display Enhancements

While fixing the viewer, add:

- **Source domain mismatch warning:** When displaying sources, if `src["domain"]` does not match the conversation's detected domain, print `⚠️ wrong-domain` in yellow (useful for auditing conversations before this fix is deployed)
- **`--full` flag:** New CLI argument to show complete message content without the 200-char excerpt truncation in `build_augmented_prompt` display
- **Fix option 3 UX:** "Open by ID/number" currently misinterprets digit input — fix so entering a list number (1, 2, 3…) correctly opens that conversation

---

## Fix 4: `tokens_used` Tracking Investigation

All messages in the DB show `tokens_used = 0`. Investigate:
- Check `NvidiaProvider.chat_stream()` in `llm_manager.py` to see if `usage` data is parsed from the streaming response
- NVIDIA NIM streaming APIs may not return `usage` in stream chunks — check if a final `[DONE]` chunk carries usage
- If fixable, extract and save tokens from the final chunk; if not available for streaming, document the limitation

---

## Architecture Summary

| Component | Change |
|---|---|
| `chat_history_viewer.py` | `_find_db_path()` replaces hardcoded relative path |
| `backend/api/chat.py` | Cross-domain guard block added after broad fallback (~15 lines) |
| `chat_history_viewer.py` | Source domain mismatch display, `--full` flag, option 3 fix |
| `backend/core/llm_manager.py` | Investigate tokens_used tracking for streaming |

No schema changes. No new dependencies. No API model changes.

---

## Testing

- **Unit:** `_find_db_path()` — cover all 4 search paths (env var, chatbot_local, relative, parent)
- **Unit:** Cross-domain guard — mock broad fallback with wrong-domain results, assert `_search_results = []`
- **Unit:** Cross-domain partial filter — mock mixed results, assert only correct-domain kept
- **Integration:** "tell me corporate tax" via `test_chat_title_generation.py` pattern — assert no VAT-domain sources
- **Regression:** Existing `general_law` suppression test unchanged
- **Viewer:** `--search "corporate tax"` against live DB — assert results found and openable

---

## Out of Scope

- Rebuilding/re-ingesting the corporate_tax RAG corpus (separate concern)
- Changing LLM model names or API keys
- Any changes to the frontend UI
