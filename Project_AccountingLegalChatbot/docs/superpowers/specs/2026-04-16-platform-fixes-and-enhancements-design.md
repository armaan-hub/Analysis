# Platform Fixes & Enhancements — Design Spec
**Date:** 2026-04-16  
**Status:** Approved for implementation  
**Scope:** 15 bugs and features across chat intelligence, PDF/OCR pipeline, financial report engine, and export

---

## Background

Six issues were observed in live testing plus three new features requested. After reading the full codebase the root causes are confirmed and this spec covers every fix end-to-end so this area does not need revisiting.

---

## Area 1 — Chat Intelligence Layer

Covers: within-session memory, cross-session memory, Pro-Tip removal, research mode, download export, source chips, rich response formatting.

### 1.1 Within-Session Memory (sliding window + compression)

**Current problem:** `chat.py` line 122 caps conversation history at 8 messages. The LLM forgets the beginning of a conversation after 8 turns.

**Fix:** Increase hard cap to 20 messages. When a conversation exceeds 20 messages, compress all messages older than the most-recent 14 into a single "Prior Context Summary" using a lightweight LLM call (max 400 tokens). Inject this summary as the first user turn in the messages list, before the 14 recent messages. This keeps the token budget bounded while preserving full context.

**Implementation:**
- New helper function `compress_history(messages: list[dict]) -> str` in `chat.py`
- Called only when `len(history) > 20`
- Summary stored as `Message(role="system", content="[CONTEXT SUMMARY] ...")` in DB so it is not re-computed on the next turn. The `role` value "system" is used here to ensure it is injected at the top of the message list before history, not treated as a user/assistant turn.
- History fetch query updated to check for an existing summary and prepend it

### 1.2 Cross-Session Persistent Memory

**Current problem:** Each new conversation starts with no knowledge of prior sessions.

**Fix:** New `UserMemory` DB table. When a conversation's last message is more than 30 minutes old (checked on next conversation creation), a background `asyncio.create_task` runs a single LLM call over that conversation's messages to extract key facts:
- Company name, company type, industry
- Topics the user frequently asks about
- Preferences (detail level, language style)
- Important numbers or dates mentioned (e.g. "VAT TRN is 100123456789")

These facts are stored as individual rows: `{user_id, key, value, source_conversation_id, created_at}`.

At the start of each new conversation, the 10 most-recent memory rows are retrieved and injected into the system prompt as a "What we know about this user" block.

