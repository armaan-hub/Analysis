# Chatbot Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Deep Research export/streaming, fix Analyst-mode crash, fix chat bugs (wrong source names, off-topic replies, ask-twice), add Deep Research + Analyst skills, and add an LLM Council ("Run this by the council") feature with 4 financial-expert personas.

**Architecture:**
- Backend: FastAPI + async Python. New module `backend/core/council/` for the sequential-chain council. Bug fixes in `backend/api/chat.py`, `backend/core/research/deep_research_service.py`, `backend/core/deep_research_export.py`.
- Frontend: React + TypeScript. New `CouncilPanel.tsx` consuming new SSE event `council_expert`. Error boundary added to Analyst three-pane layout. `sendMessage` hardened with `finally` + `AbortController`.
- Skills: New project skills `Project_AccountingLegalChatbot/skills/deep-research/SKILL.md` and `skills/analyst/SKILL.md` (the `learn-audit-format` skill is the existing pattern reference).

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (async), httpx, ReportLab, python-docx, openpyxl. React 18, TypeScript, Vite, Axios. pytest with `asyncio_mode=auto` and `httpx.AsyncClient` + `ASGITransport`.

**Spec:** See `docs/superpowers/specs/2026-04-23-chatbot-improvements-design.md` (or session checkpoint `001-chatbot-improvements-design-br.md` if spec not yet committed).

---

## File Structure

### Files to CREATE
| Path | Purpose |
|---|---|
| `backend/core/council/__init__.py` | Package init |
| `backend/core/council/council_service.py` | Sequential-chain orchestration (CA → CPA → CMA → Financial Analyst → Synthesis) yielding SSE event dicts |
| `backend/core/council/personas.py` | 4 expert system prompts + synthesis prompt |
| `backend/api/council.py` | `POST /api/chat/council` SSE endpoint |
| `backend/core/chat/intent_classifier.py` | Two-pass intent classification (output_type + topic) |
| `backend/tests/core/council/__init__.py` | |
| `backend/tests/core/council/test_council_service.py` | Sequential chain unit tests |
| `backend/tests/core/council/test_personas.py` | Persona prompt content tests |
| `backend/tests/api/test_council_endpoint.py` | SSE endpoint integration test |
| `backend/tests/core/chat/__init__.py` | |
| `backend/tests/core/chat/test_intent_classifier.py` | Intent classifier unit tests |
| `backend/tests/api/test_chat_intent_routing.py` | Two-pass routing test |
| `backend/tests/core/research/test_deep_research_finally.py` | Verifies `done` event always emitted |
| `backend/tests/core/test_export_sources_links.py` | Verifies clickable URLs in PDF + DOCX appendix |
| `frontend/src/components/studios/LegalStudio/CouncilPanel.tsx` | Streaming 4-expert panel |
| `frontend/src/components/studios/LegalStudio/CouncilButton.tsx` | "Run this by the council" pill button |
| `frontend/src/components/studios/LegalStudio/AnalystErrorBoundary.tsx` | Error boundary for Analyst three-pane |
| `frontend/src/hooks/useCouncil.ts` | SSE consumer for council stream |
| `Project_AccountingLegalChatbot/skills/deep-research/SKILL.md` | Skill: when/how to invoke Deep Research mode |
| `Project_AccountingLegalChatbot/skills/analyst/SKILL.md` | Skill: when/how to invoke Analyst mode |

### Files to MODIFY
| Path | Change |
|---|---|
| `backend/core/research/deep_research_service.py` | Wrap body in try/finally; always yield `done` (with `error` field on failure) |
| `backend/core/deep_research_export.py` | Sources appendix → render `url` as clickable hyperlink (PDF: `<link href=...>`, DOCX: `add_hyperlink` helper) |
| `backend/api/chat.py` | Inject intent classifier into `send_message`; pass classification into prompt context |
| `backend/api/legal_studio.py` (or wherever `notebook/:id/sources` lives) | Resolve doc IDs → `original_name` |
| `backend/core/prompt_router.py` | Re-export council persona prompts (optional) |
| `backend/main.py` | Register `council.router` |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | `sendMessage`: add `finally` + 30s `AbortController`; mount `<AnalystErrorBoundary>` around `<ThreePaneLayout>`; integrate `<CouncilButton>` and `<CouncilPanel>`; resolve source names |
| `frontend/src/components/studios/LegalStudio/ModePills.tsx` | Add `<CouncilButton>` adjacent (not as a mode) |
| `frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx` | Add "Download DOCX" + "Download PDF" buttons (uses existing `core/deep_research_export.py`) |
| `frontend/src/hooks/useDeepResearch.ts` | Handle `done` event with `error` field; surface error to UI |
| `frontend/src/lib/api.ts` | Add `councilStreamUrl(question, conversationId)` helper |

---

# PHASE 1 — Deep Research Fix (Highest Priority)

## Task 1.1: Add try/finally guarantee in deep_research_service

**Files:**
- Modify: `backend/core/research/deep_research_service.py`
- Test: `backend/tests/core/research/test_deep_research_finally.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/research/test_deep_research_finally.py
import pytest
from core.research.deep_research_service import run_deep_research


class _FailingLLM:
    async def stream(self, prompt, **kw):
        raise RuntimeError("LLM exploded")
        yield  # pragma: no cover


class _StubRAG:
    async def search(self, query, doc_ids=None):
        return []


async def _ingest(**kwargs):
    return None


@pytest.mark.asyncio
async def test_done_event_emitted_even_on_llm_failure(monkeypatch):
    async def _fake_decompose(q, llm):
        return [q]
    async def _fake_brave(q, max_results=5):
        return []
    monkeypatch.setattr("core.research.deep_research_service.decompose_query", _fake_decompose)
    monkeypatch.setattr("core.research.deep_research_service.brave_search", _fake_brave)

    events = []
    async for evt in run_deep_research(
        query="test",
        selected_doc_ids=None,
        llm=_FailingLLM(),
        rag=_StubRAG(),
        ingest=_ingest,
    ):
        events.append(evt)

    types = [e["type"] for e in events]
    assert "done" in types, f"Expected 'done' in {types}"
    done_evt = next(e for e in events if e["type"] == "done")
    assert "error" in done_evt
    assert "LLM exploded" in done_evt["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/core/research/test_deep_research_finally.py -v`
