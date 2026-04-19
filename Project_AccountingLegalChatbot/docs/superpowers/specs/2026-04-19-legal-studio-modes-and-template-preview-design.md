# Legal Studio Chat Modes, Doc UX, and Template Preview — Design Spec

**Date:** 2026-04-19
**Scope:** Legal Studio overhaul (chat modes, domain classifier, doc upload, UI fixes) + Template Studio preview feature
**Implementation Priority:** Bundle A → B → C → D

---

## 1. Problem Statement

Four observed issues from 2026-04-19 UX review:

1. **Legal Studio chat misroutes domain.** A UAE VAT question is classified under `General Law` instead of `vat`. An error is also shown on the chat page (exact text TBD; action item: reproduce and fix). There is no way for users to pick a chat interaction mode (normal Q&A vs. deep research vs. analyst).
2. **Research panel has no document upload.** Deep-research workflows need the ability to supply reference documents, but no upload affordance exists.
3. **Legal Studio document handling is broken.** Upload does nothing. Multi-file is not supported. No auto-summary. Chat and preview are not unified. *All* interactive buttons in the panel are non-functional, including the `Auditor` button.
4. **Template Studio has no preview.** Users cannot see what a learned template will render as; after upload there is no confirmation of correctness. Users should not need technical knowledge to verify a template is usable.

## 2. Goals

- Legal Studio chat supports three explicit modes: Normal, Deep Research, Analyst.
- Domain classifier replaces default-to-`law` fallback; correctly routes UAE-specific queries.
- Deep Research runs uncapped (no timeout, max model token budget), streams live, produces citeable structured output saveable as a source doc.
- Legal Studio matches the Finance Studio NotebookLM pattern: persistent sources sidebar, multi-file upload, auto-summary, chat/preview split-pane.
- Every interactive element in Legal Studio has a working handler; the `Auditor` button produces inline audit analysis over selected docs.
- Template Studio previews a learned template with sample output + structural placeholder view, accessible from the templates table and auto-shown after upload.

## 3. Non-Goals

- Rewriting the prompt router or global RAG engine.
- Changing backend audit wizard logic. `Auditor` agent reuses existing risk classifier.
- Desktop (Electron) integration.
- Regulatory Studio or Finance Studio UI changes (other than the Analyst handoff landing page accepting pre-fill params).

## 4. Architecture Overview

Four independent bundles, shipped together but buildable in phases.

```
┌─────────────────── Legal Studio (rebuilt) ───────────────────┐
│                                                              │
│  ┌──────────────┐  ┌────────────────────┐  ┌─────────────┐   │
│  │ SourcesSide  │  │ ChatPane           │  │ PreviewPane │   │
│  │ - upload     │  │ - messages         │  │ - PDF.js    │   │
│  │ - multi-sel  │  │ - mode dropdown    │  │   (collaps) │   │
│  │ - summaries  │  │ - domain chip      │  │             │   │
│  └──────┬───────┘  └──────────┬─────────┘  └──────┬──────┘   │
│         │                      │                   │         │
└─────────┼──────────────────────┼───────────────────┼─────────┘
          │                      │                   │
          ▼                      ▼                   ▼
  ┌──────────────┐       ┌────────────────┐   ┌─────────────┐
  │ Upload +     │       │ Chat API       │   │ Document    │
  │ auto-summary │       │ - classify     │   │ fetch       │
  │              │       │ - mode router: │   │             │
  └──────────────┘       │   Normal       │   └─────────────┘
                         │   DeepResearch │
                         │   Analyst ─────┼──→ Finance Studio
                         │   Auditor      │     handoff
                         └────────────────┘
```

```
┌───────── Template Studio (preview added) ──────────┐
│                                                    │
│  Templates table row → eye icon → TemplatePreview  │
│  Modal (tabs: Sample Output | Structure)           │
│                                                    │
│  Sample Output ── GET /api/templates/{id}/sample-render
│                   → PDF blob (rendered w/ fixture) │
│                                                    │
│  Structure    ── GET /api/templates/{id}/structure │
│                   → placeholder map + page images  │
└────────────────────────────────────────────────────┘
```

## 5. Bundle A — Chat Modes + Domain Classifier

### A.1 Mode Selector UI

- Location: left of send button in `ChatInput`.
- Shape: dropdown pill, `⚡ Normal ▾`.
- Options: `⚡ Normal`, `🔍 Deep Research`, `📊 Analyst`.
- Default: `Normal`.
- Scope: per-message. User's last choice persists within session (sticky default for next message), but each message carries its own mode value.

