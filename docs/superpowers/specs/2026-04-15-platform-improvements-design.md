# Platform Improvements Design Spec
**Date:** 2026-04-15  
**Project:** UAE Accounting & Legal AI Chatbot  
**Stack:** FastAPI + React/TypeScript + ChromaDB + SQLite  
**Status:** Approved for implementation

---

## Overview

Ten independent improvements grouped into four themes:
- **Legal Studio fixes** (Issues 1–2)
- **Financial Studio wizard fixes** (Issues 3–4–6)
- **Document processing** (Issue 5)
- **AI intelligence & output quality** (Issues 7–8–9–10)

---

## Issue 1 — RAG Training: UAE E-Invoicing & Peppol

### Problem
The chatbot gives shallow answers on UAE VAT, Peppol, and E-Invoicing topics compared to what a CA or a general-purpose LLM like Gemini provides. The knowledge base is missing structured regulatory content on these topics.

### Design

**Step 1 — Document ingestion**  
The Peppol/E-Invoicing PDF (`brain/UAE E-Invoicing and Peppol for Third-Party Shipments.pdf`) must be ingested into ChromaDB via the existing `bulk_ingest.py` pipeline. No new code needed — just run ingestion on this file.

**Step 2 — Prompt engineering in `prompt_router.py`**  
Add a UAE VAT/Peppol topic detector. When a user question matches VAT/Peppol/E-Invoicing keywords, inject a system prefix into the LLM prompt:

```
System: You are a UAE-certified tax advisor. Answer according to UAE Federal Decree-Law No. 8 of 2017 on VAT and the UAE Peppol Authority guidelines. Always cite the relevant article or section. If the answer requires Peppol ID registration, explain the threshold (AED 375,000 annual turnover), the VAT rates (standard 5%, zero-rated, exempt), and registration steps with the FTA.
```

**Step 3 — Q&A seed pairs**  
Create `backend/data/qa_seeds/vat_peppol_qa.json` with 20–30 authoritative Q&A pairs covering:
- Peppol ID registration threshold and process
- UAE VAT standard/zero/exempt rates
- E-Invoicing mandate timeline
- Third-party shipment rules
- FTA filing requirements

These seeds are ingested as high-weight documents so they always surface in RAG retrieval.

**Files to create/modify:**
- `backend/data/qa_seeds/vat_peppol_qa.json` — new
- `backend/core/prompt_router.py` — add VAT/Peppol topic branch
- Run `python bulk_ingest.py` on the PDF + seeds

---

## Issue 2 — Source Panel Bug: Chat Freezes on Close/Reopen

### Problem
Closing the source panel (right sidebar showing document references) during a conversation causes the chat to freeze. Reopening the app shows the frozen state. The source panel's open/close state is leaking into conversation state.

### Root Cause (to verify)
In `frontend/src/components/studios/LegalStudio/SourcePeeker.tsx` and `LegalStudio.tsx`, the source panel likely shares state with the message list or blocks re-renders when unmounted. The conversation ID or selected source reference may be stored in a way that survives panel close and corrupts the next render.

### Design

**State isolation rule:**  
Source panel state (`isOpen`, `selectedSource`, `sourceContent`) must live in a separate, independent state slice from conversation state (`messages`, `conversationId`, `isLoading`).

**Specific fix targets:**
1. `LegalStudio.tsx` — ensure `selectedSource` is reset to `null` on panel close, not on message change
2. `SourcePeeker.tsx` — component must render `null` cleanly when closed (no lingering effect hooks that touch message state)
3. On app reopen: conversation state loads from API; source panel always initialises as closed (`isOpen: false`, `selectedSource: null`) — never persisted to localStorage

