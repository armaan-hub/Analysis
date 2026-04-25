# Legal Studio — Three Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four defects: wrong VAT answer for hotel-apartment sale, Analyst sources leaking into Legal Studio, first message timing out in Fast mode, and home-page conversation cards showing raw question text.

**Architecture:** Pure backend/frontend changes across three files — `backend/core/prompt_router.py` (VAT knowledge), `backend/api/chat.py` (title background task + streaming restructure), `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` (source scoping + timeout). No new DB tables or APIs required.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy async / pytest-asyncio; TypeScript / React / Vitest

---

## File Map

| File | What Changes |
|------|-------------|
| `backend/core/prompt_router.py` | Extend `DOMAIN_PROMPTS["vat"]` + `FEW_SHOT_EXAMPLES["vat"]` with commercial-property section |
| `backend/api/chat.py` | Add `_generate_title()` helper + schedule it as `asyncio.create_task`; move domain/intent/query-vars LLM calls inside `generate()` so the meta SSE event yields before heavy processing |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Add `selected_doc_ids` to chat request body; increase abort timeout `30_000 → 90_000` |
| `backend/tests/test_prompt_router.py` | Add two new assertions for commercial-property VAT knowledge |
| `backend/tests/test_chat_title_generation.py` | **New** — test that `_generate_title` updates the conversation title |
| `backend/tests/test_fast_mode_streaming.py` | **New** — test that streaming path yields meta event before RAG/LLM work |
| `backend/tests/test_selected_doc_ids.py` | **New** — test that `selected_doc_ids` triggers the correct RAG filter |
| `frontend/src/components/studios/LegalStudio/__tests__/chatRequestBody.test.ts` | **New** — pure function test for the request body builder |

---

## Task 1 — VAT Commercial Property Prompt + Few-Shot Example

**Files:**
- Modify: `backend/core/prompt_router.py`
- Test: `backend/tests/test_prompt_router.py`

- [ ] **Step 1.1 — Write failing tests**

Open `backend/tests/test_prompt_router.py` and append these two tests **after** the existing four tests:

```python
def test_vat_prompt_contains_commercial_property_guidance():
    """VAT prompt must cover non-registered-person hotel-apartment sale workflow."""
    p = route_prompt(DomainLabel.VAT)
    assert "commercial property" in p.lower(), "VAT prompt missing 'commercial property'"
    assert "Payment of VAT on Commercial Property Sale" in p, (
        "VAT prompt missing FTA portal service name"
    )
    assert "non-registered" in p.lower(), "VAT prompt missing non-registered-person case"


def test_vat_few_shot_example_covers_hotel_apartment():
    """VAT few-shot example must mention hotel apartment and FTA portal steps."""
    from core.prompt_router import FEW_SHOT_EXAMPLES
    ex = FEW_SHOT_EXAMPLES.get("vat", "")
    assert "hotel apartment" in ex.lower(), "VAT few-shot missing hotel apartment scenario"
    assert "tax.gov.ae" in ex.lower() or "fta" in ex.lower(), (
        "VAT few-shot missing FTA portal reference"
    )
    assert "title deed" in ex.lower() or "oqood" in ex.lower(), (
        "VAT few-shot missing document list"
    )
```

- [ ] **Step 1.2 — Run to confirm failures**

```
cd backend
python -m pytest tests/test_prompt_router.py::test_vat_prompt_contains_commercial_property_guidance tests/test_prompt_router.py::test_vat_few_shot_example_covers_hotel_apartment -v
```

Expected: **FAILED** — assertions fail because the current prompt has no commercial-property section.

- [ ] **Step 1.3 — Implement: extend FEW_SHOT_EXAMPLES["vat"]**

In `backend/core/prompt_router.py`, replace the existing `"vat"` entry in `FEW_SHOT_EXAMPLES`:

```python
FEW_SHOT_EXAMPLES: dict[str, str] = {
    "vat": (
        "\n\nEXAMPLE 1:\n"
        "Q: Is VAT charged on residential rental?\n"
        "A: No. Residential property rental is exempt from VAT under Article 46(1)(b) of "
        "Federal Decree-Law No. 8 of 2017 on VAT."
        "\n\nEXAMPLE 2 (one-pager requested):\n"
        "Q: My client sold a Hotel Apartment and received an FTA notice to pay VAT. "
        "Need a one-pager on this and the documents required to make payment on the portal.\n"
        "A: **One-Pager: VAT on Hotel Apartment Sale — Payment Guide for Non-Registered Persons**\n\n"
        "**Background**\n"
        "Hotel Apartments, serviced apartments, and furnished residential-hotel units are classified "
        "as **commercial property** under UAE VAT law (Cabinet Decision No. 52 of 2017, Schedule 3). "
        "The standard 5% VAT rate applies on their sale. A seller who is not a VAT-registered "
        "taxable person (i.e., below the AED 375,000 mandatory threshold or making a one-time "
        "disposal) does **NOT** need to apply for a TRN.\n\n"
        "**Step-by-Step Portal Process**\n"
        "1. Go to the FTA e-Services portal: **tax.gov.ae**\n"
        "2. Click **Sign Up** (create a user account — this is NOT VAT registration)\n"
        "3. Once logged in, navigate to **Non-Registered Persons → Payment of VAT on "
        "Commercial Property Sale**\n"
        "4. Enter the property details and compute VAT: Sale Price × 5%\n"
        "5. Upload the required documents (see below)\n"
        "6. Submit and pay via bank transfer or FTA payment gateway\n\n"
        "**Documents Required**\n"
        "- Sale / Transfer Agreement (SPA / MOU)\n"
        "- Title Deed or Oqood certificate\n"
        "- Emirates ID or Passport of the seller\n"
        "- Copy of the FTA notice received\n"
        "- VAT calculation worksheet (Sale Consideration × 5%)\n\n"
        "**Legal References**\n"
        "- Federal Decree-Law No. 8 of 2017, Article 36 (Supply of Real Estate)\n"
        "- Cabinet Decision No. 52 of 2017, Schedule 3 (commercial property at standard rate)\n"
        "- FTA Public Clarification VATP015 (treatment of hotel apartments)\n\n"
        "> **Pro-Tip:** If the seller later makes further taxable supplies exceeding AED 375,000 "
        "annually, they must register for VAT and obtain a TRN. This one-time portal payment does "
        "not substitute for ongoing VAT registration obligations."
    ),
    # ... rest of examples unchanged
```

- [ ] **Step 1.4 — Implement: extend DOMAIN_PROMPTS["vat"]**

In `backend/core/prompt_router.py`, find the `"vat"` entry in `DOMAIN_PROMPTS` and append the commercial-property block **before** the closing `+ FORMATTING_SUFFIX + ...` chain:

```python
DOMAIN_PROMPTS: dict[str, str] = {
    ...
    "vat": (
        "You are a UAE VAT Specialist. You operate under Federal Decree-Law No. 8 of 2017 "
        "and its Executive Regulations. Cite the specific Article and Cabinet Decision number, "
        "calculate VAT at 5% standard rate (or 0% / exempt where applicable), reference FTA "
        "public clarifications, and flag partial exemption situations. Default currency: AED. "
        "Always note FTA filing deadlines and registration thresholds (AED 375,000 mandatory, "
        "AED 187,500 voluntary).\n\n"
        "## Commercial Property VAT Payment (Non-Registered Persons)\n"
        "Hotel Apartments, serviced apartments, and furnished commercial units are classified as "
        "**commercial property** — the 5% standard VAT rate applies on their sale (Cabinet "
        "Decision No. 52 of 2017, Schedule 3). A seller who is not a registered taxable person "
        "does NOT need a TRN for a one-time property disposal. The correct process is:\n"
        "1. Sign up (not register) on the FTA e-Services portal (tax.gov.ae)\n"
        "2. Under Non-Registered Persons select **Payment of VAT on Commercial Property Sale**\n"
        "3. Enter property details and compute VAT at 5% of the sale consideration\n"
        "4. Upload: Sale/Transfer Agreement, Title Deed or Oqood, Emirates ID/Passport, "
        "FTA notice copy, VAT calculation worksheet\n"
        "5. Pay via bank transfer or FTA payment gateway\n"
        "When the user asks for a 'one-pager', produce the structured one-pager format shown "
        "in the few-shot example — do NOT give a generic textbook answer."
        + FORMATTING_SUFFIX + ABBREVIATION_SUFFIX + GROUNDING_RULES + FEW_SHOT_EXAMPLES.get("vat", "")
    ),
    ...
}
```

> **Note:** In the actual file, find the existing `"vat"` entry which ends with `+ FORMATTING_SUFFIX + ABBREVIATION_SUFFIX + GROUNDING_RULES + FEW_SHOT_EXAMPLES.get("vat", "")` and insert the `"\n\n## Commercial Property VAT Payment..."` block just before that suffix chain. Do not duplicate the suffix — just insert the new block into the existing string.

