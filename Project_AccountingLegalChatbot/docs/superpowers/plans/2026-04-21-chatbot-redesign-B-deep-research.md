# Chatbot Redesign — Sub-project B (Deep Research) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Sub-project A placeholder Research Panel with a live Deep Research pipeline backed by Brave Search — LLM decomposes the user's query into 2–3 focused web queries, runs them in parallel, merges with RAG results, streams progress over SSE, shows a live research log on the right, and saves fetched web content back into RAG for future reuse.

**Architecture:** New `core/research/brave_search.py` wraps the Brave API. New `core/research/query_decomposer.py` turns one question into 2–3 web queries via the existing `llm_manager`. New `api/research.py` exposes `POST /api/chat/deep-research` as an SSE endpoint that orchestrates: decompose → parallel search → RAG lookup → ingest web content into RAG → LLM synthesis. Frontend adds a `useDeepResearch(conversationId)` hook that opens the SSE stream, accumulates `ResearchStep`s, and drives the existing `ResearchPanel`.

**Tech Stack:** Backend — FastAPI `StreamingResponse`, httpx async client, asyncio.gather for parallel searches, pytest + pytest-asyncio + respx for HTTP mocking. Frontend — browser native `EventSource`, Vitest + React Testing Library.

**Spec reference:** `docs/superpowers/specs/2026-04-21-chatbot-redesign-design.md` — Sub-project B (B1–B4).

**Prerequisite:** Sub-project A complete and merged. `mode === 'deep_research'` already renders `ChatWithResearchLayout` with a placeholder `ResearchPanel`.

---

## File Structure

### New files

```
backend/
  core/research/brave_search.py
  core/research/query_decomposer.py
  core/research/deep_research_service.py      # orchestrator: decompose → search → rag → ingest → synth
  api/research.py                              # POST /api/chat/deep-research SSE
  tests/core/research/test_brave_search.py
  tests/core/research/test_query_decomposer.py
  tests/core/research/test_deep_research_service.py
  tests/api/test_research_sse.py

frontend/src/
  hooks/useDeepResearch.ts
  hooks/__tests__/useDeepResearch.test.ts
```

### Modified files

```
backend/
  config.py                    # BRAVE_SEARCH_API_KEY
  main.py                      # register research router
  core/document_processor.py   # accept source="research" ingestion path (if not already supported)

frontend/src/
  lib/api.ts                                                            # deepResearchUrl helper
  components/studios/LegalStudio/ResearchPanel.tsx                     # render web/doc source lists
  components/studios/LegalStudio/LegalStudio.tsx                        # wire useDeepResearch
  components/studios/LegalStudio/ChatInput.tsx                          # route send in deep_research mode
```

---

## Task 1: Backend — Brave Search client

**Files:**
- Modify: `backend/config.py` — add `BRAVE_SEARCH_API_KEY`
- Create: `backend/core/research/brave_search.py`
- Create: `backend/tests/core/research/test_brave_search.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/core/research/test_brave_search.py`:

```python
import pytest
import respx
import httpx
from core.research.brave_search import brave_search, BRAVE_URL


@pytest.mark.asyncio
@respx.mock
async def test_brave_search_returns_mapped_results(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "TEST_KEY")
    respx.get(BRAVE_URL).mock(
        return_value=httpx.Response(
            200,
            json={"web": {"results": [
                {"title": "UAE VAT Guide", "url": "https://example.com/vat",
                 "description": "VAT is 5%"},
                {"title": "FTA Site",      "url": "https://fta.gov.ae",
                 "description": "Official site"},
            ]}},
        )
    )

    out = await brave_search("UAE VAT rate", max_results=5)

    assert out == [
        {"title": "UAE VAT Guide", "url": "https://example.com/vat", "content": "VAT is 5%"},
        {"title": "FTA Site",      "url": "https://fta.gov.ae",      "content": "Official site"},
    ]
    sent = respx.calls.last.request
    assert sent.headers["X-Subscription-Token"] == "TEST_KEY"
    assert "q=UAE+VAT+rate" in str(sent.url) or "q=UAE%20VAT%20rate" in str(sent.url)


@pytest.mark.asyncio
@respx.mock
async def test_brave_search_returns_empty_list_on_missing_web(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "x")
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json={}))
    assert await brave_search("q") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/research/test_brave_search.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Add config entry**

In `backend/config.py`, add to the `Settings` class (or equivalent):

```python
BRAVE_SEARCH_API_KEY: str = ""
```

- [ ] **Step 4: Implement the client**

Create `backend/core/research/brave_search.py`:

```python
import os
import httpx

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