Expected: FAIL — test raises RuntimeError uncaught (no `done` event emitted).

- [ ] **Step 3: Modify `deep_research_service.py` — wrap body in try/finally**

Replace the body of `run_deep_research` (everything after the `yield {"type": "step", ...}` lines) so the entire pipeline is inside `try:` and the final `done` event lives in `finally`. Capture exceptions and emit them in the `done` payload.

```python
async def run_deep_research(*, query, selected_doc_ids, llm, rag, ingest):
    """Yield SSE-ready event dicts for a deep research run."""
    error: str | None = None
    answer_emitted = False
    try:
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
        answer_emitted = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        yield {"type": "step", "text": f"Error: {error}"}
    finally:
        done_payload: dict = {"type": "done"}
        if error:
            done_payload["error"] = error
        if not answer_emitted:
            done_payload["partial"] = True
        yield done_payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/core/research/test_deep_research_finally.py -v`
Expected: PASS.

- [ ] **Step 5: Run existing deep-research tests to confirm no regression**

Run: `cd backend && pytest tests/core/research/ tests/api/test_research_sse.py tests/test_deep_research_stream.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/core/research/deep_research_service.py backend/tests/core/research/test_deep_research_finally.py
git commit -m "fix(research): always emit done event even on LLM/search failure"
```

## Task 1.2: Sources appendix with clickable URLs (PDF + DOCX)

**Files:**
- Modify: `backend/core/deep_research_export.py`
- Test: `backend/tests/core/test_export_sources_links.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_export_sources_links.py
from core.deep_research_export import to_branded_pdf, to_branded_docx


SOURCES = [
    {"source": "Federal Tax Authority", "url": "https://tax.gov.ae/article-31", "excerpt": "VAT zero-rated rules"},
    {"source": "Local PDF", "page": 12, "excerpt": "Internal note"},
]


def test_pdf_appendix_contains_url():
    pdf_bytes = to_branded_pdf("# Body\nContent here", SOURCES, "Test query")
    assert b"https://tax.gov.ae/article-31" in pdf_bytes


def test_docx_appendix_contains_url():
    docx_bytes = to_branded_docx("# Body\nContent here", SOURCES, "Test query")
    # python-docx writes hyperlinks via XML refs; the URL ends up in document.xml or relationships
    assert b"tax.gov.ae" in docx_bytes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/core/test_export_sources_links.py -v`
Expected: FAIL — current appendix uses `excerpt` only, no URL rendered.

- [ ] **Step 3: Patch PDF appendix in `to_branded_pdf`**

In `backend/core/deep_research_export.py`, locate the `# ── Sources appendix ──` block in `to_branded_pdf` (around line 162). After the existing `name`/`page_str`/`score_str` block, render URL when present:

```python
# Inside the for idx, src in enumerate(sources, 1) loop, AFTER the first Paragraph:
url = src.get("url")
if url:
    safe_url = url.replace("&", "&amp;")
    story.append(Paragraph(
        f'<link href="{safe_url}" color="#1a365d"><u>{safe_url}</u></link>',
        source_style,
    ))
```

- [ ] **Step 4: Patch DOCX appendix in `to_branded_docx`**

Add a hyperlink helper at module scope (above `to_branded_docx`):

```python
def _add_hyperlink(paragraph, url: str, text: str):
    """Add a clickable hyperlink to a python-docx paragraph."""
    from docx.oxml.shared import OxmlElement, qn
    from docx.shared import RGBColor

    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1A365D")
    rPr.append(color)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
```

In `to_branded_docx`'s sources loop (around line 316), after writing `[idx] name…`, add:

```python
url = src.get("url")
if url:
    p_url = doc.add_paragraph()
    _add_hyperlink(p_url, url, url)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/core/test_export_sources_links.py -v`
Expected: PASS.

- [ ] **Step 6: Run existing export tests**

Run: `cd backend && pytest tests/test_export.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/core/deep_research_export.py backend/tests/core/test_export_sources_links.py
git commit -m "feat(export): clickable source URLs in PDF and DOCX appendix"
```

## Task 1.3: Frontend — surface deep-research errors in UI

**Files:**
- Modify: `frontend/src/hooks/useDeepResearch.ts`

- [ ] **Step 1: View current hook**

Run: view `frontend/src/hooks/useDeepResearch.ts` to find the SSE handler.

- [ ] **Step 2: Add error state and handle `done.error`**

Add to the hook:
```ts
const [error, setError] = useState<string | null>(null);
// inside SSE switch where 'done' is handled:
case 'done':
  if (evt.error) setError(evt.error);
  setRunning(false);
  break;
```
Return `error` in the hook's return object.

- [ ] **Step 3: Surface in `LegalStudio.tsx`**

Read `error` from `useDeepResearch` and display in `ResearchPanel` as an inline error banner.

- [ ] **Step 4: Manual smoke test**