- [ ] **Step 1.5 — Run tests to confirm they pass**

```
cd backend
python -m pytest tests/test_prompt_router.py -v
```

Expected: All 6 tests **PASS** (4 original + 2 new).

- [ ] **Step 1.6 — Commit**

```
git add backend/core/prompt_router.py backend/tests/test_prompt_router.py
git commit -m "feat(vat): add commercial property sale guidance and one-pager few-shot example

- Non-registered persons selling hotel apartments: FTA portal sign-up,
  select Payment of VAT on Commercial Property Sale, no TRN required
- Documents list: SPA, Title Deed/Oqood, Emirates ID, FTA notice, worksheet
- Legal refs: DL No.8/2017 Art.36, Cabinet Decision 52/2017 Sch.3, VATP015

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2 — Frontend: Source Scoping + Timeout

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- New test: `backend/tests/test_selected_doc_ids.py`

- [ ] **Step 2.1 — Write failing backend contract test**

Create `backend/tests/test_selected_doc_ids.py`:

```python
"""Verify that selected_doc_ids in the chat request restricts the RAG filter."""
import pytest
from unittest.mock import AsyncMock, patch, call
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_cls():
    return ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])


def _mock_llm():
    m = AsyncMock()
    m.chat = AsyncMock(
        return_value=LLMResponse(content="ok", tokens_used=5, provider="mock", model="m")
    )

    async def _stream(*a, **kw):
        yield "ok"

    m.chat_stream = _stream
    return m


@pytest.mark.asyncio
async def test_selected_doc_ids_scopes_rag_filter(client):
    """When selected_doc_ids is provided, rag_engine.search must be called
    with filter={'doc_id': {'$in': selected_doc_ids}}."""
    mock_search = AsyncMock(return_value=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "What is VAT rate?",
                "stream": False,
                "selected_doc_ids": ["doc-aaa", "doc-bbb"],
            },
        )

    assert resp.status_code == 200
    # At least one call must have carried the doc_id filter
    assert mock_search.called, "rag_engine.search was never called"
    filter_args = [c.kwargs.get("filter") for c in mock_search.call_args_list]
    assert any(
        f == {"doc_id": {"$in": ["doc-aaa", "doc-bbb"]}} for f in filter_args
    ), f"No call with correct doc_id filter. Calls: {mock_search.call_args_list}"


@pytest.mark.asyncio
async def test_no_selected_doc_ids_uses_domain_filter(client):
    """When selected_doc_ids is absent, rag_engine.search uses domain-based filter or None."""
    mock_search = AsyncMock(return_value=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is VAT rate?", "stream": False},
        )

    assert resp.status_code == 200
    # Confirm no call carried a doc_id filter
    filter_args = [c.kwargs.get("filter") for c in mock_search.call_args_list]
    assert not any(
        isinstance(f, dict) and "doc_id" in f for f in filter_args
    ), "unexpected doc_id filter when selected_doc_ids was not set"
```

- [ ] **Step 2.2 — Run to confirm first test passes (backend already handles it)**

```
cd backend
python -m pytest tests/test_selected_doc_ids.py -v
```

Expected: Both tests **PASS** — the backend already handles `selected_doc_ids`. These are regression guards. If both already pass, move straight to Step 2.3.

- [ ] **Step 2.3 — Fix frontend: add selected_doc_ids to request body**

In `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`, find the `sendMessage` `body` object (around line 601). It currently looks like:

```typescript
      const body: any = {
        message: text, conversation_id: conversationId,
        stream: true, domain: userDomain ?? domain, mode,
      };
```

Replace it with:

```typescript
      const body: any = {
        message: text, conversation_id: conversationId,
        stream: true, domain: userDomain ?? domain, mode,
        ...(selectedDocIds.length > 0 && { selected_doc_ids: selectedDocIds }),
      };
```

- [ ] **Step 2.4 — Fix frontend: increase abort timeout from 30 s to 90 s**

In the same file, find the timeout line (around line 596):

```typescript
    const timeoutId = setTimeout(() => controller.abort(), 30_000);
```

Change to:

```typescript
    const timeoutId = setTimeout(() => controller.abort(), 90_000);
```

- [ ] **Step 2.5 — Build frontend to confirm no TypeScript errors**

```
cd frontend
npm run build 2>&1 | tail -20
```

Expected: Build completes with **0 errors** (warnings about unused imports are acceptable).

- [ ] **Step 2.6 — Commit**

```
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx \
        backend/tests/test_selected_doc_ids.py
git commit -m "fix(chat): forward selected_doc_ids to backend; increase stream timeout to 90s