**Files to modify:**
- `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- `frontend/src/components/studios/LegalStudio/SourcePeeker.tsx`

---

## Issue 3 — Edit Report: Navigate to Draft Step, Not Text Modal

### Problem
Clicking "Edit" on a saved report in the left sidebar opens a raw text editor modal showing the full report markdown. The correct behaviour is to re-open the report wizard at **Step 6: Draft Report** so the user can edit in structured wizard context.

### Design

**`Edit` button behaviour:**
1. Load the saved report's wizard state (report type, trial balance upload ID, company info, requirements, format selection) from the database
2. Navigate to `FinancialStudio` with the report's step set to `6` (Draft Report)
3. Hydrate all prior steps (1–5) from saved state so the user can navigate backward freely

**Data requirements:**  
The saved report record (in SQLite) must store the full wizard session state as a JSON blob. If it currently does not, add a `wizard_state` JSON column to the reports table.

**Migration note:** Existing reports in the database will have `wizard_state = NULL`. For these, the Edit button falls back to the old text modal with a banner: "This report was created before the new wizard — edit is limited to text only." New reports saved after this fix will always have a full `wizard_state` and open in the wizard.

**Backend endpoint:**  
`GET /api/reports/{report_id}/wizard-state` — returns the JSON blob needed to restore the wizard.

**Frontend:**  
`FinancialStudio.tsx` — `Edit` button calls this endpoint, sets `currentStep = 6`, hydrates state, removes the text modal entirely.

**Files to modify:**
- `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx` — remove modal, add navigation
- `backend/db/models.py` — add `wizard_state` column
- `backend/api/reports.py` — add `GET /reports/{id}/wizard-state` endpoint

---

## Issue 4 — Duplicate Company Info: Pre-fill Step 4 from Step 3

### Problem
Step 3 (Company Docs) auto-extracts Company Name, Address, Trade License, Shareholders, Registration Number, and Incorporation Date from uploaded documents. Step 4 (Requirements) then asks the user again for Company Name, Auditor Name, and Period End Date — ignoring the already-extracted data.

### Design

**Data flow:**  
Step 3 stores extracted company info in wizard state (already done — visible in the UI). Step 4 must read from that same state on mount and pre-populate:
- `Company Name` → from `extractedCompanyInfo.company_name`
- `Period End Date` → from `extractedCompanyInfo.period_end` (if found in documents) or left blank for user to fill
- `Auditor Name` → always blank (not extractable from company docs — this is the CA's own name)

**UX rule:**  
Pre-filled fields show with a light "auto-filled" indicator and remain editable. If the user changes a value, it overrides the extracted value for this report only.

**Files to modify:**
- `frontend/src/components/studios/FinancialStudio/ReportRequirements.tsx` — read wizard state on mount, pre-populate fields

---

## Issue 5 — OCR: Signed/Scanned PDFs Not Being Read

### Problem
Signed audit reports uploaded as scanned PDFs (e.g. "Signed Audit Report 2024.pdf") produce empty or garbled text. The current OCR pipeline does not handle low-contrast stamps, signatures, or heavily compressed scan images.

### Design

**Enhanced preprocessing pipeline in `document_processor.py`:**

The PDF-to-image step before Tesseract OCR must apply:

1. **DPI upscaling** — render pages at 300 DPI minimum (currently likely 150 DPI)
2. **Grayscale conversion** — convert to grayscale before thresholding
3. **Adaptive thresholding** — use `cv2.adaptiveThreshold` (Gaussian method) instead of simple binary threshold — handles uneven lighting from scanner beds
4. **Deskew** — detect and correct page rotation using `deskew` library or `cv2.minAreaRect`
5. **Noise removal** — apply median blur (`cv2.medianBlur`, kernel 3) to remove scanner noise
6. **Signature/stamp masking** — detect large dark blobs (signatures, stamps) using connected component analysis; mask them out before OCR to prevent them corrupting surrounding text

**Tesseract config for scanned docs:**  
Add `--psm 6` (assume uniform block of text) and `--oem 1` (LSTM engine) for scanned pages.

**Fallback chain:**
1. Try native PDF text extraction (pdfminer) — fast, no OCR
2. If text yield < 100 chars per page → trigger enhanced OCR pipeline above
3. If OCR still yields < 50 chars per page → mark document as `ocr_failed`, notify user with message: "This page could not be read — please provide a higher-resolution scan or a text-based PDF."

**New Python dependencies:**
- `opencv-python-headless`
- `deskew`

**Files to modify:**
- `backend/core/document_processor.py` — replace current image preprocessing with enhanced pipeline
- `backend/requirements.txt` — add opencv, deskew

---

## Issue 6 — Navigation, Auto-Save, and Sidebar Report Shortcuts

### Problem
Three linked UX problems:
1. No "Back" button in the 9-step wizard — user can only move forward
2. The left sidebar has no shortcuts to start a new report of each type
3. Reports are auto-saved as drafts immediately, even before the user explicitly saves — cluttering the saved reports list

### Design

### 6a — Back Button in Wizard

Every step (2–9) gets a "← Back" button next to the "Continue →" button.

**Behaviour:**
- Back navigates to `currentStep - 1`
- State for the current step is preserved (not reset) — so returning forward repopulates fields
- Step 1 (Select Type) has no Back button

**Implementation:**  
`FinancialStudio.tsx` — add `handleBack()` function that decrements `currentStep` and add a `Back` button to the wizard footer on all steps except step 1.

### 6b — Sidebar: New Report Shortcuts

The left sidebar panel currently shows only "Saved Reports". Add a collapsible **"New Report"** section at the top with one button per report type:

```
+ New Report
  ├── Audit Report
  ├── VAT Return
  ├── Corporate Tax
  ├── Compliance Report
  ├── MIS Report
  ├── Financial Analysis
  ├── Budget vs Actual
  ├── IFRS Financial Statements
  ├── Cash Flow Statement
  └── Custom Report
