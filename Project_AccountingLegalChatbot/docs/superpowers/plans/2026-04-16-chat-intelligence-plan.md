# Chat Intelligence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Legal chatbot's memory (within-session and cross-session), remove the Pro-Tip disclaimer, add research mode with extended web search, and display sources as inline chips.

**Architecture:** Within-session memory uses a sliding window of 20 messages + LLM compression of older messages stored in DB. Cross-session memory extracts facts from completed conversations into a `UserMemory` table and injects them into new sessions. Research mode detects power-user keywords and fires 5–8 parallel DuckDuckGo queries, aggregating and synthesizing the results.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, asyncio, duckduckgo_search, React/TypeScript.

**Prerequisite:** Plan A (audit pipeline) does not need to be complete before starting this plan.

---

## File Map

| File | What changes |
|------|-------------|
| `backend/db/models.py` | Add `UserMemory` SQLAlchemy model |
| `backend/api/chat.py` | Sliding window 20 msgs + compression; cross-session memory inject; research mode; web search improvements |
| `backend/core/rag_engine.py` | Remove Pro-Tip from SYSTEM_PROMPT |
| `backend/core/prompt_router.py` | Add structured output instruction |
| `backend/core/web_search.py` | Add `deep_search()` for research mode |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | Source chips + collapsible search indicator |
| `backend/tests/test_source_content.py` | Tests for web search and research mode |

---

## Task 1 — Remove Pro-Tip disclaimer

**Files:**
- Modify: `backend/core/rag_engine.py`
- Modify: `backend/core/prompt_router.py`

**Background:** The SYSTEM_PROMPT tells the LLM to "Flag when information might be outdated or needs verification." The LLM interprets this as: append a Pro-Tip recommending a licensed professional after every response. This undermines the product's value proposition.

- [ ] **Step 1: Fix rag_engine.py SYSTEM_PROMPT**

Open `backend/core/rag_engine.py`. Find `SYSTEM_PROMPT` (lines 169–183):

```python
    SYSTEM_PROMPT = """You are an expert AI assistant specializing in accounting, 
finance, tax law, and legal compliance — particularly for UAE regulations 
(IFRS, VAT, Corporate Tax, and related laws).

When answering questions:
- Reference the provided context documents when available
- Cite specific sources (document name, page number) when possible
- If the context doesn't contain the answer, say so clearly and provide 
  your best knowledge-based response
- Be precise with numbers, dates, and regulatory references
- Flag when information might be outdated or needs verification

Context from indexed documents:
{context}
"""
```

Replace with:

```python
    SYSTEM_PROMPT = """You are an expert AI assistant specializing in accounting, 
finance, tax law, and legal compliance — particularly for UAE regulations 
(IFRS, VAT, Corporate Tax, and related laws).

When answering questions:
- Reference the provided context documents when available
- Cite specific sources (document name, page number) when possible  
- If the context doesn't contain the answer, search your knowledge and answer directly
- Be precise with numbers, dates, and regulatory references
- When your response exceeds 150 words, structure it: one-sentence direct answer first, then numbered sections with bold headings, then a brief summary
- Use markdown tables for comparisons or multi-column data
- Cite web sources as [Source Name] inline when using web search results

Context from indexed documents:
{context}
"""
```

- [ ] **Step 2: Fix prompt_router.py**

Open `backend/core/prompt_router.py`. Find any prompt that contains "Flag when" or "Pro-Tip" or "consult with a licensed" and remove/replace those lines with the same structured output instruction from Step 1.

```bash
grep -n "Flag when\|Pro-Tip\|licensed\|outdated" backend/core/prompt_router.py
```

Replace any found instances with: `"Be precise with numbers, dates, and regulatory references."`

- [ ] **Step 3: Manual test**

Restart the backend. Ask the chatbot any question about UAE VAT. Verify the response does NOT end with "Pro-Tip: Consult with a licensed UAE lawyer..."

- [ ] **Step 4: Commit**

```bash
git add backend/core/rag_engine.py backend/core/prompt_router.py
git commit -m "fix: remove Pro-Tip disclaimer from LLM system prompts"
```

---

## Task 2 — Fix within-session memory (sliding window 20 messages)

**Files:**
- Modify: `backend/api/chat.py`

