# Option B: NotebookLM-Style Audit System — Design & Plan

> **Scope:** Build a document understanding layer. System learns custom patterns from uploaded files. Generates JSON-based structured audit reports. Then auto-converts to any format (PDF, DOCX, Excel).
> 
> **Timeline:** 3–5 days (first MVP)
> 
> **Vision:** Users upload source docs → system understands requirements → generates perfect reports on demand

---

## Problem Statement (Addressed by Option B)

Current wizard problems are **symptoms** of a deeper issue: the system treats each wizard step as isolated LLM calls. It doesn't:
- **Understand** the user's custom requirements (format, grouping, disclosure preferences)
- **Learn** from example documents (prior audits, templates, client preferences)
- **Remember** patterns across wizard steps
- **Output** machine-readable structured data (JSON) that can be formatted flexibly

Example: User says "generate format like Castle Plaza 2025" — currently this is a manual one-off PDF template. In a NotebookLM system, it's a pattern the system learned from the uploaded file.

---

## Vision: How It Works (Like NotebookLM)

### **Phase 1: Upload & Learn (⏱ Take time to understand)**

```
User uploads:
├─ Trial Balance 2024.xlsx (current year GL)
├─ Audit Report 2023.pdf (prior year audit)
├─ Castle Plaza 2025.pdf (target format example)
├─ Chart of Accounts.xlsx (account mapping guide)
└─ Firm Template.docx (custom audit structure)

System reads & understands:
├─ Financial data: Revenue 2M, Assets 5M, Liabilities 1.2M, …
├─ Format patterns: "3-column tables, Notes refs, 25 pages, organized sections"
├─ Account grouping: "Operating expenses broken into: Salaries, Rent, Admin, Other"
├─ Disclosure rules: "Include management commentary, risk assessment, going concern"
├─ Naming conventions: "Report title format, auditor signature block location"
└─ Account mappings: "Salary account 4001 → Staff Costs, Rent 4005 → Premises"
```

### **Phase 2: Analyze & Extract Patterns (⏱ Build knowledge base)**

System creates a **Audit Profile JSON** summarizing what it learned:

```json
{
  "audit_profile": {
    "client_name": "Castle Plaza Development",
    "period": "2025",
    "financial_data": {
      "revenue": 2400000,
      "cost_of_sales": 1200000,
      "gross_profit": 1200000,
      "assets_total": 5800000,
      "liabilities_total": 1200000,
      "equity": 4600000
    },
    "format_template": {
      "columns": ["Notes", "31.12.2024 AED", "31.12.2023 AED"],
      "page_structure": {
        "cover_page": { "title": "FINANCIAL STATEMENTS AND INDEPENDENT AUDITOR'S REPORT", "metadata": ["company", "location", "period"] },
        "toc_pages": 1,
        "auditor_report_pages": 3,
        "financial_statements_pages": 5,
        "notes_pages": 15,
        "total_pages": 25
      },
      "statement_groupings": {
        "balance_sheet": {
          "assets": ["Current Assets", "Non-Current Assets"],
          "liabilities": ["Current Liabilities", "Non-Current Liabilities"],
          "equity": ["Paid-up Capital", "Retained Earnings", "Reserves"]
        },
        "p_and_l": {
          "revenue": "Revenue",
          "cost_of_sales": "Cost of Sales",
          "gross_profit": "Gross Profit",
          "operating_expenses": {
            "category": "Operating Expenses",
            "sub_groups": ["Staff Costs", "Premises & Utilities", "Admin & General", "Depreciation", "Other"]
          },
          "finance_costs": "Finance Costs",
          "other_income": "Other Income",
          "net_profit": "Net Profit"
        }
      },
      "notes_requirements": {
        "mandatory": ["Accounting Policies", "Critical Accounting Estimates", "Related Party Transactions"],
        "conditional": ["Going Concern", "Contingencies", "Commitments"],
        "disclosure_levels": "Full IFRS 16+ disclosures"
      }
    },
    "account_mapping": {
      "4001": { "name": "Salaries & Wages", "group": "Staff Costs", "mapped_to": "Staff Costs" },
      "4005": { "name": "Rent Expense", "group": "Premises", "mapped_to": "Premises & Utilities" },
      ...
    },
    "custom_requirements": {
      "audit_scope": "Full audit per ISA 200-599",
      "opinion_type": "Unqualified",
      "comparative_required": true,
      "management_commentary": true,
      "risk_disclosures": ["Going Concern", "Financial Risk", "Credit Risk"]
    }
  }
}
```

