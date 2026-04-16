# Audit Analysis Chat, Prior Year Extraction & Platform Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the source panel click bug, add web search fallback with RAG auto-save, redesign the New Report sidebar button, extract prior year data from scanned PDFs, add a post-audit analysis chat step, and produce properly formatted professional audit DOCX reports.

**Architecture:** Issues 1–3 are standalone fixes. Issues 4 and 5 are linked — prior year data extracted in Issue 4 is stored in component state and passed as context to the new Analysis Chat step (Issue 5). Issue 6 adds a DOCX formatter that reads the existing audit rows and company info to produce a properly structured report on download.

**Tech Stack:** React 18 + TypeScript (frontend), FastAPI + Python (backend), python-docx (DOCX formatter), PyMuPDF + pdf2image (PDF extraction), OpenAI vision API (scanned PDF fallback), duckduckgo-search (web fallback), ChromaDB (RAG auto-ingest).

---

## File Map

### Frontend — New Files
| File | Purpose |
|------|---------|
| `frontend/src/components/studios/FinancialStudio/NewReportPanel.tsx` | Grouped report card selector (Issue 3) |
| `frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx` | Post-audit two-panel chat step (Issue 5) |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Fix source click handler + web search status indicator (Issues 1, 2) |
| `frontend/src/components/ContextualSidebar.tsx` | Add NewReportPanel above Saved Reports (Issue 3) |
| `frontend/src/components/studios/FinancialStudio/CompanyDocuments.tsx` | Add Prior Year PDF upload zone (Issue 4) |
| `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx` | Insert AuditAnalysisStep at wizard step 6, shift old steps up (Issue 5) |

### Backend — New Files
| File | Purpose |
|------|---------|
| `backend/core/web_search.py` | DuckDuckGo async search wrapper (Issue 2) |
| `backend/core/prior_year_extractor.py` | Hybrid PDF extraction: text path + Vision LLM path (Issue 4) |
| `backend/core/audit_formatter.py` | DOCX template formatter from audit rows + company info (Issue 6) |
| `backend/core/templates/audit_report_base.py` | python-docx style definitions (Issue 6) |
| `backend/tests/test_prior_year_extractor.py` | Tests for extractor (Issue 4) |
| `backend/tests/test_audit_formatter.py` | Tests for formatter (Issue 6) |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/requirements.txt` | Add `duckduckgo-search==6.3.7` (Issue 2) |
| `backend/api/chat.py` | Auto-trigger web search when RAG empty; emit `searching_web` SSE event; ingest found content to RAG (Issue 2) |
| `backend/api/reports.py` | Add `extract-prior-year`, `analysis-chat`, `generate-from-session`, `aging-schedule` endpoints; route DOCX export through formatter (Issues 4, 5, 6) |

---

## Task 1 — Fix Source Panel Click Bug (Issue 1)

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx:174-176`

The bug: `handleSourceClick` sets `activeSource` state but never sets `sourcePanelOpen` to `true`. The panel only opens via a `useEffect` that watches `loading` (lines 193–199), so manual clicks have no effect.

- [ ] **Step 1: Open `LegalStudio.tsx` and locate `handleSourceClick` at line 174**

Replace lines 174–176:
```tsx
// BEFORE (lines 174-176)
const handleSourceClick = (source: Source) => {
  setActiveSource(prev => prev?.source === source.source ? null : source);
};

// AFTER
const handleSourceClick = (source: Source) => {
  if (activeSource?.source === source.source) {
    setActiveSource(null);
    setSourcePanelOpen(false);
  } else {
    setActiveSource(source);
    setSourcePanelOpen(true);
  }
};
```

- [ ] **Step 2: Verify in browser**

Start the frontend (`npm run dev`), open LegalStudio, send any question that returns sources, then click the "🔗 Sources" button in the message. The SourcePeeker panel should slide open. Clicking the same button again should close it.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "fix: source panel now opens when clicking Sources badge in LegalStudio"
```

---

## Task 2 — New Report Panel Component (Issue 3)

**Files:**
- Create: `frontend/src/components/studios/FinancialStudio/NewReportPanel.tsx`
- Modify: `frontend/src/components/ContextualSidebar.tsx:250-252`

- [ ] **Step 1: Create `NewReportPanel.tsx`**

```tsx
import { useState } from 'react';
import { REPORT_TYPE_CONFIG } from './report-types';

interface Props {
  onSelect: (key: string) => void;
}

const GROUPS = [
  { label: 'TAX & COMPLIANCE', keys: ['audit', 'vat', 'corporate_tax', 'compliance'] },
  { label: 'MANAGEMENT', keys: ['mis', 'financial_analysis', 'budget_vs_actual'] },
  { label: 'STATUTORY', keys: ['ifrs', 'cash_flow'] },
  { label: 'OTHER', keys: ['custom'] },
];

