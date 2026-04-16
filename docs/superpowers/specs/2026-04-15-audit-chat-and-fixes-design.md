# Design Spec: Audit Analysis Chat, Prior Year Extraction & Platform Fixes
**Date:** 2026-04-15  
**Project:** Project_AccountingLegalChatbot  
**Status:** Approved

---

## Overview

This spec covers 6 issues discovered during live testing of the AccountingLegalChatbot platform. Issues 4 and 5 are linked — the structured prior year data extracted in Issue 4 feeds directly into the chat context used in Issue 5.

| # | Issue | Type | Area |
|---|-------|------|------|
| 1 | Source panel click broken in LegalStudio | Bug fix | Frontend |
| 2 | Web search fallback when RAG has no data | New feature | Backend + Frontend |
| 3 | New Report button — move above Saved Reports + redesign | UI improvement | Frontend |
| 4 | Scanned prior year audit PDF not extracting prior year figures | Bug fix + OCR | Backend |
| 5 | Post-audit analysis chat step with agent activation | New feature | Frontend + Backend |
| 6 | Report formatting does not match professional audit format | Quality fix | Backend |

---

## Issue 1 — Source Panel Click Fix

### Problem
In LegalStudio, clicking a source badge in the chat message list does not open the SourcePeeker panel. The `SourcePeeker` component and its display logic are correct.

### Root Cause
`ChatMessages.tsx` renders source badges but the `onSourceClick` callback is not wired through `LegalStudio.tsx` to the state variable that controls `SourcePeeker` visibility (`selectedSource` / `setSelectedSource`).

### Fix
In `LegalStudio.tsx`:
- Pass `onSourceClick={(source) => setSelectedSource(source)}` to `ChatMessages`
- Ensure `selectedSource` state being non-null triggers the `SourcePeeker` panel to render/open

No backend changes required.

---

## Issue 2 — Web Search Fallback + RAG Auto-Save

### Approach
**Option B selected — LLM tool calling.** The LLM receives a `web_search` tool and decides itself when to use it. It is instructed to only answer from the tool's returned content — never from its own prior knowledge when the tool is invoked.

### Backend Changes

**New tool definition added to `llm_manager.py`:**
```
web_search(query: str) -> { results: [{ title, url, snippet, full_text }] }
```
Implementation uses a web search API (e.g. Tavily, SerpAPI, or DuckDuckGo). The LLM is given this tool in the chat system prompt.

**LLM instruction additions in `prompt_router.py`:**
- "If you do not have sufficient information in your knowledge base to answer accurately, use the `web_search` tool."
- "Only answer using the content returned by `web_search`. Do not add information from your training data when using this tool."
- "Take your time. A slower, accurate answer is better than a fast, incorrect one."

**Auto-save to RAG:**
After a successful web search response, the backend automatically ingests the found content into ChromaDB under a `web_search` source type. This means the same question asked again will be answered from RAG without a repeat web search.

**Endpoint change:** `POST /api/chat/send_message` handles the tool-calling loop — calls LLM, detects tool use, executes search, re-calls LLM with results, streams final response.

### Frontend Changes
- Show a `Searching the web...` indicator with a globe icon while the web search tool is executing (SSE event: `status: "searching_web"`)
- Source badges for web-search results show the domain name and a globe icon instead of a document icon
- No other UI changes

---

## Issue 3 — New Report Button Redesign

### Current State
The "New Report" dropdown sits below Saved Reports and renders as a plain flat list of report names with no grouping or visual hierarchy.

### New Design

**Position:** Move to the top of the FinancialStudio sidebar, above the Saved Reports section.

**Component:** Replace the flat dropdown with a `NewReportPanel` component:
- A primary `+ New Report` button (full width, accent color)
- On click: expands an inline panel (not a dropdown) showing report cards grouped by category
- Groups match existing `REPORT_TYPE_CONFIG` categories:

```
TAX & COMPLIANCE
  [Audit Report]  [VAT Return]  [Corporate Tax]  [Compliance Report]

MANAGEMENT
  [MIS Report]  [Financial Analysis]  [Budget vs Actual]

STATUTORY
  [IFRS Financial Statements]  [Cash Flow Statement]

OTHER
  [Custom Report]
```

- Each card: icon + label, hover state with glassmorphism highlight
- Clicking a card: closes the panel, starts that report's wizard (existing behaviour)
- Panel closes on outside click or Escape

**Files affected:** `ContextualSidebar.tsx` (position change), new `NewReportPanel.tsx` component.

---

## Issue 4 — Prior Year Scanned PDF Extraction

### Problem
When a user uploads a scanned prior year audit report PDF in the Company Docs step, the Evidence step shows "Not provided" for all Prior Year values. The current pipeline does not attempt to extract structured financial data from uploaded company documents.