### A.2 Domain Classifier

**New module:** `backend/core/chat/domain_classifier.py`

```python
class DomainLabel(str, Enum):
    VAT = "vat"
    CORPORATE_TAX = "corporate_tax"
    PEPPOL = "peppol"
    E_INVOICING = "e_invoicing"
    LABOUR = "labour"
    COMMERCIAL = "commercial"
    IFRS = "ifrs"
    GENERAL_LAW = "general_law"

class ClassifierResult(BaseModel):
    domain: DomainLabel
    confidence: float
    alternatives: list[tuple[DomainLabel, float]]  # top-3 including primary

def classify_domain(query: str) -> ClassifierResult: ...
```

- Uses few-shot prompt with UAE-specific anchor examples per domain (minimum 3 per label).
- Prompt lives in `backend/core/chat/prompts/domain_classifier.md`.
- Model: cheap/fast tier (e.g., Haiku 4.5) — classification must not block main response > 500ms.

**Prompt router integration:** `backend/core/chat/prompt_router.py`

- Remove the current `default="law"` fallback.
- Accept `domain: DomainLabel` directly.
- Map 1:1 to existing 9 prompt keys. If `domain=general_law`, use current general-law prompt.

**Chat endpoint:** `backend/api/chat.py`

- `POST /api/chat/send_message` accepts new optional field: `domain_override: Optional[DomainLabel]`.
- Flow:
  1. If `domain_override` present → use it.
  2. Else → call `classify_domain(query)`.
  3. Route to prompt via `prompt_router`.
  4. Return response + classifier result in envelope (so frontend chip can show detected label).

**Frontend domain chip**

- Renders beside/above the outgoing user message bubble: `Domain: VAT ✎`.
- Click → dropdown of all `DomainLabel` values.
- Changing the chip before send adds `domain_override` to the request.
- Once response received, chip is read-only for that message.

### A.3 Mode behavior

| Mode           | Backend path                             | Notes                                       |
| -------------- | ---------------------------------------- | ------------------------------------------- |
| Normal         | existing `POST /api/chat/send_message`   | Unchanged flow, now with classifier result. |
| Deep Research  | `POST /api/chat/research` (Bundle B)     | Opens background job, streams via SSE.      |
| Analyst        | Client-side navigate to Finance Studio   | Passes pre-fill payload via query param.    |

### A.4 Error investigation (action item)

- Reproduce error shown in screenshot #1.
- Identify stack trace / failing endpoint / console message.
- Root-cause + fix in the same PR as Bundle A.
- If error is a symptom of the routing bug itself, document that here and close.

### A.5 Files

| Path                                                                  | Change                        |
| --------------------------------------------------------------------- | ----------------------------- |
| `backend/core/chat/domain_classifier.py`                              | New                           |
| `backend/core/chat/prompts/domain_classifier.md`                      | New                           |
| `backend/core/chat/prompt_router.py`                                  | Remove default, accept enum   |
| `backend/api/chat.py`                                                 | Call classifier, accept override |
| `frontend/src/components/studios/LegalStudio/ChatInput.tsx`           | Mode dropdown + send wiring   |
| `frontend/src/components/studios/LegalStudio/DomainChip.tsx`          | New                           |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`         | Wire mode + override state    |

## 6. Bundle B — Deep Research Mode

### B.1 Flow

1. User picks `Deep Research` + sends.
2. Frontend `POST /api/chat/research` → returns `{job_id}`.
3. Frontend opens SSE: `GET /api/chat/research/{job_id}/stream`.
4. Backend background task runs the orchestrator, emitting events on a per-job queue.
5. On completion, final report saved; SSE closes with `done` event.
6. User can leave + return. `GET /api/chat/research/{job_id}` returns final report for replay.

### B.2 Orchestrator pipeline

`backend/core/chat/deep_research.py`

```python
async def run_research(job_id: str, query: str, source_ids: list[str]) -> None:
    # Step 1: planner
    sub_questions = await plan_query(query)                # emit "plan"
    # Step 2: gather
    sources = []
    for sq in sub_questions:
        rag_hits = await rag_search(sq, source_ids)        # emit "source_found"
        web_hits = await web_fallback_search(sq)           # emit "source_found"
        sources.extend(rag_hits + web_hits)
    # Step 3: synthesize (streaming tokens)
    async for token in synthesize(query, sub_questions, sources):
        emit("token", token)
    # Step 4: persist
    save_research_result(job_id, final_report)
    emit("done")