### **Phase 3: Generate On-Demand (✨ Perfect output)**

```
User request: "Generate audit report"

System:
1. Reads audit_profile.json (learned from uploaded files)
2. Combines with current trial balance
3. Generates intermediate JSON:
   {
     "audit_report": {
       "metadata": { … },
       "sections": {
         "auditor_opinion": { … },
         "financial_statements": { … },
         "notes": { … }
       }
   }
4. Applies format_template from profile
5. Outputs:
   ├─ audit_report.json (structured, machine-readable)
   ├─ audit_report.pdf (auto-formatted per Castle Plaza pattern)
   ├─ audit_report.docx (editable version)
   └─ audit_report.xlsx (data extract for further analysis)
```

---

## Architecture: New Components

### **New Database Schema**

```sql
-- User Audit Profiles (one per engagement)
CREATE TABLE audit_profiles (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  engagement_name VARCHAR NOT NULL,
  client_name VARCHAR,
  period_end DATE,
  profile_json JSONB NOT NULL,  -- The learned audit_profile from above
  source_files JSONB,  -- Metadata of uploaded files
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Source Documents (uploaded by user)
CREATE TABLE source_documents (
  id UUID PRIMARY KEY,
  profile_id UUID REFERENCES audit_profiles(id),
  document_type ENUM('trial_balance', 'prior_audit', 'template', 'chart_of_accounts', 'custom'),
  file_path VARCHAR,
  extracted_data JSONB,  -- LLM extraction (table data, patterns, etc)
  confidence FLOAT,
  uploaded_at TIMESTAMP
);

-- Report History (for each generation)
CREATE TABLE generated_reports (
  id UUID PRIMARY KEY,
  profile_id UUID REFERENCES audit_profiles(id),
  report_json JSONB NOT NULL,  -- Full structured audit report
  format_applied VARCHAR,  -- e.g., 'castle_plaza_2025'
  output_path VARCHAR,  -- S3 path to audit_report.pdf
  generated_at TIMESTAMP
);
```

### **New Backend Services**

```
backend/
├── core/
│   ├── document_analyzer.py          [NEW] Reads source docs, extracts patterns
│   ├── audit_profile_builder.py      [NEW] Builds audit_profile.json from uploaded files
│   ├── structured_report_generator.py [NEW] Generates audit_report.json (machine-readable)
│   ├── format_applier.py             [NEW] Applies format_template to JSON → PDF/DOCX
│   └── (existing) audit_formatter.py → DEPRECATED (replaced by format_applier.py)
│
├── api/
│   ├── document_upload.py            [NEW] /upload-source-document
│   ├── profile_management.py         [NEW] /profile/{id}, /list-profiles
│   ├── report_generation.py          [NEW] /generate-report (accepts profile_id + request)
│   └── (existing) reports.py         → KEPT for backward compat (wizard steps)
│
└── db/
    └── models.py                     [NEW] SQLAlchemy models for audit_profiles, source_documents
```

### **New Frontend Pages**

```
src/pages/
├── DocumentUpload/
│   ├── DocumentUpload.tsx            [NEW] Upload source files (trial balance, templates, etc)
│   ├── DocumentPreview.tsx           [NEW] Show extracted data from uploaded file
│   └── PatternExtraction.tsx         [NEW] Show "System learned these patterns"
│
├── AuditProfile/
│   ├── ProfileBuilder.tsx            [NEW] Review/edit audit_profile.json
│   ├── AccountMapping.tsx            [NEW] Manage account → group mappings
│   └── FormatCustomizer.tsx          [NEW] Define output format preferences
│
├── ReportGenerator/
│   ├── ReportGeneration.tsx          [NEW] "Generate audit report" button + options
│   ├── ReportPreview.tsx             [NEW] Show generated report in browser
│   └── ReportExport.tsx              [NEW] Download as PDF/DOCX/Excel
│
└── (existing) FinancialStudio/ → Kept as "Quick Report" fallback mode
```

---

## Implementation Phases

### **Phase 0: Prep (✓ Already done or reuse)**
- [x] Trial balance upload & grouping
- [x] Vision LLM extraction (fitz + NVIDIA)
- [x] Backend structure (FastAPI)
- [x] Frontend framework (React)

### **Phase 1: Document Understanding (Days 1-2)**

**Goal:** System can read uploaded source files and extract structured data.