**DB schema:**
```sql
CREATE TABLE user_memory (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,       -- future-proof; use "default" for single-user mode
    key TEXT NOT NULL,           -- e.g. "company_name", "vat_trn", "preferred_detail"
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source_conversation_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Memory extraction prompt** (called at conversation end):
```
Review this conversation and extract factual details worth remembering for future sessions.
Return JSON array: [{"key": "...", "value": "...", "confidence": 0.0-1.0}]
Only extract facts explicitly stated. Do not invent. Max 8 items.
```

**Injection into system prompt:**
```
[Memory from prior sessions]
- company_name: Castles Plaza Real Estate L.L.C
- industry: Real estate (Dubai)
- vat_trn: 100123456789
```

### 1.3 Pro-Tip Removal

**Current problem:** `rag_engine.py` SYSTEM_PROMPT instructs the LLM to "Flag when information might be outdated or needs verification." This causes the LLM to append "Pro-Tip: Consult with a licensed UAE lawyer or accountant..." after every response.

**Fix:** Remove the flagging instruction from SYSTEM_PROMPT. The tool is a professional product — it should answer authoritatively. Replace with: "Be precise with numbers, dates, and regulatory references."

### 1.4 Research Mode (Deep Multi-Query Web Search)

**Current problem:** Web search fires one query only, returns 5 results, takes ~2 seconds. User wants a "research mode" that does extended multi-source search when the question contains research-type keywords.

**Trigger keywords:** `research`, `deep analysis`, `analyze`, `investigate`, `comprehensive`, `detailed report`, `full breakdown`, `explain in detail`, `in-depth`

**Behavior when triggered:**
1. Emit SSE event: `{"type":"status","status":"researching","message":"Deep research in progress..."}`
2. Generate 5–8 sub-queries from the original question using a fast LLM call (e.g., break "research UAE VAT e-invoicing" into queries for regulations, exemptions, PEPPOL, FTA guidance, recent updates, penalties)
3. Run all sub-queries in parallel via `asyncio.gather` using `search_web()`
4. Deduplicate results by URL
5. Take top 15 unique results sorted by relevance
6. Emit: `{"type":"status","status":"research_done","sources_found": 15}`
7. Feed all 15 results to LLM with instruction to synthesize, cite sources inline, and structure the response with numbered sections

**Implementation files:**
- `core/web_search.py`: add `async def deep_search(query: str, max_queries: int = 8) -> list[dict]` 
- `api/chat.py`: add `_is_research_query(message: str) -> bool` keyword detector; replace single web search with `deep_search()` when triggered

**Timing:** The LLM synthesis step may take 60–120 seconds for complex topics. The frontend must handle this with a visible "Researching..." spinner that does not time out.

### 1.5 Download Chat Responses (Word / PDF / Excel)

**Current problem:** No export functionality exists.

**Backend — new endpoint:**
```
POST /api/chat/export
Body: { message_id: str, format: "word" | "pdf" | "excel" }
Returns: file stream with appropriate Content-Type
```

**Conversion logic:**
- **Word (.docx):** Parse markdown content → `python-docx`. Bold headings, tables, bullet lists preserved.
- **PDF:** Convert markdown → HTML (using `markdown` library) → PDF (using `weasyprint` or `reportlab`). Styled with the platform's font (Inter) and color scheme.
- **Excel (.xlsx):** Extract all markdown tables from content using regex; write each table as a worksheet in `openpyxl`. Only available when the message contains at least one markdown table.

**Frontend — action bar below each assistant message:**
Four icon buttons rendered below each message bubble:
- Copy (clipboard icon) — copies raw text, already shown in Image #12
- Download Word (W icon)
- Download PDF (PDF icon)  
- Download Excel (XL icon, greyed out when no table in message)

Component: `ChatMessageActions.tsx` — receives `messageId` and `hasTable` props.

### 1.6 Source Chips and Collapsible Web Search Indicator

**Current problem:** Sources are shown in a separate collapsed panel (or not shown at all). Image #13 shows source chips inline and a "Searched the web ›" collapsible indicator.

**Fix — frontend changes in `ChatMessages.tsx`:**

1. **Source chips:** When a message has `sources` with `is_web: true`, render small pill chips inline below the message text: `[Hawksford] [ClearTax] [FTA.gov.ae]`. Each chip links to the source URL.

2. **Collapsible search indicator:** When research mode fires, the SSE stream emits a `queries_run` list. Display "Searched the web ›" as a collapsed line above the response. Clicking it expands to show the list of queries run and source URLs fetched. Matches Image #13 exactly.

3. **Structured LLM output:** Update the system prompt to instruct the LLM: when the response exceeds 200 words, use numbered sections, bold key terms, and tables for comparative data. This produces the Image #13 style output.

---

## Area 2 — PDF/OCR Pipeline (NotebookLM Approach)

Covers: scanned PDF prior year extraction, template confidence 0%, "Could not extract" error, Disclaimer of Opinion default.

### 2.1 Core Fix: fitz Pixmap → Vision LLM (replaces poppler)

**Root cause:** The existing vision fallback (`_extract_via_vision` in `prior_year_extractor.py`) uses `pdf2image.convert_from_path()` which requires poppler. Poppler is not installed. PyMuPDF (`fitz`) is already installed and can render pages to images natively.

**NotebookLM does:** Sends PDF page images directly to Gemini Vision. Our equivalent: render via `fitz.get_pixmap()` → PNG bytes → base64 → send to vision LLM (OpenAI GPT-4o or Claude Vision, both already in `llm_manager.py`).

**New extraction pipeline for `prior_year_extractor.py` (5 stages):**

```
Stage 1: PyMuPDF text extraction (fitz.get_text())
Stage 2: Regex table parsing on extracted text  
Stage 3: LLM text parsing (if text found but regex yielded 0 rows)
Stage 4: fitz.get_pixmap() → base64 PNG → vision LLM extraction  ← NEW (replaces poppler)
Stage 5: (existing vision path kept as last resort, skipped if Stage 4 succeeds)
```

Stage 4 implementation:
```python
async def _extract_via_fitz_vision(file_path: str) -> list[dict]:
    import fitz, base64
    doc = fitz.open(file_path)
    content_parts = [{"type": "text", "text": (
        "These are pages from a financial audit report. "
        "Extract every financial table row that has an account name and a numeric value. "
        "The prior year column is the SECOND (rightmost) numeric column. "
        "Return ONLY a JSON array: [{\"account_name\": str, \"prior_year_value\": number}]. "
        "No explanation."
    )}]
    for i in range(min(8, doc.page_count)):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(2, 2))
        b64 = base64.b64encode(pix.tobytes("png")).decode()
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    doc.close()

    llm = get_llm_provider("openai")   # vision requires OpenAI or Claude provider
    resp = await llm.chat([{"role": "user", "content": content_parts}], temperature=0.1, max_tokens=3000)
    # parse JSON array from resp.content the same way _extract_via_llm_text does
    ...parse and return rows...