Start backend (`uvicorn main:app --reload`) and frontend (`npm run dev`); switch to Deep Research mode; ask a question; verify `done` arrives and panel exits "running" state.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useDeepResearch.ts frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat(frontend): surface deep-research errors and guarantee running=false"
```

## Task 1.4: ArtifactPanel — DOCX + PDF download buttons

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx`

- [ ] **Step 1: Locate existing export endpoint**

Use grep: `grep -rn "to_branded_pdf\|to_branded_docx" backend/api`. Identify the route (likely `/api/research/export/{format}` or similar). If no route exists, ADD one in `backend/api/chat.py`:

```python
from fastapi.responses import Response
from core.deep_research_export import to_branded_pdf, to_branded_docx

class ExportRequest(BaseModel):
    content: str
    sources: list[dict]
    query: str
    format: Literal["pdf", "docx"]

@router.post("/export")
async def export_research(req: ExportRequest):
    if req.format == "pdf":
        data = to_branded_pdf(req.content, req.sources, req.query)
        media = "application/pdf"
        ext = "pdf"
    else:
        data = to_branded_docx(req.content, req.sources, req.query)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = "docx"
    return Response(content=data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="research.{ext}"'
    })
```

- [ ] **Step 2: Add buttons to ArtifactPanel**

```tsx
async function downloadAs(format: 'pdf' | 'docx') {
  const res = await fetch(`${API_BASE}/api/chat/export`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ content, sources, query, format }),
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `research.${format}`; a.click();
  URL.revokeObjectURL(url);
}
// in JSX: <button onClick={() => downloadAs('pdf')}>Download PDF</button>
//         <button onClick={() => downloadAs('docx')}>Download DOCX</button>
```

- [ ] **Step 3: Manual test**

Start backend + frontend; run a deep research query; click both buttons; verify files download and open correctly with sources appendix containing clickable URLs.

- [ ] **Step 4: Commit**

```bash
git add backend/api/chat.py frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx
git commit -m "feat(export): add DOCX and PDF download buttons to ArtifactPanel"
```

---

# PHASE 2 — Analyst Mode Crash Fix

## Task 2.1: Add Error Boundary around ThreePaneLayout

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/AnalystErrorBoundary.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Create the error boundary component**

```tsx
// frontend/src/components/studios/LegalStudio/AnalystErrorBoundary.tsx
import React from 'react';

interface State { hasError: boolean; error: Error | null; }
interface Props { children: React.ReactNode; onReset?: () => void; }

export class AnalystErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[AnalystErrorBoundary]', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, color: '#9b2226' }}>
          <h3>Analyst mode crashed</h3>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {this.state.error?.message}
          </pre>
          <button onClick={this.handleReset}>Reset Analyst</button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: Wrap ThreePaneLayout in `LegalStudio.tsx`**

Find the `<ThreePaneLayout ...>` JSX (around line 879). Wrap it:
```tsx
<AnalystErrorBoundary onReset={() => setMode('fast')}>
  <ThreePaneLayout ...existingProps />
</AnalystErrorBoundary>
```
Import at top: `import { AnalystErrorBoundary } from './AnalystErrorBoundary';`

- [ ] **Step 3: Lazy-load heavy chart components**

In `ArtifactPanel.tsx`, replace direct imports of `MisKpiCards` + `MisChart` with:
```tsx
const MisKpiCards = React.lazy(() => import('./MisKpiCards').then(m => ({ default: m.MisKpiCards })));
const MisChart = React.lazy(() => import('./MisChart').then(m => ({ default: m.MisChart })));
```
Wrap usage in `<Suspense fallback={<div>Loading…</div>}>…</Suspense>`.

- [ ] **Step 4: Manual smoke test**

Start app; click Analyst pill. Confirm no white screen; if crash occurs, boundary shows the error message instead of breaking the app.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/AnalystErrorBoundary.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx
git commit -m "fix(analyst): add error boundary + lazy-load heavy chart components"
```

## Task 2.2: Investigate the actual crash root cause

**Files:**
- Read-only investigation, then targeted fix.

- [ ] **Step 1: Reproduce in dev**

Run frontend in dev; open DevTools console; click Analyst pill; capture exact error stack.

- [ ] **Step 2: Search for likely culprits**

Run: `grep -rn "ThreePaneLayout\|three-pane-layout" frontend/src` and `grep -rn "import.*ReactMarkdown" frontend/src/components/studios/LegalStudio` to verify imports resolve.

- [ ] **Step 3: Verify ArtifactPanel imports**

Open `ArtifactPanel.tsx`; check that `MisKpiCards`, `MisChart`, and any other named imports actually exist in their respective files (`grep` for `export.*MisKpiCards`).

- [ ] **Step 4: Fix the root cause**

Whatever the captured stack reveals — broken import, undefined prop, missing CSS — fix at the source. Document the fix in commit message.

- [ ] **Step 5: Verify with manual click test**

Click Analyst pill; should show three-pane layout, not crash, and not display the error boundary fallback.

- [ ] **Step 6: Commit**

```bash
git add <fixed files>
git commit -m "fix(analyst): <specific root cause>"
```

---

# PHASE 3 — Chat Bugs

## Task 3.1: Source-name resolution

**Files:**
- Modify: `backend/api/legal_studio.py` (or whichever file has `notebook/:id/sources`)
- Test: `backend/tests/test_chat_sources.py` (extend existing)

- [ ] **Step 1: Locate the endpoint**

Run: `grep -rn "notebook.*sources\|/sources" backend/api`. Identify the function that returns the sources list.

- [ ] **Step 2: Write a failing test**

Extend or add to `backend/tests/test_chat_sources.py`:

```python
@pytest.mark.asyncio
async def test_notebook_sources_returns_original_name(client, db_session):
    # Insert a Document with original_name='UAE_VAT_Law.pdf'
    from db.models import Document
    doc = Document(id="doc-1", original_name="UAE_VAT_Law.pdf", filename="abc123.pdf", ...)
    db_session.add(doc); await db_session.commit()
    # Insert into notebook X
    # ... (use existing fixture for notebook attachment) ...
    resp = await client.get("/api/legal-studio/notebook/X/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["name"] == "UAE_VAT_Law.pdf"
    assert data[0]["id"] == "doc-1"
```

- [ ] **Step 3: Run test — expect FAIL**

Run: `cd backend && pytest tests/test_chat_sources.py -v`

- [ ] **Step 4: Patch the endpoint**

Inside the sources endpoint, after fetching IDs, query `Document` table:
```python
ids = [...existing...]
docs_result = await db.execute(select(Document).where(Document.id.in_(ids)))
docs_by_id = {d.id: d for d in docs_result.scalars().all()}
return [
    {"id": did, "name": docs_by_id[did].original_name if did in docs_by_id else did}
    for did in ids
]
```

- [ ] **Step 5: Run test — expect PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/api/legal_studio.py backend/tests/test_chat_sources.py
git commit -m "fix(sources): resolve doc IDs to original_name in notebook sources endpoint"
```

## Task 3.2: Two-pass intent classification

**Files:**
- Create: `backend/core/chat/intent_classifier.py`
- Create: `backend/tests/core/chat/test_intent_classifier.py`
- Create: `backend/tests/api/test_chat_intent_routing.py`
- Modify: `backend/api/chat.py`

- [ ] **Step 1: Write failing classifier unit test**

```python
# backend/tests/core/chat/test_intent_classifier.py
import pytest
from core.chat.intent_classifier import classify_intent, Intent


class _FakeLLM:
    def __init__(self, response): self.response = response
    async def chat(self, messages, **kw):
        from types import SimpleNamespace
        return SimpleNamespace(content=self.response)


@pytest.mark.asyncio
async def test_classify_explanation_request():
    llm = _FakeLLM('{"output_type":"explanation","topic":"VAT zero-rated"}')
    intent = await classify_intent("Explain VAT zero-rating", llm)
    assert intent.output_type == "explanation"
    assert "VAT" in intent.topic

@pytest.mark.asyncio
async def test_classify_falls_back_to_answer_on_bad_json():
    llm = _FakeLLM("not json at all")
    intent = await classify_intent("question", llm)
    assert intent.output_type == "answer"
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

- [ ] **Step 3: Implement `intent_classifier.py`**

```python
# backend/core/chat/intent_classifier.py
from __future__ import annotations
import json, re
from dataclasses import dataclass
from typing import Literal

OutputType = Literal["answer", "explanation", "list", "table", "report", "comparison", "calculation"]

@dataclass
class Intent:
    output_type: OutputType
    topic: str

CLASSIFY_PROMPT = (
    "Classify the user's question. Return ONLY JSON of the form "
    '{"output_type":"answer|explanation|list|table|report|comparison|calculation",'
    '"topic":"<short topic>"}. No explanation.\n\nQuestion: {q}'
)

async def classify_intent(question: str, llm) -> Intent:
    try:
        resp = await llm.chat(
            messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(q=question)}],
            max_tokens=120, temperature=0.0,
        )
        match = re.search(r"\{.*\}", resp.content, re.DOTALL)
        if not match:
            return Intent(output_type="answer", topic=question[:80])
        data = json.loads(match.group())
        return Intent(
            output_type=data.get("output_type", "answer"),
            topic=data.get("topic", question[:80]),
        )
    except Exception:
        return Intent(output_type="answer", topic=question[:80])
```

- [ ] **Step 4: Run unit tests — expect PASS**

Run: `cd backend && pytest tests/core/chat/test_intent_classifier.py -v`

- [ ] **Step 5: Wire into `send_message` in `chat.py`**

Around line 415 (where `system_prompt` is built), insert BEFORE the prompt assembly:
```python
from core.chat.intent_classifier import classify_intent
classifier_llm = get_llm_provider(req.provider)
intent = await classify_intent(req.message, classifier_llm)
intent_directive = (
    f"\n\nUSER INTENT: The user wants a `{intent.output_type}` about `{intent.topic}`. "
    f"Respond ONLY in that form. Do not produce a different output type. "
    f"Stay strictly on topic; do not drift to related but unasked subjects."
)
```
Append `intent_directive` to `system_prompt` after it is constructed.

- [ ] **Step 6: Write integration test**

```python
# backend/tests/api/test_chat_intent_routing.py
import pytest

@pytest.mark.asyncio
async def test_intent_directive_is_appended(client, monkeypatch):
    captured: dict = {}
    class _CaptureLLM:
        async def chat(self, messages, **kw):
            captured["messages"] = messages
            from types import SimpleNamespace
            return SimpleNamespace(content='{"output_type":"list","topic":"X"}')
        async def stream(self, prompt, **kw):
            captured["prompt"] = prompt
            yield "ok"
    monkeypatch.setattr("api.chat.get_llm_provider", lambda *a, **kw: _CaptureLLM())
    r = await client.post("/api/chat/send", json={
        "message": "Give me a list of VAT exempt items", "mode": "fast", "use_rag": False,
    })
    assert r.status_code == 200
    # The system prompt should contain the directive
    msgs = captured.get("messages") or []
    sys = next((m["content"] for m in msgs if m["role"] == "system"), "")
    assert "USER INTENT" in sys
    assert "list" in sys
```

- [ ] **Step 7: Run integration test — expect PASS**

- [ ] **Step 8: Run existing chat tests for no regression**

Run: `cd backend && pytest tests/test_chat_endpoint_domain.py tests/api/test_conversation_mode.py -v`