```

- **No timeout** around the orchestrator (no `asyncio.timeout()`).
- **Uvicorn `keep_alive`** raised to 1200s for research endpoints (via route-specific config or dedicated worker).
- **Model token cap** = model max. Use configured Claude Opus 4.7 or similar top-tier.
- **Web fallback** reuses existing module (no new scraper).

### B.3 Event schema (SSE)

```json
// plan
{"event": "plan", "sub_questions": ["...", "..."]}

// source_found
{"event": "source_found", "title": "...", "url": "...", "rag_id": "..."}

// token (streamed synthesis)
{"event": "token", "text": "..."}

// done
{"event": "done", "report_id": "..."}

// error
{"event": "error", "message": "..."}
```

### B.4 Final report structure

```json
{
  "report_id": "...",
  "query": "...",
  "summary": "3-5 paragraph executive summary",
  "sections": [
    {"sub_question": "...", "answer": "...", "sources": ["...", "..."]}
  ],
  "citations": [{"title": "...", "url": "...", "rag_id": "..."}]
}
```

### B.5 DB schema

New table `research_jobs`:

| Column        | Type      | Notes                                  |
| ------------- | --------- | -------------------------------------- |
| id            | UUID PK   |                                        |
| user_id       | FK        |                                        |
| thread_id     | FK        | Legal chat thread that initiated it    |
| query         | TEXT      |                                        |
| status        | ENUM      | `running`, `completed`, `failed`       |
| plan_json     | JSON      |                                        |
| result_json   | JSON      | Final report (see B.4)                 |
| started_at    | TIMESTAMP |                                        |
| completed_at  | TIMESTAMP |                                        |

### B.6 Save to Sources

- Frontend shows "Save to Sources" button on completed research bubble.
- Action: `POST /api/documents/from-research/{job_id}`
- Backend: generates PDF/Markdown doc from `result_json`, inserts into `documents` with `source='research'` tag.

### B.7 Files

| Path                                                                 | Change |
| -------------------------------------------------------------------- | ------ |
| `backend/core/chat/deep_research.py`                                 | New    |
| `backend/api/chat.py`                                                | Add research endpoints |
| `backend/api/documents.py`                                           | Add `from-research` endpoint |
| `backend/db/models.py`                                               | `research_jobs` table |
| `backend/db/migrations/NNNN_research_jobs.py`                        | New migration |
| `frontend/src/components/studios/LegalStudio/ResearchBubble.tsx`     | New    |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`       | Render research bubble variant |

## 7. Bundle C — Docs + UI Rework

### C.1 Layout

Split-pane: `SourcesSidebar | ChatPane | PreviewPane`.

- SourcesSidebar: ~260px, always visible.
- ChatPane: flex-grow.
- PreviewPane: ~480px, collapsible (default collapsed). Expands when user clicks a doc card.

### C.2 SourcesSidebar

- Upload zone at top: drag-drop or click. Accepts multiple files at once.
- Supported types: PDF, DOCX, XLSX, TXT (reuse `document_processor`).
- Per-file progress chip: `uploading → processing → summarizing → ready`.
- Doc cards: filename, summary line, key-term chips, checkbox for selection, delete button.
- Selected docs count reflected in chat input: `📎 3 docs in context`.

### C.3 Multi-file upload

- Frontend: `POST /api/documents/upload` called once per file in parallel (existing endpoint supports single file; simpler than batch endpoint).
- Backend: no change to upload endpoint. Summary task enqueued after ingestion completes.

### C.4 Auto-summary

- On ingestion complete, queue task `summarize_document(doc_id)`.
- LLM generates:
  - 3-5 line summary (~60 words).
  - 5 key terms as tags (comma-separated).
- Stored in `documents` table:
  - new column `summary TEXT`
  - new column `key_terms JSON` (list of strings)
- Summary shown in card; key terms shown as chips under summary.

### C.5 Chat context wiring

- When ≥1 doc selected in sidebar, backend RAG filters `document_id IN (selected_ids)` scope.
- Frontend passes `selected_document_ids` in chat request body.
- Backend: `rag_engine.search(query, document_ids=selected_document_ids or None)` — when None, full scope.
- Badge visible near chat input: `📎 N docs in context` with tooltip listing names.

