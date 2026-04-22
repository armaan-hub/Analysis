# Chatbot Bug Fixes & Feature Design
**Date:** 2026-04-22  
**Status:** Approved for implementation  
**Priority order:** Issue 4 (P1) → Issue 2 (P1) → Issue 3 (P2) → Issue 6 (P2) → Issue 1 (P3) → Issue 5 (P4)

---

## Issue 1 — Multi-select Non-functional + Chat Thumbnails Show Initials

### Root Causes
1. `HomePage.tsx` line 217: click handler calls `handleOpen(id)` even when `selectionMode` is active — never calls `onToggleSelect`.
2. `NotebookCard.tsx` renders `titleInitials()` for the thumbnail unconditionally; `DOMAIN_ICONS` map at lines 13–24 is defined but never used in the thumbnail element.

### Fix

**`frontend/src/pages/HomePage.tsx`**
- Change the card click handler to: `selectionMode ? onToggleSelect?.(id) : handleOpen(id)`

**`frontend/src/components/common/NotebookCard.tsx`**
- In the thumbnail render, look up `DOMAIN_ICONS[domain]` first; fall back to `titleInitials()` only if no icon is found.
- Example: `const thumb = DOMAIN_ICONS[domain] ?? titleInitials(title)`

---

## Issue 2 — Deep Research: Missing Endpoint, UUID Source Names, Not in History

### Root Causes
1. `useDeepResearch.ts` calls `POST /api/chat/deep-research` — this endpoint **does not exist** (404 always). Deep Research has never worked.
2. RAG metadata stores UUID as `source`, not `original_name`. When history reloads, `filename = id (UUID)`. `useDocumentResolver.ts` hook exists but is **not applied** in `ChatMessages` or `SourcesSidebar`.
3. Deep Research conversations are not saved to the conversations table (no `conversation_id` assigned before streaming).

### Fix

#### 2A — New `/api/chat/deep-research` SSE Endpoint
Create a dedicated streaming endpoint in `backend/api/chat.py`:

```
POST /api/chat/deep-research
Request: { conversation_id: str | None, query: str, selected_doc_ids: list[str] }
Response: SSE stream of events:
  { type: "step",   content: "Searching documents…" }
  { type: "step",   content: "Synthesising findings…" }
  { type: "answer", content: "<markdown answer>" }
  { type: "sources", sources: [{ id, original_name, page, score }] }
  { type: "done" }
  { type: "error",  message: "…" }
```

**Pipeline inside the endpoint:**
1. Hybrid RAG search (see Issue 6) with `selected_doc_ids` filter — emit `step` events as each stage runs.
2. Build a research prompt using the CA auditor system prompt + retrieved chunks + explicit instruction: *"Synthesise all retrieved evidence. Cite every finding. Do not fabricate."*
3. Stream LLM response as the `answer` event.
4. Save conversation + assistant message to DB (create `conversation_id` if none provided).
5. Return `sources` from retrieved chunks (using `original_name`, not UUID).

#### 2B — Original Filenames in Sources Everywhere
- Add `original_name` to every RAG chunk's metadata at index time (in `backend/core/rag/indexer.py` or equivalent).
- Apply `useDocumentResolver` hook in both `ChatMessages.tsx` and `SourcesSidebar.tsx` to batch-resolve any UUID `source` fields to `original_name` on load.
- In `SourcesSidebar`: display `original_name (page N)` — never show UUIDs to the user.

#### 2C — Deep Research Chats in History
- `useDeepResearch` must send `conversation_id` in the request.
- If `conversation_id` is null (new chat), the endpoint creates one and returns it in the `done` event.
- Frontend stores the returned `conversation_id` in state so the chat persists in the sidebar.
- History sidebar `mode` tag: show `"deep research"` badge for conversations where `mode = "deep_research"`.

#### 2D — No Brave Search Key
No `BRAVE_SEARCH_API_KEY` is present in `.env`. Web search fallback is skipped. The `answer` event must state: *"Web search not configured — results are from uploaded documents only."* This message is shown inline in the Deep Research answer header.