async def brave_search(query: str, max_results: int = 5) -> list[dict]:
    """Return a list of {title, url, content} dicts from Brave Search."""
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            BRAVE_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": max_results, "text_decorations": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("description", "")}
            for r in data.get("web", {}).get("results", [])
        ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/research/test_brave_search.py -v`
Expected: PASS (2 tests).

If `respx` is not yet a dev dep, add it: `uv add --dev respx pytest-asyncio`.

- [ ] **Step 6: Commit**

```bash
git add backend/core/research/brave_search.py backend/config.py backend/tests/core/research/test_brave_search.py
git commit -m "feat(research): Brave Search client"
```

---

## Task 2: Backend — LLM query decomposer

**Files:**
- Create: `backend/core/research/query_decomposer.py`
- Create: `backend/tests/core/research/test_query_decomposer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/core/research/test_query_decomposer.py`:

```python
import pytest
from unittest.mock import AsyncMock
from core.research.query_decomposer import decompose_query


@pytest.mark.asyncio
async def test_decompose_query_returns_parsed_list():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value='["UAE VAT 2025", "FTA compliance", "VAT-201 filing"]')
    result = await decompose_query("What are the current UAE VAT rules?", fake)
    assert result == ["UAE VAT 2025", "FTA compliance", "VAT-201 filing"]


@pytest.mark.asyncio
async def test_decompose_query_truncates_to_three():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value='["a","b","c","d","e"]')
    assert await decompose_query("q", fake) == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_decompose_query_falls_back_to_original_on_bad_json():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value="not json at all")
    assert await decompose_query("original question", fake) == ["original question"]


