# Bug Fixes + Fast Mode Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 chatbot bugs (UUID source names, broken markdown, silent deep research, analyst mode reset) and enhance fast mode with a larger token budget, format guard injection, multi-query RAG, and session summary memory.

**Architecture:** All 4 bugs are isolated single-file or two-file changes with no shared dependencies. Fast mode enhancements are purely additive — new helpers and conditional branches inside the existing `send_message` endpoint. Tasks 1–4 are bugs to fix first; Tasks 5–8 are fast mode enhancements in any order.

**Tech Stack:** FastAPI + SQLAlchemy async (SQLite), ChromaDB (RAG), React 19 + TypeScript, ReactMarkdown + remark-gfm, Vitest + @testing-library/react, pytest + httpx.AsyncClient + ASGITransport.

**Specs:**
- `docs/superpowers/specs/2026-04-22-chatbot-bug-fixes-design.md`
- `docs/superpowers/specs/2026-04-22-fast-mode-enhancements-design.md`

---

## File Map

| File | Action | Tasks |
|---|---|---|
| `backend/api/chat.py` | **Modify** | 1, 2, 4, 5, 6, 7, 8 |
| `backend/core/rag_engine.py` | **Modify** | 2 |
| `backend/core/prompt_router.py` | **Modify** | 6 |
| `backend/config.py` | **Modify** | 5 |
| `backend/db/models.py` | **Modify** | 8 |
| `backend/db/database.py` | **Modify** | 8 |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | **Modify** | 3 |
| `frontend/src/hooks/useDeepResearch.ts` | **Modify** | 4 |
| `frontend/src/components/studios/LegalStudio/ResearchPanel.tsx` | **Modify** | 4 |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | **Modify** | 4 |
| `backend/tests/test_chat_endpoint_domain.py` | **Modify** | 1 |
| `backend/tests/test_chat_sources.py` | **Create** | 2 |
| `frontend/src/components/studios/LegalStudio/__tests__/normalizeMarkdown.test.ts` | **Create** | 3 |
| `backend/tests/test_deep_research_stream.py` | **Create** | 4 |
| `frontend/src/hooks/__tests__/useDeepResearch.test.ts` | **Modify** | 4 |
| `backend/tests/test_token_budget.py` | **Create** | 5 |
| `backend/tests/core/test_prompt_router.py` | **Modify** | 6 |
| `backend/tests/test_multi_query_rag.py` | **Create** | 7 |
| `backend/tests/test_session_summary.py` | **Create** | 8 |

---

## Task 1: Bug 4 — Analyst Mode Resets on Send

**Root cause:** When `POST /api/chat/send` creates a new conversation (no `conversation_id`), it does NOT pass `mode=req.mode` to the `Conversation()` constructor. SQLAlchemy uses the column default `"fast"`. The frontend then reads `mode: "fast"` back and `useNotebookMode` overwrites the user's analyst selection.

**Files:**
- Modify: `backend/api/chat.py:228-232`
- Modify: `backend/tests/test_chat_endpoint_domain.py`

- [ ] **Step 1.1: Write the failing test**

Add to `backend/tests/test_chat_endpoint_domain.py` (after the existing `test_send_accepts_mode_field` test):

```python
@pytest.mark.asyncio
async def test_send_with_analyst_mode_persists_mode(client):
    """New conversation created via send must store mode from the request."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier(DomainLabel.GENERAL_LAW))),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "hello", "mode": "analyst", "stream": False},
        )
    assert resp.status_code == 200
    cid = resp.json()["conversation_id"]

    r2 = await client.get(f"/api/chat/conversations/{cid}")
    assert r2.status_code == 200
    assert r2.json()["mode"] == "analyst"
```

- [ ] **Step 1.2: Run test to verify it fails**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_chat_endpoint_domain.py::test_send_with_analyst_mode_persists_mode -v
```

Expected: FAIL — `assert r2.json()["mode"] == "analyst"` fails because the value is `"fast"`.

- [ ] **Step 1.3: Apply the one-line fix in `backend/api/chat.py`**

Find (lines 228–232):
```python
        conversation = Conversation(
            title=req.message[:80] + ("..." if len(req.message) > 80 else ""),
            llm_provider=req.provider or settings.llm_provider,
            llm_model=settings.active_model,
        )
```

Replace with:
```python
        conversation = Conversation(
            title=req.message[:80] + ("..." if len(req.message) > 80 else ""),
            llm_provider=req.provider or settings.llm_provider,
            llm_model=settings.active_model,
            mode=req.mode,
        )
```

- [ ] **Step 1.4: Run test to verify it passes**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_chat_endpoint_domain.py::test_send_with_analyst_mode_persists_mode -v
```

Expected: PASS.

- [ ] **Step 1.5: Commit**