---

## Issue 3 — Analyst Mode: Ignores Selected Documents + Audit Panel in Wrong Location

### Root Causes
1. `LegalStudio.tsx` `sendMessage` (lines 563–571) does NOT include `selected_doc_ids` in the chat request body — backend can't filter RAG to selected documents.
2. `ChatRequest` schema in `backend/api/chat.py` has no `selected_doc_ids` field.
3. Audit results are rendered as `InlineResultCard` in the CENTER panel; `ArtifactPanel` (right pane) is wired into `ThreePaneLayout` but `artifactOpen` is never set `true` when an audit finishes.
4. `ANALYST_SYSTEM_PREFIX` is defined twice in `prompt_router.py` (lines 14 and 46 — identical dead code at line 14).

### Fix

#### 3A — Pass Selected Documents to Backend
- Add `selected_doc_ids: list[str] | None` to `ChatRequest` schema.
- In `sendMessage` (LegalStudio), include `selected_doc_ids: selectedDocIds` in the request body.
- In backend `chat.py` route: pass `selected_doc_ids` to the RAG retrieval call so context is scoped to selected documents only.

#### 3B — Audit Results → Right ArtifactPanel
- When `mode === "analyst"` and the backend returns `{ type: "audit_result", ... }` in the SSE stream, set `setArtifactOpen(true)` and set `artifactContent` to the audit result.
- Remove the `InlineResultCard` render in the center panel for audit results.
- The `ArtifactPanel` already accepts a `content` prop — pass the structured audit JSON there.
- `ArtifactPanel` renders audit findings in a collapsible risk-rated table (🔴🟠🟡🟢).

#### 3C — Dead Code Cleanup
- Remove duplicate `ANALYST_SYSTEM_PREFIX` at line 14 of `prompt_router.py`.

---

## Issue 4 (P1 CRITICAL) — All Report Types: Intelligence Layer, Templates, Format, Period

### Root Causes
1. `generate-stream` endpoint uses only `REPORT_SYSTEM_PROMPTS[report_type]` — a 3-line generic prompt with no audience, no key-points mandate, no structure.
2. `_FORMAT_PROMPTS` (Big4/ISA/FTA/Internal instructions, line 619) is **only used by `/api/reports/format`**, not by `/api/reports/generate-stream`.
3. Period in user message is ignored — LLM defaults to training-data year.
4. All 12 `ReportConfig` entries in `reportConfigs.ts` have duplicate property entries (copy-paste bug).
5. `ReportConfig` interface has no `audience`, `purpose`, or `keyPoints` fields.
6. No structural template examples to guide LLM format.

### Fix

#### 4A — Report Intelligence Layer (Backend)
Create `backend/core/report_templates/report_intel.py` with a `REPORT_INTEL: dict[str, dict]` constant:

```python
REPORT_INTEL = {
  "financial_analysis": {
    "audience": "CFO and Senior Management",
    "purpose": "Provide a full Profit & Loss analysis with trend commentary and anomaly detection",
    "key_points": [
      "Revenue breakdown by segment/geography",
      "Gross margin % and trend",
      "EBITDA margin % and trend",
      "Net profit margin % and YoY change",
      "Top 5 expense drivers with commentary",
      "Significant anomalies or one-off items",
    ],
    "mandatory_sections": ["Executive Summary", "Revenue Analysis", "Cost Analysis",
                           "Profitability Ratios", "YoY Comparison", "Key Findings & Recommendations"],
  },
  "ifrs": {
    "audience": "External Auditors, Shareholders, and Regulators",
    "purpose": "Present IFRS-compliant Balance Sheet with ratio analysis and disclosure notes",
    "key_points": [
      "Current ratio and quick ratio",
      "Debt-to-equity ratio",
      "Working capital position",
      "Inventory days and receivable days",
      "IAS 1 compliance checklist",
      "Significant accounting policies",
    ],
    "mandatory_sections": ["Statement of Financial Position", "Accounting Policies",
                           "Ratio Analysis", "Comparative Period", "IAS 1 Disclosures"],
  },
  "cash_flow": {
    "audience": "CFO, Board of Directors, and Bankers",
    "purpose": "Analyse cash generation, liquidity, and capital allocation per IAS 7",
    "key_points": [
      "Net cash from operating activities",
      "Free cash flow (Operating - Capex)",
      "Net debt movement",
      "Significant non-cash items",
      "IAS 7 indirect method reconciliation",
    ],
    "mandatory_sections": ["Operating Activities", "Investing Activities",
                           "Financing Activities", "Free Cash Flow Summary", "Liquidity Commentary"],
  },
  "mis": {
    "audience": "Board of Directors and Senior Management",
    "purpose": "Management Information System report — KPI dashboard with variance and risk flags",
    "key_points": [
      "Department-wise P&L summary",
      "Revenue vs budget variance % (Favorable/Adverse)",
      "Top 5 KPIs with RAG (Red/Amber/Green) status",
      "Month-on-month and YTD trends",
      "Risks and exceptions requiring Board attention",
    ],
    "mandatory_sections": ["Executive Dashboard", "KPI Scorecard", "Departmental P&L",
                           "Budget vs Actual", "Risk & Exception Report"],
  },
  "budget_vs_actual": {
    "audience": "CFO and Department Heads",
    "purpose": "Line-by-line budget variance analysis with root cause and corrective action",
    "key_points": [
      "Variance in AED and % per line item",
      "Favorable (F) vs Adverse (A) flags",
      "Root cause explanation for variances > 10%",
      "Corrective actions proposed",
      "Cumulative YTD variance",
    ],
    "mandatory_sections": ["Summary Variance Table", "Revenue Variances",
                           "Cost Variances", "Root Cause Analysis", "Corrective Actions"],
  },
  "forecast": {
    "audience": "Board of Directors, Investors, and Bankers",
    "purpose": "Forward-looking financial forecast with scenarios and key assumptions",
    "key_points": [
      "Base / Bull / Bear scenarios",
      "Key assumptions table (growth rate, FX, headcount)",
      "12-month rolling P&L projection",
      "Sensitivity analysis on top 3 variables",
      "Comparison to last forecast/budget",
    ],
    "mandatory_sections": ["Assumptions", "Base Case Forecast", "Scenario Analysis",
                           "Sensitivity Analysis", "Risks to Forecast"],
  },
  "vat": {
    "audience": "FTA Auditors and Tax Manager",
    "purpose": "UAE VAT-201 return analysis with GL reconciliation and filing position",
    "key_points": [
      "Box-by-box VAT-201 analysis (Box 1–18)",
      "Output VAT by emirate (Emiratisation breakdown)",
      "Input VAT recovery and partial exemption",
      "Reverse charge mechanism entries",
      "GL to VAT return reconciliation",
      "Late registration or compliance risks",
    ],
    "mandatory_sections": ["VAT-201 Summary", "Output Tax Analysis", "Input Tax Recovery",
                           "Reverse Charge", "GL Reconciliation", "Compliance Observations"],
  },
  "corporate_tax": {
    "audience": "FTA, Tax Consultant, and CFO",
    "purpose": "UAE Corporate Tax computation and compliance analysis at 9%",
    "key_points": [
      "Accounting profit to taxable income bridge",
      "Disallowed expenses per CT Law",
      "Exempt income (dividends, qualifying gains)",
      "Small Business Relief eligibility check (< AED 3M)",
      "CT payable at 9%",
      "Transfer pricing considerations",
    ],
    "mandatory_sections": ["Tax Computation", "Disallowed Expenses", "Exempt Income",
                           "Small Business Relief", "CT Payable", "Compliance Calendar"],
  },
  "audit": {
    "audience": "External Auditors, Board of Directors, and Shareholders",
    "purpose": "ISA-compliant audit report with Key Audit Matters and risk-rated findings",
    "key_points": [
      "Minimum 3 Key Audit Matters (ISA 701)",
      "Going concern assessment (ISA 570)",
      "Audit opinion type (Unmodified / Modified per ISA 700/705)",
      "Emphasis of Matter paragraphs (ISA 706)",
      "Risk-rated findings: Critical🔴 High🟠 Medium🟡 Low🟢",
      "Management responses to findings",
    ],
    "mandatory_sections": ["Independent Auditor's Report", "Key Audit Matters",
                           "Going Concern", "Audit Findings", "Management Responses",
                           "Summary Opinion"],
  },
  "compliance": {
    "audience": "Board of Directors and Regulators",
    "purpose": "Regulatory compliance gap analysis across UAE financial and corporate laws",
    "key_points": [
      "VAT compliance status",
      "Corporate Tax registration and filing status",
      "AML/CFT obligations",
      "Labour Law compliance (WPS, gratuity)",
      "DIFC/ADGM regulatory requirements (if applicable)",
      "Gap analysis with risk ratings",
      "Remediation timeline",
    ],
    "mandatory_sections": ["Regulatory Checklist", "Compliance Gap Analysis",
                           "Risk-Rated Findings", "Remediation Plan", "Board Attestation"],
  },
  "custom": {
    "audience": "As specified by the user in the report description",
    "purpose": "Custom report — structure and key points defined by user input",
    "key_points": ["Extract key financial metrics relevant to the requested analysis",
                   "Structure sections based on user-defined requirements",
                   "Apply appropriate UAE regulatory context"],
    "mandatory_sections": ["Executive Summary", "Analysis", "Findings", "Recommendations"],
  },
  "summary": {
    "audience": "Senior Management",
    "purpose": "High-level financial summary for quick executive consumption",
    "key_points": [
      "Top-line revenue, profit, and cash position",
      "Key ratio snapshot",
      "3 main risks or opportunities",
    ],
    "mandatory_sections": ["Financial Snapshot", "Key Ratios", "Risks & Opportunities"],
  },
}
```

