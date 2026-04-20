# Bug Fix Bundle — April 20 2026

## Scope

7 bugs + enhancements across 4 surfaces: Deep Research, Analyst Mode, Audit Flow, Financial Reports, Notebook List.

Organized as 5 phases. Each phase is a testable surface. All share the chat-redirect questionnaire pattern (Phases 3–4).

---

## Phase 1: Deep Research — Full Answer + Sources + Export

### Problem
- Answer renders incomplete or cut off
- Sources chip not shown after Deep Research response
- Export buttons output unformatted text dump (PDF/Word/Excel)

### Fix: Full Answer Display
SSE stream accumulates all chunks before marking complete. Render full content as markdown. `done` event only fires after all chunks processed.

### Fix: Sources Display
After stream completes, aggregate all `source_documents` from stream events. Deduplicate by `source_file` field.
- Chip shows: `Sources (N files, M citations)`
- Click expands panel: grouped by file, shows cited passage per citation
- Applies to both Normal and Deep Research modes

### Fix: Export — All 3 Formats
Backend route: `POST /api/chat/export-deep-research`
Accepts: `{ content, sources, format }` where format = `pdf | docx | xlsx`

**PDF (branded):**
- Cover page: query as title, date, "Deep Research Report" label
- Auto-generated TOC from markdown headings
- Body: styled headings, tables, paragraphs
- Sources appendix: filename + cited passage per entry
- Renderer: WeasyPrint (existing pipeline)

**Word (DOCX):**
- Same structure as PDF via python-docx
- Cover page, headings, tables, sources section

**Excel (XLSX):**
- Extract markdown tables → separate sheets (one sheet per table)
- If no tables: Sheet 1 = full text in column A, Sheet 2 = Sources (filename, passage)
- Filename: `DeepResearch-{YYYY-MM-DD}.xlsx`

---

## Phase 2: Analyst Mode — xlsx Reading + Domain Routing + Source Count

### Fix A: xlsx / CSV Full Injection (small files)
On document upload, detect `.xlsx` or `.csv` file extension.

**File < 100KB:** Parse with `openpyxl` / `pandas`. Convert to structured text:
```
Sheet: [SheetName]
Row 1: AccountCode=1001, Description=Sales Revenue, Debit=5186636, Credit=0, Balance=5186636
Row 2: AccountCode=1002, Description=Other Income, Debit=2579, Credit=0, Balance=2579
...
```
Header repeated every 20 rows. Full structured text injected into LLM context alongside RAG results.

**File ≥ 100KB:** Existing chunked RAG path.

### Fix B: Domain Auto-Pick + Manual Override
Domain chip auto-classifies per message (existing behavior).
Add override: user clicks domain chip → dropdown shows all domains (Audit, VAT, Legal, General Law, Finance, Corporate Tax).
- Manual selection overrides auto-detect for remainder of session
- Chip shows lock icon 🔒 when manually overridden
- Override cleared when user navigates away or clears chat

### Fix C: Source Count Display
Frontend deduplicates `source_documents` by `source_file` field for file count. Citation count = raw chunk count.
Display: `Sources (4 files, 8 citations)`
Click panel: grouped by file → shows cited passages per file.

---

## Phase 3: Audit Flow Rework

### Fix: Run Audit Error Handling (Bug #3)
Wrap audit generation in try/catch. On failure:
- Inline error card in chat: shows error message + Retry button
- Retry re-runs same checked sources
- Log error to browser console for debugging

### Fix: Sources + Chat Persist on Navigation (Bug #4)
On every source add/remove/check: save checked source IDs to notebook record in DB.
On notebook open: restore checked sources and chat history from DB.
Sources and chat history survive navigation, page refresh, re-open.

### New Flow: Auditor Format → Conversational Questionnaire (all formats)
Clicking any format button (Standard / Big 4 / Legal Brief / Compliance / Custom Template):
1. Chat area activates
2. AI sends message: "Generating [Format] Audit Report. Let me confirm a few details first..."
3. AI pre-fills from uploaded docs:
   - **Period**: extracted from TB/FS date fields
   - **Entity name**: from license or FS header
   - **Entity type**: LLC / Free Zone / Branch (from license)
   - **Currency**: from TB
   - **Reporting framework**: IFRS / IFRS for SMEs (from FS notes)
   - **Standalone vs Comparative**: detected from FS structure
   - **Materiality threshold**: calculated as 2% of revenue or total assets
   - **Engagement type**: statutory / internal / review (inferred from docs)