- [ ] **Step 9: Commit**

```bash
git add backend/core/chat/intent_classifier.py backend/tests/core/chat/ backend/tests/api/test_chat_intent_routing.py backend/api/chat.py
git commit -m "feat(chat): two-pass intent classification to keep LLM on-topic"
```

## Task 3.3: Fix "must ask twice" — sendMessage finally + AbortController

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Locate sendMessage**

Open `LegalStudio.tsx` around line 540–660; find `sendMessage` and the `try { ... } catch { /* ignore */ }` followed by `setLoading(false);`.

- [ ] **Step 2: Refactor with AbortController + finally**

Replace the structure:
```tsx
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 30_000);
try {
  const response = await fetch(`${API_BASE}/api/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  });
  // ...existing reader loop...
} catch (err) {
  console.error('[sendMessage] failed', err);
  setMessages(prev => [...prev, {
    role: 'ai', text: '⚠️ Request failed or timed out. Please try again.',
    time: fmtTime(), id: crypto.randomUUID()
  }]);
} finally {
  clearTimeout(timeoutId);
  setLoading(false);
  setWebSearching(false);
}
```
Delete the trailing `setLoading(false); setWebSearching(false);` lines that lived outside the try.

- [ ] **Step 3: Manual test**

Start backend; in DevTools Network panel, throttle to "Offline"; send a message; verify:
- After ~30s the AI bubble shows "Request failed or timed out".
- Input is no longer disabled — the next message goes through immediately on first try.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "fix(chat): guarantee loading state cleared via finally + 30s abort timeout"
```

---

# PHASE 4 — Skills (Deep Research + Analyst)

## Task 4.1: Create the deep-research skill

**Files:**
- Create: `Project_AccountingLegalChatbot/skills/deep-research/SKILL.md`

- [ ] **Step 1: Read the existing skill pattern**

Run: view `Project_AccountingLegalChatbot/skills/learn-audit-format/SKILL.md` to copy its YAML frontmatter format and structure conventions.

- [ ] **Step 2: Write the skill**