**Deliverables:**
1. `document_analyzer.py` — Reads PDF/Excel/DOCX; extracts tables, text, structure
2. `audit_profile_builder.py` — Combines extractions into audit_profile.json
3. `/upload-source-document` endpoint — Accepts files; returns extracted_data
4. Database schema + migrations
5. `DocumentUpload.tsx` frontend

**Example:** User uploads Castle Plaza 2025.pdf → system extracts: "3-column table structure, 25 pages, Notes at pages 10-25, grouped expenses under sub-headings"

**Effort:** ~16 hours

---

### **Phase 2: Pattern Recognition (Days 2-3)**

**Goal:** System learns account mappings, grouping rules, and custom requirements.

**Deliverables:**
1. `audit_profile_builder.py` enhancements — Merge patterns from multiple source files
2. LLM-based pattern recognition — "Which account maps to which group? What's the user's format preference?"
3. `/profile/{id}` endpoint — Retrieve/update audit_profile.json
4. `ProfileBuilder.tsx` + `AccountMapping.tsx` frontend

**Example:** User uploads Chart of Accounts + prior audit → system infers: "Account 4001 (Salaries) should group as Staff Costs based on prior audit structure"

**Effort:** ~12 hours

---

### **Phase 3: Structured Report Generation (Day 4)**

**Goal:** Generate audit_report.json (machine-readable audit data), independent of format.

**Deliverables:**
1. `structured_report_generator.py` — Takes trial balance + audit_profile → generates audit_report.json
2. `/generate-report` endpoint — Async job (can take minutes)
3. Report JSON schema (OpenAPI spec)
4. `ReportGeneration.tsx` + `ReportPreview.tsx` frontend

**Example:** System generates audit_report.json with all sections (financials, notes, findings) in structured JSON format — no formatting yet.

**Effort:** ~14 hours

---

### **Phase 4: Format Application (Day 5)**

**Goal:** Convert audit_report.json to formatted PDF/DOCX/Excel matching learned patterns.

**Deliverables:**
1. `format_applier.py` — Takes audit_report.json + format_template from profile → applies layout, styling, page breaks
2. PDF renderer — Uses format_template to generate PDF
3. DOCX renderer — Uses format_template for Word format
4. Excel exporter — Extracts financial tables to Excel
5. `/export-report` endpoint — Returns file in requested format

**Example:** audit_report.json + Castle Plaza format_template → perfectly formatted PDF that matches Castle Plaza 2025 exactly

**Effort:** ~14 hours

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ UPLOAD PHASE (Document Understanding)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User uploads files                                              │
│  ├─ Trial Balance 2024.xlsx ──┐                                 │
│  ├─ Audit 2023.pdf           ├─→ document_analyzer.py           │
│  ├─ Template.docx            │   ↓                              │
│  └─ CoA.xlsx ────────────────┘   extract_structure()           │
│                                   ↓                              │
│                              [extracted_data JSON]              │
│                                   ↓                              │
│                          audit_profile_builder.py               │
│                                   ↓                              │
│                          [audit_profile.json] ← stored in DB    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ GENERATION PHASE (Report Creation)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User clicks "Generate Report"                                  │
│  ├─ Trial Balance (current year)                                │
│  ├─ audit_profile.json (learned patterns) ─┐                   │
│  └─ Request options (format, options) ─────┤                   │
│                                            ├→ structured_report_generator.py
│                                            │   ↓                 │
│                                            │   LLM generates    │
│                                            │   audit_report.json
│                                            │   ↓                 │
│                                            ├→ format_applier.py  │
│                                            │   ↓                 │
│                                    [PDF/DOCX/Excel files]      │
│                                            ↓                     │
│                              [File outputs stored in S3]        │
│                                            ↓                     │
│                            [sent to frontend for download]      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Changes & Additions

| File | Type | Change |
|------|------|--------|
| `backend/core/document_analyzer.py` | NEW | Extract tables/text from PDFs, Excel, DOCX |
| `backend/core/audit_profile_builder.py` | NEW | Merge extractions into audit_profile.json |
| `backend/core/structured_report_generator.py` | NEW | Generate audit_report.json from trial balance |
| `backend/core/format_applier.py` | NEW | Convert audit_report.json to PDF/DOCX/Excel |
| `backend/api/document_upload.py` | NEW | POST /upload-source-document |
| `backend/api/profile_management.py` | NEW | GET/POST /profile/{id} |
| `backend/api/report_generation.py` | NEW | POST /generate-report |
| `backend/db/models.py` | NEW | audit_profiles, source_documents, generated_reports |
| `backend/db/migrations/` | NEW | DB schema creation |
| `frontend/src/pages/DocumentUpload/` | NEW | Upload & preview source files |
| `frontend/src/pages/AuditProfile/` | NEW | Edit audit profile & patterns |
| `frontend/src/pages/ReportGenerator/` | NEW | Generate & download reports |
| `backend/api/reports.py` | KEEP | Wizard steps (backward compat) |
| `frontend/FinancialStudio/` | KEEP | Wizard (backward compat) |

