# Implementation Plan: Platform Improvements (10 Issues)
**Date:** 2026-04-15  
**Spec:** `docs/superpowers/specs/2026-04-15-platform-improvements-design.md`  
**Stack:** FastAPI + React/TypeScript + ChromaDB + SQLite  
**Executor:** Armaan (self-implementing)

---

## Phase 0: Discovery Summary (Already Done — Read Before Starting)

These findings come from reading the actual codebase. **Do not re-derive them — trust this summary.**

### Already Fully Implemented (No Work Needed)
| Issue | What's Already There |
|-------|---------------------|
| **Issue 5 — OCR** | `document_processor.py` already implements: 300 DPI min, adaptive Gaussian thresholding (kernel=31, C=11), `--oem 1 --psm 6` Tesseract config, deskew via scikit-image, median blur (k=3), signature blob masking. All required packages (`opencv-python-headless`, `deskew`) already in `requirements.txt`. **Skip entirely.** |
| **Issue 5 — Dependencies** | `requirements.txt` already contains `opencv-python-headless==4.10.0.84`, `deskew==1.3.2`, `scikit-image==0.24.0`, `scikit-learn==1.4.2`, `python-docx==1.1.2`, `openpyxl==3.1.5`, `reportlab==4.2.5`. |
| **Issue 3 — DB Column** | `SavedReport` model in `db/models.py` (line ~140) already has `wizard_state_json` (JSON) column. **No migration needed.** |
| **Issue 1 — VAT/Peppol Prompt** | `prompt_router.py` already has `"vat_peppol"` domain (line ~85) with correct UAE VAT advisor prompt and `VAT_PEPPOL_KEYWORDS` frozenset (line ~6). `get_system_prompt()` already detects and routes to it. |

### Already Partially Implemented (Verify Before Modifying)
| Issue | Partial State | What's Missing |
|-------|--------------|----------------|
| **Issue 4 — Pre-fill** | `ReportRequirements.tsx` lines 45–49: `useEffect` already pre-fills `company_name` from `companyInfo` prop; `autoFilledKeys` badge rendering at line ~77 | `period_end` not yet pre-filled; verify `companyInfo` is actually passed from `FinancialStudio.tsx` |
| **Issue 6a — Back Button** | `FinancialStudio.tsx` line ~190 already has `handleBack` function that decrements `activeStep` | Verify Back button renders on all steps 2–9 (not just step ~190); confirm step 1 has no Back |
| **Issue 6c — Explicit Save** | `isDirty` state (line 57), `beforeunload` useEffect (lines 57–64), explicit `handleSaveDraft()` (line 128); **backend has no auto-create-on-start** | Verify "Save Draft" button appears from Step 6 onward and "Save Final" on Step 9 |
| **Issue 7b — CA Questions** | `AuditEvidenceStep.tsx` fetches from `/api/reports/audit/ca-questions` (line ~50); opinion logic already at lines 83–92 (unqualified → qualified → disclaimer → adverse) | Backend `ca-questions` endpoint (line 1451) needs to generate ISA-grounded questions from risk flags, not generic ones |
| **Issue 9 — Format Upload UI** | `AuditFormatSelector.tsx` already calls `POST /api/reports/extract-format` (line ~17) and `POST /api/reports/extract-template`; accepts PDF/DOCX/XLSX | `extract-format` endpoint at `reports.py:1645` needs to verify it returns structured `format_template.json` (not just raw text) |

### Key Signatures to Know
```python
# llm_manager.py — how to call LLM from new agent classes
provider = get_llm_provider()  # factory, reads from settings
response = await provider.chat(messages=[{"role": "user", "content": "..."}], temperature=0.2)
# response.content is the string

# All providers also support streaming:
async for chunk in provider.chat_stream(messages, temperature=0.2):
    yield chunk

# prompt_router.py — how to get system prompts
from core.prompt_router import get_system_prompt
system = get_system_prompt(domain="audit", question=user_question)

# models.py — SavedReport columns available
# id, company_name, report_type, format, period_end_date, status,
# wizard_state_json (JSON), draft_content, final_content, created_at, updated_at
```

---

## Revised Implementation Order

Based on what's already done, the new order is:

1. **Phase 1 — Issue 2:** Source panel freeze bug (LegalStudio)
2. **Phase 2 — Issue 1:** RAG ingestion + seed Q&A (VAT/Peppol)
3. **Phase 3 — Issues 4 & 6:** Pre-fill + Back button + Save verification (wizard UX, group these as they're all in FinancialStudio.tsx)
4. **Phase 4 — Issue 3:** Edit report → wizard navigation
5. **Phase 5 — Issues 6b:** Sidebar New Report shortcuts
6. **Phase 6 — Issue 7:** Trial balance classifier + CA question improvement
7. **Phase 7 — Issue 8:** Opinion gate + account grouping
8. **Phase 8 — Issue 9:** Format extractor (verify/complete extract-format endpoint)
9. **Phase 9 — Issue 10:** Subagent architecture (base class + all 10 agents)

**Issue 5 is complete — skip.**

---

## Phase 1 — Issue 2: Source Panel Freeze Bug

**Goal:** Fix chat freezing when source panel is closed/reopened in LegalStudio.

### Files to Read First
- `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` (259 lines)
- `frontend/src/components/studios/LegalStudio/SourcePeeker.tsx` (182 lines)

### What to Fix

**LegalStudio.tsx — state isolation:**
- Lines 54–55: `activeSource` and `sourcePanelOpen` are already separate from conversation state — this is correct
- Line 173: `handleSourceClick()` toggles `activeSource` — verify it does NOT touch `messages` or `conversationId`
- **Suspected bug:** Lines 185–192 — `prevLoadingRef` useEffect auto-opens source panel after response. Verify this effect does not cause a render loop or corrupt `messages` state when panel closes mid-stream
- **Fix rule:** On panel close, call `setActiveSource(null)`. Never set `sourcePanelOpen` from inside a `messages` or `loading` state effect

**SourcePeeker.tsx — clean unmount:**
- Lines 42–53: useEffect fetches source text when panel opens — verify cleanup function cancels pending fetch on unmount
- Lines 33–39: Escape key listener — verify `removeEventListener` is called in cleanup
- Line 30: `const isOpen = isOpenProp !== undefined ? isOpenProp : sources.length > 0` — if `isOpenProp` is `false` but sources array is non-empty, panel still opens. This could cause re-open after close. **Fix:** always respect `isOpenProp` when it is explicitly provided; only use fallback when prop is `undefined`

### Verification Checklist
- [ ] Open a chat, receive a message with sources, open source panel
- [ ] Close source panel — chat input remains functional, no freeze
- [ ] Send another message — sources update correctly
- [ ] Refresh/reopen app — source panel initialises closed

### Anti-Pattern Guards
- Do NOT store `sourcePanelOpen` in localStorage
- Do NOT reset `messages` on panel close
- Do NOT use `sources.length > 0` as open condition when `isOpenProp` is explicitly `false`

---

## Phase 2 — Issue 1: VAT/Peppol RAG Training

**Goal:** Ingest the Peppol PDF + seed Q&A into ChromaDB so the chatbot answers VAT/Peppol questions better.

**Note:** The prompt router already has the `vat_peppol` domain and system prompt. Only the data ingestion and seed file are missing.

### Step 1 — Create Seed Q&A File

**Create:** `backend/data/qa_seeds/vat_peppol_qa.json`

Format (array of objects):
```json
[
  {
    "question": "What is the VAT registration threshold in the UAE?",
    "answer": "AED 375,000 annual taxable turnover triggers mandatory VAT registration under UAE Federal Decree-Law No. 8 of 2017, Article 17.",
    "source": "UAE VAT Law Art. 17"
  }
]
```

Required topics (20–30 pairs):
- Peppol ID registration threshold and steps
- UAE VAT standard (5%), zero-rated, exempt rates with examples
- E-Invoicing mandate timeline and phases
- Third-party shipment rules and Peppol network
- FTA filing requirements and deadlines
- Bad debt relief (Article 64)
- Input tax recovery rules
- VAT group registration
- Reverse charge mechanism (imports)
- Voluntary registration criteria

### Step 2 — Verify Ingestor Script

Read `backend/bulk_ingest.py` (or equivalent) to confirm:
- It accepts a file path argument
- It runs `document_processor.process()` then stores chunks in ChromaDB
- It works with JSON Q&A format (may need a separate loader for the seed JSON)

### Step 3 — Run Ingestion

```bash
cd backend
# Ingest the Peppol PDF
uv run python bulk_ingest.py "brain/UAE E-Invoicing and Peppol for Third-Party Shipments.pdf"

# Ingest the seed Q&A (if the script supports JSON, otherwise write a small one-off loader)
uv run python bulk_ingest.py "data/qa_seeds/vat_peppol_qa.json"
```

### Verification Checklist
- [ ] ChromaDB collection shows increased document count after ingestion
- [ ] Ask "What is the Peppol ID registration threshold?" in LegalStudio → answer cites AED 375,000
- [ ] Ask "What is the UAE VAT rate?" → answer cites 5% and references the Decree-Law
- [ ] Source panel shows the Peppol PDF as source

### Anti-Pattern Guards
- Do NOT modify `prompt_router.py` — the `vat_peppol` domain is already correct
- Do NOT hardcode answers in code — put them in the seed JSON for RAG retrieval

---

## Phase 3 — Issues 4 & 6a/6c: Wizard UX Verification + Fixes

**Goal:** Verify pre-fill, Back button, and explicit-save are working; fix any gaps.

### Files to Read First
- `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx` (769 lines) — read fully
- `frontend/src/components/studios/FinancialStudio/ReportRequirements.tsx` (505 lines)

### Issue 4 — Pre-fill Verification

**Check:** Is `companyInfo` prop passed from `FinancialStudio.tsx` to `ReportRequirements.tsx`?
- `FinancialStudio.tsx` state: `companyInfo` at line 46
- `ReportRequirements.tsx` props: `companyInfo?: CompanyInfo` at line 24

**If companyInfo is passed correctly:**
- Verify `period_end` field is also pre-filled (not just `company_name`)
- In `ReportRequirements.tsx` useEffect (lines 45–49): add pre-fill for `period_end_date` from `companyInfo.period_end` if field key exists in `reportFieldDefs`

**If companyInfo is NOT passed:**
- Add `companyInfo={companyInfo}` to the `<ReportRequirements>` component render in `FinancialStudio.tsx`

### Issue 6a — Back Button Verification

**Check:** Does `handleBack` render on all steps 2–9?
- Find the wizard footer render section in `FinancialStudio.tsx`
- Verify each step (2 through 9) has a "← Back" button calling `handleBack()`
- Step 1 (Select Type) must NOT have a Back button
- Back must NOT reset form state for the current step

**If Back button is missing from any step:** Add `<button onClick={handleBack}>← Back</button>` to the footer of that step's render block.

### Issue 6c — Explicit Save Verification

**Check:** Does the "Save Draft" button only appear from Step 6 onward?
- In `FinancialStudio.tsx`: find where `handleSaveDraft()` button is rendered
- Verify condition: only render when `activeStep >= 6`
- Verify "Save Final" appears only on Step 9

**Check:** Is there any auto-save call on step progression?
- Search for any `POST /api/reports/saved` or `handleSaveDraft()` call triggered by `setActiveStep` — there should be none

### Verification Checklist
- [ ] Upload company docs in Step 3 → Step 4 shows company name pre-filled with "auto-filled" badge
- [ ] Period end date pre-filled if extracted from docs
- [ ] Click Back from Step 4 → returns to Step 3 with Step 4 fields intact
- [ ] Navigate to Step 7 → "Save Draft" button is visible
- [ ] Navigate forward without saving → browser shows warning on tab close
- [ ] Step 1 has no Back button

---

## Phase 4 — Issue 3: Edit Report → Wizard Navigation

**Goal:** Replace text modal with wizard navigation to Step 6 when user clicks Edit on a saved report.

### Files to Read First
- `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx` (lines 100–180 for state management, any modal code)
- `backend/api/reports.py` (line 1408 — `get_saved_report` endpoint)

### Backend Change

**Add endpoint** in `backend/api/reports.py`:
```python
@router.get("/saved/{report_id}/wizard-state")
async def get_report_wizard_state(report_id: str, db: AsyncSession = Depends(get_db)):
    report = await db.get(SavedReport, report_id)
    if not report:
        raise HTTPException(status_code=404)
    return {
        "wizard_state": report.wizard_state_json,
        "has_wizard_state": report.wizard_state_json is not None,
        "draft_content": report.draft_content,
    }
```

### Frontend Change — FinancialStudio.tsx

**Find** the Edit button handler for saved reports in the left sidebar.

**Replace** current behaviour (opens text modal) with:
```typescript
async function handleEditReport(reportId: string) {
  const res = await fetch(`${API_BASE}/api/reports/saved/${reportId}/wizard-state`);
  const data = await res.json();
  
  if (data.has_wizard_state && data.wizard_state) {
    // Hydrate all wizard state from saved JSON
    const ws = data.wizard_state;
    setSelectedConfig(ws.selectedConfig ?? null);
    setColumns(ws.columns ?? []);
    setAuditRows(ws.auditRows ?? []);
    setReportFields(ws.reportFields ?? {});
    setRequirements(ws.requirements ?? {});
    setCompanyInfo(ws.companyInfo ?? null);
    setAuditDraft(ws.auditDraft ?? data.draft_content ?? '');
    setAuditFormat(ws.auditFormat ?? 'big4');
    setReportMode(ws.reportMode ?? 'standalone');
    setActiveStep(6);  // Navigate to Draft Report step
  } else {
    // Fallback: show banner + text editor for old reports
    setLegacyEditReport({ id: reportId, content: data.draft_content });
    setShowLegacyEditModal(true);
  }
}
```

**Remove** the current text-modal code and replace with the legacy fallback banner:
> "This report was created before the new wizard. Edit is limited to text only."

**Ensure wizard_state_json is saved** when user saves a draft/final report:
- In `handleSaveDraft()`: include current wizard state as `wizard_state_json` in the POST body

### Verification Checklist
- [ ] Generate and save a new report → Edit opens at Step 6 with correct content
- [ ] Edit a pre-existing report (wizard_state_json = null) → shows fallback banner + text editor
- [ ] Navigate backward from Step 6 in edit mode → Steps 1–5 show correct data

---

## Phase 5 — Issue 6b: Sidebar New Report Shortcuts

**Goal:** Add a "New Report" collapsible section at the top of the left sidebar with one button per report type.

### Files to Read First
- `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx` — find the sidebar render section

### Frontend Change — FinancialStudio.tsx

**Find** the left sidebar panel (currently shows "Saved Reports" list).

**Add** above the Saved Reports section:
```typescript
const REPORT_SHORTCUTS = [
  { key: 'audit', label: 'Audit Report' },
  { key: 'vat_return', label: 'VAT Return' },
  { key: 'corporate_tax', label: 'Corporate Tax' },
  { key: 'compliance', label: 'Compliance Report' },
  { key: 'mis', label: 'MIS Report' },
  { key: 'financial_analysis', label: 'Financial Analysis' },
  { key: 'budget_vs_actual', label: 'Budget vs Actual' },
  { key: 'ifrs', label: 'IFRS Financial Statements' },
  { key: 'cashflow', label: 'Cash Flow Statement' },
  { key: 'custom', label: 'Custom Report' },
] as const;

function handleNewReportShortcut(reportKey: string) {
  const config = REPORT_TYPE_CONFIGS.find(c => c.key === reportKey);
  if (config) {
    setSelectedConfig(config);
    // Reset all wizard state
    setColumns([]); setAuditRows([]); setReportFields({});
    setRequirements({}); setCompanyInfo(null); setAuditDraft('');
    setActiveStep(2);  // Skip Step 1 (type selection), go to upload
  }
}
```

**Add state** for sidebar collapse: `const [shortcutsOpen, setShortcutsOpen] = useState(true)`

**Add render:**
```tsx
<div>
  <button onClick={() => setShortcutsOpen(o => !o)}>
    {shortcutsOpen ? '▾' : '▸'} New Report
  </button>
  {shortcutsOpen && REPORT_SHORTCUTS.map(s => (
    <button key={s.key} onClick={() => handleNewReportShortcut(s.key)}>
      {s.label}
    </button>
  ))}
</div>
```

**Note:** Check that `REPORT_TYPE_CONFIGS` (or equivalent) is the array used to populate Step 1's card grid — use the same objects so `selectedConfig` is correctly set.

### Verification Checklist
- [ ] "New Report" section appears above "Saved Reports" in sidebar
- [ ] Clicking "Audit Report" jumps to Step 2 with audit config selected
- [ ] Clicking "VAT Return" jumps to Step 2 with VAT config
- [ ] Collapse arrow toggles section visibility

---

## Phase 6 — Issue 7: Trial Balance Classifier + CA Questions

**Goal:** Create the ML risk classifier and improve CA-quality audit questions.

### Files to Read First
- `backend/core/` — check if `trial_balance_classifier.py` exists yet
- `backend/api/reports.py` lines 1451–1463 — `get_audit_ca_questions` endpoint (current logic)
- `backend/core/agents/` — check if directory exists

### Step 1 — Create Training Data

**Create:** `backend/data/training/account_grouping_labels.csv`
```csv
account_name,category
Cash and Bank Balances,Current Assets
Accounts Receivable,Current Assets
Inventory,Current Assets
Prepaid Expenses,Current Assets
Property Plant and Equipment,Non-Current Assets
Accumulated Depreciation,Non-Current Assets
Intangible Assets,Non-Current Assets
Accounts Payable,Current Liabilities
Accrued Expenses,Current Liabilities
Short Term Loans,Current Liabilities
Long Term Loans,Non-Current Liabilities
Share Capital,Equity
Retained Earnings,Equity
Accumulated Losses,Equity
Revenue,Revenue
Sales,Revenue
Service Income,Revenue
Commission Received,Revenue
Interest Income,Other Income
Rental Income,Other Income
Cost of Sales,Cost of Revenue
Direct Expenses,Cost of Revenue
Salaries and Wages,Operating Expenses
Rent Expense,Operating Expenses
Utilities,Operating Expenses
Depreciation Expense,Operating Expenses
Administrative Expenses,Operating Expenses
Interest Expense,Finance Costs
Bank Charges,Finance Costs
Income Tax Expense,Tax Expense
```
(Extend to ~200 rows covering UAE-common account names)

### Step 2 — Create Classifier

**Create:** `backend/core/trial_balance_classifier.py`

The class must implement:
```python
class TrialBalanceClassifier:
    def __init__(self):
        # Train RandomForest from account_grouping_labels.csv on first use
        # Save/load model from backend/data/training/model.pkl
        
    def classify(self, account_name: str) -> tuple[str, float]:
        # Returns (suggested_group, confidence)
        # Uses TF-IDF vectorizer + RandomForestClassifier
        
    def analyze(self, rows: list[dict], company_info: dict = None) -> dict:
        # rows: [{"account_name": str, "amount": float, "category": str}]
        # Returns the full risk JSON structure from the spec:
        # {"grouping": [...], "risk_flags": [...], "financial_ratios": {...}}
        
    def _compute_risk_flags(self, rows, company_info) -> list[dict]:
        # Hard-coded rules (NOT ML):
        # going_concern: current_ratio < 1.0 OR accumulated_losses > 50% capital
        # related_party: account_name contains shareholder name
        # large_variance: change > 40% on amounts > AED 100,000
        # negative_equity: total equity < 0
        
    def _compute_ratios(self, rows) -> dict:
        # current_ratio, debt_to_equity, gross_margin
```

**Use these imports** (all already in requirements.txt):
```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
import pickle
```

### Step 3 — Improve CA Questions Endpoint

**Modify** `backend/api/reports.py` line 1451 — `get_audit_ca_questions`:

```python
@router.post("/audit/ca-questions")
async def get_audit_ca_questions(payload: dict):
    # payload should include: {"trial_balance_rows": [...], "company_info": {...}}
    # Run classifier on trial_balance_rows
    # Pass risk_flags + ratios to LLM with the prompt from the spec
    # Return {"questions": [{"id", "question", "account", "isa_reference", "risk"}]}
    
    classifier = TrialBalanceClassifier()
    analysis = classifier.analyze(payload.get("trial_balance_rows", []), payload.get("company_info"))
    
    # Build LLM prompt with risk flags
    system_prompt = """You are a senior Chartered Accountant..."""  # from spec
    # Call get_llm_provider().chat(...)
    # Parse numbered list from response into structured questions
```

**Update** `frontend/src/components/studios/FinancialStudio/AuditEvidenceStep.tsx`:
- Pass `auditRows` and `companyInfo` in the request body to `/api/reports/audit/ca-questions`
- Currently line ~50 only fetches with no body — add `body: JSON.stringify({ trial_balance_rows: auditRows, company_info: companyInfo })`

### Verification Checklist
- [ ] Upload a trial balance → `TrialBalanceClassifier.analyze()` returns risk flags JSON
- [ ] `going_concern` flag triggered when current ratio < 1.0
- [ ] `related_party` flag triggered when account matches shareholder name
- [ ] CA questions in AuditEvidenceStep are ISA-referenced and account-specific (not generic)
- [ ] Questions show ISA standard number (ISA 240, ISA 505, ISA 570, etc.)

### Anti-Pattern Guards
- Do NOT use ML for risk flag rules — they are hard-coded logic
- Do NOT call the LLM for account grouping classification — that's the RandomForest's job
- Do NOT train the model on every request — train once, pickle, reload from disk

---

## Phase 7 — Issue 8: Opinion Gate + Account Grouping

**Goal:** Block unqualified opinion when evidence is insufficient; use classifier for correct grouping.

### Files to Read First
- `frontend/src/components/studios/FinancialStudio/AuditEvidenceStep.tsx` lines 83–106 (existing opinion logic)
- `backend/api/reports.py` lines 355–474 (`generate_draft_report` endpoint)

### Backend Change — Opinion Gate

**Modify** `backend/api/reports.py` — `generate_draft_report` (line 355):

Before constructing the LLM prompt, add a gate check:
```python
# Check evidence completeness
opinion_type = "unqualified"  # default

signed_report_uploaded = any(
    r.get("account_name", "").lower() in ["signed audit report", "management accounts"]
    for r in req.audit_rows or []
)
has_signed_doc = req.prior_year_content or signed_report_uploaded

# Check if all ISA-critical questions answered (passed from frontend)
isa_critical_answered = all(
    q.get("answered") for q in (req.ca_questions or [])
    if q.get("risk") in ["going_concern", "fraud", "related_party"]
)

if not has_signed_doc or not isa_critical_answered:
    opinion_type = "disclaimer"
elif req.risk_flags and any(
    f["triggered"] for f in req.risk_flags if f.get("flag") in ["going_concern", "negative_equity"]
):
    opinion_type = "qualified"

# Add opinion_type to the LLM prompt
```

**Update `DraftReportRequest` schema** to include `ca_questions`, `risk_flags` optional fields.

### Account Grouping via Classifier

**Modify** `backend/api/reports.py` — `upload_trial_balance_endpoint` (line 1137):

After parsing rows, run the classifier:
```python
classifier = TrialBalanceClassifier()
for row in grouped_rows:
    if not row.get("category") or row["category"] == "Unknown":
        suggested, confidence = classifier.classify(row["account_name"])
        if confidence > 0.7:
            row["category"] = suggested
            row["category_source"] = "classifier"
```

### Frontend Change — Wire ca_questions + risk_flags to Draft Generation

In `FinancialStudio.tsx`, when calling the draft endpoint, include:
```typescript
ca_questions: caQuestions,    // from AuditEvidenceStep
risk_flags: evidenceResult?.risk_flags ?? [],
```

### Verification Checklist
- [ ] Generate report with no signed doc uploaded → opinion says "Disclaimer of Opinion"
- [ ] Answer all going-concern questions + upload signed report → opinion says "Unqualified"
- [ ] Current ratio < 1.0 → opinion says "Qualified"
- [ ] Account "Commission Received" groups as "Revenue" not miscellaneous

---

## Phase 8 — Issue 9: Format Extractor

**Goal:** Ensure `extract-format` endpoint returns structured `format_template.json`, not just raw text.

### Files to Read First
- `backend/api/reports.py` lines 1645–1654 — current `extract_format` endpoint
- `frontend/src/components/studios/FinancialStudio/AuditFormatSelector.tsx` — what it does with the response

### Backend Change

**Read** the current `extract_format` endpoint at line 1645. If it returns raw text only:

**Create:** `backend/core/format_extractor.py`

```python
class FormatExtractor:
    def extract(self, filepath: str, file_type: str) -> dict:
        # Returns format_template.json dict per the spec
        if file_type in ("xlsx", "xls"):
            return self._extract_excel(filepath)
        elif file_type == "pdf":
            return self._extract_pdf(filepath)
        elif file_type in ("docx", "doc"):
            return self._extract_docx(filepath)
    
    def _extract_excel(self, path) -> dict:
        # openpyxl — merged cells, column widths, indent levels, bold rows, number formats
        # Returns format_template.json structure from spec
        
    def _extract_pdf(self, path) -> dict:
        # pdfplumber — column x-positions, font sizes, horizontal lines
        # NOTE: pdfplumber NOT in requirements.txt — use PyMuPDF (fitz) instead (already installed)
        
    def _extract_docx(self, path) -> dict:
        # python-docx — table structure, heading styles, number formats
```

**Important:** `pdfplumber` is NOT in `requirements.txt`. Use `PyMuPDF` (`fitz`) for PDF extraction — it is already installed (`PyMuPDF==1.25.3`).

**Modify** `backend/api/reports.py` line 1645 — `extract_format`:
```python
@router.post("/extract-format")
async def extract_format(file: UploadFile = File(...)):
    # Save file to temp path
    # Call FormatExtractor().extract(path, file_type)
    # Return the format_template dict
```

### Frontend Change — AuditFormatSelector.tsx

The frontend already calls `extract-format` and stores `extractedSections`. Verify:
- Lines 82–96: Displays extracted sections list — confirm it shows structured data (columns, hierarchy) not just raw text
- Add a "Save as default for this company" option (optional, post-MVP)

### Add Company-Level Format Default (Optional)

If implementing company-level defaults:
- Store `format_template_json` in `UserSettings` table (key = `"format_default_{company_name_slug}"`)
- On Step 7: check for existing default and offer "Use saved company format" option

### Verification Checklist
- [ ] Upload `Castle Plaza Draft FS 2025.xlsx` → response contains columns array, hierarchy, currency="AED"
- [ ] Upload a DOCX report → response contains table structure and heading levels
- [ ] Upload a PDF → response contains column positions from PyMuPDF
- [ ] Format template used in LLM prompt → generated report matches column order

### Anti-Pattern Guards
- Do NOT add `pdfplumber` to requirements — use `fitz` (PyMuPDF) which is already installed
- Do NOT pass the entire template file as tokens to the LLM — extract structure first, then pass the JSON

---

## Phase 9 — Issue 10: Subagent Architecture

**Goal:** Create `BaseReportAgent` and 10 agent classes; wire via registry in reports.py.

### Files to Read First
- `backend/api/reports.py` lines 975–1136 — `generate_ai_report` (current logic to replace)
- `backend/core/llm_manager.py` lines 18–34 (BaseLLMProvider interface)

### Step 1 — Create Base Class

**Create:** `backend/core/agents/base_agent.py`
```python
from abc import ABC, abstractmethod
from core.llm_manager import get_llm_provider, BaseLLMProvider

class BaseReportAgent(ABC):
    def __init__(self, llm_provider: BaseLLMProvider = None, classifier=None):
        self.llm = llm_provider or get_llm_provider()
        self.classifier = classifier  # TrialBalanceClassifier instance (optional)
    
    @abstractmethod
    def collect_data(self, wizard_state: dict) -> dict:
        """Extract relevant data from wizard state for this report type."""
        ...
    
    @abstractmethod
    def ask_questions(self, data: dict) -> list[str]:
        """Return report-type-specific questions for the user."""
        ...
    
    @abstractmethod  
    def validate_evidence(self, evidence: dict) -> tuple[bool, list[str]]:
        """Check if sufficient evidence exists. Returns (is_valid, list_of_missing_items)."""
        ...
    
    @abstractmethod
    async def generate(self, data: dict, format_template: dict = None) -> str:
        """Generate the report. Returns Markdown string."""
        ...
    
    async def _call_llm(self, system: str, user: str, temperature: float = 0.2) -> str:
        response = await self.llm.chat(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
        )
        return response.content
```

### Step 2 — Create Agent Classes

**Create each file** in `backend/core/agents/`. Each agent must:
1. Inherit from `BaseReportAgent`
2. Implement all 4 abstract methods
3. Use domain-specific system prompts (ISA for audit, FTA VAT-201 for VAT, etc.)
4. Include the per-agent question sets from the spec

**Priority order for creation:**
1. `audit_agent.py` (AuditAgent) — most complex, merges Issue 7 work
2. `vat_agent.py` (VATAgent)
3. `ifrs_agent.py` (IFRSAgent)
4. `cashflow_agent.py`, `corporate_tax_agent.py`, `compliance_agent.py`
5. `mis_agent.py`, `financial_analysis_agent.py`, `budget_agent.py`, `custom_agent.py`

**Pattern to follow for each agent:**
```python
# backend/core/agents/vat_agent.py
from core.agents.base_agent import BaseReportAgent

class VATAgent(BaseReportAgent):
    SYSTEM_PROMPT = """You are a UAE VAT specialist...(FTA VAT-201 structure)..."""
    
    QUESTIONS = [
        "What is the total taxable supply for the period?",
        "Are there any zero-rated or exempt supplies to separate?",
        "Any adjustments for bad debt relief (Article 64 UAE VAT Law)?",
    ]
    
    def collect_data(self, wizard_state: dict) -> dict:
        return {
            "trial_balance": wizard_state.get("auditRows", []),
            "company_info": wizard_state.get("companyInfo"),
            "requirements": wizard_state.get("requirements", {}),
        }
    
    def ask_questions(self, data: dict) -> list[str]:
        return self.QUESTIONS
    
    def validate_evidence(self, evidence: dict) -> tuple[bool, list[str]]:
        missing = []
        if not evidence.get("trial_balance_uploaded"):
            missing.append("Trial balance required for VAT computation")
        return (len(missing) == 0, missing)
    
    async def generate(self, data: dict, format_template: dict = None) -> str:
        user_prompt = f"Generate VAT Return report for:\n{data}"
        return await self._call_llm(self.SYSTEM_PROMPT, user_prompt)
```

### Step 3 — Wire Agent Registry

**Modify** `backend/api/reports.py` — replace `generate_ai_report` logic (line 975):

```python
from core.agents.base_agent import BaseReportAgent
from core.agents.audit_agent import AuditAgent
from core.agents.vat_agent import VATAgent
# ... all agents

AGENT_REGISTRY: dict[str, type[BaseReportAgent]] = {
    "audit": AuditAgent,
    "vat_return": VATAgent,
    "corporate_tax": CorporateTaxAgent,
    "compliance": ComplianceAgent,
    "mis": MISAgent,
    "financial_analysis": FinancialAnalysisAgent,
    "budget_vs_actual": BudgetAgent,
    "ifrs": IFRSAgent,
    "cashflow": CashFlowAgent,
    "custom": CustomAgent,
}

@router.post("/generate/{report_type}")
async def generate_ai_report(report_type: str, req: GenericReportRequest):
    agent_class = AGENT_REGISTRY.get(report_type)
    if not agent_class:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")
    
    agent = agent_class()
    data = agent.collect_data(req.wizard_state or {})
    is_valid, missing = agent.validate_evidence(req.evidence or {})
    report_md = await agent.generate(data, req.format_template)
    return {"content": report_md, "missing_evidence": missing, "is_complete": is_valid}
```

### Verification Checklist
- [ ] `AGENT_REGISTRY` covers all 10 report types
- [ ] `BaseReportAgent` cannot be instantiated directly (ABC enforces this)
- [ ] `AuditAgent.generate()` checks opinion gate (from Phase 7) before calling LLM
- [ ] `VATAgent.ask_questions()` returns Article 64 question
- [ ] Unknown report_type returns 400, not 500
- [ ] Existing `/api/reports/generate/{type}` calls work identically from frontend

### Anti-Pattern Guards
- Do NOT use if/else chains for report type — use AGENT_REGISTRY dict exclusively
- Do NOT duplicate system prompts — each agent owns its own `SYSTEM_PROMPT` class attribute
- Do NOT skip `validate_evidence()` — it is always called before `generate()`

---

## New Files Summary

```
backend/
├── core/
│   ├── trial_balance_classifier.py        Phase 6
│   ├── format_extractor.py                Phase 8
│   └── agents/
│       ├── base_agent.py                  Phase 9
│       ├── audit_agent.py                 Phase 9 (merges Phase 6)
│       ├── vat_agent.py                   Phase 9
│       ├── corporate_tax_agent.py         Phase 9
│       ├── compliance_agent.py            Phase 9
│       ├── mis_agent.py                   Phase 9
│       ├── financial_analysis_agent.py    Phase 9
│       ├── budget_agent.py                Phase 9
│       ├── ifrs_agent.py                  Phase 9
│       ├── cashflow_agent.py              Phase 9
│       └── custom_agent.py               Phase 9
├── data/
│   ├── qa_seeds/
│   │   └── vat_peppol_qa.json            Phase 2
│   └── training/
│       └── account_grouping_labels.csv   Phase 6
```

## Modified Files Summary

```
backend/api/reports.py          Phases 4, 7, 8, 9
backend/db/models.py            Phase 4 (if wizard_state_json not fully wired)
frontend/FinancialStudio.tsx    Phases 3, 4, 5, 7
frontend/ReportRequirements.tsx Phase 3
frontend/AuditEvidenceStep.tsx  Phases 6, 7
frontend/AuditFormatSelector.tsx Phase 8
frontend/LegalStudio.tsx        Phase 1
frontend/SourcePeeker.tsx       Phase 1
```

---

## Dependency Map (Which Phases Block Which)

```
Phase 1 (Source bug)     — independent
Phase 2 (RAG training)   — independent
Phase 3 (Wizard UX)      — independent
Phase 4 (Edit→Wizard)    — independent (DB column already exists)
Phase 5 (Sidebar)        — independent
Phase 6 (Classifier)     — must complete before Phase 7
Phase 7 (Opinion gate)   — depends on Phase 6 (classifier must exist)
Phase 8 (Format)         — independent (parallel with 6–7)
Phase 9 (Subagents)      — depends on Phase 7 (AuditAgent merges opinion gate)
```

Phases 1–5 can be done in any order. Phases 6→7→9 must be sequential. Phase 8 is independent.