```

Clicking any shortcut navigates to the wizard at Step 1 with that report type pre-selected (skipping the type selection card grid).

**Files to modify:**
- `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx` — add sidebar section + shortcut handlers

### 6c — Explicit Save Only (No Auto-Save)

**Current broken behaviour:** A report record is created in the database as soon as the wizard starts, appearing in the sidebar as a draft before the user has done anything meaningful.

**Correct behaviour:**
- No database record is created until the user clicks an explicit **"Save Draft"** or **"Save Final"** button
- In-progress wizard state is held in React component state only (not persisted)
- If the user closes/navigates away without saving, a browser `beforeunload` dialog warns: "You have an unsaved report. Leave without saving?"
- "Save Draft" button appears from Step 6 onward
- "Save Final" button appears on Step 9 (Final Report)

**Backend:** `POST /api/reports/` is only called when user explicitly saves — not on step progression.

**Files to modify:**
- `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx`
- `backend/api/reports.py` — remove any auto-create-on-start logic

---

## Issue 7 — Audit Intelligence: LLM as Chartered Accountant + ML Risk Classifier

### Problem
The LLM currently produces a single generic audit remark ("Bank/cash — confirmation letter required"). A real Chartered Accountant would ask multiple targeted questions based on what they see in the trial balance, follow ISA standards, and flag specific risks.

### Design

### 7a — Trial Balance Risk Classifier (Python)

**File:** `backend/core/trial_balance_classifier.py`

A Scikit-Learn Random Forest classifier that takes trial balance data and outputs structured risk flags.

**Input:** Parsed trial balance as a list of `{account_name, amount, category}` rows  
**Output:** JSON risk report with these sections:

```json
{
  "grouping": [
    {"account": "Interest Income", "suggested_group": "Revenue", "confidence": 0.94},
    ...
  ],
  "risk_flags": [
    {"flag": "going_concern", "triggered": true, "reason": "Current liabilities exceed current assets by >20%"},
    {"flag": "related_party", "triggered": true, "reason": "Loan from Amarjeet Singh Dhir detected"},
    {"flag": "revenue_concentration", "triggered": false},
    {"flag": "negative_equity", "triggered": false},
    {"flag": "large_unexplained_variance", "triggered": true, "reason": "Commission Received-Rental changed >50% vs prior year"}
  ],
  "financial_ratios": {
    "current_ratio": 0.72,
    "debt_to_equity": 3.4,
    "gross_margin": 0.18
  }
}
```

**Training data:**  
Create `backend/data/training/account_grouping_labels.csv` with columns: `account_name`, `category`. Start with ~200 rows covering common UAE company account names (in English and transliterated Arabic). The classifier is trained at startup if no model file exists, or re-trained when the user uploads new labelled data.

**Risk flag rules (hard-coded, not ML):**
- `going_concern`: Current ratio < 1.0 OR accumulated losses > 50% of paid-up capital
- `related_party`: Account name contains shareholder name from company info
- `large_unexplained_variance`: Any line item > AED 100,000 changed > 40% with no prior explanation
- `negative_equity`: Total equity < 0

### 7b — CA-Level Audit Questions

**File:** `backend/core/agents/audit_agent.py` → `ask_questions()` method

After running the classifier, the Audit Agent generates ISA-grounded questions. The LLM prompt template:

```
You are a senior Chartered Accountant conducting an audit under ISA standards and UAE Federal Law No. 2 of 2015 on Commercial Companies.

You have reviewed the trial balance and the risk classifier has identified the following:
{risk_flags_json}
{financial_ratios_json}