---

## Data Schemas

### **audit_profile.json structure**

```json
{
  "profile_id": "uuid",
  "client_name": "Castle Plaza Development",
  "period": "2025",
  "financial_data": { "…": "…" },
  "format_template": {
    "columns": ["Notes", "CY AED", "PY AED"],
    "page_structure": { "…": "…" },
    "statement_groupings": { "…": "…" },
    "notes_requirements": { "…": "…" }
  },
  "account_mapping": {
    "4001": { "name": "Salaries", "group": "Staff Costs", "…": "…" }
  },
  "custom_requirements": { "…": "…" }
}
```

### **audit_report.json structure**

```json
{
  "report_id": "uuid",
  "profile_id": "uuid",
  "metadata": {
    "company_name": "Castle Plaza",
    "period_end": "2025-12-31",
    "auditor_name": "Ernst & Young"
  },
  "sections": {
    "auditor_opinion": {
      "type": "unqualified",
      "content": "We have audited the financial statements…"
    },
    "financial_statements": {
      "statement_of_financial_position": {
        "assets": { "…": "…" },
        "liabilities": { "…": "…" },
        "equity": { "…": "…" }
      },
      "statement_of_profit_loss": { "…": "…" }
    },
    "notes": {
      "accounting_policies": { "…": "…" },
      "critical_estimates": { "…": "…" }
    },
    "findings": { "…": "…" }
  }
}
```

---

## Testing Strategy

### **Unit Tests**
- `test_document_analyzer.py` — Extract from PDF/Excel/DOCX
- `test_audit_profile_builder.py` — Build profile from extractions
- `test_structured_report_generator.py` — Generate audit_report.json
- `test_format_applier.py` — Apply format to JSON → PDF

### **Integration Tests**
- End-to-end: Upload files → Generate report → Download PDF
- Format matching: Generated PDF matches Castle Plaza reference
- Account mapping: Custom mappings applied correctly
- Pattern learning: System correctly infers from multiple source files

### **Acceptance Tests**
- User can upload 5 source files without errors
- System learns Castle Plaza format from uploaded example
- Generated report matches Castle Plaza structure (page count, column count, section order)
- Report can be edited in Word, opened in Excel

---

## Effort Estimate

| Phase | Component | Hours |
|-------|-----------|-------|
| 1 | document_analyzer + upload endpoint | 16 |
| 2 | profile_builder + pattern recognition | 12 |
| 3 | structured_report_generator | 14 |
| 4 | format_applier + exporters | 14 |
| — | Testing + integration | 20 |
| — | Frontend UI | 24 |
| — | Deployment + docs | 10 |
| **TOTAL** | | **110 hours** |

**Timeline:** ~3–4 weeks (if 1 dev, part-time) or 1–2 weeks (if 2 devs, full-time)

---

## Success Criteria

- [ ] Users can upload 5+ source files (PDF, Excel, DOCX, images)
- [ ] System extracts financial data from each file (confidence > 80%)
- [ ] audit_profile.json is built from extracted patterns
- [ ] Generated audit_report.json is valid against schema
- [ ] Generated PDF matches Castle Plaza format (same column structure, page layout)
- [ ] Account mappings are applied correctly (custom groupings respected)
- [ ] Report can be edited in DOCX, analyzed in Excel
- [ ] Full workflow: Upload files → Generate perfect PDF in <2 minutes
- [ ] No manual intervention needed (fully automated)

---

## Future Enhancements (Post-MVP)

- [ ] Multi-language support (Arabic, English, etc.)
- [ ] Automated audit finding generation (based on KB of similar audits)
- [ ] Risk-based audit scope recommendation
- [ ] Compliance checker (UAE VAT, CIT, AML/CFT requirements)
- [ ] Peer review workflow (partner review before finalizing)
- [ ] Audit committee report generation
- [ ] Management letter template auto-population
- [ ] Continuous auditing (real-time data monitoring)