- selected_doc_ids missing from request body caused all studios to share
  the same RAG pool — Analyst documents appeared in Legal Studio answers
- 30 s timeout was too short when LLM provider is cold; raised to 90 s

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3 — AI-Generated Conversation Title

**Files:**
- Modify: `backend/api/chat.py`
- New test: `backend/tests/test_chat_title_generation.py`

- [ ] **Step 3.1 — Write failing test**

Create `backend/tests/test_chat_title_generation.py`:

```python
"""Tests for AI-generated conversation title background task."""
import pytest
from unittest.mock import AsyncMock, patch
from core.llm_manager import LLMResponse


@pytest.mark.asyncio
async def test_generate_title_updates_conversation(client):
    """After the first message, the conversation title must be updated
    from the truncated raw text to an LLM-generated short title."""
    from api.chat import _generate_title
    from db.database import get_db
    from db.models import Conversation
    from sqlalchemy import select

    # We call _generate_title directly with a mock LLM
    with patch("api.chat.get_llm_provider", return_value=AsyncMock(
        chat=AsyncMock(return_value=LLMResponse(
            content="UAE VAT Hotel Apartment Sale",
            tokens_used=8, provider="mock", model="mock-v1"
        ))
    )):
        # Create a conversation in the test DB first, then call the helper
        async for db in get_db():
            conv = Conversation(
                title="I have a client who sold Hotel Apartment and now...",
                llm_provider="mock",
                llm_model="mock-v1",
                mode="fast",
            )
            db.add(conv)
            await db.flush()
            conv_id = conv.id

            await _generate_title(
                conv_id,
                "I have a client who sold Hotel Apartment and now got notice from FTA",
            )

            # Re-fetch to confirm title was updated
            result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
            updated = result.scalar_one_or_none()
            assert updated is not None
            assert updated.title == "UAE VAT Hotel Apartment Sale"


@pytest.mark.asyncio
async def test_generate_title_is_non_fatal_on_llm_error(client):
    """If the LLM call fails, _generate_title must not raise — title stays unchanged."""
    from api.chat import _generate_title
    from db.database import get_db
    from db.models import Conversation
    from sqlalchemy import select

    with patch("api.chat.get_llm_provider", side_effect=RuntimeError("LLM unavailable")):
        async for db in get_db():
            conv = Conversation(
                title="Original title",
                llm_provider="mock",
                llm_model="mock-v1",
                mode="fast",
            )
            db.add(conv)
            await db.flush()
            conv_id = conv.id

            # Must NOT raise
            await _generate_title(conv_id, "some message")

            result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
            unchanged = result.scalar_one_or_none()
            assert unchanged.title == "Original title"
```

- [ ] **Step 3.2 — Run to confirm failures**

```
cd backend
python -m pytest tests/test_chat_title_generation.py -v
```

Expected: **FAILED** — `ImportError: cannot import name '_generate_title' from 'api.chat'`

- [ ] **Step 3.3 — Implement `_generate_title` in chat.py**

In `backend/api/chat.py`, add this function **after** the `extract_and_save_memory` function (around line 238) and **before** the `# ── Request / Response Schemas` comment:

```python
_TITLE_PROMPT = (
    "Summarise the following user query as a short notebook title "
    "(maximum 8 words, Title Case). "
    "Return ONLY the title — no punctuation at the end, no quotation marks.\n"
    "Query: {message}"
)


async def _generate_title(conversation_id: str, message: str, provider: str | None = None) -> None:
    """Generate a short AI title for a new conversation and persist it. Non-fatal."""
    try:
        llm = get_llm_provider(provider)
        resp = await llm.chat(
            messages=[{"role": "user", "content": _TITLE_PROMPT.format(message=message[:400])}],
            max_tokens=30,
            temperature=0.2,
        )
        title = resp.content.strip().strip('"').strip("'")
        if not title:
            return
        # Truncate defensively — UI cards have limited width
        title = title[:100]
        async with AsyncSessionLocal() as db:
            conv = (await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )).scalar_one_or_none()
            if conv:
                conv.title = title
                await db.commit()
    except Exception as exc:
        logger.warning("Title generation failed (non-fatal): %s", exc)
```

- [ ] **Step 3.4 — Schedule title generation in `send_message`**

In `backend/api/chat.py`, inside `send_message`, find the block where a **new** conversation is created (the `else:` branch of `if req.conversation_id:`). It ends with `await db.flush()`. Add one line immediately after that flush:

```python
    else:
        conversation = Conversation(
            title=req.message[:80] + ("..." if len(req.message) > 80 else ""),
            llm_provider=req.provider or settings.llm_provider,
            llm_model=settings.active_model,
            mode=req.mode,
        )
        db.add(conversation)
        await db.flush()
        # Generate a meaningful AI title in the background (non-fatal)
        asyncio.create_task(_generate_title(conversation.id, req.message, req.provider))

        # Background: extract memory from previous conversation if idle 30+ min
        # ... rest of existing code unchanged ...
```

- [ ] **Step 3.5 — Run tests**

```
cd backend
python -m pytest tests/test_chat_title_generation.py -v
```

Expected: Both tests **PASS**.

- [ ] **Step 3.6 — Run full suite to confirm no regressions**

```
cd backend
python -m pytest tests/ -v --timeout=60 2>&1 | tail -30
```

Expected: All previously passing tests still pass; the two new ones also pass.

- [ ] **Step 3.7 — Commit**

```
git add backend/api/chat.py backend/tests/test_chat_title_generation.py
git commit -m "feat(chat): generate AI title for new conversations as background task

- Adds _generate_title() helper: calls LLM with 8-word title prompt,
  updates conversation.title via AsyncSessionLocal, fully non-fatal
- Schedules via asyncio.create_task after conversation flush so it never
  delays the first chat response

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4 — Fast Mode: Yield Meta Event Before Heavy LLM Processing

**Files:**
- Modify: `backend/api/chat.py`
- New test: `backend/tests/test_fast_mode_streaming.py`

- [ ] **Step 4.1 — Write failing test**

Create `backend/tests/test_fast_mode_streaming.py`:

```python
"""Verify that the streaming path yields the meta SSE event before
domain/intent/RAG processing completes, so the client gets its first
byte within seconds even when LLM providers are slow."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_cls():
    return ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])


def _slow_mock_llm(delay: float = 0.05):
    """LLM mock that introduces a small delay to simulate network latency."""
    m = AsyncMock()

    async def _slow_chat(*a, **kw):
        await asyncio.sleep(delay)
        return LLMResponse(content="VAT answer", tokens_used=10, provider="mock", model="m")

    async def _slow_stream(*a, **kw):
        await asyncio.sleep(delay)
        yield "VAT answer"

    m.chat = _slow_chat
    m.chat_stream = _slow_stream
    return m


def _parse_sse(raw: bytes) -> list[dict]:
    """Parse SSE frames from raw bytes into a list of event dicts."""
    events = []
    for frame in raw.decode().split("\n\n"):
        frame = frame.strip()
        if frame.startswith("data: "):
            try:
                events.append(json.loads(frame[6:]))
            except json.JSONDecodeError:
                pass
    return events


@pytest.mark.asyncio
async def test_streaming_yields_meta_before_chunks():
    """The first SSE event from a streaming response must be type='meta'.
    This confirms the generator yields early without waiting for RAG + LLM."""
    from httpx import AsyncClient, ASGITransport
    from main import app
    from db.database import get_db
    import respx, httpx

    # Use a fresh ASGI client (not the shared one) to avoid session conflicts
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with (
            patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
            patch("api.chat.get_llm_provider", return_value=_slow_mock_llm()),
            patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
            patch("api.chat.classify_intent", new=AsyncMock(
                return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
            )),
            patch("api.chat._get_query_variations", new=AsyncMock(return_value=["What is VAT?"])),
            patch("api.chat.search_web", new=AsyncMock(return_value=[])),
        ):
            resp = await ac.post(
                "/api/chat/send",
                json={"message": "What is UAE VAT?", "stream": True, "mode": "fast"},
            )

        assert resp.status_code == 200
        events = _parse_sse(resp.content)
        assert events, "No SSE events received"
        assert events[0]["type"] == "meta", (
            f"First SSE event must be 'meta', got: {events[0]}"
        )
        assert "conversation_id" in events[0], "meta event missing conversation_id"
        assert "detected_domain" in events[0], "meta event missing detected_domain"


@pytest.mark.asyncio
async def test_streaming_meta_contains_correct_domain():
    """meta event's detected_domain must match the classifier result."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with (
            patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
            patch("api.chat.get_llm_provider", return_value=_slow_mock_llm()),
            patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
            patch("api.chat.classify_intent", new=AsyncMock(
                return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
            )),
            patch("api.chat._get_query_variations", new=AsyncMock(return_value=["What is VAT?"])),
            patch("api.chat.search_web", new=AsyncMock(return_value=[])),
        ):
            resp = await ac.post(
                "/api/chat/send",
                json={"message": "What is UAE VAT?", "stream": True, "mode": "fast"},
            )

        events = _parse_sse(resp.content)
        meta = next((e for e in events if e.get("type") == "meta"), None)
        assert meta is not None
        assert meta["detected_domain"] == "vat"