@pytest.mark.asyncio
async def test_decompose_query_falls_back_on_non_list_json():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value='{"queries": ["a"]}')
    assert await decompose_query("q", fake) == ["q"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/research/test_query_decomposer.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the decomposer**

Create `backend/core/research/query_decomposer.py`:

```python
import json

DECOMPOSE_PROMPT = """You are a search query expert. Given the user's question, generate 2-3 focused web search queries that together cover the most important aspects needed to fully answer the question.

Rules:
- Each query should target a distinct, specific aspect
- Keep queries concise (3-7 words)
- Use domain-specific terminology when relevant (e.g., "UAE FTA", "IFRS 15", "ISA 700")
- Output ONLY a JSON array of strings: ["query 1", "query 2", "query 3"]

User question: {question}
"""


async def decompose_query(question: str, llm_client) -> list[str]:
    """Use the LLM to break a question into 2-3 targeted search queries."""
    try:
        response = await llm_client.complete(
            DECOMPOSE_PROMPT.format(question=question),
            max_tokens=150,
            temperature=0.1,
        )
        queries = json.loads(response.strip())
        if isinstance(queries, list) and queries:
            return [str(q) for q in queries[:3]]
    except Exception:
        pass
    return [question]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/research/test_query_decomposer.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/core/research/query_decomposer.py backend/tests/core/research/test_query_decomposer.py
git commit -m "feat(research): LLM query decomposer"
```

---

## Task 3: Backend — Deep research orchestrator service

**Files:**
- Create: `backend/core/research/deep_research_service.py`
- Create: `backend/tests/core/research/test_deep_research_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/core/research/test_deep_research_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from core.research.deep_research_service import run_deep_research


@pytest.mark.asyncio
async def test_run_deep_research_emits_expected_events(monkeypatch):
    events = []

    async def fake_decompose(q, llm):
        return ["q1", "q2"]

    async def fake_search(query, max_results=5):
        return [{"title": f"T-{query}", "url": f"https://x/{query}", "content": "C"}]

    fake_rag = AsyncMock()
    fake_rag.search = AsyncMock(return_value=[
        {"text": "doc chunk", "source": "Policy.pdf", "page": 4}
    ])

    fake_llm = AsyncMock()
    async def stream_answer(prompt, **_):
        for piece in ["Hello ", "world."]:
            yield piece
    fake_llm.stream = stream_answer

    fake_ingest = AsyncMock()

    with patch("core.research.deep_research_service.decompose_query", fake_decompose), \
         patch("core.research.deep_research_service.brave_search", fake_search):
        async for ev in run_deep_research(
            query="orig", selected_doc_ids=["d1"],
            llm=fake_llm, rag=fake_rag, ingest=fake_ingest,
        ):
            events.append(ev)

    types = [e["type"] for e in events]
    assert types[0] == "step"
    assert types[-1] == "done"
    assert any(e["type"] == "answer" for e in events)

    # ingest must be called per web result (2 queries × 1 result = 2)
    assert fake_ingest.await_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/research/test_deep_research_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the service**

Create `backend/core/research/deep_research_service.py`:

```python
import asyncio
from typing import AsyncIterator
from core.research.brave_search import brave_search
from core.research.query_decomposer import decompose_query


def _build_synthesis_prompt(question: str, web: list[dict], doc_chunks: list[dict]) -> str:
    web_block = "\n".join(
        f"- [{r.get('title')}]({r.get('url')}): {r.get('content','')[:400]}"
        for r in web
    ) or "(no web results)"
    doc_block = "\n".join(
        f"- {c.get('source')} p.{c.get('page','?')}: {c.get('text','')[:400]}"
        for c in doc_chunks
    ) or "(no document chunks)"
    return (
        "You are a research assistant. Answer the user's question using ONLY the "
        "provided web results and document chunks. Cite sources inline. If the "
        "information is insufficient, say so explicitly.\n\n"
        f"Question: {question}\n\nWeb results:\n{web_block}\n\nDocument chunks:\n{doc_block}\n\nAnswer:"
    )


async def run_deep_research(
    *,
    query: str,
    selected_doc_ids: list[str] | None,
    llm,
    rag,
    ingest,
) -> AsyncIterator[dict]:
    """Yield SSE-ready event dicts for a deep research run."""
    yield {"type": "step", "text": "Analyzing query..."}

    sub_queries = await decompose_query(query, llm)
    yield {"type": "step", "text": f"Generated {len(sub_queries)} search queries"}

    for q in sub_queries:
        yield {"type": "step", "text": f"Searching: {q}"}

    search_results = await asyncio.gather(
        *[brave_search(q, max_results=5) for q in sub_queries],
        return_exceptions=True,
    )
    web: list[dict] = []
    for r in search_results:
        if isinstance(r, Exception):
            continue
        web.extend(r)

    yield {"type": "step", "text": f"Found {len(web)} web results across {len(sub_queries)} searches"}

    yield {"type": "step", "text": "Searching your documents..."}
    doc_chunks = await rag.search(query, doc_ids=selected_doc_ids) if rag else []
    yield {"type": "step", "text": f"Found {len(doc_chunks)} relevant document chunks"}

    # Persist web content to RAG for future reuse
    for r in web:
        try:
            await ingest(
                text=f"{r.get('title','')}\n\n{r.get('content','')}",
                source=r.get("url"),
                source_type="research",
            )
        except Exception:
            pass

    yield {"type": "step", "text": "Synthesizing answer..."}
    prompt = _build_synthesis_prompt(query, web, doc_chunks)

    answer_parts: list[str] = []
    async for piece in llm.stream(prompt, max_tokens=1200, temperature=0.2):
        answer_parts.append(piece)
    answer = "".join(answer_parts)

    yield {
        "type": "answer",
        "content": answer,
        "sources": [
            {"filename": c.get("source"), "page": c.get("page")} for c in doc_chunks
        ],
        "web_sources": [
            {"title": r.get("title"), "url": r.get("url")} for r in web
        ],
    }
    yield {"type": "done"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/research/test_deep_research_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/research/deep_research_service.py backend/tests/core/research/test_deep_research_service.py
git commit -m "feat(research): deep research orchestrator"
```

---

## Task 4: Backend — SSE endpoint

**Files:**
- Create: `backend/api/research.py`
- Modify: `backend/main.py` — register the router
- Create: `backend/tests/api/test_research_sse.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_research_sse.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app


async def _fake_events(**_):
    yield {"type": "step", "text": "Analyzing query..."}
    yield {"type": "answer", "content": "done", "sources": [], "web_sources": []}
    yield {"type": "done"}


def test_deep_research_streams_sse():
    client = TestClient(app)
    with patch("api.research.run_deep_research", _fake_events):
        with client.stream(
            "POST",
            "/api/chat/deep-research",
            json={"conversation_id": "c1", "query": "q", "selected_doc_ids": []},
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            body = b"".join(r.iter_bytes()).decode()

    # every frame starts with "data: " and is parseable JSON
    frames = [line[len("data: "):] for line in body.splitlines() if line.startswith("data: ")]
    parsed = [json.loads(f) for f in frames]
    types = [p["type"] for p in parsed]
    assert types == ["step", "answer", "done"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_research_sse.py -v`
Expected: FAIL — 404 or import error.

- [ ] **Step 3: Implement the endpoint**

Create `backend/api/research.py`:

```python
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.research.deep_research_service import run_deep_research
from core.llm_manager import get_llm
from core.rag_engine import get_rag
from core.document_processor import ingest_text

router = APIRouter(prefix="/api/chat", tags=["research"])


class DeepResearchRequest(BaseModel):
    conversation_id: str
    query: str
    selected_doc_ids: list[str] = []


async def _sse_stream(req: DeepResearchRequest):
    llm = get_llm()
    rag = get_rag()
    async for event in run_deep_research(
        query=req.query,
        selected_doc_ids=req.selected_doc_ids,
        llm=llm,
        rag=rag,
        ingest=ingest_text,
    ):
        yield f"data: {json.dumps(event)}\n\n"


@router.post("/deep-research")
async def deep_research(req: DeepResearchRequest):
    return StreamingResponse(_sse_stream(req), media_type="text/event-stream")
```

Adapt the imports (`get_llm`, `get_rag`, `ingest_text`) to the actual accessor names in the existing backend. If `ingest_text` doesn't exist, wrap whatever the current ingestion helper is in a thin shim that accepts `(text, source, source_type)`.

- [ ] **Step 4: Register the router**

In `backend/main.py`, alongside other `app.include_router(...)` calls:

```python
from api.research import router as research_router
app.include_router(research_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_research_sse.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/research.py backend/main.py backend/tests/api/test_research_sse.py
git commit -m "feat(api): POST /api/chat/deep-research SSE endpoint"
```

---

## Task 5: Frontend — `useDeepResearch` hook

**Files:**
- Modify: `frontend/src/lib/api.ts` — expose `deepResearchUrl`
- Create: `frontend/src/hooks/useDeepResearch.ts`
- Create: `frontend/src/hooks/__tests__/useDeepResearch.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/__tests__/useDeepResearch.test.ts`:

```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useDeepResearch } from '../useDeepResearch';

class MockEventSource {
  static instances: MockEventSource[] = [];
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 1;
  url: string;
  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  close() { this.readyState = 2; }
  emit(data: any) { this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent); }
}

beforeEach(() => {
  MockEventSource.instances = [];
  (globalThis as any).EventSource = MockEventSource;
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    body: null,
  } as any);
});

describe('useDeepResearch', () => {
  it('starts empty', () => {
    const { result } = renderHook(() => useDeepResearch('c1'));
    expect(result.current.steps).toEqual([]);
    expect(result.current.answer).toBeNull();
    expect(result.current.running).toBe(false);
  });

  it('accumulates steps and stores answer on run()', async () => {
    const { result } = renderHook(() => useDeepResearch('c1'));

    act(() => {
      result.current.run('what is UAE VAT?', []);
    });

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const es = MockEventSource.instances[0];

    act(() => { es.emit({ type: 'step', text: 'Analyzing query...' }); });
    act(() => { es.emit({ type: 'step', text: 'Searching: uae vat' }); });
    act(() => { es.emit({ type: 'answer', content: 'VAT is 5%', sources: [], web_sources: [{url:'u'}] }); });
    act(() => { es.emit({ type: 'done' }); });

    await waitFor(() => expect(result.current.running).toBe(false));
    expect(result.current.steps.map(s => s.text)).toEqual([
      'Analyzing query...', 'Searching: uae vat',
    ]);
    expect(result.current.answer?.content).toBe('VAT is 5%');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useDeepResearch.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Add API helper**

In `frontend/src/lib/api.ts`:

```typescript
export const API_BASE = 'http://localhost:8000';

export function deepResearchUrl(): string {
  return `${API_BASE}/api/chat/deep-research`;
}
```

If `API_BASE` is already defined elsewhere, reuse the existing constant.

- [ ] **Step 4: Implement the hook**

Because browsers don't support request bodies on `EventSource`, the hook POSTs the request and reads the SSE via `fetch` + a reader. Tests replace this with a mock. Implementation:

Create `frontend/src/hooks/useDeepResearch.ts`:

```typescript
import { useCallback, useRef, useState } from 'react';
import { deepResearchUrl } from '../lib/api';

export interface ResearchStep {
  text: string;
  status: 'done' | 'active' | 'error' | 'pending';
}

export interface ResearchAnswer {
  content: string;
  sources: Array<{ filename: string; page?: number }>;
  web_sources: Array<{ title?: string; url: string }>;
}

export function useDeepResearch(conversationId: string) {
  const [steps, setSteps] = useState<ResearchStep[]>([]);
  const [answer, setAnswer] = useState<ResearchAnswer | null>(null);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleFrame = (raw: string) => {
    if (!raw.startsWith('data: ')) return;
    try {
      const ev = JSON.parse(raw.slice(6));
      if (ev.type === 'step') {
        setSteps(prev => [...prev, { text: ev.text, status: 'done' }]);
      } else if (ev.type === 'answer') {
        setAnswer({
          content: ev.content,
          sources: ev.sources ?? [],
          web_sources: ev.web_sources ?? [],
        });
      } else if (ev.type === 'done') {
        setRunning(false);
      } else if (ev.type === 'error') {
        setSteps(prev => [...prev, { text: ev.text ?? 'Error', status: 'error' }]);
        setRunning(false);
      }
    } catch {
      /* malformed frame — ignore */
    }
  };

  const run = useCallback(async (query: string, selected_doc_ids: string[]) => {
    setSteps([]);
    setAnswer(null);
    setRunning(true);

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const resp = await fetch(deepResearchUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ conversation_id: conversationId, query, selected_doc_ids }),
        signal: ac.signal,
      });
      if (!resp.ok || !resp.body) {
        setRunning(false);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          handleFrame(frame.trim());
        }
      }
    } catch {
      setRunning(false);
    }
  }, [conversationId]);

  return { steps, answer, running, run };
}
```

**Note for the test**: the test uses `MockEventSource` because that's the conventional name, but the hook actually uses `fetch`. Replace the test's `beforeEach` with a fetch-body mock:

```typescript
import { vi } from 'vitest';

beforeEach(() => {
  const encoder = new TextEncoder();
  let push: (s: string) => void;
  let close: () => void;
  const stream = new ReadableStream({
    start(controller) {
      push = (s: string) => controller.enqueue(encoder.encode(s));
      close = () => controller.close();
    },
  });
  (globalThis as any).__sse = { push: (s: string) => push(s), close: () => close() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, body: stream } as any);
});
```

Then drive events in the test by calling `(globalThis as any).__sse.push('data: ' + JSON.stringify(ev) + '\n\n')` and `close()`. Update the test's assertions to `await waitFor` the state changes after pushing frames.

*(If writing the test with the real fetch-body stream is too fiddly in the harness, factor the SSE parsing into a small pure function `parseSseStream(frames: string[]): Event[]` and unit-test that instead — the hook wraps it.)*

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useDeepResearch.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useDeepResearch.ts frontend/src/hooks/__tests__/useDeepResearch.test.ts frontend/src/lib/api.ts
git commit -m "feat(hooks): useDeepResearch SSE hook"
```

---

## Task 6: Frontend — Research Panel full UI

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ResearchPanel.tsx`
- Update: existing placeholder test added in Plan A

- [ ] **Step 1: Update the test**

Replace the Plan A test file `frontend/src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx` with:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ResearchPanel } from '../ResearchPanel';

describe('ResearchPanel', () => {
  it('renders empty state when idle', () => {
    render(<ResearchPanel steps={[]} answer={null} />);
    expect(screen.getByText(/Ask a question to begin deep research/i)).toBeInTheDocument();
  });

  it('renders steps', () => {
    render(<ResearchPanel steps={[{ text: 'Analyzing', status: 'done' }]} answer={null} />);
    expect(screen.getByText('Analyzing')).toHaveClass('research-step--done');
  });

  it('renders web and doc source lists when answer present', () => {
    render(
      <ResearchPanel
        steps={[{ text: 'done', status: 'done' }]}
        answer={{
          content: 'ans',
          sources: [{ filename: 'Policy.pdf', page: 4 }],
          web_sources: [{ title: 'UAE VAT Guide', url: 'https://example.com/vat' }],
        }}
      />,
    );
    expect(screen.getByText('UAE VAT Guide')).toBeInTheDocument();
    expect(screen.getByText(/Policy\.pdf/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx`
Expected: FAIL — new `answer` prop not yet accepted.

- [ ] **Step 3: Expand ResearchPanel**

Replace the contents of `frontend/src/components/studios/LegalStudio/ResearchPanel.tsx`:

```tsx
export interface ResearchStep {
  text: string;
  status: 'pending' | 'active' | 'done' | 'error';
}

export interface ResearchAnswer {
  content: string;
  sources: Array<{ filename: string; page?: number }>;
  web_sources: Array<{ title?: string; url: string }>;
}

interface Props {
  steps: ResearchStep[];
  answer: ResearchAnswer | null;
}

export function ResearchPanel({ steps, answer }: Props) {
  return (
    <aside className="research-panel">
      <div className="research-panel__header">🔬 Research Log</div>

      {steps.length === 0 && !answer && (
        <div className="research-panel__empty">
          Ask a question to begin deep research. Results and sources will appear here.
        </div>
      )}

      {steps.length > 0 && (
        <ul className="research-steps">
          {steps.map((s, i) => (
            <li key={i} className={`research-step research-step--${s.status}`}>{s.text}</li>
          ))}
        </ul>
      )}

      {answer && (
        <>
          {answer.web_sources.length > 0 && (
            <section className="research-panel__section">
              <h4>Web Sources</h4>
              <ul>
                {answer.web_sources.map((w, i) => (
                  <li key={i}>
                    <a href={w.url} target="_blank" rel="noreferrer">
                      {w.title ?? w.url}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {answer.sources.length > 0 && (
            <section className="research-panel__section">
              <h4>Document Sources</h4>
              <ul>
                {answer.sources.map((d, i) => (
                  <li key={i}>
                    {d.filename}
                    {typeof d.page === 'number' ? ` — p.${d.page}` : ''}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </aside>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ResearchPanel.tsx frontend/src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx
git commit -m "feat(ui): ResearchPanel renders steps and source lists"
```

---

## Task 7: Frontend — Wire Deep Research into LegalStudio

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/ChatInput.tsx` (conditional routing)

- [ ] **Step 1: Thread the hook into LegalStudio**

In `LegalStudio.tsx`, inside the component:

```tsx
import { useDeepResearch } from '../../../hooks/useDeepResearch';
// ...
const { steps, answer, running, run: runDeepResearch } = useDeepResearch(conversationId ?? '');
```

Pass `steps` and `answer` to the existing `ResearchPanel` render:

```tsx
if (mode === 'deep_research') {
  return (
    <ChatWithResearchLayout
      modePills={modePills}
      chatArea={chatArea}
      researchPanel={<ResearchPanel steps={steps} answer={answer} />}
    />
  );
}
```

- [ ] **Step 2: Route message sends based on mode**

Locate the chat-send handler in `LegalStudio.tsx` (the function passed to `ChatInput` that fires on submit). Before it calls the existing send endpoint, branch:

```typescript
const handleSend = async (text: string) => {
  if (mode === 'deep_research') {
    await runDeepResearch(text, selectedDocIds ?? []);
    return;
  }
  // existing path: /api/chat/send_message, etc.
  await sendMessage(text);
};
```

When `answer` flips from `null` to a value (watch via `useEffect` on `answer`), append it to the visible chat message list as an assistant message so the user sees the synthesized reply in-line:

```typescript
useEffect(() => {
  if (!answer) return;
  appendAssistantMessage({
    content: answer.content,
    sources: answer.sources.map(s => ({ filename: s.filename, page: s.page })),
  });
}, [answer]);
```

Use whatever "append assistant message" function the component currently uses for the non-research path — do not add a new state container.

- [ ] **Step 3: Disable send button while running**

In `ChatInput.tsx`, accept an optional `disabled` prop and forward it to the submit button; in `LegalStudio.tsx`, pass `disabled={running}`.

- [ ] **Step 4: Typecheck + smoke test**

Run: `cd frontend && npx tsc --noEmit` — expect clean.

Manual test (backend must be running with a valid `BRAVE_SEARCH_API_KEY`):
- Switch to Deep Research mode.
- Type a question, press send.
- Steps appear live in the right panel ("Analyzing…", "Searching: X", …).
- Final answer appears both in chat and as a source list in the panel.
- Refresh — the conversation still shows the prior assistant message.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/components/studios/LegalStudio/ChatInput.tsx
git commit -m "feat(studio): deep research wired via useDeepResearch + SSE"
```

---

## Task 8: Backend — Verify RAG ingestion of web content

**Files:**
- Modify (if needed): `backend/core/document_processor.py`
- Manual/integration test

- [ ] **Step 1: Confirm the ingestion contract**

Run: `cd backend && git grep -n "source_type\\|source=\"research\"\\|ingest_text" core/`

If an `ingest_text(text, source, source_type)` (or equivalent) already exists, Task 4 already uses it — skip to Step 3.

If it does not, add a thin wrapper in `core/document_processor.py`:

```python
async def ingest_text(text: str, source: str | None, source_type: str = "research") -> None:
    """Index a raw text blob into the RAG engine with a source tag."""
    # Call the existing document ingestion path with a synthetic document id.
    # Reuse whatever chunking/embedding helper is already used for PDF chunks.
    ...
```

Fill in the body by following the existing PDF ingestion code path, but skip file reading — it's already text.

- [ ] **Step 2: Unit-test the wrapper (only if you added it)**

Add `backend/tests/core/test_ingest_text.py` with a small test that asserts `ingest_text` calls the same embed+store path used for document chunks. Use existing fixtures.

- [ ] **Step 3: Integration check**

Run a deep research query end-to-end, then immediately run a Fast-mode query that reuses the fetched content. The RAG engine should return the previously-ingested research chunks tagged `source="research"`.

- [ ] **Step 4: Commit (if changes were required)**

```bash
git add backend/core/document_processor.py backend/tests/core/test_ingest_text.py
git commit -m "feat(rag): ingest_text wrapper for research content persistence"
```

---

## Task 9: Regression pass

- [ ] **Step 1: Backend tests**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 2: Frontend tests + typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: all pass, no TS errors.

- [ ] **Step 3: Walk Sub-project B manual checklist**

- [ ] Deep research fires Brave Search and shows steps live in research panel
- [ ] Web sources appear in research panel after answer
- [ ] Fetched web content is saved to RAG DB with `source: "research"`
- [ ] RAG sources with page references appear alongside web sources

- [ ] **Step 4: Commit cleanups (if any)**

```bash
git add -A
git commit -m "chore: Sub-project B cleanup"
```

Sub-project B is complete. Sub-project C (Analyst) can proceed independently.