**Background:** The history fetch is capped at 9 messages (line 122). After 8 back-and-forth turns the LLM forgets the beginning of the conversation. Fix: fetch up to 21 messages; if there are more than 20, compress the oldest into a summary, store that summary, and use it as the context opener.

- [ ] **Step 1: Increase the fetch limit**

In `backend/api/chat.py`, find (around line 119):
```python
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(9)  # 9 = 8 prior + 1 just-added user message
    )
    history = list(reversed(history_result.scalars().all()))
```

Replace with:
```python
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(21)  # 21 = 20 prior + 1 just-added user message
    )
    history = list(reversed(history_result.scalars().all()))
```

- [ ] **Step 2: Add `compress_history()` helper function**

Add this function near the top of `backend/api/chat.py`, after the imports:

```python
async def compress_history(messages: list[dict]) -> str:
    """
    Compress a list of older messages into a brief context summary.
    Called when conversation exceeds 20 messages to stay within token budget.
    Returns a summary string to prepend as system context.
    """
    try:
        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:300]}"
            for m in messages
        )
        llm = get_llm_provider()
        resp = await llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Summarize the key facts and topics from this conversation excerpt "
                        "in 3-5 bullet points. Focus on: user's company/context, questions asked, "
                        "key figures or regulations mentioned. Be concise — max 400 words total."
                    ),
                },
                {"role": "user", "content": conversation_text},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        return resp.content.strip()
    except Exception as exc:
        logger.warning(f"History compression failed (non-fatal): {exc}")
        return ""
```

- [ ] **Step 3: Use compression in the send_message handler**

In `send_message()`, after `history = list(reversed(...))`, add:

```python
    # Sliding window: if conversation is long, compress the oldest messages
    context_summary = ""
    if len(history) > 20:
        # Compress messages older than the most-recent 14
        old_messages = [
            {"role": m.role, "content": m.content}
            for m in history[:-14]
            if m.role in ("user", "assistant")
        ]
        if old_messages:
            # Check if a summary for this conversation already exists in DB
            summary_result = await db.execute(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.role == "system",
                    Message.content.startswith("[CONTEXT SUMMARY]"),
                )
                .order_by(desc(Message.created_at))
                .limit(1)
            )
            existing_summary = summary_result.scalar_one_or_none()

            if existing_summary:
                context_summary = existing_summary.content.replace("[CONTEXT SUMMARY] ", "", 1)
            else:
                context_summary = await compress_history(old_messages)
                if context_summary:
                    # Store so we don't re-compute on every subsequent turn
                    summary_msg = Message(
                        conversation_id=conversation.id,
                        role="system",
                        content=f"[CONTEXT SUMMARY] {context_summary}",
                    )
                    db.add(summary_msg)
                    await db.flush()

        # Use only the most-recent 14 messages as the rolling window
        history = history[-14:]
```

Then, when building `messages` for the LLM, prepend the context summary:

Find the line that says `messages = []` and the lines building the messages list. After `messages.append({"role": "system", "content": system_prompt})` (or the augmented variant), add:

```python
    # Prepend context summary if conversation was compressed
    if context_summary:
        messages.append({
            "role": "user",
            "content": f"[Previous conversation summary]\n{context_summary}",
        })
        messages.append({
            "role": "assistant",
            "content": "Understood. I have the context from our earlier conversation.",
        })
```

This must be added AFTER the system message and BEFORE the conversation history loop.

- [ ] **Step 4: Manual test**

Restart backend. Start a new conversation. Send 25+ messages back and forth. Verify that around message 21, the LLM still references context from early in the conversation (e.g., if you mentioned your company name in message 1, it should still know it in message 25).

- [ ] **Step 5: Commit**

```bash
git add backend/api/chat.py
git commit -m "feat: sliding window 20-message history with LLM compression for long conversations"
```

---

## Task 3 — Add UserMemory table for cross-session memory

**Files:**
- Modify: `backend/db/models.py`
- Modify: `backend/api/chat.py`

**Background:** Each new conversation starts from scratch. If the user's company is "Castles Plaza Real Estate" and they ask about VAT every week, the LLM should already know the company name on session 2. Solution: extract facts after each conversation and store in `UserMemory`; inject into new conversation system prompts.

- [ ] **Step 1: Add UserMemory model to models.py**