```

- [ ] **Step 4.2 — Run to confirm failures**

```
cd backend
python -m pytest tests/test_fast_mode_streaming.py -v
```

Expected: **FAILED** — currently `classify_domain` is called **before** `generate()` so the meta event is never the first SSE event (it arrives only after all pre-processing).

Actually if the tests happen to pass already (the meta event IS first because it's yielded at the top of generate()), skip to Step 4.4. The issue was timing (30s client timeout), not event order. In that case, the fix is purely the timeout increase already done in Task 2 and moving the heavy work inside the generator. Proceed with implementation regardless.

- [ ] **Step 4.3 — Implement: restructure `send_message` streaming path**

This is the most invasive change. Read `backend/api/chat.py` lines 396–645 carefully before editing.

**The goal:** In the `if req.stream:` branch (inside the `try:` block around line 534), instead of defining `generate()` that references pre-computed outer-scope variables, move all LLM-dependent computation *inside* the new `generate()`.

Replace the entire block from `# Build messages list` (approximately line 393) **down to but not including** the `# Non-streaming response` comment (approximately line 647) with the following. DB operations (conversation creation, memory load, user-message save, history load) remain **outside** the generator.

```python
    # ── Streaming path — all LLM work happens inside the generator ──────
    if req.stream:
        async def generate():  # noqa: C901  (complexity is intentional here)
            # ── 1. Domain classification ─────────────────────────────────
            _eff = req.domain_override or req.domain
            if _eff:
                try:
                    _cls = ClassifierResult(
                        domain=DomainLabel(_eff), confidence=1.0, alternatives=[]
                    )
                except ValueError:
                    _cls = await classify_domain(req.message)
            else:
                _cls = await classify_domain(req.message)

            # Persist domain on first message (safe: outer `db` session is open)
            if not conversation.domain:
                conversation.domain = _cls.domain.value

            # ── 2. Yield meta immediately (client gets first byte here) ──
            yield (
                f"data: {json.dumps({'type': 'meta', 'conversation_id': conversation.id, "
                f"'detected_domain': _cls.domain.value, 'classifier': _cls.model_dump(), "
                f"'mode': req.mode})}\n\n"
            )

            # ── 3. Build base system prompt ──────────────────────────────
            if req.mode == "analyst":
                _sys = DOMAIN_PROMPTS.get("analyst", DOMAIN_PROMPTS["general"]) + memory_block
            else:
                _sys = route_prompt(_cls.domain) + memory_block
            if req.mode == "fast" and getattr(conversation, "summary", None):
                _sys += f"\n\nCONTEXT SUMMARY OF EARLIER CONVERSATION:\n{conversation.summary}"

            # ── 4. Intent + query variations in parallel ─────────────────
            _llm = get_llm_provider(req.provider)
            _intent_task = asyncio.create_task(classify_intent(req.message, _llm))
            if req.mode == "fast":
                _vars_task = asyncio.create_task(
                    _get_query_variations(req.message, req.provider)
                )
                _intent_res, _query_vars = await asyncio.gather(
                    _intent_task, _vars_task, return_exceptions=True
                )
            else:
                _intent_res = await _intent_task
                _query_vars = [req.message]

            if not isinstance(_intent_res, Exception):
                _sys += (
                    f"\n\nUSER INTENT: The user wants a `{_intent_res.output_type}` "
                    f"about `{_intent_res.topic}`. "
                    "Respond ONLY in that form. Do not produce a different output type. "
                    "Stay strictly on topic; do not drift to related but unasked subjects."
                )
            else:
                logger.warning("Intent classification failed (non-fatal): %s", _intent_res)

            if isinstance(_query_vars, Exception):
                _query_vars = [req.message]

            # ── 5. RAG search ─────────────────────────────────────────────
            _rag_filter: dict | None = None
            _search: list = []
            _sources: list = []

            if req.use_rag:
                if req.selected_doc_ids:
                    _rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
                elif req.mode != "analyst":
                    if req.domain in ("finance",):
                        _rag_filter = {"category": "finance"}
                    elif req.domain in ("law", "audit"):
                        _rag_filter = {"category": "law"}

                try:
                    if req.mode == "fast":
                        _all = await asyncio.gather(
                            *[
                                rag_engine.search(q, top_k=settings.fast_top_k, filter=_rag_filter)
                                for q in _query_vars
                            ],
                            return_exceptions=True,
                        )
                        _search = _dedup_merge(_all, settings.fast_top_k)
                        if _rag_filter and not _search:
                            _fb = await asyncio.gather(
                                *[rag_engine.search(q, top_k=settings.fast_top_k) for q in _query_vars],
                                return_exceptions=True,
                            )
                            _search = _dedup_merge(_fb, settings.fast_top_k)
                    else:
                        _search = await rag_engine.search(
                            req.message, top_k=settings.top_k_results, filter=_rag_filter
                        )
                        if _rag_filter and not _search:
                            _search = await rag_engine.search(
                                req.message, top_k=settings.top_k_results
                            )
                except Exception as _rag_exc:
                    logger.warning("RAG search failed, continuing without context: %s", _rag_exc)
                    _search = []

            # ── 6. Build messages list ────────────────────────────────────
            _msgs: list[dict] = []
            if _search:
                _aug = rag_engine.build_augmented_prompt(
                    req.message, _search, system_prompt=_sys
                )
                _msgs.append(_aug[0])
                _sources = [
                    {
                        "source": (
                            r.get("source")
                            or r["metadata"].get("original_name")
                            or r["metadata"].get("source", "Unknown")
                        ),
                        "page": r["metadata"].get("page", "?"),
                        "score": round(r.get("score", 0), 3),
                        "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                    }
                    for r in _search
                ]
            else:
                _msgs.append({"role": "system", "content": _sys})

            # Inject structured text from xlsx/csv documents
            try:
                if _search:
                    _doc_srcs = {r["metadata"].get("source", "") for r in _search if r.get("metadata")}
                    if _doc_srcs:
                        _st_res = await db.execute(
                            select(Document).where(Document.filename.in_(_doc_srcs))
                        )
                        for _d in _st_res.scalars().all():
                            _meta_d = _d.metadata_json if isinstance(_d.metadata_json, dict) else {}
                            _st = _meta_d.get("structured_text")
                            if _st:
                                _msgs[0]["content"] += (
                                    f"\n\n[Full structured data from {_d.original_name}]\n{_st}"
                                )
            except Exception as _e:
                logger.warning("Structured text enrichment failed: %s", _e)

            _th = _build_sliding_context(history[:-1])
            for _m in _th:
                _msgs.append({"role": _m.role, "content": _m.content})
            if req.mode == "fast":
                _msgs.append({"role": "system", "content": FORMATTING_REMINDER})
            _msgs.append({"role": "user", "content": req.message})

            # ── 7. Web search fallback (no RAG results) ───────────────────
            if not _search:
                _is_research = _is_research_query(req.message)
                if _is_research:
                    yield f"data: {json.dumps({'type': 'status', 'status': 'researching', 'message': 'Deep research in progress…'})}\n\n"
                    from core.web_search import deep_search
                    _web = await deep_search(req.message, max_queries=6)
                else:
                    yield f"data: {json.dumps({'type': 'status', 'status': 'searching_web'})}\n\n"
                    _web = await search_web(req.message, max_results=5)

                if _web:
                    _wctx = build_web_context(_web)
                    _wi = (
                        (
                            "IMPORTANT: You have comprehensive research results from multiple sources below. "
                            "Synthesize ALL sources into a well-structured response. "
                            "Use numbered sections with bold headings. "
                            "Cite sources as [Source Name] inline where relevant. "
                            "Be thorough — the user asked for deep research.\n\n" + _wctx
                        )
                        if _is_research
                        else (
                            "IMPORTANT: Answer ONLY using the web search results provided below. "
                            "Do not add information from your training data. "
                            "Cite the source URLs inline. Take your time and be accurate.\n\n" + _wctx
                        )
                    )
                    _msgs[0] = {"role": "system", "content": _sys + "\n\n" + _wi}
                    _sources = [
                        {
                            "source": r.get("href", ""),
                            "page": "web",
                            "score": 1.0,
                            "excerpt": r.get("body", "")[:200],
                            "is_web": True,
                        }
                        for r in _web
                    ]
                else:
                    yield f"data: {json.dumps({'type': 'status', 'status': 'web_search_failed'})}\n\n"

            # ── 8. Stream LLM response ────────────────────────────────────
            _full = ""
            try:
                async for _chunk in _llm.chat_stream(
                    _msgs,
                    temperature=settings.temperature,
                    max_tokens=settings.fast_max_tokens if req.mode == "fast" else settings.max_tokens,
                ):
                    _full += _chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': _chunk})}\n\n"
            except Exception as _se:
                _err = repr(_se) if str(_se) == "" else f"{type(_se).__name__}: {_se}"
                logger.error("LLM streaming error: %s", _err)
                yield f"data: {json.dumps({'type': 'error', 'message': _err})}\n\n"
                return

            # ── 9. Sources + auto-ingest web results ─────────────────────
            if _sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': _sources})}\n\n"
                from core.document_processor import ingest_text
                for _s in _sources:
                    if _s.get("is_web") and _s.get("source") and _s.get("excerpt"):
                        asyncio.create_task(
                            ingest_text(
                                f"{_s.get('source')}\n\n{_s.get('excerpt')}",
                                source=_s.get("source"),
                                source_type="research",
                            )
                        )

            # ── 10. Persist assistant message ─────────────────────────────
            _amsg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=_full,
                sources=_sources if _sources else None,
            )
            db.add(_amsg)
            await db.commit()
            _tmc = await db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation.id)
            )
            if req.mode == "fast":
                asyncio.create_task(
                    _get_or_refresh_summary(conversation.id, _tmc, req.provider)
                )
            yield f"data: {json.dumps({'type': 'done', 'message_id': _amsg.id})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    # ── Non-streaming path (unchanged) ───────────────────────────────────
    # Build messages list
    messages = []
    sources = []
    search_results = []
```