### Approach
**Option C selected — Hybrid: text extraction first, Vision LLM fallback.**

### Backend Pipeline

**New endpoint:** `POST /api/reports/extract-prior-year`
- Accepts: `file` (PDF), `session_id`
- Returns: `{ rows: [...], extraction_method: "text" | "vision", confidence: float }`

**Step 1 — PDF type detection**
Use `pdfplumber` to attempt text extraction on the first financial statement page. If extracted text contains recognisable numeric patterns (amounts with decimals) → use text path. If blank or image-only → use Vision path.

**Step 2a — Text path**
- `pdfplumber` extracts raw text
- `tabula-py` extracts tables with two numeric columns
- Parser identifies rows: `account_name | category | current_year_value | prior_year_value`
- Maps to IFRS standard account categories

**Step 2b — Vision LLM path**
- Convert each relevant PDF page to image (`pdf2image`)
- Send to vision-capable LLM with prompt:
  > "This is a page from a financial audit report. Extract all financial statement tables as structured JSON. For each row output: account_name, category (e.g. Current Assets, Revenue), current_year_value (number or null), prior_year_value (number or null). Return only JSON."
- Parse and validate the JSON response
- Merge results across pages

**Step 3 — Store**
Extracted rows stored in DB against `session_id` as `prior_year_data`. Available to:
- Evidence step (auto-populates Prior Year column)
- Analysis chat context (Issue 5)
- Final report generation (Issue 6)

### Frontend Changes
In Company Docs step (`CompanyDocuments.tsx`):
- Add a clearly labelled **"Prior Year Audit Report"** upload zone (separate from general company docs)
- After upload: spinner with text "Extracting prior year financials…"
- On success: inline preview table showing extracted figures (account name + prior year value)
- User can verify and proceed — no manual entry required
- On failure: message "Could not extract automatically — you can enter prior year figures manually in the Evidence step"

---

## Issue 5 — Post-Audit Analysis Chat Step

### Placement
New Step 8 added to the Audit Report wizard only, inserted between:
- Current Step 7: Draft Report (AuditDraftViewer)
- Current Step 8 (now Step 9): Select Format (AuditFormatSelector)

**New step label:** "Analysis & Discussion"

This step is **optional** — a "Continue to Format →" button is always visible at the bottom. The user can skip it entirely.

### Context Pre-loaded Into Chat
The chat session is initialised with:
- Current year trial balance (mapped + grouped)
- Prior year extracted data (from Issue 4, if uploaded)
- Audit opinion type (unqualified / qualified / disclaimer / adverse)
- Risk flags identified in Evidence step (going concern, related party, large variance, negative equity)
- Company name and reporting period

**Opening AI message:**
> "I've analysed [Company Name]'s financials for [current period] against the prior year. The audit opinion is [opinion type]. What would you like to discuss?"

### Layout — Two-Panel Design

**Left panel (60% width) — Chat interface**
- Streaming chat using existing SSE pattern from LegalStudio
- User can ask any question about the financials (variances, ratios, account movements, risk areas)
- Inline source citations when referencing specific line items
- Chat history persisted with the audit session in DB

**Right panel (40% width) — Quick Analysis Actions**

```
GENERATE A REPORT FROM THIS DATA
[ MIS Report              ]
[ Financial Analysis      ]
[ Budget vs Actual        ]
[ IFRS Financial Statements ]
[ Cash Flow Statement     ]

ADD SUPPORTING SCHEDULES
[ Receivables Aging       ]
[ Payables Aging          ]
```

Panel is extensible — new analysis types can be added without changing the layout.

### Agent Activation Flow

When user clicks a report card (e.g. "Financial Analysis"):
1. Modal opens with prompt: *"What do you need in this Financial Analysis? (e.g. focus on profitability ratios, compare to last year)"*
2. User enters free-text requirements
3. Backend spawns the appropriate report agent using already-mapped trial balance + prior year data — no re-upload
4. Report generated in background, saved to Saved Reports with `draft` status
5. Toast notification: *"Financial Analysis ready — View"*

When user clicks an aging schedule card (e.g. "Receivables Aging"):
1. Modal opens: *"Upload your Accounts Receivable ledger export (Excel or CSV)"*
2. User uploads file
3. Backend generates aging buckets: 0–30 days, 31–60 days, 61–90 days, 90+ days
4. Result saved as a schedule report linked to the current audit session

### Backend Changes
- New endpoint: `POST /api/reports/analysis-chat` — same SSE pattern as `/api/chat/send_message` but accepts `session_context` (trial balance + prior year + flags) as additional system context
- New endpoint: `POST /api/reports/generate-from-session` — accepts `session_id`, `report_type`, `user_requirements`; reuses existing report generation logic with session data pre-injected
- New endpoint: `POST /api/reports/aging-schedule` — accepts file + schedule type (receivable/payable), returns bucketed aging table