Generate a numbered list of audit questions the auditor must ask the client. Each question must:
1. Reference the specific account or ratio that triggered it
2. Cite the relevant ISA standard (e.g. ISA 240, ISA 505, ISA 570)
3. Ask for a specific document or explanation

Do not ask generic questions. Every question must be grounded in the data above.
```

**Output in UI:** Step 5 (Evidence/Requirements) shows the generated CA questions in a checklist. User marks each as "Answered" or "Evidence Uploaded" before proceeding. Unanswered ISA-critical questions (going concern, fraud risk) block the Final Report generation with a warning.

**Files to create/modify:**
- `backend/core/trial_balance_classifier.py` — new
- `backend/core/agents/audit_agent.py` — new
- `backend/data/training/account_grouping_labels.csv` — new
- `frontend/src/components/studios/FinancialStudio/AuditEvidenceStep.tsx` — update to show CA questions

---

## Issue 8 — Audit Report Quality: Opinion Gate + Correct Grouping

### Problem
1. The LLM issues a "fair" audit opinion even when no supporting documents have been uploaded — this is professionally and legally incorrect
2. Account grouping in the financial statements is wrong — multiple income items that should be "Revenue" appear scattered across incorrect categories

### Design

### 8a — Opinion Gate

**Rule:** The system may not generate an "Unqualified (Fair)" opinion unless ALL of the following conditions are met:
- At least one signed audit report or management accounts document has been uploaded
- All ISA-critical questions (going concern, fraud, related party) are marked "Answered" or "Evidence Uploaded"
- The trial balance classifier shows no unresolved high-severity flags

**If conditions not met:**  
The LLM prompt is instructed to issue a **"Disclaimer of Opinion"** or **"Qualified Opinion"** with specific paragraphs explaining what evidence is missing. Sample language:

```
Basis for Disclaimer of Opinion: We were not provided with sufficient appropriate audit evidence to form an opinion on the financial statements. Specifically, [list missing evidence]. As a result, we are unable to express an opinion on the financial statements.
```

**Implementation:**  
`backend/core/agents/audit_agent.py` → `generate()` method checks evidence completeness before constructing the LLM prompt. Sets `opinion_type` parameter to `unqualified` | `qualified` | `disclaimer` based on gate checks.

### 8b — Correct Account Grouping via Classifier

The grouping classifier from Issue 7a (`trial_balance_classifier.py`) handles this. The classifier maps each account to the correct IFRS/UAE financial statement line:

**Standard groups:**
- Revenue (turnover)
- Cost of Revenue (direct expenses)
- Gross Profit
- Operating Expenses (indirect)
- Finance Costs
- Other Income
- Tax Expense
- Non-Current Assets
- Current Assets
- Equity
- Non-Current Liabilities
- Current Liabilities

**Prior-year learning:**  
If the user uploads a prior-year signed audit report (PDF), the parser extracts the prior-year groupings and uses them as high-confidence overrides for the classifier. This means the grouping matches the prior auditor's structure exactly.

**Files to modify:**
- `backend/core/agents/audit_agent.py`
- `backend/core/trial_balance_classifier.py` — add prior-year override logic

---

## Issue 9 — Custom Format Learning: PDF / Excel / DOCX Template Parser

### Problem
The generated audit report does not match the user's preferred format (e.g. Castle Plaza Draft FS 2025). The LLM must learn the user's format from an uploaded template file, not by reading the entire file as tokens.

### Design

**File:** `backend/core/format_extractor.py`

A parser that accepts PDF, Excel (.xlsx/.xls), or DOCX and outputs a `format_template.json`.

### Excel format extraction (new — user's addition)
Excel files carry rich structural information:
- **Merged cells** → identify header rows and section titles
- **Column widths** → detect alignment (narrow = label, wide = description, right-aligned = amounts)
- **Row indent levels** → detect from `alignment.indent` property (openpyxl) → maps to financial statement hierarchy
- **Number formats** → detect AED/USD currency format strings, decimal places, thousands separator
- **Bold/italic rows** → detect section headers vs detail lines vs total lines
- **Note markers** → detect `Note X` or `(X)` patterns → extract note numbering convention

### PDF format extraction
Using `pdfplumber`:
- Extract column x-positions → determine number of columns and their labels
- Detect row font size changes → headers vs body vs totals
- Detect horizontal lines → section separators
- Extract note text blocks → note format and numbering style

### DOCX format extraction
Using `python-docx`:
- Read table structure → column count, header row
- Read paragraph styles → Heading1/2/3 → map to report hierarchy
- Read number list styles → note numbering format

### Output: `format_template.json`
```json
{
  "source_file": "Draft FS - Castle Plaza 2025.xlsx",
  "columns": [
    {"label": "Account", "position": "left", "width": "wide"},
    {"label": "Note", "position": "center", "width": "narrow"},
    {"label": "2025 AED", "position": "right", "format": "#,##0"},
    {"label": "2024 AED", "position": "right", "format": "#,##0"}
  ],
  "hierarchy": ["group_header", "sub_header", "line_item", "total_line"],
  "indent_chars": 4,
  "note_format": "Note {n} — {title}",
  "currency": "AED",
  "decimal_places": 0,
  "section_separator": "horizontal_line",
  "totals_style": "bold_underline",
  "header": {
    "company_name_position": "center_top",
    "report_title": "Statement of Financial Position",
    "period_label": "For the year ended {period_end}"
  }
}
```

### LLM generation with template
When generating the final report, the LLM prompt includes:
```
Generate the financial statements strictly following this format template:
{format_template_json}