Open `backend/db/models.py`. After the last model class, add:

```python
class UserMemory(Base):
    """
    Persistent facts extracted from conversations.
    Injected into new conversations so the LLM remembers across sessions.
    """
    __tablename__ = "user_memory"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="default")
    key: Mapped[str] = mapped_column(String, nullable=False)   # e.g. "company_name"
    value: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_conversation_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

Make sure `Float` and `Optional` are imported at the top of `models.py`. Check existing imports and add any missing:
```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Float, Text
from typing import Optional
import uuid
from datetime import datetime
```

- [ ] **Step 2: Create the table on startup**

In `backend/db/database.py`, find where tables are created (likely `Base.metadata.create_all`). If it's using Alembic migrations, you may need to run a migration. For SQLite (which this project uses), `create_all` on startup is the pattern. Verify `UserMemory` is included by restarting the backend and checking the DB:

```bash
cd backend
uv run python -c "from db.database import engine; from db.models import Base; import asyncio; asyncio.run(engine.run_sync(Base.metadata.create_all))"
```

Or simply restart the backend — if `create_all` runs on startup, the table will be created automatically.

- [ ] **Step 3: Add memory extraction function to chat.py**

In `backend/api/chat.py`, add this helper:

```python
async def extract_and_save_memory(
    conversation_id: str,
    messages: list[dict],
    db: AsyncSession,
) -> None:
    """
    Extract memorable facts from a conversation and store in UserMemory.
    Called as a background task when a conversation becomes inactive.
    """
    if len(messages) < 4:
        return  # Not enough context to extract anything useful

    try:
        from db.models import UserMemory

        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:400]}"
            for m in messages[-20:]  # Use last 20 messages
        )

        llm = get_llm_provider()
        resp = await llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract factual details from this conversation worth remembering for future sessions. "
                        "Return ONLY a JSON array. Each item: {\"key\": \"string\", \"value\": \"string\", \"confidence\": 0.0-1.0}. "
                        "Keys to extract (only if explicitly stated): company_name, industry, vat_trn, trn_number, "
                        "preferred_language, detail_level (brief/detailed), company_location, business_type. "
                        "Do NOT invent. Max 8 items. Return [] if nothing clear is stated."
                    ),
                },
                {"role": "user", "content": conversation_text},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        import json as _json
        raw = resp.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return
        facts = _json.loads(match.group(0))

        for fact in facts:
            key = fact.get("key", "").strip()
            value = fact.get("value", "").strip()
            confidence = float(fact.get("confidence", 1.0))
            if not key or not value or confidence < 0.5:
                continue

            # Upsert: update existing memory for same key, or insert new
            existing = await db.execute(
                select(UserMemory).where(
                    UserMemory.user_id == "default",
                    UserMemory.key == key,
                )
            )
            existing_row = existing.scalar_one_or_none()
            if existing_row:
                existing_row.value = value
                existing_row.confidence = confidence
                existing_row.source_conversation_id = conversation_id
            else:
                db.add(UserMemory(
                    user_id="default",
                    key=key,
                    value=value,
                    confidence=confidence,
                    source_conversation_id=conversation_id,
                ))

        await db.commit()
        logger.info(f"Saved {len(facts)} memory facts from conversation {conversation_id}")

    except Exception as exc:
        logger.warning(f"Memory extraction failed (non-fatal): {exc}")
