# Chatbot Redesign — Sub-project C (Analyst Mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full Analyst mode — LLM scoped to attached documents, audit auto-detection without dialogs, draggable persistent audit overlay, extended report config system, artifact panel (MIS + charts), smart confirm card replacing the questionnaire flow, streaming report generation into the artifact panel, and follow-up chat refinement of generated reports.

**Architecture:** Six tasks in sequential order. Backend adds `ANALYST_SYSTEM_PREFIX` to the analyst prompt, a new `POST /api/reports/detect` RAG-based endpoint, and a new `POST /api/reports/generate-stream` SSE endpoint. Frontend adds `AuditOverlayContext` (app-root level), `AuditOverlay.tsx` (fixed/draggable), extends `reportConfigs.ts` with sections/formats/detectFields, adds `ArtifactPanel.tsx` with MIS charts (Recharts), adds `ConfirmReportCard.tsx`, and rewires `LegalStudio.tsx` to use the new confirm-card + artifact panel flow instead of the questionnaire.

**Tech Stack:** Backend — FastAPI, SQLAlchemy async, SQLite, pytest + pytest-asyncio + httpx. Frontend — React 18 + TypeScript + Vite, Recharts, Vitest + React Testing Library.

**Spec reference:** `docs/superpowers/specs/2026-04-21-chatbot-redesign-design.md` — Sub-project C (C1–C6).

**Prerequisites:** Sub-project A and B complete. Mode system (`fast`/`deep_research`/`analyst`) is persisted per conversation. `ChatWithResearchLayout` exists. `ThreePaneLayout` already renders for analyst mode.

---

## File Structure

### New files

```
backend/
  tests/api/test_reports_detect.py
  tests/api/test_reports_generate_stream.py

frontend/src/
  context/
    AuditOverlayContext.tsx
  components/studios/LegalStudio/
    AuditOverlay.tsx
    ArtifactPanel.tsx
    MisKpiCards.tsx
    MisChart.tsx
    ConfirmReportCard.tsx
    __tests__/
      AuditOverlay.test.tsx
      ArtifactPanel.test.tsx
      ConfirmReportCard.test.tsx
      MisKpiCards.test.tsx
```

### Modified files

```
backend/
  core/prompt_router.py              # add ANALYST_SYSTEM_PREFIX constant
  api/chat.py                        # prepend ANALYST_SYSTEM_PREFIX when mode==analyst
  api/reports.py                     # add POST /detect + POST /generate-stream endpoints

frontend/src/
  components/studios/LegalStudio/
    reportConfigs.ts                  # add sections, supportedFormats, detectFields, chartTypes
    LegalStudio.tsx                   # replace questionnaire flow with ConfirmReportCard + ArtifactPanel
    StudioPanel.tsx                   # trigger onReportRequest (already exists, no questionnaire)
  App.tsx                             # wrap with AuditOverlayProvider
```

Each file has one responsibility. No file exceeds 200 lines. The `ConfirmReportCard` is a pure presentational message bubble. `LegalStudio` owns detection state and streaming.

---

## Task 1: Backend — Analyst system prompt prefix (C1)

**Files:**
- Modify: `backend/core/prompt_router.py` — add `ANALYST_SYSTEM_PREFIX`
- Modify: `backend/api/chat.py` — prepend prefix when `req.mode == "analyst"`
- Create: `backend/tests/api/test_analyst_prompt.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_analyst_prompt.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app


def _make_stream_chunks(text: str):
    async def _gen(*args, **kwargs):
        yield text
    return _gen


def _mock_rag_empty():
    async def _search(*args, **kwargs):
        return []
    return _search


@pytest.mark.asyncio
async def test_analyst_mode_prepends_document_scope_prefix(monkeypatch):
    """When mode=analyst, system prompt must contain the ANALYST_SYSTEM_PREFIX."""
    from core.prompt_router import ANALYST_SYSTEM_PREFIX
    assert ANALYST_SYSTEM_PREFIX, "ANALYST_SYSTEM_PREFIX must be a non-empty string"
    assert "MUST base your answers primarily on the documents" in ANALYST_SYSTEM_PREFIX


def test_analyst_prefix_constant_imported():
    from core.prompt_router import ANALYST_SYSTEM_PREFIX, DOMAIN_PROMPTS
    # Analyst system prompt must include the doc-scoping prefix
    assert ANALYST_SYSTEM_PREFIX in DOMAIN_PROMPTS.get("analyst", "") or ANALYST_SYSTEM_PREFIX
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_analyst_prompt.py -v`
Expected: FAIL — `ANALYST_SYSTEM_PREFIX` not yet exported.

- [ ] **Step 3: Add `ANALYST_SYSTEM_PREFIX` to `prompt_router.py`**

In `backend/core/prompt_router.py`, add this constant near the top (after the existing suffix constants):

```python
ANALYST_SYSTEM_PREFIX = (
    "You are a financial and legal analyst. You MUST base your answers primarily on the documents "
    "provided below. If the answer is clearly contained in the documents, cite the document and page. "
    "If the answer is not in the documents, you may draw on your professional knowledge but must "
    "explicitly say: \"This is based on general knowledge, not your attached documents.\" "
    "Do NOT make up figures, dates, or entities.\n\n"
)
```

Then update the analyst entry in `DOMAIN_PROMPTS` so the prefix is prepended:

```python
# In the try/except block loading ca_auditor_system_prompt.md:
DOMAIN_PROMPTS["analyst"] = ANALYST_SYSTEM_PREFIX + _ca_prompt_text + FORMATTING_SUFFIX + ...
# And in the except fallback:
DOMAIN_PROMPTS["analyst"] = ANALYST_SYSTEM_PREFIX + "You are a comprehensive AI Auditor ..."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_analyst_prompt.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Verify `chat.py` already uses `DOMAIN_PROMPTS.get("analyst")`**

Check line ~307 of `api/chat.py`:
```python
if req.mode == "analyst":
    system_prompt = DOMAIN_PROMPTS.get("analyst", DOMAIN_PROMPTS["general"]) + memory_block
```
Since `DOMAIN_PROMPTS["analyst"]` now starts with `ANALYST_SYSTEM_PREFIX`, this is correct.
If `req.mode` is not being checked there, add the check. No additional code needed if it already exists.

- [ ] **Step 6: Commit**

```bash
git add backend/core/prompt_router.py backend/tests/api/test_analyst_prompt.py
git commit -m "feat(analyst): prepend ANALYST_SYSTEM_PREFIX to analyst mode system prompt"
```

---

## Task 2: Backend — Detect endpoint (C2)

**Files:**
- Modify: `backend/api/reports.py` — add `POST /api/reports/detect`
- Create: `backend/tests/api/test_reports_detect.py`

The endpoint runs two targeted RAG searches against `selected_doc_ids` to extract `entity_name` and `period_end`, then returns them with a `confidence` rating (`high | low | none`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_reports_detect.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_detect_returns_schema():
    """POST /api/reports/detect must return entity_name, period_end, confidence."""
    with patch("api.reports.rag_engine") as mock_rag, \
         patch("api.reports.get_llm_provider") as mock_llm_factory:

        mock_rag.search = AsyncMock(return_value=[
            {"text": "ABC Trading LLC annual report for year ended 31 December 2024",
             "metadata": {"source": "financial_report.pdf", "page": 1}, "score": 0.92}
        ])

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(
            content='{"entity_name": "ABC Trading LLC", "period_end": "31 Dec 2024"}'
        ))
        mock_llm_factory.return_value = mock_llm

        r = client.post(
            "/api/reports/detect",
            json={"report_type": "audit", "selected_doc_ids": ["doc-1"]}
        )

    assert r.status_code == 200
    data = r.json()
    assert "entity_name" in data
    assert "period_end" in data
    assert data["confidence"] in ("high", "low", "none")


def test_detect_returns_none_confidence_when_no_docs():
    """When no docs are selected, confidence must be 'none'."""
    with patch("api.reports.rag_engine") as mock_rag, \
         patch("api.reports.get_llm_provider") as mock_llm_factory:

        mock_rag.search = AsyncMock(return_value=[])
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(content='{}'))
        mock_llm_factory.return_value = mock_llm

        r = client.post(
            "/api/reports/detect",
            json={"report_type": "audit", "selected_doc_ids": []}
        )

    assert r.status_code == 200
    assert r.json()["confidence"] == "none"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_reports_detect.py -v`