### New Frontend Component
`AuditAnalysisStep.tsx` — self-contained, no changes to other wizard steps except adding it at index 7 in `FinancialStudio.tsx`'s step array.

---

## Issue 6 — Report Formatting Fix

### Problem
The generated audit report (Image 10) is a flat Markdown table dump. The target format (Images 11–13) requires:
- **Page 1:** Cover page — company name, location, report title, year ended date
- **Page 2:** Table of contents with section names and page numbers
- **Page 3+:** IFRS-structured financial statements with two-column numeric layout (Current Year AED | Prior Year AED), notes references, bold totals/subtotals

### Approach — DOCX Template Injection

The LLM produces **structured JSON**, not formatted text. The backend's `audit_formatter.py` populates a Word template with that JSON. Content and formatting are fully separated.

### Report JSON Structure (LLM output)
```json
{
  "company_name": "...",
  "location": "Dubai - United Arab Emirates",
  "period_end": "December 31, 2024",
  "opinion_type": "qualified",
  "sections": [
    {
      "title": "Independent Auditors' Report",
      "type": "narrative",
      "content": "..."
    },
    {
      "title": "Statement of Financial Position",
      "type": "financial_table",
      "rows": [
        {
          "account": "Property, plant & equipment",
          "category": "Non-Current Assets",
          "notes_ref": "6",
          "current_year": 1919606,
          "prior_year": 2131198
        }
      ]
    }
  ]
}
```

### Template Structure (`audit_template.docx`)
Pre-built Word template with named paragraph styles:
- `CoverCompanyName` — large bold centered
- `CoverSubtitle` — centered normal
- `TOCEntry` — tab stop at right margin for page numbers
- `SectionHeading` — bold, border-bottom
- `BodyText` — normal narrative paragraphs
- `TableAccountName` — left-aligned
- `TableNotes` — small centered column
- `TableAmount` — right-aligned numeric, AED formatted
- `TableTotal` — bold, top border (accounting underline convention)

### New Backend File
`backend/core/audit_formatter.py`:
- `format_audit_report(report_json: dict) -> bytes` — returns DOCX buffer
- Generates cover page from `company_name`, `location`, `period_end`
- Auto-builds TOC from `sections` array with sequential page estimation
- For `financial_table` sections: inserts a 4-column table (Account | Notes | Current Year | Prior Year) with subtotals bolded
- Returns DOCX bytes → existing export endpoint streams it as download

### Template File Location
`backend/core/templates/audit_template.docx` — committed to repo.

---

## Data Flow Summary (Issues 4 → 5 → 6)

```
Company Docs Step
  └── User uploads prior year PDF
        └── POST /api/reports/extract-prior-year
              └── Hybrid OCR → prior_year_data stored in session

Evidence Step
  └── prior_year_data auto-fills Prior Year column

Draft Step (Step 7)
  └── LLM generates draft with current + prior year figures

Analysis & Discussion Step (NEW Step 8)
  └── Chat pre-loaded with full session context
  └── Agent cards → generate sub-reports or aging schedules from same data

Format Step (Step 9)
  └── User selects output format

Export (Step 10)
  └── audit_formatter.py populates audit_template.docx
  └── Exports as DOCX / PDF with cover page + TOC + formatted statements
```

---

## Files Changed Summary

### Frontend
| File | Change |
|------|--------|
| `LegalStudio.tsx` | Wire `onSourceClick` to `setSelectedSource` (Issue 1) |
| `ChatMessages.tsx` | Confirm `onSourceClick` prop is passed through (Issue 1) |
| `ContextualSidebar.tsx` | Move New Report above Saved Reports (Issue 3) |
| `NewReportPanel.tsx` | New component — grouped report card selector (Issue 3) |
| `CompanyDocuments.tsx` | Add Prior Year PDF upload zone + extraction preview (Issue 4) |
| `FinancialStudio.tsx` | Insert AuditAnalysisStep at wizard index 7 (Issue 5) |
| `AuditAnalysisStep.tsx` | New component — two-panel chat + agent cards (Issue 5) |

### Backend
| File | Change |
|------|--------|
| `llm_manager.py` | Add `web_search` tool definition and tool-calling loop (Issue 2) |
| `prompt_router.py` | Add web search instructions to system prompts (Issue 2) |
| `api/chat.py` | Handle tool-call SSE events, auto-ingest found content to RAG (Issue 2) |
| `api/reports.py` | Add `extract-prior-year`, `analysis-chat`, `generate-from-session`, `aging-schedule` endpoints (Issues 4, 5) |
| `core/audit_formatter.py` | New — DOCX template population from report JSON (Issue 6) |
| `core/templates/audit_template.docx` | New — pre-built Word template with named styles (Issue 6) |