```
git add backend/api/chat.py backend/tests/test_chat_endpoint_domain.py
git commit -m "fix: persist mode when send creates new conversation

When POST /api/chat/send created a new conversation, Conversation()
was missing mode=req.mode — the column default 'fast' overwrote the
user's analyst selection on every new chat.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Bug 1 — UUID Source Names

**Root cause:** Two places read `meta.get("source")` (a UUID-prefixed storage filename like `a1b2c3_contract.pdf`) instead of `meta.get("original_name")` (the human-readable name the user uploaded). Both `rag_engine.py:342` and `chat.py:368` need to prefer `original_name`.

**Files:**
- Modify: `backend/core/rag_engine.py:342`
- Modify: `backend/api/chat.py:368`
- Create: `backend/tests/test_chat_sources.py`

- [ ] **Step 2.1: Write the failing test**

Create `backend/tests/test_chat_sources.py`:

```python
"""Tests that source names in chat responses use original_name, not UUID hash filenames."""
import pytest
from unittest.mock import AsyncMock, patch
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_classifier():
    return ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.9, alternatives=[])


def _mock_llm():
    mock = AsyncMock()
    mock.chat = AsyncMock(
        return_value=LLMResponse(
            content="VAT is 5%.", tokens_used=10, provider="mock", model="mock-v1"
        )
    )

    async def _fake_stream(*a, **kw):
        yield "VAT is 5%."

    mock.chat_stream = _fake_stream
    return mock


RAG_RESULT = [
    {
        "text": "VAT rate is 5% on most goods.",
        "metadata": {
            "source": "a1b2c3d4_vat_guide.pdf",
            "original_name": "UAE VAT Guide 2024.pdf",
            "page": 3,
            "doc_id": "doc-001",
        },
        "score": 0.92,
    }
]


@pytest.mark.asyncio
async def test_sources_use_original_name_not_uuid(client):
    """Source names in the chat response must be original_name, not UUID-prefixed filename."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT rate?", "use_rag": True, "stream": False},
        )
    assert resp.status_code == 200
    sources = resp.json()["message"]["sources"]
    assert sources, "Expected at least one source"
    assert sources[0]["source"] == "UAE VAT Guide 2024.pdf", (
        f"Expected original_name, got: {sources[0]['source']}"
    )
    assert "a1b2c3d4" not in sources[0]["source"]
```

- [ ] **Step 2.2: Run test to verify it fails**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_chat_sources.py -v
```

Expected: FAIL — source is `"a1b2c3d4_vat_guide.pdf"` instead of `"UAE VAT Guide 2024.pdf"`.

- [ ] **Step 2.3: Fix `backend/core/rag_engine.py` line 342**

Find:
```python
                    "source": meta.get("source", meta.get("filename", "Unknown")),
```

Replace with:
```python
                    "source": meta.get("original_name") or meta.get("source", meta.get("filename", "Unknown")),
```

- [ ] **Step 2.4: Fix `backend/api/chat.py` lines 366–374**

Find:
```python
            sources = [
                {
                    "source": r["metadata"].get("source", "Unknown"),
                    "page": r["metadata"].get("page", "?"),
                    "score": round(r.get("score", 0), 3),
                    "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                }
                for r in search_results
            ]
```

Replace with:
```python
            sources = [
                {
                    "source": r["metadata"].get("original_name") or r["metadata"].get("source", "Unknown"),
                    "page": r["metadata"].get("page", "?"),
                    "score": round(r.get("score", 0), 3),
                    "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                }
                for r in search_results
            ]
```

- [ ] **Step 2.5: Run test to verify it passes**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_chat_sources.py -v
```

Expected: PASS.

- [ ] **Step 2.6: Commit**

```
git add backend/core/rag_engine.py backend/api/chat.py backend/tests/test_chat_sources.py
git commit -m "fix: use original_name for source display instead of UUID hash filename

Two places read metadata['source'] (UUID-prefixed storage name) instead
of metadata['original_name'] (human-readable upload name). Fixed both
rag_engine.py and api/chat.py to prefer original_name with source fallback.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Bug 2 — Broken Markdown in Long Chats

**Root cause:** `ReactMarkdown` requires blank lines before `##` headers and around `---` dividers to render them structurally. The LLM omits these blank lines, so they render as plain text in long conversations. A `normalizeMarkdown()` pre-processor inserted before `<ReactMarkdown>` fixes this.

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` (add `normalizeMarkdown`, apply on line 101)
- Create: `frontend/src/components/studios/LegalStudio/__tests__/normalizeMarkdown.test.ts`

- [ ] **Step 3.1: Write the failing test**

Create `frontend/src/components/studios/LegalStudio/__tests__/normalizeMarkdown.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { normalizeMarkdown } from '../ChatMessages';

describe('normalizeMarkdown', () => {
  it('adds blank line before ## header when preceded by a non-blank line', () => {
    const result = normalizeMarkdown('Some text\n## Section Title\nMore text');
    expect(result).toMatch(/Some text\n\n## Section Title/);
  });

  it('does not triple-up blank lines when blank line already present', () => {
    const result = normalizeMarkdown('Some text\n\n## Section Title\nMore text');
    expect(result).not.toMatch(/\n\n\n/);
  });

  it('adds blank lines around --- divider with no surrounding blank lines', () => {
    const result = normalizeMarkdown('First paragraph\n---\nSecond paragraph');
    expect(result).toMatch(/First paragraph\n\n---/);
    expect(result).toMatch(/---\n\nSecond paragraph/);
  });

  it('leaves plain text unchanged', () => {
    const input = 'Hello world\nThis is a normal message.';
    expect(normalizeMarkdown(input)).toBe(input);
  });
});
```

- [ ] **Step 3.2: Run test to verify it fails**

```
cd Project_AccountingLegalChatbot/frontend
npx vitest run src/components/studios/LegalStudio/__tests__/normalizeMarkdown.test.ts
```

Expected: FAIL — `normalizeMarkdown` is not exported from `ChatMessages`.

- [ ] **Step 3.3: Add `normalizeMarkdown` to `ChatMessages.tsx` and apply it**

In `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`, insert after the `parseThinking` function (after line 41):

```typescript
export function normalizeMarkdown(text: string): string {
  return text
    // Blank lines around --- dividers
    .replace(/([^\n])\n(---+)(\n|$)/g, '$1\n\n$2\n\n')
    .replace(/(^|\n)(---+)\n([^\n])/g, '$1$2\n\n$3')
    // Blank line before ## headers
    .replace(/([^\n])\n(#{1,6} )/g, '$1\n\n$2');
}
```

Then change line 101 from:
```typescript
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayText}</ReactMarkdown>
```

To:
```typescript
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeMarkdown(displayText)}</ReactMarkdown>
```

- [ ] **Step 3.4: Run test to verify it passes**

```
cd Project_AccountingLegalChatbot/frontend
npx vitest run src/components/studios/LegalStudio/__tests__/normalizeMarkdown.test.ts
```

Expected: PASS (all 4 tests).

- [ ] **Step 3.5: Commit**

```
git add "frontend/src/components/studios/LegalStudio/ChatMessages.tsx" "frontend/src/components/studios/LegalStudio/__tests__/normalizeMarkdown.test.ts"
git commit -m "fix: normalizeMarkdown pre-processor to restore broken markdown structure

ReactMarkdown needs blank lines around --- and ## to render structurally.
LLM output omits these, causing dividers/headers to render as plain text
in long conversations. normalizeMarkdown() inserts the missing blank lines.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Bug 3 — Deep Research Shows No Output

**Root cause (two sub-bugs):**
1. **Backend key typo:** `chat.py:822` reads `r.get("document", "")` but RAG results use key `"text"` → snippets are empty → LLM synthesises nothing.
2. **No streaming yield:** LLM chunks accumulate in `answer_parts` without ever being `yield`-ed → frontend gets nothing until the entire response is assembled server-side.
3. **Frontend misrouting:** `LegalStudio.tsx` answer useEffect pushes `role:"ai"` message → `ChatMessages.tsx` renders `<AIMessage>` instead of `<ResearchBubble>`.

**Files:**
- Modify: `backend/api/chat.py:822` (key fix) and surrounding `async for chunk` loop (add yield)
- Modify: `frontend/src/hooks/useDeepResearch.ts` (add `streamingContent` state)
- Modify: `frontend/src/components/studios/LegalStudio/ResearchPanel.tsx` (add `streamingContent` prop)
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` (fix answer useEffect, pass streamingContent)
- Create: `backend/tests/test_deep_research_stream.py`
- Modify: `frontend/src/hooks/__tests__/useDeepResearch.test.ts`

- [ ] **Step 4.1: Write the backend failing test**

Create `backend/tests/test_deep_research_stream.py`:

```python
"""Tests for deep research SSE streaming — Bug 3 fix."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from starlette.testclient import TestClient
from main import app
from core.llm_manager import LLMResponse