4. AI presents as one confirmation message. User corrects/adds missing fields in chat.
5. "Generate Audit" button appears as chat message when all fields confirmed.
6. Click → audit runs → result rendered as inline card in chat.

### Audit Inline Card (Bug #5 layout)
Audit result = special card in chat stream, not a side panel.
Card sections: Risk Flags, Anomalies, Compliance Gaps (collapsible).
Export button on card: PDF / Word / Excel (same branded format as Phase 1).
Chat remains scrollable above and below card.

### Custom Template Auditor (Bug #5 missing option)
Add "Custom Template" as 5th option in Auditor Format panel (after Compliance).
Click → modal opens showing user's Template Learning Studio saved templates.
User selects template → name shown as active in sidebar.
Questionnaire flow identical to other formats. Template ID passed to backend with generation request.

### Upload After Audit
After audit card renders, source panel remains active.
User can add/remove sources. Re-run available via Auditor Format panel.

---

## Phase 4: Financial Reports — Chat-Redirect Pattern

All report buttons in Financial Reports sidebar redirect to chat questionnaire.

### Common Fields (AI pre-fills from docs for all reports)
- Period (from TB / FS dates)
- Entity name
- Currency
- Reporting framework

### Report-Specific Fields

| Report | Extra Fields |
|--------|-------------|
| P&L Statement | Standalone vs Comparative, IFRS vs local GAAP |
| Balance Sheet | Standalone vs Comparative, IFRS vs local GAAP |
| Cash Flow | Direct vs Indirect method |
| MIS Report | Department filter, KPI selection |
| VAT Return | Quarter, Input/Output split verification |
| Corporate Tax | Fiscal year, Free Zone status, Related party flag |
| Budget vs Actual | Budget source (upload or manual), Variance threshold % |
| Forecasting | Horizon (3/6/12 months), Scenario count |
| IFRS Statements | Full set vs partial, Comparative period |
| Board Report | Audience (internal/external), Risk appetite |
| Custom Report | Free-form prompt: user describes what to generate |

### Flow
1. User clicks report in right sidebar
2. Chat activates with AI pre-filled confirmation message
3. User corrects/adds fields in chat
4. "Generate [Report Name]" button appears as chat message
5. Click → report renders as inline card with Export PDF / Word / Excel

### Error Handling
Generation failure → inline error card with message + Retry button.

---

## Phase 5: Notebook List UX (Legal Studio)

### Layout
- "Create New Notebook" card = first position (top-left of grid)
- View toggle: Grid | List
  - Grid: current card layout (updated with gradient thumbnails)
  - List: compact rows — title, date, source count, action icons

### Thumbnails
Replace generic page icon. Gradient auto-generated from title string hash → consistent color pair per notebook. Title text overlaid. Computed on create, stored with notebook or recomputed client-side from title.

### Search
Search input at top of notebook list. Client-side filter on title. Real-time.
Empty state: "No notebooks match '[query]'"

### Delete
Hover on notebook card → trash icon appears (top-right corner).
Click → confirmation modal: "Delete [notebook title]? This cannot be undone."
Confirm → delete notebook + all sources + chat history from DB.

---

## Shared Patterns

### Chat-Redirect Questionnaire (Phases 3 + 4)
Used by: all Auditor Formats + all Financial Report buttons.

Pattern:
1. Click button in sidebar → no modal, no right-panel redirect
2. Chat area activates with AI questionnaire message
3. AI pre-fills from docs, presents as editable confirmation
4. User answers/confirms in chat
5. Generate button appears as chat message
6. Result = inline card in chat

### Inline Result Card
Used by: Audit Report, all Financial Reports, Deep Research (export).

Card structure:
- Header: report type + date + format tag
- Body: report content with collapsible sections
- Footer: Export PDF | Export Word | Export Excel buttons

### Export Format — Branded (Phase 1 + inline cards)
Cover page → TOC → body → sources/appendix. Consistent across all report exports.

---

## Out of Scope
- Template Learning Studio internal functionality changes (upload/learn flow unchanged)
- Backend LLM provider changes
- New report types not listed above
- Mobile / Electron app changes