Expected: FAIL — 404 (endpoint does not exist yet).

- [ ] **Step 3: Implement the `POST /api/reports/detect` endpoint**

Add to `backend/api/reports.py` (after existing imports, add `rag_engine` import if not present):

```python
from core.rag_engine import rag_engine
```

Then add the schema and handler:

```python
# ── C2: Auto-detect entity name and period end from documents ─────────────────

class DetectRequest(BaseModel):
    report_type: str
    selected_doc_ids: list[str] = []


class DetectResponse(BaseModel):
    entity_name: str = ""
    period_end: str = ""
    confidence: str = "none"  # "high" | "low" | "none"


@router.post("/detect", response_model=DetectResponse)
async def detect_report_metadata(req: DetectRequest):
    """
    Run targeted RAG searches to auto-detect entity_name and period_end
    from the selected documents.

    Confidence:
      high  → score ≥ 0.7 and both fields extracted
      low   → score 0.3–0.69 or only one field extracted
      none  → score < 0.3 or no results
    """
    if not req.selected_doc_ids:
        return DetectResponse(confidence="none")

    # Build a doc filter for RAG (filter by document ids)
    doc_filter = {"document_id": {"$in": req.selected_doc_ids}} if req.selected_doc_ids else None

    entity_results = []
    period_results = []
    try:
        entity_results = await rag_engine.search(
            "company name entity name organization",
            top_k=3,
            filter=doc_filter,
        )
        period_results = await rag_engine.search(
            "financial year period end date reporting date",
            top_k=3,
            filter=doc_filter,
        )
    except Exception as e:
        logger.warning(f"RAG search failed in detect: {e}")
        return DetectResponse(confidence="none")

    all_results = entity_results + period_results
    if not all_results:
        return DetectResponse(confidence="none")

    combined_text = "\n".join(r.get("text", "")[:500] for r in all_results[:6])
    avg_score = sum(r.get("score", 0) for r in all_results) / len(all_results)

    # Use LLM to extract structured fields from the combined text
    llm = get_llm_provider(None)
    extract_prompt = (
        "Extract the entity (company) name and the financial period end date from the text below. "
        "Return ONLY valid JSON with these exact keys: "
        '{"entity_name": "...", "period_end": "..."} '
        "Use empty string if a field cannot be found.\n\n"
        f"Text:\n{combined_text}"
    )
    try:
        resp = await llm.chat(
            [{"role": "user", "content": extract_prompt}],
            temperature=0.0,
            max_tokens=150,
        )
        raw = resp.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        extracted = json.loads(match.group(0)) if match else {}
    except Exception as e:
        logger.warning(f"LLM extraction failed in detect: {e}")
        extracted = {}

    entity_name = extracted.get("entity_name", "").strip()
    period_end = extracted.get("period_end", "").strip()

    both_found = bool(entity_name and period_end)
    one_found = bool(entity_name or period_end)

    if both_found and avg_score >= 0.7:
        confidence = "high"
    elif (both_found and avg_score >= 0.3) or (one_found and avg_score >= 0.5):
        confidence = "low"
    else:
        confidence = "none"

    return DetectResponse(
        entity_name=entity_name,
        period_end=period_end,
        confidence=confidence,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_reports_detect.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/api/reports.py backend/tests/api/test_reports_detect.py
git commit -m "feat(api): POST /api/reports/detect — RAG-based entity and period auto-detection"
```

---

## Task 3: Backend — Streaming report generation endpoint (C6 backend)

**Files:**
- Modify: `backend/api/reports.py` — add `POST /api/reports/generate-stream`
- Create: `backend/tests/api/test_reports_generate_stream.py`

The endpoint accepts `report_type`, `selected_doc_ids`, `entity_name`, `period_end`, `auditor_format`, and optionally `refinement_instruction`. It streams the LLM report over SSE so the frontend artifact panel can render it live.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_reports_generate_stream.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


async def _fake_rag_search(*args, **kwargs):
    return [{"text": "Revenue: AED 1,000,000", "metadata": {"source": "tb.pdf", "page": 1}, "score": 0.9}]


async def _fake_stream(messages, **kwargs):
    for chunk in ["## MIS Report\n", "Revenue: AED 1,000,000\n", "Net Profit: AED 200,000\n"]:
        yield chunk