#### 4B — Richer System Prompt in `generate-stream`
In `backend/api/reports.py`, update the `generate-stream` endpoint to build the system prompt dynamically:

```python
intel = REPORT_INTEL.get(req.report_type, REPORT_INTEL["custom"])
format_instructions = _FORMAT_PROMPTS.get(req.auditor_format, "")

system_prompt = f"""
You are a Senior {req.auditor_format or 'Professional'} accountant and financial analyst.

REPORT TYPE: {req.report_type.upper()}
AUDIENCE: {intel['audience']}
PURPOSE: {intel['purpose']}

MANDATORY SECTIONS (include ALL, in this order):
{chr(10).join(f"  {i+1}. {s}" for i, s in enumerate(intel['mandatory_sections']))}

KEY POINTS YOU MUST EXTRACT AND ANALYSE (every point must appear in the report):
{chr(10).join(f"  • {kp}" for kp in intel['key_points'])}

FORMAT STANDARD — {req.auditor_format or 'Professional'}:
{format_instructions}

CRITICAL PERIOD ENFORCEMENT:
This report is for the financial period: {req.period_end or req.year or 'as specified in the documents'}.
EVERY figure, date, and reference MUST belong to this period.
If the uploaded documents do not contain data for this period, state this explicitly.
Fabricating figures for any other year is strictly prohibited.

REFERENCE TEMPLATE:
{template_content}  # loaded by TemplateManager.get(report_type, auditor_format) — see section 4C

General rules:
- Use AED as currency unless documents specify otherwise.
- Apply UAE regulatory context (VAT Law, CT Law, CBUAE, DFSA as applicable).
- Every numerical claim must be sourced from the uploaded documents.
- State clearly when a finding is inferred vs directly evidenced.
"""
```

Apply the same enhanced system prompt to the `/api/reports/generate/{report_type}` endpoint for consistency.