def _mock_llm_stream(text: str):
    """LLM mock that streams tokens one word at a time."""
    mock = MagicMock()
    mock.chat = AsyncMock(return_value=LLMResponse(content=text, tokens_used=8, provider="mock", model="mock-v1"))

    async def _stream(*a, **kw):
        for word in text.split():
            yield word + " "

    mock.chat_stream = _stream
    return mock


RAG_HITS = [
    {
        "text": "UAE VAT applies at 5% on standard-rated supplies.",
        "metadata": {"source": "vat.pdf", "original_name": "UAE VAT Guide.pdf", "page": 1, "doc_id": "doc1"},
        "score": 0.95,
    }
]


def test_deep_research_streams_chunks():
    """deep-research endpoint must yield SSE chunks and then the final answer."""
    with (
        patch("api.chat.get_llm_provider", return_value=_mock_llm_stream("VAT is 5 percent.")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_HITS)),
    ):
        client = TestClient(app)
        with client.stream("POST", "/api/chat/deep-research", json={"query": "UAE VAT rate", "doc_ids": []}) as r:
            raw = b"".join(r.iter_bytes()).decode()

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    types = [e["type"] for e in events]

    assert "chunk" in types, f"No chunk events found. Events: {types}"
    answer_events = [e for e in events if e["type"] == "answer"]
    assert answer_events, "No answer event found"
    assert "VAT" in answer_events[0]["content"]


def test_deep_research_passes_text_key_to_llm():
    """RAG results must pass the 'text' key (not 'document') to the LLM context."""
    captured_prompt = []

    def _mock_with_capture():
        mock = MagicMock()

        async def _stream(*a, messages=None, **kw):
            if messages:
                captured_prompt.append(messages[-1]["content"])
            yield "Answer."

        mock.chat_stream = _stream
        return mock

    with (
        patch("api.chat.get_llm_provider", return_value=_mock_with_capture()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_HITS)),
    ):
        client = TestClient(app)
        with client.stream("POST", "/api/chat/deep-research", json={"query": "VAT", "doc_ids": []}) as r:
            b"".join(r.iter_bytes())

    assert captured_prompt, "LLM was not called"
    assert "VAT applies at 5%" in captured_prompt[0], (
        f"Expected document text in prompt. Got: {captured_prompt[0][:200]}"
    )
