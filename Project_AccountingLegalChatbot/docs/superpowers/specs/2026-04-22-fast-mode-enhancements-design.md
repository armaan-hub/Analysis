# Fast Mode Enhancements Design

**Date:** 2026-04-22  
**Status:** Approved  
**Scope:** Fast mode quality improvements — token budget, formatting reliability, multi-query RAG, session memory

---

## Problem Statement

Fast mode degrades in long conversations: answers get cut off before finishing, markdown formatting (headers, bullets) stops being applied consistently, and earlier context (company name, topic, decisions) is lost once the sliding window trims older messages. Additionally, RAG retrieval is limited to 8 chunks per query, which can miss relevant passages from large document sets.

---

## Goals

1. Allow the LLM to write longer, complete answers (no truncation)
2. Maintain consistent markdown formatting throughout a long chat
3. Keep more conversation history in context before trimming kicks in
4. Retrieve richer document context per query via multi-query RAG
5. Preserve earlier conversation facts once the sliding window trims old turns

---

## Non-Goals

- Does not change the Analyst or Deep Research modes
- Does not change the frontend rendering (Bug 2 fix handles that separately)
- Does not change the embedding or chunking strategy

---

## Design

### 1. Token Budget Expansion

Three config changes in `backend/config.py`:

| Setting | Current | New |
|---|---|---|
| `max_tokens` | 4096 | 8192 |
| `top_k_results` | 8 | 15 |

One code change in `backend/api/chat.py`, `_build_sliding_context`:

| Parameter | Current | New |
|---|---|---|
| `max_tokens_estimate` | 6000 | 12000 |

**Rationale:** `max_tokens` caps LLM output — doubling it removes truncation for complex legal/tax answers. The sliding window at 12 000 token estimate keeps ~30–35 messages before trimming (up from ~15). More RAG chunks give richer document coverage.

---

### 2. Formatting Reliability (Format Guard)

**Root cause:** Formatting rules live at the top of the system prompt. In long conversations they are far from the user's question and receive less attention from the model.

**Fix:** A short `FORMATTING_REMINDER` constant is injected as the **last system message** in the messages array, immediately before the user's question, on every request.

```
FORMATTING: Use ## for section headers, **bold** for key terms and figures,
- bullet lists for enumeration. Write a complete, thorough answer. Do not truncate.
```

**Location:**
- Constant defined in `backend/core/prompt_router.py` as `FORMATTING_REMINDER`
- Injected in `backend/api/chat.py` after conversation history, before the user message

This applies in Fast mode only (not Analyst, which has its own system prefix).

---

### 3. Multi-Query RAG

**Current:** 1 query → `top_k_results` (15) chunks.

**New:** 1 query → 3 parallel searches → deduplicated top-15 unique chunks.

#### New helper: `_get_query_variations(query, llm) -> list[str]`

- Makes a small LLM call (`temperature=0.3`, `max_tokens=150`) requesting 2 alternative phrasings of the user's question, returned as a JSON array
- Returns `[original_query] + variations` (2–3 queries total)
- Graceful fallback: if the call fails or returns malformed JSON, returns `[original_query]` only

```python
QUERY_VARIATION_PROMPT = (
    "Generate 2 alternative phrasings of the following question for a legal/finance document search. "
    "Return ONLY a JSON array of 2 strings. Keep each under 20 words."
)
```

#### Multi-query search flow (in `chat.py`, `send_message`)

1. Call `_get_query_variations(req.message, llm)`
2. Run `asyncio.gather(*[rag_engine.search(q, top_k=15, filter=rag_filter) for q in queries])`
3. Merge all results; deduplicate by `(doc_id, page)` fingerprint, keeping the highest-scoring duplicate
4. Sort merged list by score descending, take top `top_k_results` (15)
5. Continue with the merged search_results as before

**Note:** The query-variation LLM call uses the same provider as the main chat, with a lightweight prompt to minimise latency. If `rag_filter` is active, the same filter is applied to all variation searches.

---

### 4. Session Summary Memory

**Root cause:** Once the sliding window trims old turns, the LLM loses earlier context (e.g., company name, VAT TRN, topic agreed on in message 3 of a 50-message chat).

**Fix:** A rolling summary is generated from trimmed turns and injected as the first history item.

#### Schema change

Add a `summary` TEXT (nullable) column and `summary_msg_count` INTEGER column to the `conversations` table via a safe startup migration:

```python
# In db/database.py startup
for col_def in [
    "ALTER TABLE conversations ADD COLUMN summary TEXT",
    "ALTER TABLE conversations ADD COLUMN summary_msg_count INTEGER DEFAULT 0",
]:
    try:
        await db.execute(text(col_def))
        await db.commit()
    except Exception:
        pass  # column already exists
```

#### New helper: `_get_or_refresh_summary(conversation, history, db) -> str`

- **When to refresh:** `len(history) > 20` AND `len(history) > conversation.summary_msg_count + 10`
- **What to summarise:** the messages that fall outside the current sliding window (the oldest turns)
- **LLM call:** `temperature=0.1`, `max_tokens=600`, focused prompt:

```
Summarise the key facts, decisions, and topics discussed in these conversation turns
for an accounting/legal AI assistant. Be factual. Include: company name/TRN if mentioned,
the main questions asked, answers given, and any pending issues. Max 300 words.
```

- Store result in `conversation.summary` and `conversation.summary_msg_count = len(history)`
- Run in background (fire-and-forget via `asyncio.create_task`) to avoid blocking the response

#### Injection

Append the summary to the system message content (messages[0]) so it is always honoured regardless of provider:

```python
if conversation.summary:
    messages[0]["content"] += (
        f"\n\nCONTEXT SUMMARY OF EARLIER CONVERSATION:\n{conversation.summary}"
    )
```

---

## Files Changed

| File | Change |
|---|---|
| `backend/config.py` | `max_tokens` 4096→8192, `top_k_results` 8→15 |
| `backend/api/chat.py` | `_build_sliding_context` window 6000→12000; `_get_query_variations()` new helper; multi-query RAG loop; `_get_or_refresh_summary()` new helper; startup migration; format reminder injection |
| `backend/core/prompt_router.py` | Add `FORMATTING_REMINDER` constant |
| `backend/db/database.py` | Startup ALTER TABLE for `summary` and `summary_msg_count` columns |

---

## Error Handling & Fallbacks

- **Query variation failure** → fall back to single-query RAG (no degradation)
- **Summary generation failure** → log warning, skip injection (no degradation)
- **Startup migration** → wrapped in try/except (idempotent, safe to re-run)
- **Multi-query RAG partial failure** → use results from whichever searches succeeded

---

## Testing Checklist

- [ ] Long answer (legal memo, step-by-step VAT guide) renders completely, not truncated
- [ ] Markdown headers/bullets consistent at message 30+ in a conversation
- [ ] Second query on same document returns more distinct passages than single-query
- [ ] After 25+ messages, the summary is non-empty and injected (visible in server logs)
- [ ] After 25+ messages, LLM correctly references facts from earlier in the conversation
- [ ] All fallbacks work when variation LLM call raises an exception