Rules:
- Use exactly the column order and labels specified
- Apply the indent levels for hierarchy
- Format all numbers as {currency} with {decimal_places} decimal places
- Number notes as: {note_format}
- Do not add or remove columns
- Match the grouping structure to the classifier output
```

**Storage:** The extracted `format_template.json` is stored in two places:
1. Attached to the current wizard session state (per-report)
2. Optionally saved as a company-level default (keyed by company name) so the user doesn't re-upload the same template every time

**User upload flow:**  
On Step 7 (Select Format), user can choose:
- "Use default format" (BIG4 standard)
- "Use saved company format" (if a template was previously saved for this company)
- "Upload my format" → accepts PDF/Excel/DOCX → runs extractor → shows preview of detected structure → user confirms or manually adjusts → option to "Save as default for this company"

**Files to create:**
- `backend/core/format_extractor.py` — new
- `backend/api/reports.py` — add `POST /reports/extract-format` endpoint
- `frontend/src/components/studios/FinancialStudio/AuditFormatSelector.tsx` — update to support format upload + preview
- `backend/requirements.txt` — add `pdfplumber`, `openpyxl`, `python-docx`

---

## Issue 10 — Report Subagents: One Agent Class Per Report Type

### Problem
All 10 report types share generic generation logic. Each type needs its own data collection, question set, and generation prompt to produce professional output.

### Design

**Directory:** `backend/core/agents/`

**Base class:** `backend/core/agents/base_agent.py`
```python
class BaseReportAgent:
    def collect_data(self, wizard_state: dict) -> dict: ...
    def ask_questions(self, data: dict) -> list[str]: ...
    def validate_evidence(self, evidence: dict) -> tuple[bool, list[str]]: ...
    def generate(self, data: dict, format_template: dict) -> str: ...