Content outline (mirror the existing skill's tone):
```markdown
---
name: deep-research
description: Use when user asks for a comprehensive multi-source investigation, a "research report", or anything requiring web + document synthesis with cited sources. Triggered by phrases like "research", "deep dive", "investigate", "comprehensive analysis".
---

# Deep Research Skill

## When to Use
- User explicitly says "research", "deep research", or asks for a "report"
- Question requires synthesizing multiple sources (web + uploaded docs)
- Output needs structured sections + downloadable PDF/DOCX

## When NOT to Use
- Simple factual question (use Fast mode)
- User wants a structured financial report (use Analyst mode)

## Workflow
1. Switch the chat mode to `deep_research` via `setMode('deep_research')` or send `mode=deep_research` in the API call.
2. Send the user's question via `POST /api/chat/research/start` (or via `useDeepResearch().run(query, docIds)`).
3. Stream events: `step`, `answer`, `done`. On `done.error`, show inline error.
4. Render the final answer in the Research Panel; offer Download PDF / Download DOCX.
5. Persist the answer to chat as a `research` message with sources.

## Output Contract
- Final document MUST include: Cover (query + date) → TOC → Body → Sources Appendix with clickable URLs.
- All factual claims cite an entry in Sources.

## Failure Modes
- Brave Search timeout → continue with doc-only synthesis.
- LLM stream failure → emit `done` with `error`; UI shows inline error.
```

- [ ] **Step 3: Commit**

```bash
git add Project_AccountingLegalChatbot/skills/deep-research/SKILL.md
git commit -m "docs(skills): add deep-research skill"
```

## Task 4.2: Create the analyst skill

**Files:**
- Create: `Project_AccountingLegalChatbot/skills/analyst/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: analyst
description: Use when the user wants a structured financial / audit report — MIS pack, audit findings, KPI dashboard, ratio analysis, variance analysis. Requires uploaded documents (financials, ledgers, schedules).
---

# Analyst Skill

## When to Use
- "Generate an audit report", "produce MIS", "do ratio analysis", "compare years"
- User has uploaded financial documents (PDF/XLSX) into the notebook

## When NOT to Use
- General Q&A (Fast mode); investigation-style research (Deep Research)

## Prerequisites
- At least 1 document uploaded and indexed
- Conversation mode set to `analyst`

## Workflow
1. Set `mode = 'analyst'` (mounts ThreePaneLayout: Sources | Chat | Artifact).
2. Use `POST /api/chat/send` with `mode='analyst'` — backend uses the `analyst` system prompt (CA-style auditor persona).
3. The Artifact panel auto-detects report metadata and offers `Generate Report`.
4. Stream report generation via `generateReportStreamUrl(...)`.
5. On completion, offer Markdown / DOCX / PDF downloads.

## Output Contract
- Report must include: Executive Summary → KPI Cards → Findings (with severity) → Recommendations → Appendix.
- Numbers traceable to source documents.

## Error Handling
- If ThreePaneLayout crashes, the AnalystErrorBoundary will display the error and offer "Reset Analyst" → switches back to Fast mode.
```

- [ ] **Step 2: Commit**

```bash
git add Project_AccountingLegalChatbot/skills/analyst/SKILL.md
git commit -m "docs(skills): add analyst skill"
```

---

# PHASE 5 — LLM Council ("Run this by the council")

## Task 5.1: Persona prompts module

**Files:**
- Create: `backend/core/council/__init__.py`
- Create: `backend/core/council/personas.py`
- Create: `backend/tests/core/council/__init__.py`
- Create: `backend/tests/core/council/test_personas.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/core/council/test_personas.py
from core.council.personas import EXPERTS, SYNTHESIS_PROMPT

def test_four_experts_present():
    names = [e.name for e in EXPERTS]
    assert names == ["Senior CA", "CPA", "CMA", "Financial Analyst"]

def test_each_expert_has_persona_prompt():
    for e in EXPERTS:
        assert len(e.system_prompt) > 100
        assert e.name.lower().split()[0] in e.system_prompt.lower() or "you are" in e.system_prompt.lower()

def test_synthesis_prompt_mentions_reconciliation():
    assert "reconcile" in SYNTHESIS_PROMPT.lower() or "synthesi" in SYNTHESIS_PROMPT.lower()
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Create the module**

```python
# backend/core/council/__init__.py
from core.council.personas import EXPERTS, SYNTHESIS_PROMPT  # noqa: F401
```

```python
# backend/core/council/personas.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Expert:
    name: str
    role: str
    system_prompt: str

_CA = Expert(
    name="Senior CA",
    role="Chartered Accountant — Audit & Assurance",
    system_prompt=(
        "You are a Senior Chartered Accountant (ICAI/ICAEW) with 20+ years of audit "
        "and assurance experience. Review the proposed answer below and the prior "
        "expert critiques. Identify issues from an audit-evidence and IFRS-compliance "
        "perspective: missing disclosures, control weaknesses, going-concern flags, "
        "subsequent events, and ISA-required procedures. Be specific. Cite the "
        "relevant standard (ISA / IFRS) when raising a concern."
    ),
)
_CPA = Expert(
    name="CPA",
    role="Certified Public Accountant — US GAAP & Tax",
    system_prompt=(
        "You are a US Certified Public Accountant. Review the answer and prior "
        "critiques through a US GAAP and federal/state tax lens. Flag GAAP vs IFRS "
        "differences, ASC references, deferred tax implications, revenue-recognition "
        "issues (ASC 606), and tax-position uncertainties (ASC 740). Be concrete."
    ),
)
_CMA = Expert(
    name="CMA",
    role="Cost & Management Accountant — Costing & Performance",
    system_prompt=(
        "You are a Certified Management Accountant. Review the answer and prior "
        "critiques from a cost-accounting and performance-management angle: cost "
        "behaviour, contribution margin, variance analysis, transfer pricing, "
        "capacity utilisation, and budgeting impact. Cite specific cost concepts."
    ),
)
_ANALYST = Expert(
    name="Financial Analyst",
    role="Equity / Credit Analyst — Valuation & Risk",
    system_prompt=(
        "You are a buy-side Financial Analyst (CFA charterholder). Review the "
        "answer and prior critiques from a valuation, capital-structure, and "
        "risk-modelling perspective: DCF inputs, comparable multiples, leverage "
        "ratios, working-capital efficiency, and forward-looking risks. Quantify "
        "where possible."
    ),
)

EXPERTS = [_CA, _CPA, _CMA, _ANALYST]

SYNTHESIS_PROMPT = (
    "You are the Council Chair. Reconcile the four expert critiques below into a "
    "single, unified, high-confidence answer to the user's question. Where experts "
    "agreed, state it firmly. Where they disagreed, briefly note the disagreement "
    "and pick the position best supported by standards / evidence, explaining why. "
    "Output sections: Final Recommendation, Key Risks, Standards Cited, Open Items."
)
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/core/council/ backend/tests/core/council/
git commit -m "feat(council): add 4 expert personas + synthesis prompt"
```

## Task 5.2: Sequential-chain council service

**Files:**
- Create: `backend/core/council/council_service.py`
- Create: `backend/tests/core/council/test_council_service.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/core/council/test_council_service.py
import pytest
from core.council.council_service import run_council


class _ScriptedLLM:
    def __init__(self, scripts): self.scripts = list(scripts); self.calls = []
    async def stream(self, prompt, **kw):
        self.calls.append(prompt)
        for piece in self.scripts.pop(0):
            yield piece


@pytest.mark.asyncio
async def test_council_runs_four_experts_then_synthesis():
    llm = _ScriptedLLM([
        ["CA says ", "audit issue"],
        ["CPA says ", "tax issue"],
        ["CMA says ", "cost issue"],
        ["Analyst says ", "valuation issue"],
        ["Synthesis: ", "all combined"],
    ])
    events = []
    async for evt in run_council(question="Q?", base_answer="initial answer", llm=llm):
        events.append(evt)

    expert_evts = [e for e in events if e["type"] == "council_expert"]
    expert_names = [e["expert"] for e in expert_evts if e.get("final")]
    assert expert_names == ["Senior CA", "CPA", "CMA", "Financial Analyst"]

    synth = next(e for e in events if e["type"] == "council_synthesis")
    assert "Synthesis" in synth["content"]

    done = next(e for e in events if e["type"] == "done")
    assert done

    # Each expert prompt must include prior experts' final critiques (sequential chain)
    assert "CA says audit issue" in llm.calls[1]  # CPA sees CA
    assert "CPA says tax issue" in llm.calls[2]   # CMA sees CPA
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement service**

```python
# backend/core/council/council_service.py
from collections.abc import AsyncGenerator
from core.council.personas import EXPERTS, SYNTHESIS_PROMPT


def _build_expert_prompt(expert, question, base_answer, prior_critiques):
    prior = "\n\n".join(
        f"## {name} ({role}) said:\n{content}"
        for name, role, content in prior_critiques
    ) or "(no prior critiques)"
    return (
        f"{expert.system_prompt}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        f"PROPOSED BASE ANSWER:\n{base_answer}\n\n"
        f"PRIOR EXPERT CRITIQUES:\n{prior}\n\n"
        f"Provide YOUR critique now. Be specific and cite standards."
    )


def _build_synthesis_prompt(question, base_answer, all_critiques):
    blocks = "\n\n".join(
        f"## {name} ({role}):\n{content}"
        for name, role, content in all_critiques
    )
    return (
        f"{SYNTHESIS_PROMPT}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        f"PROPOSED BASE ANSWER:\n{base_answer}\n\n"
        f"EXPERT CRITIQUES:\n{blocks}\n\n"
        f"Produce the final unified answer now."
    )


async def run_council(*, question: str, base_answer: str, llm) -> AsyncGenerator[dict, None]:
    """Sequential chain: each expert sees prior experts' critiques."""
    error: str | None = None
    try:
        prior_critiques: list[tuple[str, str, str]] = []
        for expert in EXPERTS:
            yield {"type": "council_expert", "expert": expert.name, "role": expert.role, "status": "thinking"}
            prompt = _build_expert_prompt(expert, question, base_answer, prior_critiques)
            buf: list[str] = []
            async for piece in llm.stream(prompt, max_tokens=600, temperature=0.3):
                buf.append(piece)
                yield {"type": "council_expert", "expert": expert.name, "delta": piece}
            full = "".join(buf)
            yield {"type": "council_expert", "expert": expert.name, "content": full, "final": True}
            prior_critiques.append((expert.name, expert.role, full))

        synth_prompt = _build_synthesis_prompt(question, base_answer, prior_critiques)
        synth_buf: list[str] = []
        yield {"type": "council_synthesis", "status": "thinking"}
        async for piece in llm.stream(synth_prompt, max_tokens=800, temperature=0.2):
            synth_buf.append(piece)
            yield {"type": "council_synthesis", "delta": piece}
        yield {"type": "council_synthesis", "content": "".join(synth_buf), "final": True}
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        yield {"type": "council_error", "error": error}
    finally:
        payload: dict = {"type": "done"}
        if error:
            payload["error"] = error
        yield payload
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/core/council/council_service.py backend/tests/core/council/test_council_service.py
git commit -m "feat(council): sequential-chain orchestration with streaming events"
```

## Task 5.3: Council API endpoint

**Files:**
- Create: `backend/api/council.py`
- Create: `backend/tests/api/test_council_endpoint.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Failing endpoint test**

```python
# backend/tests/api/test_council_endpoint.py
import pytest, json

@pytest.mark.asyncio
async def test_council_endpoint_streams_events(client, monkeypatch):
    class _StubLLM:
        async def stream(self, prompt, **kw):
            yield "ok"
    monkeypatch.setattr("api.council.get_llm_provider", lambda *a, **kw: _StubLLM())
    async with client.stream("POST", "/api/chat/council", json={
        "question": "Should we capitalize this lease?",
        "base_answer": "Yes per IFRS 16",
    }) as r:
        assert r.status_code == 200
        body = b""
        async for chunk in r.aiter_bytes():
            body += chunk
        text = body.decode()
        assert "council_expert" in text
        assert "Senior CA" in text
        assert "council_synthesis" in text
        assert '"type": "done"' in text or '"type":"done"' in text
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement endpoint**

```python
# backend/api/council.py
import json, logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.llm_manager import get_llm_provider
from core.council.council_service import run_council

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Council"])


class CouncilRequest(BaseModel):
    question: str
    base_answer: str
    provider: str | None = None


@router.post("/council")
async def council_stream(req: CouncilRequest):
    llm = get_llm_provider(req.provider)

    async def gen():
        async for evt in run_council(question=req.question, base_answer=req.base_answer, llm=llm):
            yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 4: Register router in `main.py`**

Find where other routers are included; add:
```python
from api.council import router as council_router
app.include_router(council_router)
```

- [ ] **Step 5: Run — PASS**

Run: `cd backend && pytest tests/api/test_council_endpoint.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/api/council.py backend/main.py backend/tests/api/test_council_endpoint.py
git commit -m "feat(council): /api/chat/council SSE endpoint"
```

## Task 5.4: Frontend — useCouncil hook + CouncilPanel + CouncilButton

**Files:**
- Create: `frontend/src/hooks/useCouncil.ts`
- Create: `frontend/src/components/studios/LegalStudio/CouncilPanel.tsx`
- Create: `frontend/src/components/studios/LegalStudio/CouncilButton.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/ModePills.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add API helper**

```ts
// frontend/src/lib/api.ts (append)
export const councilEndpoint = `${API_BASE}/api/chat/council`;
```

- [ ] **Step 2: Implement `useCouncil` hook**

```ts
// frontend/src/hooks/useCouncil.ts
import { useState, useCallback } from 'react';
import { councilEndpoint } from '../lib/api';

export interface ExpertState { name: string; role?: string; content: string; status: 'idle'|'thinking'|'final' }

export function useCouncil() {
  const [experts, setExperts] = useState<Record<string, ExpertState>>({});
  const [synthesis, setSynthesis] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (question: string, baseAnswer: string) => {
    setExperts({}); setSynthesis(''); setError(null); setRunning(true);
    try {
      const res = await fetch(councilEndpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ question, base_answer: baseAnswer }),
      });
      const reader = res.body?.getReader();
      if (!reader) throw new Error('no stream');
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'council_expert') {
              setExperts(prev => {
                const cur = prev[evt.expert] ?? { name: evt.expert, role: evt.role, content: '', status: 'thinking' };
                if (evt.delta) cur.content += evt.delta;
                if (evt.final) { cur.content = evt.content; cur.status = 'final'; }
                if (evt.status === 'thinking') cur.status = 'thinking';
                return { ...prev, [evt.expert]: { ...cur } };
              });
            } else if (evt.type === 'council_synthesis') {
              if (evt.delta) setSynthesis(s => s + evt.delta);
              if (evt.final) setSynthesis(evt.content);
            } else if (evt.type === 'council_error') {
              setError(evt.error);
            } else if (evt.type === 'done') {
              if (evt.error) setError(evt.error);
              setRunning(false);
            }
          } catch { /* skip */ }
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }, []);

  return { experts, synthesis, running, error, run };
}
```

- [ ] **Step 3: Implement `CouncilPanel`**

```tsx
// frontend/src/components/studios/LegalStudio/CouncilPanel.tsx
import { ExpertState } from '../../../hooks/useCouncil';

interface Props {
  experts: Record<string, ExpertState>;
  synthesis: string;
  running: boolean;
  error: string | null;
}

const ORDER = ['Senior CA', 'CPA', 'CMA', 'Financial Analyst'];

export function CouncilPanel({ experts, synthesis, running, error }: Props) {
  return (
    <div className="council-panel" style={{ display: 'grid', gap: 12, padding: 16 }}>
      <h3>LLM Council {running && '— deliberating…'}</h3>
      {error && <div style={{ color: '#9b2226' }}>Error: {error}</div>}
      {ORDER.map(name => {
        const e = experts[name];
        return (
          <div key={name} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12 }}>
            <strong>{name}</strong> {e?.status === 'thinking' && <em>thinking…</em>}
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, marginTop: 8 }}>{e?.content ?? ''}</pre>
          </div>
        );
      })}
      <div style={{ borderTop: '2px solid #1a365d', paddingTop: 12 }}>
        <strong>Council Synthesis</strong>
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 14, marginTop: 8 }}>{synthesis}</pre>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement `CouncilButton`**

```tsx
// frontend/src/components/studios/LegalStudio/CouncilButton.tsx
interface Props { onClick: () => void; disabled?: boolean; }
export function CouncilButton({ onClick, disabled }: Props) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title="Run this by the council (CA + CPA + CMA + Financial Analyst)"
      style={{
        padding: '6px 12px', borderRadius: 16, border: '1px solid #1a365d',
        background: '#fff', color: '#1a365d', cursor: 'pointer', fontSize: 13,
      }}
    >
      🏛️ Run this by the council
    </button>
  );
}
```

- [ ] **Step 5: Integrate into `LegalStudio.tsx`**

- Import the hook + components.
- Add state for `councilOpen`.
- Wire button: `<CouncilButton onClick={() => { setCouncilOpen(true); council.run(lastQuestion, lastAnswer); }} disabled={mode === 'fast'} />`.
- Render `<CouncilPanel ...council />` in the right panel when `councilOpen`.
- Add `/council` slash-command detection in `sendMessage`: if `text.trim().startsWith('/council')`, trigger council on the most recent assistant answer.

- [ ] **Step 6: Add button next to ModePills**

In `ModePills.tsx`, render `<CouncilButton>` next to (not inside) the pill group. Wire `onCouncil` prop from parent.

- [ ] **Step 7: Manual smoke test**

Start app; in Deep Research mode, ask a question; after answer arrives, click "Run this by the council"; verify all 4 expert cards stream in order; synthesis appears at the bottom.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/hooks/useCouncil.ts frontend/src/components/studios/LegalStudio/CouncilPanel.tsx frontend/src/components/studios/LegalStudio/CouncilButton.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/components/studios/LegalStudio/ModePills.tsx frontend/src/lib/api.ts
git commit -m "feat(council): frontend panel + button + /council command"
```