```

Make sure `UserMemory` is imported at the top of `chat.py`:
```python
from db.models import Conversation, Message, UserMemory
```

And `select` is already imported (it should be).

- [ ] **Step 4: Trigger memory extraction when a new conversation starts**

In the `send_message` handler, in the `else` branch where a NEW conversation is created (not an existing one), add a background task to extract memory from the most-recently-completed conversation:

```python
    # Get or create conversation
    if req.conversation_id:
        # ... existing code ...
    else:
        conversation = Conversation(...)
        db.add(conversation)
        await db.flush()

        # Background: extract memory from the previous conversation (if it's been idle 30+ min)
        import asyncio
        from datetime import timezone, timedelta

        prev_conv_result = await db.execute(
            select(Conversation)
            .where(Conversation.id != conversation.id)
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        prev_conv = prev_conv_result.scalar_one_or_none()
        if prev_conv:
            idle_minutes = (
                datetime.utcnow() - prev_conv.updated_at.replace(tzinfo=None)
            ).total_seconds() / 60
            if idle_minutes >= 30:
                prev_msgs_result = await db.execute(
                    select(Message)
                    .where(
                        Message.conversation_id == prev_conv.id,
                        Message.role.in_(["user", "assistant"]),
                    )
                    .order_by(Message.created_at)
                )
                prev_msgs = [
                    {"role": m.role, "content": m.content}
                    for m in prev_msgs_result.scalars().all()
                ]
                asyncio.create_task(
                    extract_and_save_memory(prev_conv.id, prev_msgs, db)
                )
```

- [ ] **Step 5: Inject memory into new conversation system prompt**

In `send_message()`, after the conversation is created/fetched and before building the `messages` list, add:

```python
    # Load cross-session memory
    from db.models import UserMemory
    memory_result = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == "default")
        .order_by(desc(UserMemory.updated_at))
        .limit(10)
    )
    memory_rows = memory_result.scalars().all()
    memory_block = ""
    if memory_rows:
        memory_lines = [f"- {m.key}: {m.value}" for m in memory_rows]
        memory_block = "\n[Memory from prior sessions]\n" + "\n".join(memory_lines) + "\n"
```

Then, when the system prompt is set, append `memory_block`:

Find the line:
```python
    system_prompt = get_system_prompt(req.domain)
```

Change to:
```python
    system_prompt = get_system_prompt(req.domain) + memory_block
```

- [ ] **Step 6: Manual test**

1. Start a new conversation. Tell the chatbot "My company is Castles Plaza Real Estate L.L.C, based in Dubai."
2. Have 5+ more exchanges.
3. Wait (or temporarily lower the idle threshold to 0 minutes for testing).
4. Start a NEW conversation. Ask "What is my company name?" — the LLM should answer "Castles Plaza Real Estate L.L.C" from memory.

- [ ] **Step 7: Commit**

```bash
git add backend/db/models.py backend/api/chat.py
git commit -m "feat: cross-session persistent memory with UserMemory table and automatic extraction"
```

---

## Task 4 — Add Research Mode (deep multi-query web search)

**Files:**
- Modify: `backend/core/web_search.py`
- Modify: `backend/api/chat.py`
- Test: `backend/tests/test_source_content.py`

**Background:** When a user asks a research-style question ("research UAE VAT e-invoicing", "give me a deep analysis of..."), the current system fires one web search and uses 5 results. Research mode fires 5–8 parallel sub-queries, aggregates 15 unique results, and feeds the full synthesis to the LLM for a comprehensive structured response.

- [ ] **Step 1: Write a failing test for deep_search**

In `backend/tests/test_source_content.py`, add:

```python
@pytest.mark.asyncio
async def test_deep_search_returns_more_than_single_search():
    """deep_search should return more unique results than a single search_web call."""
    from core.web_search import deep_search, search_web

    # Use a safe query unlikely to hit rate limits in test
    query = "UAE VAT rate 2024"
    
    single_results = await search_web(query, max_results=5)
    deep_results = await deep_search(query, max_queries=3)  # Use 3 to be fast in test

    # Deep search should return at least as many results as single search
    assert len(deep_results) >= len(single_results)
    # All results must have href (URL)
    for r in deep_results:
        assert "href" in r


def test_is_research_query_detects_keywords():
    from api.chat import _is_research_query
    
    assert _is_research_query("research UAE corporate tax exemptions") is True
    assert _is_research_query("deep analysis of IFRS 16") is True
    assert _is_research_query("comprehensive guide to VAT") is True
    assert _is_research_query("what is VAT") is False
    assert _is_research_query("how much is the VAT rate") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_source_content.py::test_is_research_query_detects_keywords -v