```

**One class per report type:**

| File | Class | Report |
|------|-------|--------|
| `audit_agent.py` | `AuditAgent` | Audit Report (ISA, UAE Law 2/2015) |
| `vat_agent.py` | `VATAgent` | VAT Return (FTA VAT-201 form structure) |
| `corporate_tax_agent.py` | `CorporateTaxAgent` | Corporate Tax (Decree-Law 47/2022) |
| `compliance_agent.py` | `ComplianceAgent` | Compliance Report (regulatory checklist) |
| `mis_agent.py` | `MISAgent` | MIS Report (KPIs, trends, commentary) |
| `financial_analysis_agent.py` | `FinancialAnalysisAgent` | Financial Analysis (ratios, liquidity) |
| `budget_agent.py` | `BudgetAgent` | Budget vs Actual (variance analysis) |
| `ifrs_agent.py` | `IFRSAgent` | IFRS Financial Statements (full set) |
| `cashflow_agent.py` | `CashFlowAgent` | Cash Flow Statement (direct/indirect) |
| `custom_agent.py` | `CustomAgent` | Custom Report (user-defined columns) |

**Routing:** `backend/api/reports.py` reads `report_type` from the request and instantiates the correct agent class. No if/else chains — use a registry dict:
```python
AGENT_REGISTRY = {
    "audit": AuditAgent,
    "vat_return": VATAgent,
    ...
}
agent = AGENT_REGISTRY[report_type](llm_manager, trial_balance_classifier)
```

**Per-agent question sets (examples):**

*AuditAgent questions:*
- "Has the company received a going concern letter from the bank? (ISA 570)"
- "Are there any related-party transactions not disclosed in the trial balance? (ISA 550)"
- "Has management provided written representation? (ISA 580)"

*VATAgent questions:*
- "What is the total taxable supply for the period?"
- "Are there any zero-rated or exempt supplies to separate?"
- "Any adjustments for bad debt relief (Article 64 UAE VAT Law)?"

*IFRSAgent questions:*
- "Confirm the accounting policies applied (IFRS 1 / IAS 1)"
- "Any changes in accounting estimates to disclose? (IAS 8)"
- "Confirm the going concern assessment period is at least 12 months (IAS 1 para 25)"

**Files to create:**
- `backend/core/agents/base_agent.py`
- `backend/core/agents/audit_agent.py` (merge with Issue 7 work)
- `backend/core/agents/vat_agent.py`
- `backend/core/agents/corporate_tax_agent.py`
- `backend/core/agents/compliance_agent.py`
- `backend/core/agents/mis_agent.py`
- `backend/core/agents/financial_analysis_agent.py`
- `backend/core/agents/budget_agent.py`
- `backend/core/agents/ifrs_agent.py`
- `backend/core/agents/cashflow_agent.py`
- `backend/core/agents/custom_agent.py`
- `backend/api/reports.py` — replace current generation logic with agent registry

---

## Implementation Order

Build in this sequence to avoid blocking dependencies:

1. **Issue 5** — OCR fix (unblocks all document uploads, including signed prior-year reports)
2. **Issue 2** — Source panel bug (quick frontend fix, unblocks Legal Studio testing)
3. **Issue 6** — Back button + explicit save + sidebar shortcuts (wizard foundation)
4. **Issue 4** — Pre-fill company info Step 4 (depends on Step 3 state being stable)
5. **Issue 3** — Edit report → navigate to draft step (depends on wizard_state DB column)
6. **Issue 1** — RAG training for VAT/Peppol (independent, can run anytime)
7. **Issue 7** — Trial balance classifier + CA questions (core AI, needed before 8)
8. **Issue 8** — Opinion gate + correct grouping (depends on classifier from 7)
9. **Issue 9** — Format extractor: PDF/Excel/DOCX (independent, parallel with 7–8)
10. **Issue 10** — Subagents for all report types (depends on base from 7–8)

---

## New Files Summary

```
backend/
├── core/
│   ├── trial_balance_classifier.py   (Issue 7 — ML classifier)
│   ├── format_extractor.py           (Issue 9 — PDF/Excel/DOCX parser)
│   └── agents/
│       ├── base_agent.py             (Issue 10)
│       ├── audit_agent.py            (Issues 7+10)
│       ├── vat_agent.py              (Issue 10)
│       ├── corporate_tax_agent.py    (Issue 10)
│       ├── compliance_agent.py       (Issue 10)
│       ├── mis_agent.py              (Issue 10)
│       ├── financial_analysis_agent.py (Issue 10)
│       ├── budget_agent.py           (Issue 10)
│       ├── ifrs_agent.py             (Issue 10)
│       ├── cashflow_agent.py         (Issue 10)
│       └── custom_agent.py           (Issue 10)
├── data/
│   ├── qa_seeds/
│   │   └── vat_peppol_qa.json        (Issue 1)
│   └── training/
│       └── account_grouping_labels.csv (Issue 7)
docs/
└── superpowers/specs/
    └── 2026-04-15-platform-improvements-design.md  (this file)
```

## Modified Files Summary

```
backend/
├── core/
│   ├── document_processor.py   (Issue 5 — OCR enhancement)
│   └── prompt_router.py        (Issue 1 — VAT/Peppol topic branch)
├── db/
│   └── models.py               (Issue 3 — wizard_state column)
└── api/
    └── reports.py              (Issues 3, 6c, 10 — agent registry, save logic)
frontend/src/components/studios/FinancialStudio/
├── FinancialStudio.tsx         (Issues 3, 6a, 6b, 6c — back btn, sidebar, save)
├── ReportRequirements.tsx      (Issue 4 — pre-fill from Step 3)
├── AuditEvidenceStep.tsx       (Issue 7 — CA questions checklist)
└── AuditFormatSelector.tsx     (Issue 9 — format upload + preview)
frontend/src/components/studios/LegalStudio/
├── LegalStudio.tsx             (Issue 2 — state isolation)
└── SourcePeeker.tsx            (Issue 2 — clean unmount)
```