def test_generate_stream_returns_sse():
    """POST /api/reports/generate-stream must return an SSE text/event-stream."""
    with patch("api.reports.rag_engine") as mock_rag, \
         patch("api.reports.get_llm_provider") as mock_llm_factory:

        mock_rag.search = AsyncMock(side_effect=_fake_rag_search)

        mock_llm = MagicMock()
        mock_llm.chat_stream = _fake_stream
        mock_llm_factory.return_value = mock_llm

        with client.stream(
            "POST",
            "/api/reports/generate-stream",
            json={
                "report_type": "mis",
                "selected_doc_ids": ["doc-1"],
                "entity_name": "ABC Trading LLC",
                "period_end": "31 Dec 2024",
                "auditor_format": "standard",
            },
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            body = b"".join(r.iter_bytes()).decode()

    frames = [line[len("data: "):] for line in body.splitlines() if line.startswith("data: ")]
    assert len(frames) >= 1
    parsed = [json.loads(f) for f in frames]
    types = [p["type"] for p in parsed]
    assert "chunk" in types
    assert "done" in types
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_reports_generate_stream.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Implement the streaming endpoint**

Add to `backend/api/reports.py`:

```python
# ── C6: Streaming report generation ──────────────────────────────────────────

REPORT_SYSTEM_PROMPTS: dict[str, str] = {
    "mis": (
        "You are a financial analyst generating a Management Information System (MIS) report. "
        "Extract data ONLY from the provided document chunks. Do not invent figures, names, or dates. "
        "Structure: ## KPI Summary (Revenue, Expenses, Net Profit, Gross Margin) | "
        "## Department P&L Table (markdown table) | "
        "## Revenue vs Expenses Chart Data (JSON array: [{period, revenue, expenses}]) | "
        "## Narrative Summary (2-3 paragraphs with source citations). "
        "Use AED. Cite source document and page for every figure."
    ),
    "audit": (
        "You are a senior auditor generating an ISA 700 audit report. "
        "Extract data ONLY from the provided document chunks. "
        "Structure per ISA 700: Opinion | Basis for Opinion | Key Audit Matters | "
        "Management Responsibility | Auditor Responsibilities | Going Concern | Signature Block. "
        "Cite document sources for every material figure."
    ),
    "vat": (
        "You are a UAE VAT compliance specialist generating a VAT-201 return summary. "
        "Extract data ONLY from the provided documents. "
        "Map values to: Box 1 (Standard-rated supplies) | Box 2 (Zero-rated) | Box 3 (Exempt) | "
        "Box 4 (Imports) | Box 5 (Adjustments) | Box 6 (Total supplies) | "
        "Box 7 (VAT due) | Box 8 (Input tax) | Box 9 (Net payable/reclaimable). "
        "Show source document and page for each box value."
    ),
    "corporate_tax": (
        "You are a UAE Corporate Tax specialist generating a CT computation report. "
        "Extract data ONLY from the provided documents. "
        "Structure: Accounting profit | Non-deductible adjustments | Exempt income | "
        "Taxable income | Small Business Relief check (revenue < AED 3M) | "
        "CT payable at 9% (or 0% if SBR applies). Cite UAE Decree-Law No. 47 of 2022."
    ),
    "ifrs": (
        "You are a financial reporting specialist generating IFRS financial statements. "
        "Extract data ONLY from the provided documents. "
        "Include: Statement of Financial Position | P&L and Other Comprehensive Income | "
        "Cash Flow Statement | Notes to Financial Statements (IFRS-referenced). "
        "Cite all figures to source documents."
    ),
    "budget_vs_actual": (
        "You are a financial analyst generating a Budget vs Actual variance report. "
        "Extract data ONLY from the provided documents. "
        "Structure: Budget table | Actual table | Variance % | Commentary on material variances. "
        "Cite all figures to source documents."
    ),
    "compliance": (
        "You are a compliance officer generating a Board/Compliance report. "
        "Extract data ONLY from the provided documents. "
        "Structure: Executive summary | Financial highlights | Risk register | Decisions needed. "
        "Cite regulatory references (UAE law / IFRS)."
    ),
    "custom": (
        "You are a report writer. Generate a report using ONLY the data from the provided documents. "
        "Follow the user's requested structure exactly. Do not invent figures, names, or dates."
    ),
}

_DEFAULT_REPORT_SYSTEM = (
    "You are a financial and legal analyst generating a professional report. "
    "Extract data ONLY from the provided document chunks. Do not invent figures, names, or dates. "
    "Cite source documents and page numbers for every material claim."
)


class GenerateStreamRequest(BaseModel):
    report_type: str
    selected_doc_ids: list[str] = []
    entity_name: str = ""
    period_end: str = ""
    auditor_format: str = "standard"
    refinement_instruction: Optional[str] = None
    current_report_content: Optional[str] = None  # for refinement


@router.post("/generate-stream")
async def generate_report_stream(req: GenerateStreamRequest):
    """Stream report generation over SSE. Streams {type: chunk, content: str} + {type: done}."""

    async def _stream():
        # 1. Retrieve document context via RAG
        doc_filter = {"document_id": {"$in": req.selected_doc_ids}} if req.selected_doc_ids else None
        try:
            rag_results = await rag_engine.search(
                f"{req.entity_name} {req.period_end} {req.report_type}",
                top_k=10,
                filter=doc_filter,
            )
        except Exception as e:
            logger.warning(f"RAG search failed in generate-stream: {e}")
            rag_results = []

        doc_block = "\n".join(
            f"[{r['metadata'].get('source','?')} p.{r['metadata'].get('page','?')}]: {r['text'][:600]}"
            for r in rag_results
        ) or "(No document chunks found. Generate based on general knowledge but state this clearly.)"

        system_prompt = REPORT_SYSTEM_PROMPTS.get(req.report_type, _DEFAULT_REPORT_SYSTEM)

        # 2. Build user message
        if req.refinement_instruction and req.current_report_content:
            user_content = (
                f"The current report is:\n\n{req.current_report_content}\n\n"
                f"Apply this change: {req.refinement_instruction}\n\n"
                f"Return the complete updated report.\n\n"
                f"Available document context:\n{doc_block}"
            )
        else:
            user_content = (
                f"Generate a {req.report_type.upper()} report for:\n"
                f"Entity: {req.entity_name or 'Unknown'}\n"
                f"Period: {req.period_end or 'Unknown'}\n"
                f"Format: {req.auditor_format}\n\n"
                f"Document context:\n{doc_block}"
            )

        messages_payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        llm = get_llm_provider(None)
        try:
            async for chunk in llm.chat_stream(messages_payload, temperature=0.2, max_tokens=None):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_reports_generate_stream.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/reports.py backend/tests/api/test_reports_generate_stream.py
git commit -m "feat(api): POST /api/reports/generate-stream SSE endpoint"
```

---

## Task 4: Frontend — Install Recharts + extend `reportConfigs.ts` (C4)

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/reportConfigs.ts`

`reportConfigs.ts` currently uses a `PrefilledField[]` structure for the old questionnaire flow. This task extends it with `sections`, `supportedFormats`, `detectFields`, and `chartTypes` fields **alongside** the existing `fields` array (backwards-compatible — do not remove `fields`).

- [ ] **Step 1: Install Recharts**

```bash
cd frontend && npm install recharts
```

Verify it appears in `package.json` under `dependencies`.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/components/studios/LegalStudio/__tests__/reportConfigs.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { REPORT_CONFIGS } from '../reportConfigs';

describe('reportConfigs', () => {
  it('all entries have an id, label, icon', () => {
    for (const key of Object.keys(REPORT_CONFIGS)) {
      const c = REPORT_CONFIGS[key];
      expect(c.type, `${key}.type`).toBeTruthy();
      expect(c.label, `${key}.label`).toBeTruthy();
      expect(c.icon, `${key}.icon`).toBeTruthy();
    }
  });

  it('mis config has sections with kpi_cards and chart types', () => {
    const mis = REPORT_CONFIGS['mis'];
    expect(mis.sections).toBeDefined();
    const types = mis.sections!.map(s => s.type);
    expect(types).toContain('kpi_cards');
    expect(types).toContain('chart');
    expect(mis.chartTypes).toContain('bar');
    expect(mis.detectFields).toContain('entity_name');
  });

  it('audit config has supportedFormats including big4', () => {
    expect(REPORT_CONFIGS['audit'].supportedFormats).toContain('big4');
  });

  it('vat config has regulatoryNote mentioning VAT-201', () => {
    expect(REPORT_CONFIGS['vat'].regulatoryNote).toMatch(/VAT-201/i);
  });

  it('corporate_tax config has detectFields including period_end', () => {
    expect(REPORT_CONFIGS['corporate_tax'].detectFields).toContain('period_end');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/reportConfigs.test.ts`
Expected: FAIL — `sections`, `chartTypes`, `detectFields`, `supportedFormats`, `regulatoryNote` don't exist yet.

- [ ] **Step 4: Extend `reportConfigs.ts`**

Add these interfaces at the top of `reportConfigs.ts` (above the existing `ReportConfig`):

```typescript
export type AuditorFormat = 'standard' | 'big4' | 'legal' | 'compliance' | 'custom';

export interface ReportSection {
  id: string;
  label: string;
  type: 'kpi_cards' | 'chart' | 'table' | 'narrative' | 'regulatory_form' | 'signature_block';
  extractionPrompt: string;
  required: boolean;
}

export interface ReportConfig {
  type: string;
  label: string;
  icon: string;
  fields: PrefilledField[];           // existing — keep for backward compat
  sections?: ReportSection[];          // new — drives artifact panel rendering
  supportedFormats?: AuditorFormat[];  // new
  detectFields?: string[];             // new — fields to auto-detect from docs
  regulatoryNote?: string;             // new
  chartTypes?: string[];               // new — e.g. ['bar', 'line']
  category?: 'financial' | 'regulatory' | 'audit' | 'custom';
}
```

Then add `sections`, `supportedFormats`, `detectFields`, `regulatoryNote`, and `chartTypes` to each entry in `REPORT_CONFIGS`. Key entries:

**MIS (`'mis'`):**
```typescript
category: 'financial',
detectFields: ['entity_name', 'period_end'],
chartTypes: ['bar', 'line'],
supportedFormats: ['standard', 'big4'],
sections: [
  { id: 'kpi', label: 'KPI Cards', type: 'kpi_cards',
    extractionPrompt: 'Extract Revenue, Expenses, Net Profit, Gross Margin from documents', required: true },
  { id: 'chart', label: 'Revenue vs Expenses Chart', type: 'chart',
    extractionPrompt: 'Extract revenue and expenses by period for chart data', required: true },
  { id: 'pl_table', label: 'Department P&L Table', type: 'table',
    extractionPrompt: 'Extract department-level P&L figures from documents', required: false },
  { id: 'narrative', label: 'Narrative Summary', type: 'narrative',
    extractionPrompt: 'Write a 2-paragraph summary of financial performance citing sources', required: true },
],
```

**Audit (`'audit'`):**
```typescript
category: 'audit',
detectFields: ['entity_name', 'period_end'],
chartTypes: [],
supportedFormats: ['standard', 'big4', 'legal', 'compliance'],
regulatoryNote: 'Based on ISA 700 Big 4 structure',
sections: [
  { id: 'opinion', label: "Independent Auditor's Report", type: 'narrative',
    extractionPrompt: 'Generate ISA 700 opinion paragraph', required: true },
  { id: 'basis', label: 'Basis for Opinion', type: 'narrative',
    extractionPrompt: 'State standards applied and evidence obtained', required: true },
  { id: 'kam', label: 'Key Audit Matters', type: 'narrative',
    extractionPrompt: 'Identify key audit matters from document contents', required: false },
  { id: 'responsibilities', label: 'Responsibilities', type: 'narrative',
    extractionPrompt: 'Management vs auditor responsibilities per ISA 700.33', required: true },
  { id: 'signature', label: 'Signature Block', type: 'signature_block',
    extractionPrompt: 'Firm name, date, location — auto-detect or leave editable', required: true },
],
```

**VAT (`'vat'`):**
```typescript
category: 'regulatory',
detectFields: ['entity_name', 'period_end'],
chartTypes: [],
supportedFormats: ['standard', 'compliance'],
regulatoryNote: 'Based on UAE FTA VAT-201 form structure',
sections: [
  { id: 'vat_form', label: 'VAT-201 Return', type: 'regulatory_form',
    extractionPrompt: 'Extract values for VAT-201 Boxes 1–9 from accounting documents', required: true },
],
```

**Corporate Tax (`'corporate_tax'`):**
```typescript
category: 'regulatory',
detectFields: ['entity_name', 'period_end'],
chartTypes: [],
supportedFormats: ['standard', 'compliance'],
regulatoryNote: 'Based on UAE CT Decree-Law No. 47 of 2022',
sections: [
  { id: 'ct_computation', label: 'CT Computation', type: 'table',
    extractionPrompt: 'Extract accounting profit, adjustments, exempt income, CT payable', required: true },
],
```

**IFRS (`'ifrs'`):**
```typescript
category: 'financial',
detectFields: ['entity_name', 'as_of_date'],
chartTypes: [],
supportedFormats: ['standard', 'big4'],
sections: [
  { id: 'sfp', label: 'Statement of Financial Position', type: 'table',
    extractionPrompt: 'Extract assets, liabilities, equity for balance sheet', required: true },
  { id: 'pnl', label: 'P&L Statement', type: 'table',
    extractionPrompt: 'Extract revenue, expenses, net profit', required: true },
  { id: 'cashflow', label: 'Cash Flow Statement', type: 'table',
    extractionPrompt: 'Extract operating, investing, financing activities', required: true },
  { id: 'notes', label: 'Notes to Financial Statements', type: 'narrative',
    extractionPrompt: 'IFRS accounting policies and significant estimates', required: false },
],
```

Add similar `sections` + `detectFields` to `budget_vs_actual`, `compliance`, `financial_analysis`, `cash_flow`, `forecast`, and `custom`. For `custom`:
```typescript
category: 'custom',
detectFields: ['entity_name'],
chartTypes: [],
supportedFormats: ['standard', 'big4', 'legal', 'compliance', 'custom'],
sections: [],  // built dynamically from user input
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/reportConfigs.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/reportConfigs.ts frontend/package.json frontend/package-lock.json frontend/src/components/studios/LegalStudio/__tests__/reportConfigs.test.ts
git commit -m "feat(config): extend reportConfigs with sections, detectFields, chartTypes"
```

---

## Task 5: Frontend — `AuditOverlay` + `AuditOverlayContext` (C3)

**Files:**
- Create: `frontend/src/context/AuditOverlayContext.tsx`
- Create: `frontend/src/components/studios/LegalStudio/AuditOverlay.tsx`
- Create: `frontend/src/components/studios/LegalStudio/__tests__/AuditOverlay.test.tsx`
- Modify: `frontend/src/App.tsx` — wrap with `AuditOverlayProvider`

The overlay renders at app-root level (fixed position, `z-index: 1000`) and persists across route navigation. State is `full | minimized | closed`. Dragging is controlled by pointer events on the header.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/studios/LegalStudio/__tests__/AuditOverlay.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AuditOverlayProvider, useAuditOverlay } from '../../../../context/AuditOverlayContext';
import { AuditOverlay } from '../AuditOverlay';