```

Expected: `ImportError: cannot import name '_is_research_query'`

- [ ] **Step 3: Add `deep_search()` to web_search.py**

In `backend/core/web_search.py`, add after the existing `build_web_context()` function:

```python
async def generate_sub_queries(query: str, max_queries: int = 6) -> list[str]:
    """
    Use LLM to generate diverse sub-queries from the original question.
    Falls back to simple keyword variations if LLM is unavailable.
    """
    try:
        from core.llm_manager import get_llm_provider
        llm = get_llm_provider()
        resp = await llm.chat(
            [
                {
                    "role": "user",
                    "content": (
                        f"Generate {max_queries} distinct search queries to comprehensively research this topic: "
                        f'"{query}"\n\n'
                        "Return ONLY a JSON array of strings. No explanation. "
                        "Each query should cover a different angle: regulations, examples, exceptions, "
                        "recent updates, official guidance, penalties/compliance."
                    ),
                }
            ],
            temperature=0.3,
            max_tokens=300,
        )
        import json as _json, re as _re
        raw = resp.content.strip()
        raw = _re.sub(r"^```(?:json)?\s*", "", raw, flags=_re.MULTILINE)
        raw = _re.sub(r"\s*```\s*$", "", raw, flags=_re.MULTILINE)
        match = _re.search(r"\[.*\]", raw, _re.DOTALL)
        if match:
            queries = _json.loads(match.group(0))
            return [str(q) for q in queries[:max_queries] if q]
    except Exception as exc:
        logger.warning(f"Sub-query generation failed: {exc}")

    # Fallback: use the original query with simple variations
    return [query, f"{query} UAE regulations", f"{query} FTA guidance"]


async def deep_search(query: str, max_queries: int = 6) -> list[dict]:
    """
    Extended multi-query web search for research mode.
    Generates sub-queries, runs them in parallel, deduplicates by URL.
    Returns up to 15 unique results.
    """
    sub_queries = await generate_sub_queries(query, max_queries)

    # Run all sub-queries in parallel
    import asyncio as _asyncio
    tasks = [search_web(q, max_results=5) for q in sub_queries]
    all_results_nested = await _asyncio.gather(*tasks, return_exceptions=True)

    # Flatten and deduplicate by URL
    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for batch in all_results_nested:
        if isinstance(batch, Exception):
            continue
        for result in batch:
            url = result.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

    logger.info(f"Deep search: {len(sub_queries)} queries → {len(unique_results)} unique results")
    return unique_results[:15]
```

- [ ] **Step 4: Add `_is_research_query()` to chat.py**

In `backend/api/chat.py`, add after the `_classify_domain()` function:

```python
_RESEARCH_KEYWORDS = {
    "research", "deep analysis", "deep dive", "analyze", "analyse",
    "investigate", "comprehensive", "detailed report", "full breakdown",
    "explain in detail", "in-depth", "in depth", "thorough", "complete guide",
    "everything about", "all about",
}