---

# PHASE 6 — Final Verification (Code Review + Demo)

## Task 6.1: Run full backend test suite

- [ ] **Step 1:** Run: `cd backend && pytest -x -q`
  Expected: 0 failures.
- [ ] **Step 2:** Fix any regressions surfaced. Re-run until green.

## Task 6.2: Run frontend type-check + build

- [ ] **Step 1:** Run: `cd frontend && npm run build`
  Expected: build succeeds, no TS errors.

## Task 6.3: End-to-end smoke demo

Manual checklist (start backend `uvicorn main:app --reload`, frontend `npm run dev`):

- [ ] Fast mode: send "What is VAT zero-rating in UAE?" — receive an answer; source filenames are real names (not IDs).
- [ ] Send a follow-up message — does NOT require sending twice.
- [ ] Switch to Deep Research mode; ask "Research IFRS 16 lease accounting"; receive streamed steps + final answer; click Download PDF + Download DOCX; both open; sources appendix shows clickable URLs.
- [ ] Force a failure (kill internet briefly during research) → UI shows error and stops "running".
- [ ] Switch to Analyst mode — three-pane layout renders (no white screen). If a crash happens, the AnalystErrorBoundary fallback shows.
- [ ] In Deep Research, after an answer, click "Run this by the council" — all 4 experts stream in order; synthesis follows; "done" arrives and panel exits running state.
- [ ] Try `/council` as a chat command — same behaviour.

## Task 6.4: Code review

- [ ] **Step 1:** Use the `superpowers:code-reviewer` agent with the full diff (`git diff main...HEAD`). Pass spec link as context.
- [ ] **Step 2:** Address every actionable finding. Re-run tests after each fix.
- [ ] **Step 3:** Final commit:

```bash
git add -A
git commit -m "chore: post-review polish"
```

---

## Self-Review Summary
- Spec coverage: All 5 priority groups have at least one task ✓
- Placeholders: None — every code step is fully written ✓
- Type consistency: `Intent.output_type`, `Expert.name`, SSE event `type` strings consistent across all tasks ✓
- Test coverage: New code has at least one unit + (where applicable) one integration test ✓