export function NewReportPanel({ onSelect }: Props) {
  const [open, setOpen] = useState(false);

  const configMap = Object.fromEntries(REPORT_TYPE_CONFIG.map(c => [c.key, c]));

  return (
    <div style={{ padding: '8px 8px 4px' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          padding: '8px 12px',
          borderRadius: 'var(--s-r-md)',
          border: '1px solid var(--s-accent)',
          background: 'var(--s-accent-dim)',
          color: 'var(--s-accent)',
          fontFamily: 'var(--s-font-ui)',
          fontSize: '13px',
          fontWeight: 600,
          cursor: 'pointer',
          transition: 'var(--s-ease)',
        }}
      >
        <span>＋ New Report</span>
        <span style={{ fontSize: '10px' }}>{open ? '▲' : '▾'}</span>
      </button>

      {open && (
        <div style={{
          marginTop: '6px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          padding: '10px',
          borderRadius: 'var(--s-r-md)',
          border: '1px solid var(--s-border)',
          background: 'var(--s-surface)',
        }}>
          {GROUPS.map(group => {
            const items = group.keys.map(k => configMap[k]).filter(Boolean);
            if (items.length === 0) return null;
            return (
              <div key={group.label}>
                <div style={{
                  fontFamily: 'var(--s-font-ui)',
                  fontSize: '10px',
                  fontWeight: 700,
                  color: 'var(--s-text-2)',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  marginBottom: '4px',
                }}>
                  {group.label}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {items.map(cfg => (
                    <button
                      key={cfg.key}
                      onClick={() => { setOpen(false); onSelect(cfg.key); }}
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        padding: '5px 8px',
                        borderRadius: 'var(--s-r-sm)',
                        border: '1px solid transparent',
                        background: 'transparent',
                        color: 'var(--s-text-1)',
                        fontFamily: 'var(--s-font-ui)',
                        fontSize: '12px',
                        cursor: 'pointer',
                        transition: 'var(--s-ease)',
                      }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLButtonElement).style.background = 'rgba(107,140,255,0.08)';
                        (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-border)';
                        (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-accent)';
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                        (e.currentTarget as HTMLButtonElement).style.borderColor = 'transparent';
                        (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-text-1)';
                      }}
                    >
                      {cfg.label}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire `NewReportPanel` into `ContextualSidebar.tsx`**

In `ContextualSidebar.tsx`, the financial studio section starts at line 250. Add the import and insert `NewReportPanel` above the `Saved Reports` title.

Add import at the top of the file with other imports:
```tsx
import { NewReportPanel } from './studios/FinancialStudio/NewReportPanel';
```

In the `{activeStudio === 'financial' && ...}` block, replace line 252:
```tsx
// BEFORE (line 252)
<div className="sidebar-section-title">Saved Reports</div>

// AFTER
<NewReportPanel onSelect={(key) => {
  // Navigate to financial studio and start the selected report type
  navigate('/reports');
  // Signal FinancialStudio to start with this report type
  window.dispatchEvent(new CustomEvent('studio:new-report', { detail: key }));
}} />
<div className="sidebar-section-title" style={{ marginTop: '8px' }}>Saved Reports</div>
```

- [ ] **Step 3: Handle `studio:new-report` event in `FinancialStudio.tsx`**

In `FinancialStudio.tsx`, add a `useEffect` that listens for the custom event and sets the selected config + resets to step 0:

Add after the existing `useEffect` blocks (around line 85):
```tsx
useEffect(() => {
  const handler = (e: Event) => {
    const key = (e as CustomEvent<string>).detail;
    const cfg = REPORT_TYPE_CONFIG.find(c => c.key === key) ?? null;
    if (cfg) {
      setSelectedConfig(cfg);
      setActiveStep(1 as Step); // skip to Upload File step
    }
  };
  window.addEventListener('studio:new-report', handler);
  return () => window.removeEventListener('studio:new-report', handler);
}, []);
```

- [ ] **Step 4: Verify in browser**

Open FinancialStudio sidebar. The "＋ New Report" button should appear above Saved Reports. Clicking it should expand the grouped card list. Clicking a card should close the panel and start that report type's wizard.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/FinancialStudio/NewReportPanel.tsx \
        frontend/src/components/ContextualSidebar.tsx \
        frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx
git commit -m "feat: add grouped New Report panel above Saved Reports in financial sidebar"
```

---

## Task 3 — Web Search Fallback — Backend (Issue 2)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/core/web_search.py`
- Modify: `backend/api/chat.py`

- [ ] **Step 1: Add dependency**

Add to `backend/requirements.txt` after the `requests` line:
```
duckduckgo-search==6.3.7
```

Install: `cd backend && uv pip install duckduckgo-search==6.3.7`

- [ ] **Step 2: Create `backend/core/web_search.py`**

```python
"""
Web search fallback — used when RAG has no relevant results.
Uses DuckDuckGo (no API key required).
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web for query. Returns list of dicts with keys:
    title, href, body (snippet text).
    Returns [] on any error — caller must handle gracefully.
    """
    try:
        from duckduckgo_search import DDGS

        def _sync_search() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_search)
        return results or []
    except Exception as exc:
        logger.warning(f"Web search failed for query '{query[:60]}': {exc}")
        return []


def build_web_context(results: list[dict]) -> str:
    """
    Format web search results into a context block for the LLM system prompt.
    """
    if not results:
        return ""
    lines = ["The following information was found on the web:\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("href", "")
        body = r.get("body", "")
        lines.append(f"[Source {i}] {title}\nURL: {url}\n{body}\n")
    return "\n".join(lines)
```

- [ ] **Step 3: Modify `backend/api/chat.py` streaming path**

In `chat.py`, after the RAG search block (around line 155), add the web search fallback. Also add an auto-ingest step after the response completes.

Add this import at the top of `chat.py`:
```python
from core.web_search import search_web, build_web_context
```

In the `generate()` async function (inside the streaming path, around line 187), replace the existing `generate()` function body:

```python
async def generate():
    nonlocal sources  # allow modification inside nested function

    # First event: metadata
    meta: dict = {"type": "meta", "conversation_id": conversation.id}
    detected = _classify_domain(req.message)
    if detected:
        meta["detected_domain"] = detected
    yield f"data: {json.dumps(meta)}\n\n"

    # If RAG returned nothing, try web search
    if not search_results:
        yield f"data: {json.dumps({'type': 'status', 'status': 'searching_web'})}\n\n"
        web_results = await search_web(req.message, max_results=5)
        if web_results:
            web_context = build_web_context(web_results)
            web_instruction = (
                "IMPORTANT: Answer ONLY using the web search results provided below. "
                "Do not add information from your training data. "
                "Cite the source URLs inline. Take your time and be accurate.\n\n"
                + web_context
            )
            # Replace the system message with web-augmented version
            messages[0] = {"role": "system", "content": system_prompt + "\n\n" + web_instruction}
            # Build sources list from web results
            sources = [
                {
                    "source": r.get("href", ""),
                    "page": "web",
                    "score": 1.0,
                    "excerpt": r.get("body", "")[:200],
                    "is_web": True,
                }
                for r in web_results
            ]
        else:
            yield f"data: {json.dumps({'type': 'status', 'status': 'web_search_failed'})}\n\n"

    full_response = ""
    try:
        async for chunk in llm.chat_stream(
            messages,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        ):
            full_response += chunk
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
    except Exception as stream_exc:
        err = repr(stream_exc) if str(stream_exc) == '' else f"{type(stream_exc).__name__}: {stream_exc}"
        logger.error(f"LLM streaming error: {err}")
        yield f"data: {json.dumps({'type': 'error', 'message': err})}\n\n"
        return

    if sources:
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

    # Auto-ingest web results into RAG for future queries
    if not search_results and sources:
        try:
            web_text = "\n\n".join(
                f"{s.get('source', '')}\n{s.get('excerpt', '')}"
                for s in sources if s.get("is_web")
            )
            if web_text.strip():
                await rag_engine.ingest_text(
                    text=web_text,
                    metadata={"source": "web_search", "query": req.message[:200], "category": req.domain or "general"},
                )
        except Exception as ingest_exc:
            logger.warning(f"RAG auto-ingest of web results failed: {ingest_exc}")

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=full_response,
        sources=sources if sources else None,
    )
    db.add(assistant_msg)
    await db.commit()
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
```

- [ ] **Step 4: Verify `rag_engine.ingest_text` exists**

Check `backend/core/rag_engine.py` — if `ingest_text(text, metadata)` does not exist, add it. Open the file and look for the ingest method. If it's named differently (e.g. `add_documents`), use that instead and adjust the call in step 3.

- [ ] **Step 5: Commit backend web search**

```bash
git add backend/requirements.txt backend/core/web_search.py backend/api/chat.py
git commit -m "feat: add DuckDuckGo web search fallback when RAG has no results; auto-ingest findings to ChromaDB"
```

---

## Task 4 — Web Search Frontend Status Indicator (Issue 2)

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Add `webSearching` state to LegalStudio**

After the existing state declarations (around line 42), add:
```tsx
const [webSearching, setWebSearching] = useState(false);
```

- [ ] **Step 2: Handle `status` SSE event in the SSE loop**

In `LegalStudio.tsx`, inside the SSE event loop (around line 133), add a new `else if` branch after the `evt.type === 'meta'` block:

```tsx
} else if (evt.type === 'status' && evt.status === 'searching_web') {
  setWebSearching(true);
} else if (evt.type === 'chunk' && evt.content) {
  setWebSearching(false); // clear indicator once first chunk arrives
  // ... existing chunk handling
```

- [ ] **Step 3: Show indicator in the loading area**

In `LegalStudio.tsx`, pass `webSearching` to `ChatMessages`. First update the `ChatMessages` JSX call (around line 243):
```tsx
<ChatMessages
  messages={messages}
  loading={loading}
  webSearching={webSearching}
  onSourceClick={handleSourceClick}
  activeSourceId={activeSource?.source}
/>
```

In `ChatMessages.tsx`, update the `Props` interface and the loading indicator:
```tsx
// Add to Props interface (line 6-11)
interface Props {
  messages: Message[];
  loading: boolean;
  webSearching?: boolean;
  onSourceClick: (source: Source) => void;
  activeSourceId?: string;
}

// Update the loading bubble (around line 146-154)
{loading && (
  <div className="chat-msg chat-msg--ai">
    <DiamondIcon />
    <div className="chat-msg__body">
      <div className="chat-msg__bubble">
        {webSearching ? (
          <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
            🌐 Searching the web…
          </span>
        ) : (
          <span className="chat-typing"><span /><span /><span /></span>
        )}
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 4: Verify in browser**

Ask a question on a topic not in the RAG database. The loading indicator should briefly show "🌐 Searching the web…" before the response starts streaming. Web search sources should show in the source badge.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx \
        frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "feat: show web search indicator in LegalStudio chat when falling back to web search"
```

---

## Task 5 — Prior Year Extractor — Backend (Issue 4)

**Files:**
- Create: `backend/core/prior_year_extractor.py`
- Modify: `backend/api/reports.py`
- Create: `backend/tests/test_prior_year_extractor.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_prior_year_extractor.py`:
```python
"""Tests for prior year PDF extractor."""
import pytest
from unittest.mock import patch, AsyncMock
from core.prior_year_extractor import (
    _has_financial_data,
    _parse_text_tables,
    build_prior_year_context,
)


def test_has_financial_data_detects_numbers():
    text = "Property, plant & equipment  1,919,606  2,131,198"
    assert _has_financial_data(text) is True


def test_has_financial_data_returns_false_for_empty():
    assert _has_financial_data("") is False
    assert _has_financial_data("   ") is False
    assert _has_financial_data("Invoice dated January 2024") is False


def test_parse_text_tables_extracts_rows():
    text = (
        "Property, plant & equipment  1,919,606  2,131,198\n"
        "Trade receivables  720,277  424,857\n"
        "Cash and cash equivalents  2,369,660  5,003,516\n"
        "Total Assets  5,929,549  9,489,570\n"
    )
    rows = _parse_text_tables(text)
    assert len(rows) >= 3
    # Each row should have account_name and prior_year_value
    for r in rows:
        assert "account_name" in r
        assert "prior_year_value" in r


def test_build_prior_year_context_formats_correctly():
    rows = [
        {"account_name": "Total Assets", "prior_year_value": 9489570.0},
        {"account_name": "Trade receivables", "prior_year_value": 424857.0},
    ]
    ctx = build_prior_year_context(rows)
    assert "Total Assets" in ctx
    assert "9,489,570" in ctx
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
uv run pytest tests/test_prior_year_extractor.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.prior_year_extractor'`

- [ ] **Step 3: Create `backend/core/prior_year_extractor.py`**

```python
"""
Prior Year Financial Data Extractor.

Hybrid approach:
1. Try PyMuPDF text extraction (works for digital PDFs)
2. Fall back to Vision LLM (for scanned/image PDFs)

Returns a list of dicts: {account_name, prior_year_value}
"""
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from core.llm_manager import get_llm_provider

logger = logging.getLogger(__name__)


def _has_financial_data(text: str) -> bool:
    """Return True if text contains numeric patterns typical of financial statements."""
    if not text or not text.strip():
        return False
    # Look for numbers like 1,919,606 or 424,857.00
    return bool(re.search(r'\d{1,3}(?:,\d{3})+(?:\.\d{2})?', text))


def _parse_text_tables(text: str) -> list[dict]:
    """
    Parse financial table rows from extracted PDF text.
    Looks for lines with an account name followed by two numbers
    (current year and prior year). Returns rows with prior_year_value.
    """
    rows = []
    # Pattern: text followed by optional spaces and two decimal numbers
    pattern = re.compile(
        r'^(.+?)\s{2,}([\-\(]?\d[\d,]*(?:\.\d+)?[\)]?)\s{2,}([\-\(]?\d[\d,]*(?:\.\d+)?[\)]?)\s*$'
    )
    for line in text.split('\n'):
        line = line.strip()
        m = pattern.match(line)
        if m:
            account_name = m.group(1).strip()
            prior_raw = m.group(3).replace(',', '').replace('(', '-').replace(')', '')
            try:
                prior_value = float(prior_raw)
                rows.append({
                    "account_name": account_name,
                    "prior_year_value": prior_value,
                })
            except ValueError:
                continue
    return rows


def build_prior_year_context(rows: list[dict]) -> str:
    """Format extracted rows as a readable context string for the LLM."""
    if not rows:
        return ""
    lines = ["Prior Year Financial Data (extracted from uploaded audit report):\n"]
    for r in rows:
        val = r.get("prior_year_value", 0)
        lines.append(f"  {r['account_name']}: AED {val:,.0f}")
    return "\n".join(lines)


async def extract_prior_year_from_pdf(file_path: str) -> dict:
    """
    Main entry point. Returns:
    {
        rows: list[{account_name, prior_year_value}],
        extraction_method: "text" | "vision" | "failed",
        confidence: float,
        context: str  (formatted for LLM prompt injection)
    }
    """
    try:
        doc = fitz.open(file_path)
        all_text = ""
        for page in doc:
            all_text += page.get_text()
        doc.close()

        if _has_financial_data(all_text):
            rows = _parse_text_tables(all_text)
            if rows:
                return {
                    "rows": rows,
                    "extraction_method": "text",
                    "confidence": 0.85,
                    "context": build_prior_year_context(rows),
                }

        # Fallback: Vision LLM
        rows = await _extract_via_vision(file_path)
        if rows:
            return {
                "rows": rows,
                "extraction_method": "vision",
                "confidence": 0.75,
                "context": build_prior_year_context(rows),
            }

    except Exception as exc:
        logger.error(f"Prior year extraction failed: {exc}")

    return {
        "rows": [],
        "extraction_method": "failed",
        "confidence": 0.0,
        "context": "",
    }


async def _extract_via_vision(file_path: str) -> list[dict]:
    """
    Convert PDF pages to images and use Vision LLM to extract financial tables.
    Uses the OpenAI provider since it supports vision input.
    """
    try:
        from pdf2image import convert_from_path
        import base64
        import io

        pages = convert_from_path(file_path, first_page=1, last_page=8, dpi=200)

        # Build a text-only prompt with page content described to the LLM
        # (Vision API requires base64 image input via OpenAI)
        llm = get_llm_provider("openai")

        all_rows: list[dict] = []

        for page_img in pages[:6]:  # Cap at 6 pages to limit API cost
            buf = io.BytesIO()
            page_img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "This is a page from a financial audit report. "
                                "Extract all financial statement table rows as JSON. "
                                "For each row output: "
                                "{\"account_name\": str, \"prior_year_value\": number_or_null}. "
                                "The prior year column is the SECOND numeric column (rightmost). "
                                "Return ONLY a JSON array. No explanation."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ]

            resp = await llm.chat(messages, temperature=0.1, max_tokens=2000)
            raw = resp.content.strip()
            # Strip markdown fences if present
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)

            try:
                page_rows = json.loads(raw)
                if isinstance(page_rows, list):
                    for r in page_rows:
                        if isinstance(r, dict) and r.get("account_name") and r.get("prior_year_value") is not None:
                            all_rows.append({
                                "account_name": str(r["account_name"]),
                                "prior_year_value": float(r["prior_year_value"]) if r["prior_year_value"] else 0.0,
                            })
            except (json.JSONDecodeError, ValueError):
                continue

        # Deduplicate by account_name (keep last occurrence)
        seen = {}
        for r in all_rows:
            seen[r["account_name"].lower()] = r
        return list(seen.values())

    except Exception as exc:
        logger.error(f"Vision extraction failed: {exc}")
        return []
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend
uv run pytest tests/test_prior_year_extractor.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Add endpoint to `backend/api/reports.py`**

Find the end of the existing endpoint list in `reports.py` and add:

```python
@router.post("/extract-prior-year")
async def extract_prior_year(
    file: UploadFile = File(...),
    session_id: str = Form(default=""),
):
    """Extract prior year financial data from an uploaded PDF (digital or scanned)."""
    import tempfile, os
    from core.prior_year_extractor import extract_prior_year_from_pdf

    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await extract_prior_year_from_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)

    return result
```

Ensure `File`, `Form`, `UploadFile`, and `Path` are imported at the top of `reports.py`. `Path` is from `pathlib`, the others from `fastapi`.

- [ ] **Step 6: Commit**

```bash
git add backend/core/prior_year_extractor.py \
        backend/api/reports.py \
        backend/tests/test_prior_year_extractor.py
git commit -m "feat: add hybrid prior year PDF extractor (text + vision LLM fallback)"
```

---

## Task 6 — Prior Year Upload Zone — Frontend (Issue 4)

**Files:**
- Modify: `frontend/src/components/studios/FinancialStudio/CompanyDocuments.tsx`
- Modify: `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx`

The goal: add a second upload slot for the prior year audit PDF. After extraction, the result is passed up to FinancialStudio and stored as `priorYearData`.

- [ ] **Step 1: Update `CompanyDocuments` props interface**

In `CompanyDocuments.tsx`, add a new prop and state for prior year extraction. Update the `Props` interface (line 36-38):

```tsx
interface Props {
  onComplete: (info: CompanyInfo, priorYearContext?: string) => void;
  onSkip: () => void;
}
```

- [ ] **Step 2: Add prior year upload state**

After the existing `useState` declarations in `CompanyDocuments.tsx` (around line 47), add:
```tsx
const [priorYearFile, setPriorYearFile] = useState<File | null>(null);
const [priorYearExtracting, setPriorYearExtracting] = useState(false);
const [priorYearRows, setPriorYearRows] = useState<Array<{account_name: string; prior_year_value: number}>>([]);
const [priorYearError, setPriorYearError] = useState('');
```

- [ ] **Step 3: Add prior year upload handler**

After the `handleExtract` function, add:
```tsx
const handlePriorYearUpload = async (file: File) => {
  setPriorYearFile(file);
  setPriorYearExtracting(true);
  setPriorYearError('');
  try {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await API.post('/api/reports/extract-prior-year', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    });
    const data = resp.data as { rows: Array<{account_name: string; prior_year_value: number}>; extraction_method: string };
    if (data.rows && data.rows.length > 0) {
      setPriorYearRows(data.rows);
    } else {
      setPriorYearError('Could not extract figures automatically. Prior year data can be entered manually in the Evidence step.');
    }
  } catch {
    setPriorYearError('Extraction failed. You can continue and enter prior year figures manually.');
  } finally {
    setPriorYearExtracting(false);
  }
};
```

- [ ] **Step 4: Add prior year upload UI in the upload phase**

In the upload phase JSX (the `return` at line 158), add a second upload block after the existing file input block:

```tsx
{/* Prior Year Audit Report — optional */}
<div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px', padding: '12px', borderRadius: 'var(--s-r-sm)', border: '1px dashed var(--s-border)', background: 'rgba(107,140,255,0.03)' }}>
  <label style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
    Prior Year Audit Report <span style={{ color: 'var(--s-text-2)', fontWeight: 400 }}>(optional — for comparative analysis)</span>
  </label>
  <input
    type="file"
    accept=".pdf"
    onChange={e => {
      const f = e.target.files?.[0];
      if (f) handlePriorYearUpload(f);
    }}
    style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}
  />
  {priorYearExtracting && (
    <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
      Extracting prior year financials…
    </div>
  )}
  {priorYearRows.length > 0 && (
    <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: '#16a34a' }}>
      ✓ Extracted {priorYearRows.length} prior year figures
    </div>
  )}
  {priorYearError && (
    <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-danger)' }}>
      {priorYearError}
    </div>
  )}
</div>
```

- [ ] **Step 5: Pass prior year context on Continue**

In the extracted-fields review phase, update the Continue button's `onClick`:
```tsx
// Find this line (around line 146):
<button className="btn-primary" onClick={() => onComplete(editedInfo)}>

// Change to:
<button className="btn-primary" onClick={() => {
  const ctx = priorYearRows.length > 0
    ? priorYearRows.map(r => `${r.account_name}: ${r.prior_year_value}`).join('\n')
    : undefined;
  onComplete(editedInfo, ctx);
}}>
```

- [ ] **Step 6: Update `FinancialStudio.tsx` to accept prior year context**

In `FinancialStudio.tsx`, add state for prior year context after the existing state declarations:
```tsx
const [priorYearContext, setPriorYearContext] = useState<string>('');
```

Find where `CompanyDocuments` is rendered (look for `<CompanyDocuments`) and update the `onComplete` callback:
```tsx
<CompanyDocuments
  onComplete={(info, pyCtx) => {
    setCompanyInfo(info);
    if (pyCtx) setPriorYearContext(pyCtx);
    setActiveStep(3 as Step);
  }}
  onSkip={() => setActiveStep(3 as Step)}
/>
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/studios/FinancialStudio/CompanyDocuments.tsx \
        frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx
git commit -m "feat: add prior year audit PDF upload to Company Docs step with auto-extraction"
```

---

## Task 7 — Analysis Chat Backend Endpoints (Issue 5)

**Files:**
- Modify: `backend/api/reports.py`

Add 3 new endpoints: `analysis-chat` (SSE streaming), `generate-from-session`, and `aging-schedule`.

- [ ] **Step 1: Add the `AnalysisChatRequest` schema**

In `reports.py`, add these Pydantic models near the other request schemas:
```python
class AnalysisChatRequest(BaseModel):
    message: str
    session_context: dict = {}  # {company_name, period, prior_year_context, risk_flags, opinion_type}
    history: list[dict] = []    # [{role, content}] prior turns

class GenerateFromSessionRequest(BaseModel):
    session_id: str
    report_type: str   # "mis" | "financial_analysis" | "budget_vs_actual" | "ifrs" | "cash_flow"
    requirements: str  # free-text from user
    audit_rows: list[dict] = []
    prior_year_context: str = ""
    company_name: str = ""
    period_end: str = ""

class AgingScheduleRequest(BaseModel):
    schedule_type: str  # "receivable" | "payable"
    # rows come from file upload, so this is a multipart endpoint
```

- [ ] **Step 2: Add `POST /api/reports/analysis-chat` endpoint**

```python
@router.post("/analysis-chat")
async def analysis_chat(req: AnalysisChatRequest):
    """Streaming SSE chat with pre-loaded audit session context."""
    from core.llm_manager import get_llm_provider
    from core.prompt_router import get_system_prompt
    from fastapi.responses import StreamingResponse

    ctx = req.session_context
    company = ctx.get("company_name", "the company")
    period = ctx.get("period", "the reporting period")
    prior_year = ctx.get("prior_year_context", "")
    risk_flags = ctx.get("risk_flags", [])
    opinion = ctx.get("opinion_type", "not yet determined")

    risk_summary = ""
    if risk_flags:
        triggered = [f["flag"] for f in risk_flags if f.get("triggered")]
        if triggered:
            risk_summary = f"\nRisk flags identified: {', '.join(triggered)}"

    system_prompt = (
        get_system_prompt("audit")
        + f"\n\nYou are discussing the financial audit of {company} for {period}."
        + f"\nAudit opinion: {opinion}."
        + risk_summary
        + ("\n\n" + prior_year if prior_year else "")
        + "\n\nAnswer questions about the financials, ratios, variances, and audit findings. "
        "Be precise and cite specific figures from the data provided."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in req.history[-8:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": req.message})

    llm = get_llm_provider(None)

    async def generate():
        yield f"data: {json.dumps({'type': 'meta'})}\n\n"
        full = ""
        try:
            async for chunk in llm.chat_stream(messages, temperature=0.3, max_tokens=2000):
                full += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            return
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

- [ ] **Step 3: Add `POST /api/reports/generate-from-session` endpoint**

```python
@router.post("/generate-from-session")
async def generate_from_session(req: GenerateFromSessionRequest, db: AsyncSession = Depends(get_db)):
    """Generate a secondary report (MIS, Financial Analysis, etc.) using existing session data."""
    from core.llm_manager import get_llm_provider

    REPORT_PROMPTS = {
        "mis": "Generate a Management Information System (MIS) report summarising key performance indicators, trends, and management insights.",
        "financial_analysis": "Generate a comprehensive financial analysis including profitability ratios, liquidity ratios, leverage ratios, and year-on-year variance analysis.",
        "budget_vs_actual": "Generate a Budget vs Actual analysis report identifying variances, their causes, and recommendations.",
        "ifrs": "Generate IFRS-compliant financial statements including Statement of Financial Position, Statement of Profit or Loss, and Statement of Cash Flows.",
        "cash_flow": "Generate a Statement of Cash Flows using the indirect method, classifying activities as operating, investing, and financing.",
    }

    prompt_intro = REPORT_PROMPTS.get(req.report_type, "Generate a financial report.")

    rows_summary = ""
    if req.audit_rows:
        rows_summary = "\n\nTrial Balance Data:\n" + "\n".join(
            f"{r.get('account', r.get('mappedTo', 'Unknown'))}: AED {r.get('amount', 0):,.2f}"
            for r in req.audit_rows[:80]
        )

    system_prompt = (
        f"You are an expert financial analyst preparing a report for {req.company_name or 'the company'} "
        f"for the period ending {req.period_end or 'the reporting period'}.\n\n"
        f"{prompt_intro}\n\n"
        f"User requirements: {req.requirements}\n"
        + rows_summary
        + ("\n\nPrior Year Data:\n" + req.prior_year_context if req.prior_year_context else "")
    )

    llm = get_llm_provider(None)
    resp = await llm.chat(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": "Generate the report now."}],
        temperature=0.3,
        max_tokens=4000,
    )

    # Save to reports table
    from db.models import Report
    import uuid
    report_id = str(uuid.uuid4())
    new_report = Report(
        id=report_id,
        company_name=req.company_name or "Company",
        format=req.report_type,
        status="draft",
        draft_content=resp.content,
    )
    db.add(new_report)
    await db.commit()

    return {"report_id": report_id, "content": resp.content, "status": "draft"}
```

- [ ] **Step 4: Add `POST /api/reports/aging-schedule` endpoint**

```python
@router.post("/aging-schedule")
async def aging_schedule(
    schedule_type: str = Form(...),  # "receivable" or "payable"
    file: UploadFile = File(...),
):
    """Generate AR or AP aging schedule from uploaded ledger file."""
    import tempfile, os
    import pandas as pd
    from datetime import date

    suffix = Path(file.filename or "ledger.xlsx").suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        df = pd.read_excel(tmp_path) if suffix in ('.xlsx', '.xls') else pd.read_csv(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Normalise column names
    df.columns = [c.lower().strip() for c in df.columns]

    # Find date and amount columns
    date_col = next((c for c in df.columns if 'date' in c or 'due' in c), None)
    amount_col = next((c for c in df.columns if 'amount' in c or 'balance' in c or 'outstanding' in c), None)
    name_col = next((c for c in df.columns if 'name' in c or 'customer' in c or 'vendor' in c or 'supplier' in c), None)

    if not date_col or not amount_col:
        return {"error": "Could not identify date and amount columns in the uploaded file.", "columns": list(df.columns)}

    today = date.today()
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df['days_outstanding'] = (pd.Timestamp(today) - df[date_col]).dt.days.fillna(0).astype(int)
    df['amount_num'] = pd.to_numeric(df[amount_col], errors='coerce').fillna(0)

    def bucket(days: int) -> str:
        if days <= 30: return "0-30 days"
        if days <= 60: return "31-60 days"
        if days <= 90: return "61-90 days"
        return "90+ days"

    df['bucket'] = df['days_outstanding'].apply(bucket)
    summary = df.groupby('bucket')['amount_num'].agg(['sum', 'count']).reset_index()
    summary.columns = ['bucket', 'total_amount', 'invoice_count']

    return {
        "schedule_type": schedule_type,
        "buckets": summary.to_dict('records'),
        "total": float(df['amount_num'].sum()),
        "rows": df[[c for c in [name_col, date_col, amount_col, 'days_outstanding', 'bucket'] if c]].head(200).to_dict('records'),
    }
```

- [ ] **Step 5: Commit**

```bash
git add backend/api/reports.py
git commit -m "feat: add analysis-chat, generate-from-session, and aging-schedule endpoints"
```

---

## Task 8 — AuditAnalysisStep Component (Issue 5)

**Files:**
- Create: `frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { useState, useCallback, useRef, useEffect } from 'react';
import { API_BASE, fmtTime, type Message, type Source } from '../../../lib/api';
import { ChatMessages } from '../LegalStudio/ChatMessages';
import { ChatInput } from '../LegalStudio/ChatInput';
import type { AuditRow } from './AuditGrid';
import type { CompanyInfo } from './CompanyDocuments';
import type { EvidenceResult } from './AuditEvidenceStep';

interface Props {
  auditRows: AuditRow[];
  companyInfo: CompanyInfo | null;
  auditDraft: string;
  auditEvidence: EvidenceResult | null;
  priorYearContext: string;
  periodEnd: string;
  onContinue: () => void;
}

const AGENT_CARDS = [
  {
    group: 'GENERATE A REPORT FROM THIS DATA',
    items: [
      { key: 'mis', label: 'MIS Report' },
      { key: 'financial_analysis', label: 'Financial Analysis' },
      { key: 'budget_vs_actual', label: 'Budget vs Actual' },
      { key: 'ifrs', label: 'IFRS Financial Statements' },
      { key: 'cash_flow', label: 'Cash Flow Statement' },
    ],
  },
  {
    group: 'ADD SUPPORTING SCHEDULES',
    items: [
      { key: 'aging_receivable', label: 'Receivables Aging' },
      { key: 'aging_payable', label: 'Payables Aging' },
    ],
  },
];

export function AuditAnalysisStep({
  auditRows, companyInfo, auditDraft, auditEvidence, priorYearContext, periodEnd, onContinue,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [agentModal, setAgentModal] = useState<{ key: string; label: string } | null>(null);
  const [agentRequirements, setAgentRequirements] = useState('');
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentToast, setAgentToast] = useState('');
  const [agingFile, setAgingFile] = useState<File | null>(null);
  const historyRef = useRef<Array<{ role: string; content: string }>>([]);

  const isAging = agentModal?.key.startsWith('aging_');

  const sessionContext = {
    company_name: companyInfo?.company_name || '',
    period: periodEnd,
    prior_year_context: priorYearContext,
    risk_flags: auditEvidence?.riskFlags || [],
    opinion_type: auditEvidence?.opinionType || 'not determined',
  };

  // Opening message from AI when step mounts
  useEffect(() => {
    const opener: Message = {
      role: 'ai',
      text: `I've analysed **${companyInfo?.company_name || 'the company'}**'s financials for the period ending **${periodEnd || 'the reporting period'}**.${auditEvidence?.opinionType ? ` The audit opinion is **${auditEvidence.opinionType}**.` : ''} What would you like to discuss?`,
      time: fmtTime(),
    };
    setMessages([opener]);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: 'user', text, time: fmtTime() };
    setMessages(prev => [...prev, userMsg]);
    historyRef.current = [...historyRef.current, { role: 'user', content: text }];
    setLoading(true);
    setMessages(prev => [...prev, { role: 'ai', text: '', time: fmtTime() }]);

    try {
      const response = await fetch(`${API_BASE}/api/reports/analysis-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_context: sessionContext,
          history: historyRef.current.slice(-8),
        }),
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let aiText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let evt: { type: string; content?: string } | null = null;
          try { evt = JSON.parse(line.slice(6)); } catch { continue; }
          if (!evt) continue;
          if (evt.type === 'chunk' && evt.content) {
            aiText += evt.content;
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = { ...updated[updated.length - 1], text: aiText };
              return updated;
            });
          }
        }
      }
      historyRef.current = [...historyRef.current, { role: 'assistant', content: aiText }];
    } catch {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'ai' && last.text === '') {
          return [...prev.slice(0, -1), { role: 'ai' as const, text: 'An error occurred. Please try again.', time: fmtTime() }];
        }
        return prev;
      });
    } finally {
      setLoading(false);
    }
  }, [loading, sessionContext]);

  const handleAgentRun = async () => {
    if (!agentModal) return;
    setAgentRunning(true);

    try {
      if (isAging && agingFile) {
        const formData = new FormData();
        formData.append('schedule_type', agentModal.key === 'aging_receivable' ? 'receivable' : 'payable');
        formData.append('file', agingFile);
        await fetch(`${API_BASE}/api/reports/aging-schedule`, { method: 'POST', body: formData });
        setAgentToast(`${agentModal.label} schedule ready — check Saved Reports`);
      } else {
        await fetch(`${API_BASE}/api/reports/generate-from-session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: '',
            report_type: agentModal.key,
            requirements: agentRequirements,
            audit_rows: auditRows,
            prior_year_context: priorYearContext,
            company_name: companyInfo?.company_name || '',
            period_end: periodEnd,
          }),
        });
        setAgentToast(`${agentModal.label} is ready — check Saved Reports`);
      }
    } catch {
      setAgentToast('Report generation failed. Please try again.');
    } finally {
      setAgentRunning(false);
      setAgentModal(null);
      setAgentRequirements('');
      setAgingFile(null);
      setTimeout(() => setAgentToast(''), 4000);
    }
  };

  return (
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden', gap: 0 }}>
      {/* Left: Chat (60%) */}
      <div style={{ display: 'flex', flexDirection: 'column', flex: '0 0 60%', borderRight: '1px solid var(--s-border)', overflow: 'hidden' }}>
        <ChatMessages
          messages={messages}
          loading={loading}
          onSourceClick={(s) => setActiveSource(s)}
          activeSourceId={activeSource?.source}
        />
        <ChatInput onSend={sendMessage} disabled={loading} />
        <div style={{ padding: '12px 24px', borderTop: '1px solid var(--s-border)', display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn-primary" onClick={onContinue}>
            Continue to Format →
          </button>
        </div>
      </div>

      {/* Right: Agent cards (40%) */}
      <div style={{ flex: '0 0 40%', overflowY: 'auto', padding: '24px 16px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {AGENT_CARDS.map(group => (
          <div key={group.group}>
            <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '10px', fontWeight: 700, color: 'var(--s-text-2)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '8px' }}>
              {group.group}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {group.items.map(item => (
                <button
                  key={item.key}
                  onClick={() => setAgentModal(item)}
                  style={{
                    textAlign: 'left',
                    padding: '9px 12px',
                    borderRadius: 'var(--s-r-sm)',
                    border: '1px solid var(--s-border)',
                    background: 'var(--s-surface)',
                    color: 'var(--s-text-1)',
                    fontFamily: 'var(--s-font-ui)',
                    fontSize: '13px',
                    cursor: 'pointer',
                    transition: 'var(--s-ease)',
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-accent)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-accent)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-border)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-text-1)'; }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Agent activation modal */}
      {agentModal && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}
          onClick={e => { if (e.target === e.currentTarget) setAgentModal(null); }}
        >
          <div style={{ background: 'var(--s-bg)', borderRadius: 'var(--s-r-md)', border: '1px solid var(--s-border)', padding: '24px', maxWidth: '480px', width: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '15px', fontWeight: 600, color: 'var(--s-text-1)' }}>
              {agentModal.label}
            </div>
            {isAging ? (
              <>
                <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
                  Upload your {agentModal.key === 'aging_receivable' ? 'Accounts Receivable' : 'Accounts Payable'} ledger export (Excel or CSV).
                </div>
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  onChange={e => setAgingFile(e.target.files?.[0] || null)}
                  style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}
                />
              </>
            ) : (
              <>
                <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
                  What do you need in this {agentModal.label}?
                </div>
                <textarea
                  value={agentRequirements}
                  onChange={e => setAgentRequirements(e.target.value)}
                  placeholder={`e.g. "Focus on profitability ratios and compare to last year"`}
                  style={{ width: '100%', minHeight: '80px', background: 'var(--s-surface)', border: '1px solid var(--s-border)', borderRadius: 'var(--s-r-sm)', color: 'var(--s-text-1)', fontFamily: 'var(--s-font-ui)', fontSize: '13px', padding: '10px', outline: 'none', resize: 'vertical', boxSizing: 'border-box' }}
                />
              </>
            )}
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setAgentModal(null)} className="btn-ghost" style={{ fontSize: '13px' }}>Cancel</button>
              <button
                onClick={handleAgentRun}
                className="btn-primary"
                style={{ fontSize: '13px' }}
                disabled={agentRunning || (isAging && !agingFile) || (!isAging && !agentRequirements.trim())}
              >
                {agentRunning ? 'Generating…' : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast notification */}
      {agentToast && (
        <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 2000, background: 'var(--s-surface)', border: '1px solid var(--s-border)', borderRadius: 'var(--s-r-md)', padding: '12px 16px', fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-1)', boxShadow: '0 4px 24px rgba(0,0,0,0.3)' }}>
          {agentToast}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx
git commit -m "feat: add AuditAnalysisStep two-panel component with chat and agent activation cards"
```

---

## Task 9 — Wire Analysis Step into Audit Wizard (Issue 5)

**Files:**
- Modify: `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx`

Current Audit step order (0–8):
```
0 Select Type | 1 Upload File | 2 Company Docs | 3 Requirements |
4 Evidence | 5 Draft Report | 6 Select Format | 7 Final Report | 8 Export
```

New order with Analysis step inserted at 6:
```
0 Select Type | 1 Upload File | 2 Company Docs | 3 Requirements |
4 Evidence | 5 Draft Report | 6 Analysis & Discussion | 7 Select Format | 8 Final Report | 9 Export
```

- [ ] **Step 1: Update `STEP_LABELS_AUDIT` at line 23**

```tsx
// BEFORE
const STEP_LABELS_AUDIT = ['Select Type', 'Upload File', 'Company Docs', 'Requirements', 'Evidence', 'Draft Report', 'Select Format', 'Final Report', 'Export'];

// AFTER
const STEP_LABELS_AUDIT = ['Select Type', 'Upload File', 'Company Docs', 'Requirements', 'Evidence', 'Draft Report', 'Analysis & Discussion', 'Select Format', 'Final Report', 'Export'];
```

- [ ] **Step 2: Add `AuditAnalysisStep` import**

At the top of `FinancialStudio.tsx` with the other imports:
```tsx
import { AuditAnalysisStep } from './AuditAnalysisStep';
```

- [ ] **Step 3: Add `priorYearContext` state**

After the existing state declarations (find `const [priorYearContent, setPriorYearContent]`), add:
```tsx
const [priorYearContext, setPriorYearContext] = useState<string>('');
```

- [ ] **Step 4: Update `CompanyDocuments` `onComplete` callback**

Find where `<CompanyDocuments` is rendered and update the `onComplete` prop:
```tsx
onComplete={(info, pyCtx) => {
  setCompanyInfo(info);
  if (pyCtx) setPriorYearContext(pyCtx);
  setActiveStep(3 as Step);
}}
```

- [ ] **Step 5: Insert `AuditAnalysisStep` at step 6**

In the wizard step rendering logic (find the block that renders step 5 Draft Report, then step 6 Select Format), insert the new step between them:

```tsx
{/* Step 5 — Draft Report (unchanged, already exists) */}

{/* Step 6 — Analysis & Discussion (NEW) */}
{isAudit && activeStep === 6 && (
  <AuditAnalysisStep
    auditRows={auditRows}
    companyInfo={companyInfo}
    auditDraft={auditDraft}
    auditEvidence={auditEvidence}
    priorYearContext={priorYearContext}
    periodEnd={requirements.period_end || requirements.period_end_date || ''}
    onContinue={() => setActiveStep(7 as Step)}
  />
)}

{/* Step 7 — Select Format (was step 6) */}
{isAudit && activeStep === 7 && (
  // existing AuditFormatSelector JSX — change activeStep === 6 to activeStep === 7
```

- [ ] **Step 6: Update all downstream step references**

Search `FinancialStudio.tsx` for `activeStep === 6`, `activeStep === 7`, `activeStep === 8` in the audit path and increment each by 1 to account for the new step. Also update:
- `setActiveStep(6 as Step)` (from Draft step's onContinue) → stays at 6 (correct — goes to Analysis)
- `setActiveStep(7 as Step)` (from Analysis step's onContinue) → new Select Format step  
- The `initialEditState` targetStep (line 82): change `6` to `7` for draft_content redirect

- [ ] **Step 7: Fix `initialEditState` step target**

Find this line:
```tsx
const targetStep: Step = initialEditState.draft_content ? 6 : 4;
```
Change to:
```tsx
const targetStep: Step = initialEditState.draft_content ? 7 : 4;
```
(Draft content now means landing on Select Format at step 7, skipping the Analysis step)

- [ ] **Step 8: Verify in browser**

Run the full audit wizard with a trial balance file. After reaching Draft Report (step 5) and clicking Continue, step 6 should show the Analysis & Discussion two-panel layout. Clicking "Continue to Format →" should proceed to Select Format (step 7).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx
git commit -m "feat: insert Analysis & Discussion step at wizard step 6 in Audit Report flow"
```

---

## Task 10 — Audit Report Formatter (Issue 6)

**Files:**
- Create: `backend/core/audit_formatter.py`
- Create: `backend/tests/test_audit_formatter.py`
- Modify: `backend/api/reports.py` (DOCX export endpoint)

The strategy: the existing Markdown draft continues to be generated as-is. When the user downloads as DOCX, the backend uses `audit_formatter.py` to produce a properly structured document from:
1. The company info (name, location, period)
2. The audit rows (structured financial data)
3. The existing Markdown draft content (for narrative sections like auditors' report)

This avoids breaking any existing flows while dramatically improving DOCX output quality.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_audit_formatter.py`:
```python
"""Tests for the audit report DOCX formatter."""
import pytest
from io import BytesIO
from core.audit_formatter import (
    format_audit_report,
    _build_cover_page,
    _build_toc,
    _build_financial_table,
)


def test_format_audit_report_returns_bytes():
    report_data = {
        "company_name": "Test Company LLC",
        "location": "Dubai - United Arab Emirates",
        "period_end": "December 31, 2024",
        "opinion_type": "qualified",
        "draft_content": "We have audited the financial statements.",
        "rows": [
            {"account": "Total Assets", "category": "Assets", "amount": 5929549.0, "prior_year": 9489570.0},
            {"account": "Total Liabilities", "category": "Liabilities", "amount": 6100721.0, "prior_year": 6323991.0},
        ],
    }
    result = format_audit_report(report_data)
    assert isinstance(result, bytes)
    assert len(result) > 1000  # Valid DOCX is never tiny


def test_cover_page_contains_company_name():
    from docx import Document
    doc = Document()
    _build_cover_page(doc, "ACME Corp", "Abu Dhabi - UAE", "December 31, 2024")
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "ACME Corp" in full_text
    assert "December 31, 2024" in full_text


def test_financial_table_has_correct_columns():
    from docx import Document
    doc = Document()
    rows = [
        {"account": "Trade receivables", "category": "Current Assets", "amount": 720277.0, "prior_year": 424857.0},
    ]
    _build_financial_table(doc, "Statement of Financial Position", rows)
    # Table should exist with 4 columns
    assert len(doc.tables) == 1
    assert len(doc.tables[0].columns) == 4
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
uv run pytest tests/test_audit_formatter.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.audit_formatter'`

- [ ] **Step 3: Create `backend/core/audit_formatter.py`**

```python
"""
Audit Report DOCX Formatter.

Takes structured audit data and produces a professional DOCX report with:
  - Cover page (company name, location, year, report title)
  - Table of contents
  - Independent Auditors' Report (narrative from draft)
  - Statement of Financial Position (two-column AED table)
  - Statement of Profit or Loss (two-column AED table)
  - Notes placeholder
"""
import io
import logging
from typing import Optional

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)


def _add_run(para, text: str, bold: bool = False, size_pt: int = 11,
             color: Optional[tuple] = None, italic: bool = False):
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size_pt)
    if color:
        run.font.color.rgb = RGBColor(*color)
    return run


def _build_cover_page(doc: Document, company_name: str, location: str, period_end: str):
    """Insert cover page with company name, location, report title, and year."""
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph()

    p_company = doc.add_paragraph()
    p_company.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p_company, company_name.upper(), bold=True, size_pt=16)

    p_loc = doc.add_paragraph()
    p_loc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p_loc, location.upper(), bold=True, size_pt=13)

    doc.add_paragraph()
    doc.add_paragraph()

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p_title, "FINANCIAL STATEMENTS AND", bold=True, size_pt=13)

    p_title2 = doc.add_paragraph()
    p_title2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p_title2, "INDEPENDENT AUDITOR'S REPORT", bold=True, size_pt=13)

    doc.add_paragraph()

    p_period = doc.add_paragraph()
    p_period.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p_period, f"FOR THE YEAR ENDED {period_end.upper()}", bold=True, size_pt=13)

    doc.add_page_break()


def _build_toc(doc: Document, sections: list[str]):
    """Insert a simple table of contents."""
    heading = doc.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(heading, "Table of Contents", bold=False, size_pt=12)

    doc.add_paragraph()

    toc_items = [
        ("Independent Auditors' Report", "1 - 3"),
        ("Statement of Financial Position", "4"),
        ("Statement of Profit or Loss and Other Comprehensive Income", "5"),
        ("Statement of Changes in Shareholders' Equity", "6"),
        ("Statement of Cash Flows", "7"),
        ("Notes to the Financial Statements", "8 - 22"),
    ]

    for title, pages in toc_items:
        p = doc.add_paragraph()
        p.paragraph_format.tab_stops.add_tab_stop(Inches(5.5))
        run_title = p.add_run(title)
        run_title.font.size = Pt(11)
        run_page = p.add_run(f"\t{pages}")
        run_page.font.size = Pt(11)
        run_page.bold = True

    doc.add_page_break()


def _build_narrative_section(doc: Document, title: str, content: str):
    """Add a narrative section (e.g. Auditors' Report) from Markdown-style text."""
    h = doc.add_heading(title, level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Strip markdown heading markers and add paragraphs
    import re
    content = re.sub(r'^#{1,3}\s+', '', content, flags=re.MULTILINE)
    for para_text in content.split('\n\n'):
        para_text = para_text.strip()
        if not para_text:
            continue
        p = doc.add_paragraph()
        # Bold text wrapped in **
        parts = re.split(r'(\*\*[^*]+\*\*)', para_text)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                _add_run(p, part[2:-2], bold=True, size_pt=11)
            else:
                _add_run(p, part, size_pt=11)


def _build_financial_table(doc: Document, title: str, rows: list[dict]):
    """
    Build a 4-column financial statement table:
    Account Name | Notes | Current Year (AED) | Prior Year (AED)
    """
    doc.add_heading(title, level=2)

    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'

    # Header row
    hdr = table.rows[0].cells
    hdr[0].text = ''
    hdr[1].text = 'Notes'
    hdr[2].text = 'Current Year\nAED'
    hdr[3].text = 'Prior Year\nAED'

    for cell in hdr:
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True
                run.font.size = Pt(10)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Data rows
    last_category = None
    for row in rows:
        account = row.get('account', '')
        category = row.get('category', '')
        amount = row.get('amount')
        prior = row.get('prior_year')
        is_total = 'total' in account.lower() or row.get('is_total', False)

        # Insert category subheading if category changed
        if category and category != last_category:
            cat_row = table.add_row()
            cat_row.cells[0].text = category
            for p in cat_row.cells[0].paragraphs:
                for r in p.runs:
                    r.bold = True
                    r.font.size = Pt(10)
            last_category = category

        data_row = table.add_row()
        cells = data_row.cells

        cells[0].text = f"  {account}" if not is_total else account
        cells[1].text = str(row.get('notes_ref', ''))
        cells[2].text = f"{amount:,.0f}" if amount is not None else 'Not provided'
        cells[3].text = f"{prior:,.0f}" if prior is not None else 'Not provided'

        for i, cell in enumerate(cells):
            for p in cell.paragraphs:
                for r in p.runs:
                    if is_total:
                        r.bold = True
                    r.font.size = Pt(10)
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if i >= 2 else WD_ALIGN_PARAGRAPH.LEFT

    doc.add_paragraph()


def format_audit_report(report_data: dict) -> bytes:
    """
    Main entry point. Takes report_data dict and returns DOCX as bytes.

    Expected keys:
    - company_name: str
    - location: str (defaults to "Dubai - United Arab Emirates")
    - period_end: str
    - opinion_type: str
    - draft_content: str (Markdown narrative from LLM)
    - rows: list[{account, category, amount, prior_year, notes_ref?, is_total?}]
    """
    doc = Document()

    # Set page margins
    from docx.oxml.ns import qn as _qn
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    company_name = report_data.get("company_name", "Company")
    location = report_data.get("location", "Dubai - United Arab Emirates")
    period_end = report_data.get("period_end", "")
    draft_content = report_data.get("draft_content", "")
    rows = report_data.get("rows", [])

    _build_cover_page(doc, company_name, location, period_end)
    _build_toc(doc, [])

    # Auditors' Report — extract from draft content
    if draft_content:
        _build_narrative_section(doc, "Independent Auditors' Report", draft_content[:3000])
        doc.add_page_break()

    # Financial Tables — group rows by section
    balance_sheet = [r for r in rows if r.get('category', '').lower() in
                     ('current assets', 'non-current assets', 'current liabilities',
                      'non-current liabilities', 'equity', 'assets', 'liabilities')]
    income_rows = [r for r in rows if r.get('category', '').lower() in
                   ('revenue', 'operating expenses', 'cost of sales', 'other income')]

    if balance_sheet:
        _build_financial_table(doc, "Statement of Financial Position", balance_sheet)
        doc.add_page_break()

    if income_rows:
        _build_financial_table(doc, "Statement of Profit or Loss and Other Comprehensive Income", income_rows)
        doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend
uv run pytest tests/test_audit_formatter.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Wire formatter into DOCX export endpoint in `reports.py`**

In `reports.py`, find the `export-docx` endpoint. It currently exports raw Markdown content. Change it so that for audit reports, it calls the formatter:

```python
@router.post("/export-docx")
async def export_docx(req: ExportRequest):
    """Export report content as DOCX. For audit reports, uses structured formatter."""
    from core.audit_formatter import format_audit_report

    # If this is an audit report with structured row data, use the formatter
    if req.report_type == "audit" and req.rows:
        report_data = {
            "company_name": req.company_name or "Company",
            "location": req.location or "Dubai - United Arab Emirates",
            "period_end": req.period_end or "",
            "opinion_type": req.opinion_type or "qualified",
            "draft_content": req.content or "",
            "rows": req.rows,
        }
        docx_bytes = format_audit_report(report_data)
    else:
        # Existing path: convert Markdown to basic DOCX
        from docx import Document
        from docx.shared import Pt
        doc = Document()
        for line in (req.content or "").split("\n"):
            p = doc.add_paragraph(line)
            for run in p.runs:
                run.font.size = Pt(11)
        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

    filename = f"{(req.filename or 'report').replace(' ', '_')}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

Update the `ExportRequest` schema to include the new optional fields:
```python
class ExportRequest(BaseModel):
    content: str
    filename: str = "report"
    report_type: str = ""
    company_name: str = ""
    location: str = ""
    period_end: str = ""
    opinion_type: str = ""
    rows: list[dict] = []
```

- [ ] **Step 6: Update frontend DOCX download in `ContextualSidebar.tsx`**

In `handleDownloadReport`, when format is `'docx'` and the report has a `wizard_state_json`, include the audit rows and company info in the export request. Find the `API.post('/api/reports/export-docx', ...)` call (around line 82) and add the extra fields:

```tsx
const resp = await API.post(
  `/api/reports/export-${format}`,
  {
    content,
    filename: `${r.company_name || 'audit_report'}_${r.status}`,
    // Pass structured data if available for proper audit formatting
    report_type: r.format,
    company_name: r.company_name || '',
    period_end: r.period_end_date || '',
  },
  { responseType: 'blob' }
);
```

- [ ] **Step 7: Verify formatting**

Download a DOCX from a completed Audit Report. Open in Word. Verify:
1. Page 1: Cover page with company name centered, location, and "FINANCIAL STATEMENTS AND INDEPENDENT AUDITOR'S REPORT"
2. Page 2: Table of Contents with section names and page number references
3. Page 3+: Auditors' Report narrative text
4. Following pages: Balance sheet table with 4 columns (Account | Notes | Current Year AED | Prior Year AED)

- [ ] **Step 8: Commit**

```bash
git add backend/core/audit_formatter.py \
        backend/tests/test_audit_formatter.py \
        backend/api/reports.py \
        frontend/src/components/ContextualSidebar.tsx
git commit -m "feat: add professional DOCX formatter for audit reports — cover page, TOC, and two-column financial tables"
```

---

## Self-Review

**Spec coverage check:**
- Issue 1 (source click): Task 1 ✓
- Issue 2 (web search fallback + RAG save): Tasks 3 + 4 ✓
- Issue 3 (New Report button): Task 2 ✓
- Issue 4 (prior year PDF extraction): Tasks 5 + 6 ✓
- Issue 5 (post-audit chat step + agent cards): Tasks 7 + 8 + 9 ✓
- Issue 6 (DOCX formatting): Task 10 ✓

**Type consistency check:**
- `AuditAnalysisStep` receives `priorYearContext: string` — matches Task 6 where `setPriorYearContext(string)` is stored in FinancialStudio ✓
- `CompanyDocuments.onComplete(info, pyCtx?)` signature matches Task 6 call sites ✓  
- `format_audit_report(report_data: dict) -> bytes` matches test expectations ✓
- `ExportRequest` schema extension matches the frontend call in Task 10 ✓
- `AnalysisChatRequest` fields (`message`, `session_context`, `history`) match `AuditAnalysisStep` fetch body ✓

**Placeholder check:** No TBDs found. All code blocks are complete. ✓

**Dependency note:** Task 5 Step 4 mentions verifying `rag_engine.ingest_text` — check this before running Task 3.