def _is_research_query(message: str) -> bool:
    """Return True if the message contains research-mode trigger keywords."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _RESEARCH_KEYWORDS)
```

- [ ] **Step 5: Use deep_search when research mode is triggered**

In the `generate()` streaming function inside `send_message()`, find the web search section:

```python
                # If RAG returned nothing, try web search
                if not search_results:
                    yield f"data: {json.dumps({'type': 'status', 'status': 'searching_web'})}\n\n"
                    web_results = await search_web(req.message, max_results=5)
```

Replace with:

```python
                # If RAG returned nothing, try web search
                if not search_results:
                    is_research = _is_research_query(req.message)
                    if is_research:
                        yield f"data: {json.dumps({'type': 'status', 'status': 'researching', 'message': 'Deep research in progress — this may take 1-2 minutes…'})}\n\n"
                        from core.web_search import deep_search, generate_sub_queries
                        sub_queries = await generate_sub_queries(req.message, max_queries=6)
                        yield f"data: {json.dumps({'type': 'queries_run', 'queries': sub_queries})}\n\n"
                        from core.web_search import deep_search
                        web_results = await deep_search(req.message, max_queries=6)
                        yield f"data: {json.dumps({'type': 'status', 'status': 'research_done', 'sources_found': len(web_results)})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'status', 'status': 'searching_web'})}\n\n"
                        web_results = await search_web(req.message, max_results=5)
```

Also update the web instruction to tell the LLM it has comprehensive research results:

Find:
```python
                        web_instruction = (
                            "IMPORTANT: Answer ONLY using the web search results provided below. "
                            "Do not add information from your training data. "
                            "Cite the source URLs inline. Take your time and be accurate.\n\n"
                            + web_context
                        )
```

Replace with:
```python
                        if is_research:
                            web_instruction = (
                                "IMPORTANT: You have comprehensive research results from multiple sources below. "
                                "Synthesize ALL sources into a well-structured response. "
                                "Use numbered sections with bold headings. "
                                "Cite sources as [Source Name] inline where relevant. "
                                "Be thorough — the user asked for deep research.\n\n"
                                + web_context
                            )
                        else:
                            web_instruction = (
                                "IMPORTANT: Answer ONLY using the web search results provided below. "
                                "Do not add information from your training data. "
                                "Cite the source URLs inline. Take your time and be accurate.\n\n"
                                + web_context
                            )
```

- [ ] **Step 6: Run tests**

```bash
cd backend
uv run pytest tests/test_source_content.py -v
```

Expected: `test_is_research_query_detects_keywords` passes. The async deep_search test may be slow (real web calls) — that's OK.

- [ ] **Step 7: Commit**

```bash
git add backend/core/web_search.py backend/api/chat.py backend/tests/test_source_content.py
git commit -m "feat: research mode with deep multi-query web search and structured synthesis"
```

---

## Task 5 — Add source chips and collapsible search indicator (Frontend)

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

**Background:** When a message has web sources, show them as small pill chips below the message text (like Image #13). When research mode fires, show a "Searched the web ›" collapsible indicator above the response that expands to show the queries run and source chips.

- [ ] **Step 1: Read the current ChatMessages.tsx to understand the existing structure**

Open `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`. Understand:
- How messages are rendered (map over messages array)
- Where sources are currently shown (likely in SourcePeeker)
- The TypeScript interface for message objects

- [ ] **Step 2: Add source chip rendering**

In `ChatMessages.tsx`, find where each assistant message is rendered. After the message text content, add source chip rendering:

```tsx
{/* Source chips for web results */}
{msg.sources && msg.sources.length > 0 && (
  <div className="flex flex-wrap gap-1 mt-2">
    {msg.sources.filter(s => s.source && s.source.startsWith('http')).map((s, i) => {
      const domain = (() => {
        try { return new URL(s.source).hostname.replace('www.', ''); }
        catch { return s.source.slice(0, 20); }
      })();
      return (
        <a
          key={i}
          href={s.source}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors"
        >
          {domain}
        </a>
      );
    })}
  </div>
)}
```

- [ ] **Step 3: Add collapsible search indicator**

In the message object type, add an optional `queriesRun` field:
```tsx
interface ChatMessage {
  // ... existing fields
  queriesRun?: string[];
  isResearching?: boolean;
}
```

In `LegalStudio.tsx` (or wherever SSE events are consumed), handle the new event types from the backend:

```tsx
} else if (event.type === 'queries_run') {
  // Store queries on the in-progress message
  setMessages(prev => {
    const updated = [...prev];
    const last = updated[updated.length - 1];
    updated[updated.length - 1] = { ...last, queriesRun: event.queries };
    return updated;
  });
} else if (event.type === 'status' && event.status === 'researching') {
  setMessages(prev => {
    const updated = [...prev];
    const last = updated[updated.length - 1];
    updated[updated.length - 1] = { ...last, isResearching: true };
    return updated;
  });
}
```

Then in `ChatMessages.tsx`, add the collapsible indicator above the message content when `msg.queriesRun` exists:

```tsx
{msg.queriesRun && msg.queriesRun.length > 0 && (
  <SearchIndicator queries={msg.queriesRun} />
)}
```

Add the `SearchIndicator` component in the same file:

```tsx
function SearchIndicator({ queries }: { queries: string[] }) {
  const [expanded, setExpanded] = React.useState(false);
  return (
    <div className="mb-2">
      <button
        onClick={() => setExpanded(e => !e)}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        Searched the web
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
      {expanded && (
        <div className="mt-1 pl-4 text-xs text-gray-400 space-y-0.5">
          {queries.map((q, i) => (
            <div key={i} className="truncate">"{q}"</div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Test in browser**

Start the frontend (`npm run dev`). Ask a research-mode question: "research UAE corporate tax small business relief". Verify:
1. "Searched the web ›" appears above the response
2. Clicking expands to show the sub-queries
3. Source chips appear below the response

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ChatMessages.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat: add source chips and collapsible web search indicator to chat messages"
```