#### 4C — Public Template Library (Backend)
Create `backend/core/report_templates/template_manager.py`:

**Template sources (public, freely available):**

| Format | Source | Content |
|--------|--------|---------|
| IAASB ISA 700/701 Auditor's Report | iaasb.org illustrative reports | KAM wording, opinion paragraphs, going concern |
| Big4-style Financial Statements | ACCA/ICAI public illustrative financials | P&L, Balance Sheet, Cash Flow layout |
| UAE VAT Return (VAT-201) | FTA UAE public guidance (tax.gov.ae) | Box headings, field definitions, filing structure |
| UAE Corporate Tax | FTA CT public user guide | CT computation, 9% rate, exempt income treatment |
| MIS / Board Report | Pre-bundled JSON template (CIMA-inspired) | KPI dashboard, executive summary, variance table |

**Implementation:**
- Templates are downloaded once and cached as structured markdown in `backend/core/report_templates/cache/{format}_{report_type}.md`.
- `TemplateManager.get(report_type, auditor_format)` → returns cached template markdown.
- Fallback: if no template found, returns `""` (empty string — system prompt still works without it).
- New endpoint: `POST /api/reports/refresh-templates` — re-downloads and re-caches all templates; returns `{ refreshed: int, failed: list[str] }`.
- Templates are versioned by date header; `template_manager` skips re-download if cache is < 30 days old.

**Injection in system prompt:**  
Template content is labelled clearly: `# REFERENCE TEMPLATE — FOLLOW THIS STRUCTURE EXACTLY (do not copy text — use as structural guide only)`.

#### 4D — Frontend ReportConfig Expansion
**`frontend/src/components/studios/LegalStudio/reportConfigs.ts`**
- Fix all duplicate property entries (copy-paste bug across all 12 configs).
- Extend `ReportConfig` interface:
  ```ts
  interface ReportConfig {
    // existing fields...
    audience: string;
    purpose: string;
    keyPoints: string[];
  }
  ```
- Populate `audience`, `purpose`, `keyPoints` for all 12 report types (matching `REPORT_INTEL` above).
- Display `audience` as a small info pill in `ConfirmReportCard` so user sees who the report is for before generating.

#### 4E — Report Panel Scroll Fix
- `ThreePaneLayout.tsx`: right pane wrapper → add `overflow-y: auto; height: 100%; min-height: 0`.
- `ArtifactPanel.tsx`: outer container → `display: flex; flex-direction: column; height: 100%`; inner body → `flex: 1; overflow-y: auto`.

#### 4F — Frontend "Refresh Templates" in Settings
- Add a "Refresh Report Templates" button on the Settings page.
- Calls `POST /api/reports/refresh-templates`; shows spinner then toast: `"Refreshed N templates"`.

---

## Issue 5 (P4 — Low) — Light Mode Text Invisible

### Root Cause
Components use CSS variables `--s-bg`, `--s-text`, `--s-border`, `--s-accent`, `--s-card` etc. These `--s-*` variables are **never defined** in `index.css` or `App.css`. In dark mode they fall back to hardcoded dark values. In light mode there are no `[data-theme="light"]` overrides for `--s-*` — text becomes invisible.

### Fix
In `frontend/src/index.css`:
1. Define all `--s-*` variables in `:root` (dark mode defaults matching current dark hardcoded values).
2. Add `[data-theme="light"]` block with light overrides for every `--s-*` variable:
   ```css
   :root {
     --s-bg:     #1e1e2e;
     --s-card:   #252535;
     --s-border: #3a3a5c;
     --s-text:   #e2e8f0;
     --s-text2:  #94a3b8;
     --s-accent: #7c6af7;
   }
   [data-theme="light"] {
     --s-bg:     #f8fafc;
     --s-card:   #ffffff;
     --s-border: #e2e8f0;
     --s-text:   #1e293b;
     --s-text2:  #64748b;
     --s-accent: #6d28d9;
   }
   ```
3. Do a grep for any remaining hardcoded hex colours in component files that should use `--s-*` variables and replace them.