### C.6 PreviewPane

- Click doc card → PreviewPane expands, loads doc via PDF.js (PDFs) or text viewer (other types).
- Collapse button returns to hidden state; chat reclaims space.
- Multi-selection: preview shows most recently clicked doc only.

### C.7 Button audit

**Action:** enumerate every `onClick`, `onSubmit`, `onChange` in current Legal Studio tree (`LegalStudio.tsx`, `ChatInput.tsx`, `ChatMessages.tsx`, `SourcePeeker.tsx`). For each, verify:

- Handler is defined and imported.
- Handler calls a real API or sets real state (no placeholder `console.log` or no-op).
- UI feedback on success/failure.

Document result as a checklist in the implementation plan. Known broken items include:
- `Auditor` button (see C.8).
- All source-related action buttons.
- Mode/domain controls (provided by Bundle A).

### C.8 Auditor button

**New behavior:** runs inline audit analysis on currently selected docs, returns structured result in chat.

- Frontend: `Auditor` button disabled when no docs selected; enabled and prominent when ≥1 selected.
- Click → `POST /api/chat/auditor` with `document_ids`.
- Backend: `backend/core/chat/auditor_agent.py` — reuses existing audit wizard risk classifier. Returns:

```json
{
  "risk_flags": [{"severity": "high", "document": "...", "finding": "..."}],
  "anomalies":  [...],
  "compliance_gaps": [...],
  "summary": "..."
}
```

- Frontend: renders as structured chat bubble with collapsible sections per category.

### C.9 Analyst handoff

- User picks `Analyst` mode + sends → client-side:
  1. Save current chat message into Legal thread as pending.
  2. `POST /api/sessions/finance-from-legal` with `{question, thread_id, document_ids}`.
  3. Backend creates a new Finance Studio session, copies doc references (not duplicates), returns `{session_id}`.
  4. Navigate to `/finance-studio?session=<session_id>`.
- Finance Studio landing page recognizes `session` param:
  - Pre-fills question in whatever Finance entry is appropriate.
  - Shows breadcrumb: `← Back to Legal chat (thread title)`.
  - Breadcrumb link: `/legal-studio?thread=<legal_thread_id>`.

### C.10 Files

| Path                                                                        | Change |
| --------------------------------------------------------------------------- | ------ |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`               | Rework to 3-pane layout |
| `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx`            | New    |
| `frontend/src/components/studios/LegalStudio/PreviewPane.tsx`               | New    |
| `frontend/src/components/studios/LegalStudio/ChatInput.tsx`                 | Add context badge, mode dropdown integration |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`              | Audit render variant + domain chip |
| `frontend/src/components/studios/LegalStudio/AuditorResultBubble.tsx`       | New    |
| `backend/core/chat/auditor_agent.py`                                        | New (reuses risk classifier) |
| `backend/api/chat.py`                                                       | `/api/chat/auditor` endpoint |
| `backend/api/documents.py`                                                  | Auto-summary hook |
| `backend/core/documents/summarizer.py`                                      | New (or reuse existing LLM util) |
| `backend/db/models.py`                                                      | `documents.summary`, `documents.key_terms` |
| `backend/db/migrations/NNNN_document_summary.py`                            | New    |
| `backend/api/sessions.py`                                                   | `finance-from-legal` endpoint |

## 8. Bundle D — Template Studio Preview

### D.1 Modal trigger

- Eye icon in each templates table row.
- Auto-open modal after upload completes (user does not have to hunt for the icon).

### D.2 Modal structure

- Header: template name, close button, quick actions (`Send`, `Delete`).
- Two tabs: `Sample Output` (default) | `Structure`.

### D.3 Sample Output tab

- PDF.js viewer showing template rendered against fixture data.
- Fixture lives at `backend/core/templates/sample_fixture.json` — a small, representative dataset used across all templates (TB rows, balance sheet, P&L, company info).
- Backend: `GET /api/templates/{id}/sample-render` → PDF blob.
- Cache rendered PDF by `(template_id, fixture_version)` to avoid re-render on every open.

### D.4 Structure tab

- Page-by-page static image previews (one per template page).
- Placeholder regions overlaid as colored rectangles:
  - `company_name` — blue
  - `tb_row` — green
  - `opinion_text` — purple
  - etc.
- Legend below viewer.
- Backend: `GET /api/templates/{id}/structure` → `{pages: [{image_url, placeholders: [{type, bbox}]}]}`.