```

- [ ] **Step 4.2: Run backend test to verify it fails**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_deep_research_stream.py -v
```

Expected: FAIL — no `chunk` events; `text` not in LLM prompt.

- [ ] **Step 4.3: Fix `backend/api/chat.py` — key typo and add streaming yield**

*Change 1* — Fix the `"document"` key typo on line 822.

Find:
```python
            snippet = r.get("document", "")[:600]
```

Replace with:
```python
            snippet = r.get("text", "")[:600]
```

*Change 2* — Add `yield` inside the `async for chunk` loop (around line 856).

Find the synthesis `async for` loop which looks like:
```python
                async for chunk in llm.chat_stream(
                    messages=synthesis_messages,
                    max_tokens=2000,
                    temperature=0.3,
                ):
                    answer_parts.append(chunk)
```

Replace with:
```python
                async for chunk in llm.chat_stream(
                    messages=synthesis_messages,
                    max_tokens=2000,
                    temperature=0.3,
                ):
                    answer_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
```

- [ ] **Step 4.4: Run backend test to verify it passes**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_deep_research_stream.py -v
```

Expected: PASS (both tests).

- [ ] **Step 4.5: Fix `frontend/src/hooks/useDeepResearch.ts`**

Add `streamingContent` state and handle `chunk` events. The current hook tracks `steps` and `answer`. Add streaming partial content alongside those.

Find (around line 10 near the existing state declarations):
```typescript
  const [steps, setSteps] = useState<ResearchStep[]>([]);
  const [answer, setAnswer] = useState<string>('');
  const [running, setRunning] = useState(false);
```

Replace with:
```typescript
  const [steps, setSteps] = useState<ResearchStep[]>([]);
  const [answer, setAnswer] = useState<string>('');
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [running, setRunning] = useState(false);
```

Inside the `run()` function, find the reset block (before the `fetch` call):
```typescript
    setSteps([]);
    setAnswer('');
    setRunning(true);
```

Replace with:
```typescript
    setSteps([]);
    setAnswer('');
    setStreamingContent('');
    setRunning(true);
```

Inside `handleFrame` (the SSE event dispatcher), find where event types are handled. Add a `chunk` branch. The existing structure likely looks like:
```typescript
    if (frame.type === 'step') { ... }
    else if (frame.type === 'answer') { setAnswer(frame.content); }
```

Add after the `step` branch:
```typescript
    else if (frame.type === 'chunk') {
      setStreamingContent(prev => prev + (frame.content ?? ''));
    }
```

Find the return statement of the hook:
```typescript
  return { steps, answer, running, run };
```

Replace with:
```typescript
  return { steps, answer, streamingContent, running, run };