---

## Issue 6 (P2) — RAG Deduplication + Hybrid Vector + Graph RAG

### Root Causes
1. Same PDF uploaded multiple times → multiple UUID `Document` records → duplicate chunks in vector store → bloated search results, redundant sources.
2. No `content_hash` column on `Document` model to detect duplicates.
3. Plain vector similarity only; no structural/relational traversal.

### Fix

#### 6A — SHA-256 Deduplication on Upload
In `backend/api/documents.py` upload handler:
1. Compute `sha256` of the uploaded file bytes.
2. Query `Document` table for existing record with same `content_hash`.
3. If found: return the existing document record (no re-index). Response body unchanged (still returns `UploadResponse` with `document` field).
4. If not found: proceed with normal indexing, store `content_hash` on the new `Document` row.
5. Migration: add `content_hash VARCHAR(64) NULL` to `documents` table (nullable for backwards compat).

#### 6B — Graph RAG with NetworkX
Create `backend/core/rag/graph_rag.py`:
- At index time, extract entities and relationships from each chunk using the LLM (one-shot extraction prompt) and store to the existing SQLite `entities` table.
- Build an in-memory `networkx.DiGraph` on first query (lazy-loaded, cached per process).
- `graph_search(query_entities, top_k)` → returns chunks reachable within 2 hops from query entities.

#### 6C — Hybrid Retrieval
Create `backend/core/rag/hybrid_retriever.py`:
```python
def hybrid_retrieve(query, doc_ids, top_k=20):
    vec_results = vector_search(query, doc_ids, top_k=top_k)
    graph_results = graph_search(extract_entities(query), doc_ids, top_k=top_k//2)
    merged = deduplicate_by_source_page(vec_results + graph_results)
    return rerank(merged, query)[:top_k]
```
- Deduplication key: `(original_name, page_number)` — same page from same file is never returned twice.
- Reranking: simple cross-encoder score or cosine similarity tie-break.

#### 6D — Apply Hybrid Retriever
Replace plain vector search calls in:
- `/api/chat/send` (normal chat RAG path)
- `/api/chat/deep-research` (new endpoint — see Issue 2)
- `/api/reports/generate-stream`

---

## Summary of File Changes

| File | Changes |
|------|---------|
| `frontend/src/pages/HomePage.tsx` | Multi-select click fix |
| `frontend/src/components/common/NotebookCard.tsx` | Use `DOMAIN_ICONS` in thumbnail |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Pass `selected_doc_ids`; audit → ArtifactPanel |
| `frontend/src/components/studios/LegalStudio/reportConfigs.ts` | Add audience/purpose/keyPoints; fix duplicates |
| `frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx` | Scroll fix |
| `frontend/src/components/ThreePaneLayout.tsx` | Right pane overflow fix |
| `frontend/src/hooks/useDeepResearch.ts` | Point to new endpoint; handle `conversation_id` return |
| `frontend/src/hooks/useDocumentResolver.ts` | Apply in `ChatMessages` and `SourcesSidebar` |
| `frontend/src/index.css` | Define + override all `--s-*` CSS variables |
| `backend/api/chat.py` | Add `selected_doc_ids` to `ChatRequest`; add `/deep-research` endpoint |
| `backend/api/reports.py` | Rich system prompt in `generate-stream`; `/refresh-templates` endpoint |
| `backend/api/documents.py` | SHA-256 dedup on upload |
| `backend/core/prompt_router.py` | Remove duplicate `ANALYST_SYSTEM_PREFIX` |
| `backend/core/rag/hybrid_retriever.py` | New — hybrid vector+graph retrieval |
| `backend/core/rag/graph_rag.py` | New — NetworkX graph extraction + search |
| `backend/core/report_templates/report_intel.py` | New — audience + key points per report type |
| `backend/core/report_templates/template_manager.py` | New — download, cache, refresh public templates |
| DB migration | Add `content_hash` column to `documents` table |