### D.5 Fixture data

```json
{
  "company": {"name": "Sample Trading LLC", "trn": "100000000000003", ...},
  "trial_balance": [{"account": "Cash", "debit": 50000, "credit": 0}, ...],
  "balance_sheet": {...},
  "profit_loss": {...},
  "period": "2025"
}
```

Version this file. If shape changes, bump fixture version and invalidate cached PDFs.

### D.6 Files

| Path                                                                                 | Change |
| ------------------------------------------------------------------------------------ | ------ |
| `frontend/src/components/studios/TemplateStudio/TemplatePreviewModal.tsx`            | New    |
| `frontend/src/components/studios/TemplateStudio/TemplateStudio.tsx`                  | Wire eye icon + auto-open |
| `backend/api/templates.py`                                                           | `sample-render`, `structure` endpoints |
| `backend/core/templates/sample_fixture.json`                                         | New    |
| `backend/core/templates/renderer.py`                                                 | `render_sample(template_id)` function + caching |
| `backend/core/templates/structure_analyzer.py`                                       | `extract_placeholders(template_id)` |

## 9. Data Model Changes (summary)

### `documents`
- `summary TEXT NULL`
- `key_terms JSON NULL`
- `source VARCHAR(32) DEFAULT 'upload'` — values: `upload`, `research`, etc.

### `research_jobs` (new)
- See §6.5.

### `chat_messages` (existing; extend)
- `mode VARCHAR(32)` — `normal`, `deep_research`, `analyst`.
- `domain VARCHAR(32)` — classifier result or override.
- `domain_override_by_user BOOLEAN DEFAULT FALSE`.

## 10. API Surface (summary)

| Endpoint                                            | Method | Bundle |
| --------------------------------------------------- | ------ | ------ |
| `/api/chat/send_message`                            | POST   | A      |
| `/api/chat/research`                                | POST   | B      |
| `/api/chat/research/{job_id}`                       | GET    | B      |
| `/api/chat/research/{job_id}/stream`                | GET    | B      |
| `/api/chat/auditor`                                 | POST   | C      |
| `/api/documents/upload`                             | POST   | C (existing) |
| `/api/documents/from-research/{job_id}`             | POST   | B      |
| `/api/sessions/finance-from-legal`                  | POST   | C      |
| `/api/templates/{id}/sample-render`                 | GET    | D      |
| `/api/templates/{id}/structure`                     | GET    | D      |

## 11. Error Handling

- **Domain classifier failure** — fall back to `general_law` and log warning; do not block response.
- **Deep Research orchestrator failure** — mark job `failed`, emit `error` SSE event, preserve partial progress for user review.
- **Auto-summary failure** — doc still usable; summary shows "Summary unavailable" + retry button.
- **Auditor agent failure** — return error bubble with retry.
- **Template render failure** — modal shows error state + "Re-learn template" CTA.

## 12. Testing

- **Domain classifier unit tests** — fixture of ≥ 30 UAE-flavored queries with expected labels; CI threshold ≥ 90% accuracy.
- **Deep Research integration test** — mock orchestrator, verify SSE stream contract, verify job persists.
- **Auditor agent integration test** — reuses audit wizard test fixtures.
- **Button audit checklist** — documented in implementation plan, each item verified manually in browser.
- **Template preview** — snapshot test on fixture → PDF render, assert placeholders populated.

## 13. Implementation Phases

1. **Phase 1 — Bundle A** (mode selector + classifier + domain chip + error fix).
2. **Phase 2 — Bundle B** (Deep Research). Depends on Bundle A mode selector.
3. **Phase 3 — Bundle C** (3-pane layout, multi-upload, auto-summary, button audit, Auditor agent, Analyst handoff). Note: Analyst handoff depends on Finance Studio accepting `session` param — verify early.
4. **Phase 4 — Bundle D** (Template preview). Independent of A/B/C; can run in parallel with any other phase.

## 14. Open Items / Deferred

- Exact text of error in screenshot #1 — investigate during Bundle A implementation.
- Full enumeration of Legal Studio broken buttons — captured during Bundle C implementation phase.
- Research job retention policy — default 90 days; revisit post-launch.
- Fixture data evolution — future spec if templates expand beyond current schema.

## 15. Out of Scope (this spec)

- Chat history search / filtering UI.
- Export of deep-research reports to DOCX.
- Regulatory Studio enhancements.
- Performance tuning for multi-tenant load.