function TestHarness() {
  const { open, result } = useAuditOverlay();
  return (
    <>
      <button onClick={() => open({
        summary: 'Net profit margin 12%',
        risk_flags: [{ severity: 'high', document: 'TB.pdf', finding: 'Negative equity' }],
        anomalies: [],
        compliance_gaps: [],
      })}>Open</button>
      <AuditOverlay />
    </>
  );
}

describe('AuditOverlay', () => {
  it('is not visible when closed', () => {
    render(
      <AuditOverlayProvider>
        <AuditOverlay />
      </AuditOverlayProvider>
    );
    expect(screen.queryByText(/Audit Overview/i)).not.toBeInTheDocument();
  });

  it('shows summary and risk flags after open()', () => {
    render(
      <AuditOverlayProvider>
        <TestHarness />
      </AuditOverlayProvider>
    );
    fireEvent.click(screen.getByText('Open'));
    expect(screen.getByText(/Audit Overview/i)).toBeInTheDocument();
    expect(screen.getByText(/Negative equity/i)).toBeInTheDocument();
  });

  it('minimizes to pill on minimize click', () => {
    render(
      <AuditOverlayProvider>
        <TestHarness />
      </AuditOverlayProvider>
    );
    fireEvent.click(screen.getByText('Open'));
    const minBtn = screen.getByRole('button', { name: /minimize/i });
    fireEvent.click(minBtn);
    expect(screen.queryByText(/Negative equity/i)).not.toBeInTheDocument();
    expect(screen.getByText('📊')).toBeInTheDocument();
  });

  it('closes on close button', () => {
    render(
      <AuditOverlayProvider>
        <TestHarness />
      </AuditOverlayProvider>
    );
    fireEvent.click(screen.getByText('Open'));
    const closeBtn = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    expect(screen.queryByText(/Audit Overview/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/AuditOverlay.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Create `AuditOverlayContext.tsx`**

Create `frontend/src/context/AuditOverlayContext.tsx`:

```typescript
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

export interface AuditResult {
  summary: string;
  risk_flags: Array<{ severity: 'low' | 'medium' | 'high'; document: string; finding: string }>;
  anomalies: Array<{ severity: 'low' | 'medium' | 'high'; document: string; finding: string }>;
  compliance_gaps: Array<{ severity: 'low' | 'medium' | 'high'; document: string; finding: string }>;
}

type OverlayState = 'full' | 'minimized' | 'closed';

interface AuditOverlayCtx {
  overlayState: OverlayState;
  result: AuditResult | null;
  position: { x: number; y: number };
  open: (result: AuditResult) => void;
  close: () => void;
  minimize: () => void;
  restore: () => void;
  setPosition: (pos: { x: number; y: number }) => void;
}

const AuditOverlayContext = createContext<AuditOverlayCtx | null>(null);

export function AuditOverlayProvider({ children }: { children: ReactNode }) {
  const [overlayState, setOverlayState] = useState<OverlayState>('closed');
  const [result, setResult] = useState<AuditResult | null>(null);
  const [position, setPosition] = useState({ x: window.innerWidth - 380, y: window.innerHeight - 420 });

  const open = useCallback((r: AuditResult) => {
    setResult(r);
    setOverlayState('full');
  }, []);

  const close = useCallback(() => setOverlayState('closed'), []);
  const minimize = useCallback(() => setOverlayState('minimized'), []);
  const restore = useCallback(() => setOverlayState('full'), []);

  return (
    <AuditOverlayContext.Provider value={{ overlayState, result, position, open, close, minimize, restore, setPosition }}>
      {children}
    </AuditOverlayContext.Provider>
  );
}

export function useAuditOverlay() {
  const ctx = useContext(AuditOverlayContext);
  if (!ctx) throw new Error('useAuditOverlay must be used inside AuditOverlayProvider');
  return ctx;
}
```

- [ ] **Step 4: Create `AuditOverlay.tsx`**

Create `frontend/src/components/studios/LegalStudio/AuditOverlay.tsx`:

```tsx
import { useCallback, useRef } from 'react';
import { useAuditOverlay } from '../../../context/AuditOverlayContext';

const SEVERITY_COLOR: Record<string, string> = {
  high: '#e53e3e',
  medium: '#dd6b20',
  low: '#38a169',
};

export function AuditOverlay() {
  const { overlayState, result, position, close, minimize, restore, setPosition } = useAuditOverlay();
  const dragOffset = useRef<{ dx: number; dy: number } | null>(null);

  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragOffset.current = { dx: e.clientX - position.x, dy: e.clientY - position.y };
  }, [position]);

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragOffset.current) return;
    setPosition({ x: e.clientX - dragOffset.current.dx, y: e.clientY - dragOffset.current.dy });
  }, [setPosition]);

  const onPointerUp = useCallback(() => { dragOffset.current = null; }, []);

  if (overlayState === 'closed' || !result) return null;

  if (overlayState === 'minimized') {
    return (
      <div
        role="button"
        aria-label="restore"
        onClick={restore}
        style={{
          position: 'fixed', left: position.x, top: position.y,
          width: 56, height: 56, borderRadius: '50%',
          background: 'var(--s-brand, #4299e1)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', zIndex: 1000, fontSize: 24, boxShadow: '0 4px 16px rgba(0,0,0,.2)',
        }}
      >📊</div>
    );
  }

  return (
    <div style={{
      position: 'fixed', left: position.x, top: position.y,
      width: 340, maxHeight: 420, background: 'var(--s-bg-2, #fff)',
      border: '1px solid var(--s-border, #e2e8f0)', borderRadius: 12,
      boxShadow: '0 8px 32px rgba(0,0,0,.15)', zIndex: 1000,
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Draggable header */}
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        style={{
          padding: '10px 12px', background: 'var(--s-bg-3, #f7fafc)',
          borderBottom: '1px solid var(--s-border)', cursor: 'grab',
          display: 'flex', alignItems: 'center', gap: 8, userSelect: 'none',
        }}
      >
        <span style={{ flex: 1, fontWeight: 600, fontSize: 13 }}>📊 Audit Overview</span>
        <button aria-label="minimize" onClick={minimize}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16 }}>—</button>
        <button aria-label="close" onClick={close}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16 }}>✕</button>
      </div>

      {/* Scrollable content */}
      <div style={{ overflowY: 'auto', padding: '12px', flex: 1 }}>
        {result.summary && (
          <p style={{ margin: '0 0 12px', fontSize: 13 }}>{result.summary}</p>
        )}

        {result.risk_flags.length > 0 && (
          <section>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Risk Flags</div>
            {result.risk_flags.map((f, i) => (
              <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 4, alignItems: 'flex-start' }}>
                <span style={{
                  background: SEVERITY_COLOR[f.severity] ?? '#718096', color: '#fff',
                  borderRadius: 4, padding: '1px 5px', fontSize: 10, whiteSpace: 'nowrap',
                }}>{f.severity.toUpperCase()}</span>
                <span style={{ fontSize: 12 }}>{f.finding}</span>
              </div>
            ))}
          </section>
        )}

        {result.anomalies.length > 0 && (
          <section style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Anomalies</div>
            {result.anomalies.map((a, i) => (
              <div key={i} style={{ fontSize: 12, marginBottom: 3 }}>• {a.finding}</div>
            ))}
          </section>
        )}

        {result.compliance_gaps.length > 0 && (
          <section style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Compliance Gaps</div>
            {result.compliance_gaps.map((g, i) => (
              <div key={i} style={{ fontSize: 12, marginBottom: 3 }}>• {g.finding}</div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Wrap `App.tsx` with `AuditOverlayProvider`**

In `frontend/src/App.tsx`, import `AuditOverlayProvider` and `AuditOverlay`, then:
1. Wrap the app root with `<AuditOverlayProvider>`
2. Render `<AuditOverlay />` just inside the provider (outside of any router outlet) so it persists across navigation

Example structure:
```tsx
import { AuditOverlayProvider } from './context/AuditOverlayContext';
import { AuditOverlay } from './components/studios/LegalStudio/AuditOverlay';

export default function App() {
  return (
    <AuditOverlayProvider>
      <AuditOverlay />
      {/* ... existing router / layout ... */}
    </AuditOverlayProvider>
  );
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/AuditOverlay.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/context/AuditOverlayContext.tsx \
        frontend/src/components/studios/LegalStudio/AuditOverlay.tsx \
        frontend/src/components/studios/LegalStudio/__tests__/AuditOverlay.test.tsx \
        frontend/src/App.tsx
git commit -m "feat(overlay): draggable persistent AuditOverlay with context"
```

---

## Task 6: Frontend — `ArtifactPanel` + MIS charts (C5)

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/MisKpiCards.tsx`
- Create: `frontend/src/components/studios/LegalStudio/MisChart.tsx`
- Create: `frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx`
- Create: `frontend/src/components/studios/LegalStudio/__tests__/ArtifactPanel.test.tsx`
- Create: `frontend/src/components/studios/LegalStudio/__tests__/MisKpiCards.test.tsx`

`ArtifactPanel` is a right-side panel that renders the streaming report content. When `report_type === 'mis'`, it parses the LLM output for KPI cards and chart data sections. Otherwise it renders the raw markdown report.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/studios/LegalStudio/__tests__/ArtifactPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ArtifactPanel } from '../ArtifactPanel';

describe('ArtifactPanel', () => {
  it('renders null when not open', () => {
    const { container } = render(
      <ArtifactPanel
        open={false}
        title="MIS Report"
        reportType="mis"
        content=""
        loading={false}
        onClose={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders loading state', () => {
    render(
      <ArtifactPanel
        open={true}
        title="MIS Report"
        reportType="mis"
        content=""
        loading={true}
        onClose={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText(/Generating/i)).toBeInTheDocument();
  });

  it('renders report title and export button when content available', () => {
    render(
      <ArtifactPanel
        open={true}
        title="VAT Return"
        reportType="vat"
        content="## VAT Return\nBox 1: AED 100,000"
        loading={false}
        onClose={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText('VAT Return')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(
      <ArtifactPanel
        open={true}
        title="Report"
        reportType="audit"
        content="content"
        loading={false}
        onClose={onClose}
        onExport={vi.fn()}
      />
    );
    const closeBtn = screen.getByRole('button', { name: /close/i });
    closeBtn.click();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
```

Create `frontend/src/components/studios/LegalStudio/__tests__/MisKpiCards.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MisKpiCards } from '../MisKpiCards';

describe('MisKpiCards', () => {
  it('renders KPI cards with labels and values', () => {
    render(
      <MisKpiCards kpis={[
        { label: 'Revenue', value: 'AED 1,000,000' },
        { label: 'Net Profit', value: 'AED 200,000' },
      ]} />
    );
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('AED 1,000,000')).toBeInTheDocument();
    expect(screen.getByText('Net Profit')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ArtifactPanel.test.tsx src/components/studios/LegalStudio/__tests__/MisKpiCards.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Create `MisKpiCards.tsx`**

Create `frontend/src/components/studios/LegalStudio/MisKpiCards.tsx`:

```tsx
interface Kpi {
  label: string;
  value: string;
}

interface Props {
  kpis: Kpi[];
}

export function MisKpiCards({ kpis }: Props) {
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
      {kpis.map((k, i) => (
        <div key={i} style={{
          flex: '1 1 140px', padding: '12px 16px',
          background: 'var(--s-bg-3, #f7fafc)',
          border: '1px solid var(--s-border, #e2e8f0)', borderRadius: 8,
        }}>
          <div style={{ fontSize: 11, color: 'var(--s-text-2)', marginBottom: 4 }}>{k.label}</div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{k.value}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Create `MisChart.tsx`**

Create `frontend/src/components/studios/LegalStudio/MisChart.tsx`:

```tsx
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

export interface ChartDataPoint {
  period: string;
  revenue?: number;
  expenses?: number;
  profit?: number;
}

interface Props {
  data: ChartDataPoint[];
  type: 'bar' | 'line';
}

export function MisChart({ data, type }: Props) {
  if (!data.length) return null;

  if (type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {data[0].revenue !== undefined && <Line type="monotone" dataKey="revenue" stroke="#4299e1" />}
          {data[0].expenses !== undefined && <Line type="monotone" dataKey="expenses" stroke="#e53e3e" />}
          {data[0].profit !== undefined && <Line type="monotone" dataKey="profit" stroke="#38a169" />}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        {data[0].revenue !== undefined && <Bar dataKey="revenue" fill="#4299e1" />}
        {data[0].expenses !== undefined && <Bar dataKey="expenses" fill="#e53e3e" />}
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 5: Create `ArtifactPanel.tsx`**

Create `frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx`:

```tsx
import { useMemo } from 'react';
import { MisKpiCards } from './MisKpiCards';
import { MisChart, type ChartDataPoint } from './MisChart';

interface Props {
  open: boolean;
  title: string;
  reportType: string;
  content: string;
  loading: boolean;
  onClose: () => void;
  onExport: () => void;
}

/**
 * Parse KPI lines like "Revenue: AED 1,000,000" from markdown content.
 */
function parseKpis(content: string) {
  const KPI_KEYS = ['Revenue', 'Expenses', 'Net Profit', 'Gross Margin', 'EBITDA', 'Cash Position'];
  return KPI_KEYS.flatMap(key => {
    const m = content.match(new RegExp(`${key}[:\\s]+(AED[\\s\\d,]+|\\d[\\d,\\.]+)`, 'i'));
    return m ? [{ label: key, value: m[1].trim() }] : [];
  });
}

/**
 * Parse a JSON array inside a "Chart Data" block in the report content.
 */
function parseChartData(content: string): ChartDataPoint[] {
  try {
    const m = content.match(/```(?:json)?\s*(\[[\s\S]*?\])\s*```/);
    if (m) return JSON.parse(m[1]) as ChartDataPoint[];
  } catch {
    // ignore malformed JSON
  }
  return [];
}

export function ArtifactPanel({ open, title, reportType, content, loading, onClose, onExport }: Props) {
  if (!open) return null;

  const kpis = useMemo(() => reportType === 'mis' ? parseKpis(content) : [], [content, reportType]);
  const chartData = useMemo(() => reportType === 'mis' ? parseChartData(content) : [], [content, reportType]);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--s-bg-1, #fff)', borderLeft: '1px solid var(--s-border, #e2e8f0)',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--s-border)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ fontWeight: 700, fontSize: 14, flex: 1 }}>📊 {title}</span>
        <button
          aria-label="export"
          onClick={onExport}
          style={{ background: 'none', border: '1px solid var(--s-border)', borderRadius: 6,
                   padding: '4px 10px', cursor: 'pointer', fontSize: 12 }}
        >Export PDF</button>
        <button
          aria-label="close"
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--s-text-2)' }}
        >✕</button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {loading ? (
          <div style={{ color: 'var(--s-text-2)', textAlign: 'center', marginTop: 40 }}>
            ⏳ Generating report…
          </div>
        ) : (
          <>
            {reportType === 'mis' && kpis.length > 0 && <MisKpiCards kpis={kpis} />}
            {reportType === 'mis' && chartData.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <MisChart data={chartData} type="bar" />
              </div>
            )}
            {/* Render report as pre-formatted text */}
            <pre style={{
              whiteSpace: 'pre-wrap', fontFamily: 'var(--s-font-mono, monospace)',
              fontSize: 12, lineHeight: 1.6, color: 'var(--s-text-1)',
            }}>{content}</pre>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ArtifactPanel.test.tsx src/components/studios/LegalStudio/__tests__/MisKpiCards.test.tsx`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx \
        frontend/src/components/studios/LegalStudio/MisKpiCards.tsx \
        frontend/src/components/studios/LegalStudio/MisChart.tsx \
        frontend/src/components/studios/LegalStudio/__tests__/ArtifactPanel.test.tsx \
        frontend/src/components/studios/LegalStudio/__tests__/MisKpiCards.test.tsx
git commit -m "feat(ui): ArtifactPanel with MIS KPI cards and Recharts bar/line charts"
```

---

## Task 7: Frontend — `ConfirmReportCard` + wire `LegalStudio.tsx` (C6 frontend)

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/ConfirmReportCard.tsx`
- Create: `frontend/src/components/studios/LegalStudio/__tests__/ConfirmReportCard.test.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `frontend/src/lib/api.ts` — add `generateReportStreamUrl()` and `detectReportMetadata()`

This task replaces the `QuestionnaireMessage` flow with a `ConfirmReportCard` message bubble that appears in chat after auto-detection, and connects the Generate button to the streaming artifact panel.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/studios/LegalStudio/__tests__/ConfirmReportCard.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConfirmReportCard } from '../ConfirmReportCard';

const defaultProps = {
  reportType: 'audit',
  reportLabel: 'ISA 700 Audit Report',
  entityName: 'ABC Trading LLC',
  periodEnd: 'FY ended 31 Dec 2024',
  documentsCount: 3,
  format: 'big4' as const,
  confidence: 'high' as const,
  onGenerate: vi.fn(),
  onEdit: vi.fn(),
};

describe('ConfirmReportCard', () => {
  it('renders report type label', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    expect(screen.getByText(/ISA 700 Audit Report/i)).toBeInTheDocument();
  });

  it('renders detected entity and period', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    expect(screen.getByText(/ABC Trading LLC/i)).toBeInTheDocument();
    expect(screen.getByText(/31 Dec 2024/i)).toBeInTheDocument();
  });

  it('calls onGenerate when Generate Report button clicked', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /Generate Report/i }));
    expect(defaultProps.onGenerate).toHaveBeenCalledWith({
      entityName: 'ABC Trading LLC',
      periodEnd: 'FY ended 31 Dec 2024',
      format: 'big4',
    });
  });

  it('shows edit fields when Edit Details clicked', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /Edit Details/i }));
    expect(screen.getByLabelText(/entity/i)).toBeInTheDocument();
  });

  it('shows low-confidence warning when confidence is low', () => {
    render(<ConfirmReportCard {...defaultProps} confidence="low" />);
    expect(screen.getByText(/Please verify/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ConfirmReportCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `ConfirmReportCard.tsx`**

Create `frontend/src/components/studios/LegalStudio/ConfirmReportCard.tsx`:

```tsx
import { useState, type FormEvent } from 'react';
import { type AuditorFormat } from './AuditorFormatGrid';

interface GenerateParams {
  entityName: string;
  periodEnd: string;
  format: AuditorFormat;
}

interface Props {
  reportType: string;
  reportLabel: string;
  entityName: string;
  periodEnd: string;
  documentsCount: number;
  format: AuditorFormat;
  confidence: 'high' | 'low' | 'none';
  onGenerate: (params: GenerateParams) => void;
  onEdit?: () => void;
}

export function ConfirmReportCard({
  reportLabel, entityName: initialEntity, periodEnd: initialPeriod,
  documentsCount, format: initialFormat, confidence, onGenerate,
}: Props) {
  const [editing, setEditing] = useState(confidence === 'none');
  const [entityName, setEntityName] = useState(initialEntity);
  const [periodEnd, setPeriodEnd] = useState(initialPeriod);
  const [format, setFormat] = useState<AuditorFormat>(initialFormat);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onGenerate({ entityName, periodEnd, format });
  };

  return (
    <div style={{
      background: 'var(--s-bg-2, #f7fafc)', border: '1px solid var(--s-border, #e2e8f0)',
      borderRadius: 10, padding: '14px 16px', maxWidth: 420,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>📋 Ready to generate {reportLabel}</div>

      {confidence === 'low' && (
        <div style={{ color: '#dd6b20', fontSize: 12, marginBottom: 8 }}>
          ⚠ Please verify the detected details before generating.
        </div>
      )}

      {!editing ? (
        <>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <strong>Entity:</strong> {entityName || '—'}
          </div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <strong>Period:</strong> {periodEnd || '—'}
          </div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <strong>Documents:</strong> {documentsCount} in scope
          </div>
          <div style={{ fontSize: 13, marginBottom: 12 }}>
            <strong>Format:</strong> {format}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              aria-label="Generate Report"
              onClick={() => onGenerate({ entityName, periodEnd, format })}
              style={{
                background: 'var(--s-brand, #4299e1)', color: '#fff',
                border: 'none', borderRadius: 6, padding: '7px 14px',
                cursor: 'pointer', fontWeight: 600, fontSize: 13,
              }}
            >✅ Generate Report</button>
            <button
              type="button"
              aria-label="Edit Details"
              onClick={() => setEditing(true)}
              style={{
                background: 'none', border: '1px solid var(--s-border)', borderRadius: 6,
                padding: '7px 14px', cursor: 'pointer', fontSize: 13,
              }}
            >✏️ Edit Details</button>
          </div>
        </>
      ) : (
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
            Entity Name
            <input
              aria-label="entity name"
              value={entityName}
              onChange={e => setEntityName(e.target.value)}
              style={{ display: 'block', width: '100%', padding: '5px 8px', marginTop: 3,
                       border: '1px solid var(--s-border)', borderRadius: 5, fontSize: 13 }}
            />
          </label>
          <label style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
            Period End
            <input
              value={periodEnd}
              onChange={e => setPeriodEnd(e.target.value)}
              style={{ display: 'block', width: '100%', padding: '5px 8px', marginTop: 3,
                       border: '1px solid var(--s-border)', borderRadius: 5, fontSize: 13 }}
            />
          </label>
          <label style={{ display: 'block', marginBottom: 12, fontSize: 13 }}>
            Format
            <select
              value={format}
              onChange={e => setFormat(e.target.value as AuditorFormat)}
              style={{ display: 'block', width: '100%', padding: '5px 8px', marginTop: 3,
                       border: '1px solid var(--s-border)', borderRadius: 5, fontSize: 13 }}
            >
              {(['standard', 'big4', 'legal', 'compliance', 'custom'] as AuditorFormat[]).map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            aria-label="Generate Report"
            style={{
              background: 'var(--s-brand, #4299e1)', color: '#fff',
              border: 'none', borderRadius: 6, padding: '7px 14px',
              cursor: 'pointer', fontWeight: 600, fontSize: 13,
            }}
          >✅ Generate Report</button>
        </form>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Add API helpers to `lib/api.ts`**

In `frontend/src/lib/api.ts`, add:

```typescript
export function generateReportStreamUrl(): string {
  return `${API_BASE}/api/reports/generate-stream`;
}

export async function detectReportMetadata(
  reportType: string,
  selectedDocIds: string[],
): Promise<{ entity_name: string; period_end: string; confidence: 'high' | 'low' | 'none' }> {
  const r = await API.post('/api/reports/detect', {
    report_type: reportType,
    selected_doc_ids: selectedDocIds,
  });
  return r.data;
}
```

- [ ] **Step 5: Wire `LegalStudio.tsx` — report request flow**

In `LegalStudio.tsx`:

1. **Add state** for the confirm card and artifact panel:

```typescript
const [confirmCard, setConfirmCard] = useState<{
  reportType: string;
  reportLabel: string;
  entityName: string;
  periodEnd: string;
  confidence: 'high' | 'low' | 'none';
  format: AuditorFormat;
} | null>(null);

const [artifactOpen, setArtifactOpen] = useState(false);
const [artifactTitle, setArtifactTitle] = useState('');
const [artifactReportType, setArtifactReportType] = useState('');
const [artifactContent, setArtifactContent] = useState('');
const [artifactLoading, setArtifactLoading] = useState(false);
const abortReportRef = useRef<AbortController | null>(null);
```

2. **Replace `handleReportRequest`** (which previously launched the questionnaire) with:

```typescript
const handleReportRequest = useCallback(async (reportType: string) => {
  const config = REPORT_CONFIGS[reportType];
  if (!config) return;

  // Auto-detect entity and period from docs
  let entity_name = '';
  let period_end = '';
  let confidence: 'high' | 'low' | 'none' = 'none';
  try {
    const detected = await detectReportMetadata(reportType, selectedDocIds);
    entity_name = detected.entity_name;
    period_end = detected.period_end;
    confidence = detected.confidence;
  } catch {
    // Fallback — show card with empty fields
  }

  // Insert a ConfirmReportCard message into the chat
  setConfirmCard({
    reportType,
    reportLabel: config.label,
    entityName: entity_name,
    periodEnd: period_end,
    confidence,
    format: auditorFormat,
  });
}, [selectedDocIds, auditorFormat]);
```

3. **Add `handleGenerate`** — called when user confirms the card:

```typescript
const handleGenerateReport = useCallback(async (params: {
  entityName: string;
  periodEnd: string;
  format: AuditorFormat;
}) => {
  if (!confirmCard) return;
  setConfirmCard(null);

  const config = REPORT_CONFIGS[confirmCard.reportType];
  const title = `${config?.icon ?? '📊'} ${config?.label ?? confirmCard.reportType} — ${params.entityName}`;
  setArtifactTitle(title);
  setArtifactReportType(confirmCard.reportType);
  setArtifactContent('');
  setArtifactLoading(true);
  setArtifactOpen(true);

  abortReportRef.current?.abort();
  const ac = new AbortController();
  abortReportRef.current = ac;

  try {
    const resp = await fetch(generateReportStreamUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        report_type: confirmCard.reportType,
        selected_doc_ids: selectedDocIds,
        entity_name: params.entityName,
        period_end: params.periodEnd,
        auditor_format: params.format,
      }),
      signal: ac.signal,
    });
    if (!resp.ok || !resp.body) { setArtifactLoading(false); return; }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    setArtifactLoading(false);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 2);
        if (!frame.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(frame.slice(6));
          if (ev.type === 'chunk') setArtifactContent(prev => prev + ev.content);
        } catch { /* malformed */ }
      }
    }
  } catch {
    setArtifactLoading(false);
  }
}, [confirmCard, selectedDocIds]);
```

4. **Add chat refinement**: When `artifactOpen` and user sends a normal message in chat, check if the content looks like a refinement instruction (e.g. starts with "Add", "Change", "Make", "Update", "Remove") and send it as `refinement_instruction` to `/api/reports/generate-stream` instead of the normal chat endpoint.

```typescript
// In the send message handler, before calling the normal chat API:
if (artifactOpen && artifactContent && isRefinementInstruction(message)) {
  handleRefinement(message);
  return;
}

// Helper:
function isRefinementInstruction(text: string): boolean {
  const REFINEMENT_STARTS = ['add', 'change', 'make', 'update', 'remove', 'include', 'shorten', 'expand'];
  return REFINEMENT_STARTS.some(s => text.toLowerCase().startsWith(s));
}

const handleRefinement = useCallback(async (instruction: string) => {
  if (!artifactReportType || !artifactContent) return;
  setArtifactLoading(true);
  const prevContent = artifactContent;
  setArtifactContent('');

  abortReportRef.current?.abort();
  const ac = new AbortController();
  abortReportRef.current = ac;

  try {
    const resp = await fetch(generateReportStreamUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        report_type: artifactReportType,
        selected_doc_ids: selectedDocIds,
        refinement_instruction: instruction,
        current_report_content: prevContent,
      }),
      signal: ac.signal,
    });
    if (!resp.ok || !resp.body) { setArtifactContent(prevContent); setArtifactLoading(false); return; }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    setArtifactLoading(false);
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 2);
        if (!frame.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(frame.slice(6));
          if (ev.type === 'chunk') setArtifactContent(prev => prev + ev.content);
        } catch { /* ignore */ }
      }
    }
  } catch {
    setArtifactContent(prevContent);
    setArtifactLoading(false);
  }
}, [artifactReportType, artifactContent, selectedDocIds]);
```

5. **Render the `ConfirmReportCard`** in the messages area: When `confirmCard` is not null, append it as a special message just above the chat input:

```tsx
{confirmCard && (
  <ConfirmReportCard
    reportType={confirmCard.reportType}
    reportLabel={confirmCard.reportLabel}
    entityName={confirmCard.entityName}
    periodEnd={confirmCard.periodEnd}
    documentsCount={selectedDocIds.length}
    format={confirmCard.format}
    confidence={confirmCard.confidence}
    onGenerate={handleGenerateReport}
    onEdit={() => {/* allow editing by setting confidence to 'none' in confirmCard */}}
  />
)}
```

6. **Render the `ArtifactPanel`** in the right column of `ThreePaneLayout` when `artifactOpen`:

```tsx
// Replace studioPanel with artifactPanel when artifact is open:
const rightPanel = artifactOpen ? (
  <ArtifactPanel
    open={artifactOpen}
    title={artifactTitle}
    reportType={artifactReportType}
    content={artifactContent}
    loading={artifactLoading}
    onClose={() => setArtifactOpen(false)}
    onExport={() => {
      const blob = new Blob([artifactContent], { type: 'text/plain' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${artifactReportType}-report.md`;
      a.click();
    }}
  />
) : (
  <StudioPanel
    sourceIds={selectedDocIds}
    companyName={docs[0]?.source}
    mode={mode}
    onReportRequest={handleReportRequest}
    onFormatChange={setAuditorFormat}
    auditorFormat={auditorFormat}
  />
);

// Then in the ThreePaneLayout:
return <ThreePaneLayout left={sourcesSidebar} center={chatArea} right={rightPanel} />;
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ConfirmReportCard.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add \
  frontend/src/components/studios/LegalStudio/ConfirmReportCard.tsx \
  frontend/src/components/studios/LegalStudio/__tests__/ConfirmReportCard.test.tsx \
  frontend/src/components/studios/LegalStudio/LegalStudio.tsx \
  frontend/src/lib/api.ts
git commit -m "feat(analyst): ConfirmReportCard + ArtifactPanel wired into LegalStudio"
```

---

## Run All Tests

After all 7 tasks are complete, run the full test suite:

**Backend:**
```bash
cd backend && uv run pytest tests/ -v --tb=short
```

Expected: All tests pass, including:
- `tests/api/test_analyst_prompt.py` (2)
- `tests/api/test_reports_detect.py` (2)
- `tests/api/test_reports_generate_stream.py` (1)
- All prior Plan A and Plan B tests

**Frontend:**
```bash
cd frontend && npx vitest run --reporter=verbose
```

Expected: All tests pass, including:
- `__tests__/reportConfigs.test.ts` (5)
- `__tests__/AuditOverlay.test.tsx` (4)
- `__tests__/ArtifactPanel.test.tsx` (4)
- `__tests__/MisKpiCards.test.tsx` (1)
- `__tests__/ConfirmReportCard.test.tsx` (5)
- All prior Plan A and Plan B tests

---

## Final Checklist (from spec §Testing Checklist Sub-project C)

- [ ] Run Audit auto-detects entity + period; no dialog shown (just confirm card toast)
- [ ] Confirm card shows `low` warning when detection confidence is low
- [ ] Audit overlay is draggable; doesn't block chat area by default
- [ ] Audit overlay persists when navigating to Home and back (AuditOverlayProvider at app root)
- [ ] MIS report is grounded in attached docs (no generic invented content)
- [ ] MIS artifact panel shows KPI cards + charts + P&L table
- [ ] Report confirm card shows auto-detected entity/period/format
- [ ] Report generates into artifact panel immediately on confirm; loading state shown
- [ ] Follow-up chat messages starting with "Add/Change/Make/Update" trigger refinement
- [ ] Artifact panel Export button downloads the report as markdown
- [ ] Analyst mode system prompt contains the document-grounding prefix