```

- [ ] **Step 4.6: Fix `frontend/src/components/studios/LegalStudio/ResearchPanel.tsx`**

Add `streamingContent` prop to show partial output while research is in progress.

Find the `ResearchPanelProps` type (or the props destructuring):
```typescript
interface ResearchPanelProps {
  steps: ResearchStep[];
  answer: string | null;
```

Add `streamingContent` to the interface:
```typescript
interface ResearchPanelProps {
  steps: ResearchStep[];
  answer: string | null;
  streamingContent?: string;
```

In the component body, find the section that shows the answer (typically a conditional `{answer && <div>...</div>}`). Add streaming content display just before it:

```typescript
{!answer && streamingContent && (
  <div className="research-streaming">
    <div className="text-xs text-muted-foreground mb-1">Synthesising…</div>
    <div className="text-sm whitespace-pre-wrap opacity-80">{streamingContent}</div>
  </div>
)}
```

- [ ] **Step 4.7: Fix `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`**

*Change 1* — Add `lastResearchQuery` ref and `streamingContent` to destructuring (around line 68):

Find:
```typescript
  const { steps, answer, running: researchRunning, run: runDeepResearch } = useDeepResearch();
```

Replace with:
```typescript
  const { steps, answer, streamingContent, running: researchRunning, run: runDeepResearch } = useDeepResearch();
  const lastResearchQuery = useRef<string>('');
```

*Change 2* — Capture the query before running deep research (around line 565):

Find the call to `runDeepResearch`:
```typescript
    await runDeepResearch(text, selectedDocIds);
```

Replace with:
```typescript
    lastResearchQuery.current = text;
    await runDeepResearch(text, selectedDocIds);
```

*Change 3* — Fix the `answer` useEffect (lines 696–710) to emit `role:'research'` message. Find the `useEffect` that pushes to messages when `answer` changes. It currently looks like:

```typescript
  useEffect(() => {
    if (!answer) return;
    const msg: TextMessage = {
      role: 'ai',
      id: Date.now().toString(),
      content: answer,
    };
    setMessages(prev => [...prev, msg]);
  }, [answer]);
```

Replace with:
```typescript
  useEffect(() => {
    if (!answer) return;
    const msg: ResearchMessage = {
      role: 'research',
      id: Date.now().toString(),
      query: lastResearchQuery.current,
      phases: steps.map(s => ({ phase: s.status, message: s.text })),
      report: answer,
      sources: [],
      time: fmtTime(Date.now()),
    };
    setMessages(prev => [...prev, msg]);
  }, [answer]);
```

Make sure `ResearchMessage` and `fmtTime` are imported at the top of `LegalStudio.tsx`:
```typescript
import type { ResearchMessage } from '@/lib/api';
import { fmtTime } from '@/lib/api';
```

*Change 4* — Pass `streamingContent` to `<ResearchPanel>` (around line 873):

Find:
```typescript
              <ResearchPanel steps={steps} answer={answer} />
```

Replace with:
```typescript
              <ResearchPanel steps={steps} answer={answer} streamingContent={streamingContent} />
```

- [ ] **Step 4.8: Run backend and frontend tests**

Backend:
```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_deep_research_stream.py -v
```

Frontend:
```
cd Project_AccountingLegalChatbot/frontend
npx vitest run src/hooks/__tests__/useDeepResearch.test.ts
```

Expected: all tests PASS.

- [ ] **Step 4.9: Commit**

```
git add backend/api/chat.py frontend/src/hooks/useDeepResearch.ts "frontend/src/components/studios/LegalStudio/ResearchPanel.tsx" "frontend/src/components/studios/LegalStudio/LegalStudio.tsx" backend/tests/test_deep_research_stream.py
git commit -m "fix: deep research now streams and displays correctly

Three root causes fixed:
1. chat.py used wrong key 'document' instead of 'text' for RAG snippets
2. LLM chunks were buffered with no yield — frontend got nothing mid-stream
3. answer useEffect pushed role:'ai' instead of role:'research',
   bypassing ResearchBubble renderer

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Fast Mode — Token Budget

**What this does:** Doubles the token budget for fast mode answers so the LLM has room to write complete, well-structured responses instead of truncating mid-section.

**Files:**
- Modify: `backend/config.py:78-79` (`top_k_results` 8→15, `max_tokens` 4096→8192)
- Modify: `backend/api/chat.py:54` (`max_tokens_estimate` 6000→12000 in `_build_sliding_context`)
- Create: `backend/tests/test_token_budget.py`

- [ ] **Step 5.1: Write the failing test**

Create `backend/tests/test_token_budget.py`:

```python
"""Tests that config and sliding-context use the expanded token budget."""
import inspect
import pytest
from config import Settings
from api.chat import _build_sliding_context


def test_default_max_tokens_is_8192():
    """max_tokens field default must be 8192 for fast mode quality."""
    field = Settings.model_fields.get("max_tokens")
    assert field is not None, "max_tokens field not found in Settings"
    assert field.default == 8192, f"Expected 8192, got {field.default}"


def test_default_top_k_results_is_15():
    """top_k_results field default must be 15 for broader RAG coverage."""
    field = Settings.model_fields.get("top_k_results")
    assert field is not None, "top_k_results field not found in Settings"
    assert field.default == 15, f"Expected 15, got {field.default}"


def test_sliding_context_default_is_12000():
    """_build_sliding_context default max_tokens_estimate must be 12000."""
    sig = inspect.signature(_build_sliding_context)
    param = sig.parameters.get("max_tokens_estimate")
    assert param is not None, "max_tokens_estimate param not found"
    assert param.default == 12000, f"Expected 12000, got {param.default}"
```

- [ ] **Step 5.2: Run test to verify it fails**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_token_budget.py -v
```

Expected: FAIL — defaults are 4096, 8, and 6000 respectively.

- [ ] **Step 5.3: Apply the config changes**

In `backend/config.py`, find (lines 78–79):
```python
    top_k_results: int = 8
    max_tokens: int = 4096
```

Replace with:
```python
    top_k_results: int = 15
    max_tokens: int = 8192
```

In `backend/api/chat.py`, find (line 54):
```python
def _build_sliding_context(history: list, max_tokens_estimate: int = 6000) -> list:
```

Replace with:
```python
def _build_sliding_context(history: list, max_tokens_estimate: int = 12000) -> list:
```

- [ ] **Step 5.4: Run test to verify it passes**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_token_budget.py -v
```

Expected: PASS.

- [ ] **Step 5.5: Commit**

```
git add backend/config.py backend/api/chat.py backend/tests/test_token_budget.py
git commit -m "feat(fast-mode): expand token budget for richer responses

max_tokens 4096->8192, top_k_results 8->15, sliding context 6000->12000.
Gives LLM enough room to complete structured answers without truncation.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Fast Mode — Format Guard

**What this does:** Injects a one-line formatting reminder into every fast-mode request just before the user message. The LLM sees the reminder fresh on every turn, preventing structural drift in long conversations.

**Files:**
- Modify: `backend/core/prompt_router.py` (add `FORMATTING_REMINDER` constant)
- Modify: `backend/api/chat.py` (import + inject between history and user message)
- Modify: `backend/tests/core/test_prompt_router.py`

- [ ] **Step 6.1: Write the failing test**

In `backend/tests/core/test_prompt_router.py`, add this test:

```python
from core.prompt_router import FORMATTING_REMINDER


def test_formatting_reminder_is_exported():
    """FORMATTING_REMINDER must exist and mention blank lines."""
    assert isinstance(FORMATTING_REMINDER, str)
    assert len(FORMATTING_REMINDER) > 20
    assert "blank" in FORMATTING_REMINDER.lower() or "line" in FORMATTING_REMINDER.lower()
```

- [ ] **Step 6.2: Run test to verify it fails**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/core/test_prompt_router.py::test_formatting_reminder_is_exported -v
```

Expected: FAIL — `ImportError: cannot import name 'FORMATTING_REMINDER'`.

- [ ] **Step 6.3: Add constant to `backend/core/prompt_router.py`**

Find the existing constants section (around line 33). Add after the last existing constant:

```python
FORMATTING_REMINDER = (
    "Formatting reminder: always add blank lines before and after --- dividers and ## headers. "
    "Do not nest more than 2 levels deep. Short answers (1-2 sentences) need no structure."
)
```

- [ ] **Step 6.4: Inject into `backend/api/chat.py`**

*Import:* Find the existing import from `prompt_router` (line 23):
```python
from core.prompt_router import get_system_prompt, route_prompt, DOMAIN_PROMPTS
```

Replace with:
```python
from core.prompt_router import get_system_prompt, route_prompt, DOMAIN_PROMPTS, FORMATTING_REMINDER
```

*Inject:* Find the block where `trimmed_history` is extended into `messages` and the user message is appended. The sequence looks like (around lines 400–406):

```python
    messages.extend(trimmed_history)
    messages.append({"role": "user", "content": req.message})
```

Replace with:
```python
    messages.extend(trimmed_history)
    if req.mode == "fast":
        messages.append({"role": "system", "content": FORMATTING_REMINDER})
    messages.append({"role": "user", "content": req.message})
```

- [ ] **Step 6.5: Run tests to verify they pass**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/core/test_prompt_router.py -v
```

Expected: PASS.

- [ ] **Step 6.6: Commit**

```
git add backend/core/prompt_router.py backend/api/chat.py backend/tests/core/test_prompt_router.py
git commit -m "feat(fast-mode): inject formatting reminder before user message

Prevents structural drift in long conversations where LLM stops adding
blank lines around --- and ## headers, breaking ReactMarkdown rendering.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Fast Mode — Multi-Query RAG

**What this does:** For fast mode only, generates 2 query variations (synonyms/rephrasing) alongside the original, runs all 3 searches in parallel, deduplicates by `(doc_id, page)`, and keeps the top-15 results by score. This gives the LLM broader document context without slowing down analyst mode.

**Files:**
- Modify: `backend/api/chat.py` (add `_get_query_variations` helper + replace single search with parallel gather)
- Create: `backend/tests/test_multi_query_rag.py`

- [ ] **Step 7.1: Write the failing test**

Create `backend/tests/test_multi_query_rag.py`:

```python
"""Tests for multi-query RAG in fast mode."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, call
from api.chat import _get_query_variations


@pytest.mark.asyncio
async def test_get_query_variations_returns_list_with_original():
    """_get_query_variations must always include the original query."""
    from core.llm_manager import LLMResponse
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value=LLMResponse(
            content='["What is UAE VAT?", "UAE value added tax rate"]',
            tokens_used=20, provider="mock", model="mock-v1"
        )
    )
    with patch("api.chat.get_llm_provider", return_value=mock_llm):
        result = await _get_query_variations("UAE VAT rate")
    assert result[0] == "UAE VAT rate", "Original query must be first"
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_get_query_variations_falls_back_on_error():
    """_get_query_variations must return [original] when LLM fails."""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(side_effect=Exception("LLM timeout"))
    with patch("api.chat.get_llm_provider", return_value=mock_llm):
        result = await _get_query_variations("UAE VAT rate")
    assert result == ["UAE VAT rate"]


@pytest.mark.asyncio
async def test_fast_mode_calls_rag_multiple_times(client):
    """Fast mode send must call rag_engine.search for each query variation."""
    from core.llm_manager import LLMResponse
    from unittest.mock import MagicMock
    from core.chat.domain_classifier import DomainLabel, ClassifierResult

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=LLMResponse(content="Answer.", tokens_used=10, provider="mock", model="mock-v1"))

    async def _fake_stream(*a, **kw):
        yield "Answer."

    mock_llm.chat_stream = _fake_stream

    search_mock = AsyncMock(return_value=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(
            return_value=ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.9, alternatives=[])
        )),
        patch("api.chat.get_llm_provider", return_value=mock_llm),
        patch("api.chat.rag_engine.search", search_mock),
        patch("api.chat._get_query_variations", new=AsyncMock(return_value=["q1", "q2", "q3"])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "UAE VAT rate?", "use_rag": True, "mode": "fast", "stream": False},
        )
    assert resp.status_code == 200
    assert search_mock.call_count >= 2, (
        f"Expected multiple RAG calls in fast mode, got {search_mock.call_count}"
    )
```

- [ ] **Step 7.2: Run test to verify it fails**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_multi_query_rag.py -v
```

Expected: `_get_query_variations` import fails (not yet defined); fast mode still calls search once.

- [ ] **Step 7.3: Add `_get_query_variations` helper to `backend/api/chat.py`**

After the `extract_and_save_memory` function (~line 140), add:

```python
QUERY_VARIATION_PROMPT = (
    "Generate 2 alternative phrasings for this search query. "
    "Return ONLY a JSON array of strings, no explanation.\n"
    "Query: {query}"
)


async def _get_query_variations(query: str, provider: str | None = None) -> list[str]:
    """Return [original, variation1, variation2]. Falls back to [original] on any error."""
    try:
        llm = get_llm_provider(provider)
        resp = await llm.chat(
            messages=[{"role": "user", "content": QUERY_VARIATION_PROMPT.format(query=query)}],
            max_tokens=150,
            temperature=0.3,
        )
        import re
        match = re.search(r'\[.*?\]', resp.content, re.DOTALL)
        if not match:
            return [query]
        variations: list[str] = json.loads(match.group())
        return [query] + [v for v in variations if isinstance(v, str)][:2]
    except Exception:
        return [query]
```

- [ ] **Step 7.4: Replace single RAG call with parallel gather in fast mode**

In `backend/api/chat.py`, find the `if req.use_rag:` block (around lines 347–359):

```python
        try:
            search_results = await rag_engine.search(
                query=req.message,
                doc_ids=req.doc_ids,
                top_k=settings.top_k_results,
            )
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            search_results = []
```

Replace with:

```python
        try:
            if req.mode == "fast":
                query_variations = await _get_query_variations(req.message, req.provider)
                all_results = await asyncio.gather(
                    *[
                        rag_engine.search(query=q, doc_ids=req.doc_ids, top_k=settings.top_k_results)
                        for q in query_variations
                    ],
                    return_exceptions=True,
                )
                seen: set[tuple] = set()
                merged: list = []
                for batch in all_results:
                    if isinstance(batch, Exception):
                        continue
                    for r in batch:
                        key = (r["metadata"].get("doc_id", ""), r["metadata"].get("page", 0))
                        if key not in seen:
                            seen.add(key)
                            merged.append(r)
                search_results = sorted(merged, key=lambda x: x.get("score", 0), reverse=True)[:settings.top_k_results]
            else:
                search_results = await rag_engine.search(
                    query=req.message,
                    doc_ids=req.doc_ids,
                    top_k=settings.top_k_results,
                )
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            search_results = []
```

- [ ] **Step 7.5: Run tests to verify they pass**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_multi_query_rag.py -v
```

Expected: all PASS.

- [ ] **Step 7.6: Commit**

```
git add backend/api/chat.py backend/tests/test_multi_query_rag.py
git commit -m "feat(fast-mode): multi-query RAG with deduplication

Fast mode now generates 2 query variations and runs 3 parallel searches,
deduplicating by (doc_id, page). Analyst mode unchanged. Falls back to
single search on any variation error.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Fast Mode — Session Summary Memory

**What this does:** When a fast-mode conversation exceeds 20 messages, a background task summarises the oldest messages and stores the summary on the `Conversation` row. The summary is then prepended to the system prompt on subsequent turns, preventing context drift in very long sessions.

**Files:**
- Modify: `backend/db/models.py` (add `summary`, `summary_msg_count` columns)
- Modify: `backend/db/database.py` (add ALTER TABLE migrations)
- Modify: `backend/api/chat.py` (add `_get_or_refresh_summary` helper, inject summary, fire background task)
- Create: `backend/tests/test_session_summary.py`

- [ ] **Step 8.1: Write the failing test**

Create `backend/tests/test_session_summary.py`:

```python
"""Tests for session summary memory in fast mode."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from db.models import Conversation
from db.database import AsyncSessionLocal
from sqlalchemy import select
from core.llm_manager import LLMResponse
from core.chat.domain_classifier import DomainLabel, ClassifierResult


def _mock_llm(answer: str = "Summary text."):
    mock = MagicMock()
    mock.chat = AsyncMock(
        return_value=LLMResponse(content=answer, tokens_used=10, provider="mock", model="mock-v1")
    )

    async def _stream(*a, **kw):
        yield answer

    mock.chat_stream = _stream
    return mock


@pytest.mark.asyncio
async def test_summary_columns_exist():
    """Conversation model must have summary and summary_msg_count columns."""
    assert hasattr(Conversation, "summary"), "Conversation.summary column missing"
    assert hasattr(Conversation, "summary_msg_count"), "Conversation.summary_msg_count column missing"


@pytest.mark.asyncio
async def test_summary_written_after_many_messages(client):
    """After 21+ messages in fast mode, summary must be written to the conversation."""
    stub_classifier = ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.9, alternatives=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=stub_classifier)),
        patch("api.chat.get_llm_provider", return_value=_mock_llm("Older turns covered VAT basics.")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        # Create conversation via first message
        r = await client.post("/api/chat/send", json={"message": "msg0", "mode": "fast", "stream": False})
        assert r.status_code == 200
        cid = r.json()["conversation_id"]

        # Send 20 more messages to cross the threshold
        for i in range(1, 22):
            await client.post("/api/chat/send", json={
                "message": f"msg{i}", "conversation_id": cid, "mode": "fast", "stream": False
            })

    # Poll for summary (background task may need a moment)
    import asyncio
    await asyncio.sleep(0.5)

    async with AsyncSessionLocal() as db:
        conv = (await db.execute(select(Conversation).where(Conversation.id == cid))).scalar_one()
        assert conv.summary is not None, "Summary was never written"
        assert conv.summary_msg_count > 0
```

- [ ] **Step 8.2: Run test to verify it fails**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_session_summary.py::test_summary_columns_exist -v
```

Expected: FAIL — `Conversation.summary` attribute missing.

- [ ] **Step 8.3: Add columns to `backend/db/models.py`**

In `backend/db/models.py`, find the `Conversation` class and locate the `mode` column (around line 40):

```python
    mode = Column(String, default="fast")
```

Add the two new columns immediately after:

```python
    mode = Column(String, default="fast")
    summary = Column(Text, nullable=True)
    summary_msg_count = Column(Integer, default=0)
```

Make sure `Text` and `Integer` are imported from `sqlalchemy`. Find the import line:

```python
from sqlalchemy import Column, String, DateTime, Boolean
```

Add `Text` and `Integer`:

```python
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
```

- [ ] **Step 8.4: Add migrations to `backend/db/database.py`**

In `backend/db/database.py`, find the `init_db()` migration `try/except` block. It should look like (lines 51–66):

```python
    try:
        async with engine.begin() as conn:
            for stmt in [
                "ALTER TABLE conversations ADD COLUMN llm_provider TEXT",
                # ... other migrations ...
            ]:
                try:
                    await conn.execute(text(stmt))
                except Exception:
                    pass
    except Exception:
        pass
```

Add these two lines to the list inside the existing loop:

```python
                "ALTER TABLE conversations ADD COLUMN summary TEXT",
                "ALTER TABLE conversations ADD COLUMN summary_msg_count INTEGER DEFAULT 0",
```

- [ ] **Step 8.5: Add `_get_or_refresh_summary` helper to `backend/api/chat.py`**

After `_get_query_variations` function, add:

```python
async def _get_or_refresh_summary(conversation_id: str, history_count: int, provider: str | None = None) -> None:
    """Summarise oldest messages when conversation grows beyond 20 turns. Non-fatal."""
    if history_count <= 20:
        return
    try:
        async with AsyncSessionLocal() as db:
            conv = (await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )).scalar_one_or_none()
            if conv is None:
                return
            if history_count <= getattr(conv, "summary_msg_count", 0) + 10:
                return  # Not enough new messages to re-summarise
            old_count = history_count - 20
            old_messages = (await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
                .limit(old_count)
            )).scalars().all()
            if not old_messages:
                return
            context = "\n".join(
                f"{m.role.upper()}: {m.content[:400]}" for m in old_messages
            )
            llm = get_llm_provider(provider)
            resp = await llm.chat(
                messages=[{
                    "role": "user",
                    "content": (
                        "Summarise the following conversation excerpt in 3-5 sentences, "
                        "capturing the main topics and conclusions:\n\n" + context
                    ),
                }],
                max_tokens=600,
                temperature=0.1,
            )
            conv.summary = resp.content
            conv.summary_msg_count = history_count
            await db.commit()
    except Exception as exc:
        logger.warning(f"Session summary failed for {conversation_id}: {exc}")
```

Make sure `Message` is imported (it should already be). Verify:
```python
from db.models import Conversation, Message
```

- [ ] **Step 8.6: Inject summary into system message and fire background task**

*Injection* — Find the block where `messages[0]` (the system message) is assembled (around line 397). It looks like:

```python
    messages = [{"role": "system", "content": system_prompt}]
```

After this line, add:

```python
    if req.mode == "fast" and getattr(conversation, "summary", None):
        messages[0]["content"] += f"\n\nCONTEXT SUMMARY OF EARLIER CONVERSATION:\n{conversation.summary}"
```

*Background fire* — There are two commit points in the streaming endpoint. Find the `await db.commit()` inside `generate()` (streaming path, around line 498) and the one in the non-streaming path (around line 548). After each, add:

```python
            asyncio.create_task(
                _get_or_refresh_summary(conversation.id, len(history), req.provider)
            )
```

Note: Make sure `asyncio` is imported at the top of `chat.py`. Find the existing import:
```python
import asyncio
```
It should already be there.

- [ ] **Step 8.7: Run all session summary tests**

```
cd Project_AccountingLegalChatbot/backend
python -m pytest tests/test_session_summary.py -v
```

Expected: all PASS.

- [ ] **Step 8.8: Commit**

```
git add backend/db/models.py backend/db/database.py backend/api/chat.py backend/tests/test_session_summary.py
git commit -m "feat(fast-mode): session summary memory for long conversations

When fast-mode conversation exceeds 20 messages, a background task
summarises the oldest messages and appends the summary to the system
prompt on subsequent turns. Prevents context drift. Non-fatal on failure.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final Integration Check

After all tasks are committed, run the full test suite to confirm nothing regressed:

```
cd Project_AccountingLegalChatbot/backend
python -m pytest --tb=short -q

cd Project_AccountingLegalChatbot/frontend
npx vitest run
```

All tests must PASS before declaring done.

---

*Plan written with the writing-plans skill. Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to execute task-by-task.*