```

**Confidence scoring:**
- Stage 1+2 (text + regex): 0.90
- Stage 3 (text + LLM): 0.80
- Stage 4 (fitz vision): 0.75
- Stage 5 (pdf2image fallback): 0.70
- Failed: 0.0

### 2.2 Fix `document_format_analyzer.py` for Scanned PDFs

**Root cause:** Line 72-73: `if not full_text.strip(): doc.close(); return _empty_result()`. For scanned PDFs text is empty → returns immediately → confidence 0%, method: failed, pages: undefined.

**Fix:** When `full_text.strip()` is empty after PyMuPDF text extraction, instead of returning empty, trigger a **vision-based template analysis**:

```python
if not full_text.strip():
    doc.close()
    return await _analyze_via_vision(file_path)
```

New function `_analyze_via_vision(file_path)`:
- Render first 6 pages via `fitz.get_pixmap()` → base64
- Send to vision LLM with structured prompt:
  ```
  Analyze these pages from a financial audit report PDF.
  Extract:
  1. Document sections (title, page number, level 1/2/3)
  2. Currency used and number format (e.g. AED #,##0 or #,##0.00)
  3. Negative number format: parentheses (X,XXX) or dash -X,XXX
  4. Font style of headings: bold/not bold
  5. Company name and period end date
  Return structured JSON matching the schema: {document_structure, account_grouping, terminology, formatting_rules}
  ```
- Parse JSON response
- Set `pages` from actual `doc.page_count` (fixes "pages: undefined")
- Return populated template dict with realistic confidence

### 2.3 Disclaimer of Opinion Default Fix

**Current problem:** When prior year data is missing (extraction failed), the system defaults to DISCLAIMER_OF_OPINION. This means even when the current year trial balance is complete, the report says "we cannot express an opinion."

**Fix in `api/reports.py` (audit draft generation):**
- Default opinion = `"unqualified"` unless the user explicitly selects otherwise
- When prior year data is missing: set prior year column to `"N/A"` (not "Not provided") and include a note: "Comparative figures not available — first year of audit or prior report not uploaded"
- Remove the logic that auto-downgrades to disclaimer when prior year is missing

---

## Area 3 — Financial Report Engine

Covers: account grouping in draft, analysis chat error, audit report formatting.

### 3.1 IFRS Account Grouping in Draft Report

**Current problem:** The audit draft (`AuditDraftViewer`) shows every account as an individual row in a flat unsorted table. No IFRS structure. Prior year = "Not provided" for all.

**Fix — pre-aggregation in `audit_agent.py` before generating the draft:**

The `generate()` method currently sends raw `tb_data` rows to the LLM. Instead, group first:

```
IFRS grouping structure:
  Statement of Financial Position:
    Non-Current Assets
      Fixed Assets (subtotal)
      Other Non-Current Assets (subtotal)
    Current Assets
      Trade Receivables (subtotal)
      Cash and Bank (subtotal)
    TOTAL ASSETS
    
    Non-Current Liabilities (subtotal)
    Current Liabilities (subtotal)
    TOTAL LIABILITIES
    
    Share Capital
    Retained Earnings / (Accumulated Loss)
    TOTAL EQUITY
    
    TOTAL LIABILITIES AND EQUITY

  Statement of Profit or Loss:
    Revenue (subtotal)
    Cost of Sales (subtotal)
    GROSS PROFIT
    Operating Expenses (subtotal)
    OPERATING PROFIT / (LOSS)
    Finance Costs
    Other Income/Expense
    NET PROFIT / (LOSS) BEFORE TAX
    Corporate Tax
    NET PROFIT / (LOSS) AFTER TAX
```

**Implementation:**
- New function `group_tb_for_ifrs(tb_data: list[dict]) -> dict` in `trial_balance_classifier.py`
- Maps each row's `mappedTo` category to IFRS group
- Returns structured dict with groups, subtotals, and grand totals
- `audit_agent.generate()` passes the grouped structure to the LLM prompt
- LLM prompt updated: "Generate a properly structured IFRS Statement of Financial Position and Statement of Profit or Loss using the grouped data below. Show subtotals and totals in bold. Use AED as currency."

**Prior year column:** When `prior_year_rows` is available, match by account name (fuzzy match by normalized lowercase key). Show matched prior year values; unmatched = `"N/A"`.

### 3.2 Analysis & Discussion Chat Error Fix

**Root cause:** The `/analysis-chat` endpoint streams large context (full trial balance + draft content) to the NVIDIA API. When the total tokens exceed the model's context window, the NVIDIA API returns an error mid-stream. This causes the TCP connection to reset. The frontend's `reader.read()` throws → catch block fires → "Sorry, I encountered an error."

**Fix — `api/reports.py` `/analysis-chat` endpoint:**

1. **Context size limits:** Before building the messages array, trim:
   - `trial_balance_summary`: max 2500 characters (keep the grouped summary, not individual rows)
   - `draft_content`: max 2000 characters (first 2000 chars of draft)
   - `prior_year_context`: max 1000 characters

2. **Error recovery in stream:** Wrap the stream loop so errors emit a JSON error event instead of crashing the TCP connection:
   ```python
   async def generate():
       try:
           llm = get_llm_provider()
           async for chunk in llm.chat_stream(messages, temperature=0.3, max_tokens=2000):
               yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
           yield f"data: {json.dumps({'type': 'done'})}\n\n"
       except Exception as e:
           yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
   ```

3. **Frontend `AuditAnalysisStep.tsx`:** Update to parse JSON events (`{"type":"chunk","content":"..."}`) instead of raw text. Handle `{"type":"error"}` by showing a user-friendly message that includes a "Retry" button.

4. **Note:** The existing frontend reads raw text (line 95: `const chunk = line.slice(6)`). It needs to be updated to `const event = JSON.parse(line.slice(6))` and use `event.content` for chunks.

### 3.3 Audit Report Formatting and Alignment

**Current problem:** Template extraction returns confidence 0%, font=undefined, decimals=undefined. The generated DOCX uses fallback formatting and doesn't match the prior year report.

**Fix:** This is resolved by Area 2.1 + 2.2. Once vision-based template extraction works:
- `formatting_rules.table_formatting.currency_format` will be populated (e.g. `#,##0` for AED whole numbers)
- `formatting_rules.font_hierarchy` will specify bold headings
- `document_structure.sections` will list the actual sections from the prior year PDF

Additional fix in `template_report_generator.py`:
- When `formatting_rules.table_formatting.currency_format == "#,##0"`, format all AED amounts as whole numbers (no decimal places) — consistent with UAE audit practice
- When `formatting_rules.font_hierarchy.heading_1_bold == True`, apply bold to all section headings in the DOCX
- Table column widths: Account name column = 60% width, Current year = 20%, Prior year = 20% — hardcode these proportions to ensure alignment regardless of data length

---

## Area 4 — Export Architecture

### 4.1 Backend Export Endpoint

```
POST /api/chat/export
Body: { message_id: str, format: "word" | "pdf" | "excel" }
```

**Word export:**
- Use `python-docx` 
- Parse markdown headings (`#`, `##`) → Word Heading 1/2 styles
- Parse `**bold**` → bold runs
- Parse markdown tables → Word tables with header row shading
- Parse bullet lists → bulleted list style
- Apply company font (Times New Roman 11pt, consistent with audit DOCX)

**PDF export:**
- Convert markdown → HTML using `markdown` Python library
- Apply CSS: Times New Roman font, A4 page size, proper margins
- Convert HTML → PDF using `weasyprint` (pure Python, no browser dependency)
- Embed the platform logo in the header

**Excel export:**
- Extract all `|table|` markdown tables from message content
- Each table → one worksheet, named after the first heading found above it
- Format numeric cells with number format `#,##0.00`
- Bold the header row
- Auto-fit column widths
- Use `openpyxl`

**Audit report export** (already exists in `audit_formatter.py`): The existing Word/Excel/PDF export buttons in the audit wizard are separate and already functional. This Area 4 export is specifically for the Legal Chat responses.

### 4.2 Frontend Action Bar

New component `ChatMessageActions.tsx`:

```tsx
interface Props {
  messageId: string;
  content: string;
  hasTable: boolean;
}
```

Renders 4 icon buttons below each assistant message:
1. Copy (copies `content` to clipboard)
2. Word (calls `POST /api/chat/export` with `format: "word"`, downloads file)
3. PDF (calls `POST /api/chat/export` with `format: "pdf"`, downloads file)
4. Excel (disabled when `!hasTable`, calls `POST /api/chat/export` with `format: "excel"`)

Button style: small icon-only buttons, 28px height, light ghost style. Matches the icon bar shown in Image #12.

---

## Area 5 — UX Polish

### 5.1 Structured LLM Output (Image #13 Style)

Update `SYSTEM_PROMPT` in `rag_engine.py` and `get_system_prompt()` in `prompt_router.py`:

Add instruction: "When your response exceeds 150 words, structure it with: a one-sentence direct answer first, then numbered sections with bold headings, then a summary. Use markdown tables for comparisons. Cite sources as [Source Name] inline."

### 5.2 Research Mode Source Display

When research mode response arrives, the SSE stream includes:
```json
{"type": "queries_run", "queries": ["query 1", "query 2", ...]}
{"type": "sources", "sources": [...]}
```

Frontend renders:
- A collapsed "Searched the web ›" line above the assistant message
- Click to expand: shows list of queries run and source chips
- Source chips: `[FTA.gov.ae]` `[PWC UAE]` `[Hawksford]` — each links to URL

---

## Implementation Order

The items should be implemented in this order to unblock dependent fixes:

1. **Area 2.1** — fitz pixmap vision extraction (unblocks everything audit-related)
2. **Area 2.2** — document_format_analyzer vision path (unblocks template formatting)
3. **Area 2.3** — default opinion fix (quick win)
4. **Area 3.1** — account grouping (unblocks draft quality)
5. **Area 3.2** — analysis chat error fix (unblocks management reports analysis)
6. **Area 3.3** — audit formatting (depends on 2.2 being done)
7. **Area 1.1** — within-session memory (sliding window 20 msgs)
8. **Area 1.3** — Pro-Tip removal (2-line change)
9. **Area 1.2** — cross-session memory (new DB table)
10. **Area 1.4** — research mode
11. **Area 1.5** — download export
12. **Area 1.6** — source chips + collapsible search indicator
13. **Area 4** — export endpoint (depends on 1.5 frontend)
14. **Area 5** — UX polish (prompt updates)

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/core/prior_year_extractor.py` | Add Stage 4: `_extract_via_fitz_vision()` using fitz.get_pixmap() |
| `backend/core/document_format_analyzer.py` | Add `_analyze_via_vision()` triggered when text is empty |
| `backend/core/agents/audit_agent.py` | Add `group_tb_for_ifrs()` aggregation before LLM call |
| `backend/core/agents/trial_balance_classifier.py` | New `group_tb_for_ifrs()` function |
| `backend/core/template_report_generator.py` | Apply extracted formatting_rules to DOCX output |
| `backend/api/reports.py` | Fix `/analysis-chat`: trim context + JSON SSE events + error recovery |
| `backend/api/reports.py` | Fix default opinion logic (unqualified when prior year missing) |
| `backend/api/chat.py` | Sliding window memory + research mode + export endpoint |
| `backend/core/rag_engine.py` | Remove Pro-Tip from SYSTEM_PROMPT |
| `backend/core/web_search.py` | Add `deep_search()` for research mode |
| `backend/core/prompt_router.py` | Structured output instruction |
| `backend/db/models.py` | New `UserMemory` table |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | Source chips + action bar |
| `frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx` | Parse JSON SSE events + retry on error |
| `frontend/src/components/ChatMessageActions.tsx` | New: Copy/Word/PDF/Excel action buttons |

---

## Dependencies Required

| Package | Use | Already installed? |
|---------|-----|-------------------|
| `fitz` (PyMuPDF) | PDF → image rendering | ✅ Yes |
| `python-docx` | Word export | ✅ Yes (used in audit_formatter) |
| `weasyprint` | HTML → PDF | ❌ Needs pip install |
| `openpyxl` | Excel export | Check — likely yes |
| `markdown` | Markdown → HTML | Check — likely yes |
| `duckduckgo_search` | Web search | ✅ Yes (used in web_search.py) |

New packages to add to requirements: `weasyprint` only (everything else already present).