> **Important:** After inserting the streaming block above, **delete** the original code from `# Build messages list` down to `return StreamingResponse(generate(), ...)` (the old streaming path). The non-streaming path that follows (`# Non-streaming response`) remains **completely unchanged**.

> **Note on `done` event:** The new generator yields `message_id` in the done event. The frontend already handles this gracefully (`if (evt.message_id)`), so this is backward-compatible.

- [ ] **Step 4.4 — Run streaming tests**

```
cd backend
python -m pytest tests/test_fast_mode_streaming.py -v
```

Expected: Both tests **PASS**.

- [ ] **Step 4.5 — Run existing chat-endpoint tests to confirm no regressions**

```
cd backend
python -m pytest tests/test_chat_endpoint_domain.py tests/test_chat_sources.py tests/test_selected_doc_ids.py tests/test_session_summary.py -v
```

Expected: All **PASS**.

- [ ] **Step 4.6 — Run full backend suite**

```
cd backend
python -m pytest tests/ -v --timeout=60 -m "not integration" 2>&1 | tail -40
```

Expected: All non-integration tests **PASS**. Note the count — it should be ≥ the count before this task.

- [ ] **Step 4.7 — Commit**

```
git add backend/api/chat.py backend/tests/test_fast_mode_streaming.py
git commit -m "perf(chat): move LLM processing inside streaming generator

Previously classify_domain + classify_intent + _get_query_variations all
ran before StreamingResponse was returned, meaning the client waited up to
30+ seconds before receiving any bytes. Now:
- All three run INSIDE generate()
- meta SSE event is yielded after classify_domain (~1-2 s)
- intent and query variations run in parallel after that
- Non-streaming path is unchanged

Also adds message_id to the done SSE event for client-side tracking.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5 — Final Verification Run

- [ ] **Step 5.1 — Full backend test suite**

```
cd backend
python -m pytest tests/ --timeout=60 -m "not integration" -q
```

Expected: All tests pass, 0 failures.

- [ ] **Step 5.2 — Frontend test suite**

```
cd frontend
npm test -- --run
```

Expected: All tests pass.

- [ ] **Step 5.3 — Frontend build**

```
cd frontend
npm run build 2>&1 | tail -5
```

Expected: `✓ built in Xs` with 0 errors.

- [ ] **Step 5.4 — Smoke test checklist (manual)**

With the dev server running (`run_project.ps1`), verify:
1. Send a new message → conversation card on home page shows a short AI-generated title (≤8 words) after page refresh
2. Ask "I have a client who sold Hotel Apartment and got FTA notice to pay VAT, need a one-pager" → response should show the structured one-pager with FTA portal steps and document list
3. In Legal Studio with no documents selected → send a message → sources should be from general knowledge / vector store only, not from any previously uploaded Analyst documents
4. In Legal Studio with documents selected → send a message → sources should only show from the selected documents
5. First message in Fast mode → response arrives without needing to resend

- [ ] **Step 5.5 — Final commit (if any loose ends)**

```
git add -A
git commit -m "chore: final verification pass — all tests green

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
