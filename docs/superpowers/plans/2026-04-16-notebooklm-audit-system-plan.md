# Option B: NotebookLM-Style Audit System — Implementation Plan

> **Goal:** Build a document understanding layer. System learns custom patterns from uploaded files. Generates structured JSON audit reports. Auto-converts to any format.
>
> **Timeline:** 3–5 weeks (110 hours total)
>
> **Dependencies:** Option A (quick fixes) should be done first OR this replaces the wizard entirely
>
> **Status:** Architecture defined, ready to phase

---

## High-Level Phases

```
Phase 1: Document Understanding (Days 1-2, ~28 hours)
   ├─ file upload endpoint
   ├─ document_analyzer.py (extract from PDF/Excel/DOCX)
   └─ audit_profile_builder.py (merge extractions)

Phase 2: Pattern Recognition (Days 2-3, ~12 hours)
   ├─ account mapping inference
   ├─ format template extraction
   └─ profile editing UI

Phase 3: Structured Report Generation (Day 4, ~14 hours)
   ├─ audit_report.json schema
   ├─ structured_report_generator.py
   └─ LLM-based content generation

Phase 4: Format Application (Day 5, ~14 hours)
   ├─ format_applier.py (JSON → PDF/DOCX/Excel)
   ├─ PDF renderer (layout + styling)
   └─ export endpoints

Phase 5: Frontend UI (Days 3-6, ~24 hours)
   ├─ DocumentUpload page
   ├─ ProfileBuilder page
   ├─ ReportGenerator page
   └─ Integration with Phase 1-4 APIs

Phase 6: Testing + Integration (Days 5-6, ~20 hours)
   ├─ unit tests (all backend modules)
   ├─ integration tests (full workflow)
   ├─ acceptance tests (user scenarios)
   └─ performance testing

Phase 7: Deployment + Docs (Day 7, ~10 hours)
   ├─ Database migrations
   ├─ Deployment playbook
   └─ API documentation
```

---

## Phase 1: Document Understanding (Days 1-2)

### **Task B1.1: Create Database Schema**

**File:** `backend/db/models.py` (NEW)

```python
# Models:
# - AuditProfile (id, user_id, engagement_name, client_name, profile_json, created_at)
# - SourceDocument (id, profile_id, document_type, file_path, extracted_data, confidence)
# - GeneratedReport (id, profile_id, report_json, format_applied, output_path, generated_at)
```

**Subtasks:**
- [ ] Define SQLAlchemy models for audit_profiles, source_documents, generated_reports
- [ ] Define columns: id (UUID), foreign keys, JSONB fields, timestamps
- [ ] Add indexes for user_id, profile_id, created_at
- [ ] Write migration file (Alembic if using SQLAlchemy)

**Acceptance:**
- Models defined and can be instantiated
- Migration runs without error: `alembic upgrade head`
- Database tables created: `audit_profiles`, `source_documents`, `generated_reports`

---

### **Task B1.2: Implement Document Analyzer**

**File:** `backend/core/document_analyzer.py` (NEW)

**Functionality:** Read PDF/Excel/DOCX files; extract tables, text, structure.

**Subtasks:**
- [ ] Function `extract_from_pdf(file_path: str) -> dict` — PyMuPDF or pdfplumber
  - Extracts: tables, text, page layout, images
  - Returns: `{"tables": [...], "text": "...", "pages": 25, "structure": {...}}`
  
- [ ] Function `extract_from_excel(file_path: str) -> dict` — openpyxl
  - Extracts: sheet names, table data, cell formatting (columns, widths)
  - Returns: `{"sheets": {...}, "tables": [...], "formatting": {...}}`
  
- [ ] Function `extract_from_docx(file_path: str) -> dict` — python-docx
  - Extracts: paragraphs, tables, headings, formatting
  - Returns: `{"headings": [...], "tables": [...], "structure": {...}}`
  
- [ ] Main function `analyze_document(file_path: str, doc_type: str) -> dict`
  - Routes to correct extractor based on doc_type
  - Returns combined extraction dict

**Acceptance:**
- Can extract tables from Castle Plaza 2025.pdf (25 pages)
- Can extract trial balance from Excel file
- Can extract structure from DOCX template
- All extractions return valid JSON (no errors)

---

### **Task B1.3: Implement Audit Profile Builder**

**File:** `backend/core/audit_profile_builder.py` (NEW)

**Functionality:** Merge extractions from multiple source files into a unified audit_profile.json

**Subtasks:**
- [ ] Function `build_profile_from_documents(documents: list[dict]) -> dict`
  - Input: List of extracted_data dicts from Task B1.2
  - Merges: Financial figures, format templates, account groupings
  - Returns: Full audit_profile.json (see schema in design doc)
  
- [ ] Function `extract_financial_data(extraction: dict) -> dict`
  - Finds revenue, assets, liabilities, equity in extraction
  - Returns: `{"revenue": 2M, "assets": 5M, ...}`
  
- [ ] Function `extract_format_template(extraction: dict) -> dict`
  - Finds table structure, column count, page layout from PDF/DOCX
  - Returns: `{"columns": [...], "page_structure": {...}}`
  
- [ ] Function `infer_account_mapping(extraction: dict, prior_mapping: dict = None) -> dict`
  - Looks at account names, uses NLP/regex to infer groups
  - Example: "Salaries" account → "Staff Costs" group
  - Returns: `{"4001": {"name": "Salaries", "group": "Staff Costs"}}`

**Acceptance:**
- Takes 5 source files (trial balance, prior audit, template, CoA, sample report)
- Builds complete audit_profile.json with all required fields
- Account mappings make sense (verified manually)
- Financial data matches expected values

---

### **Task B1.4: File Upload Endpoint**

**File:** `backend/api/document_upload.py` (NEW)

**Endpoint:** `POST /upload-source-document`

**Subtasks:**
- [ ] Accept multipart form data: file + document_type + profile_id
- [ ] Save file to disk (or S3)
- [ ] Call `analyze_document()` (Task B1.2)
- [ ] Extract metadata: file_path, document_type, extracted_data, confidence
- [ ] Save to DB: `source_documents` table
- [ ] Return: extracted_data + success response

**Request:**
```json
{
  "profile_id": "uuid",
  "document_type": "trial_balance",  // or "prior_audit", "template", etc.
  "file": <multipart file>
}
```

**Response:**
```json
{
  "document_id": "uuid",
  "document_type": "trial_balance",
  "extracted_data": {
    "tables": [...],
    "text": "..."
  },
  "confidence": 0.92
}
```

**Acceptance:**
- Upload Castle Plaza 2025.pdf → returns extracted tables + text
- Upload trial balance.xlsx → returns table data + sheets
- File saved to disk (can verify with `ls`)
- Record created in DB (can query with `SELECT * FROM source_documents`)

---

### **Task B1.5: Create Audit Profile Endpoint**

**File:** `backend/api/profile_management.py` (NEW)

**Endpoints:**
- `POST /profiles` — Create new audit profile
- `GET /profiles/{id}` — Retrieve profile
- `PUT /profiles/{id}` — Update profile

**Subtasks:**
- [ ] Create endpoint: Accept engagement_name, client_name, period_end
  - Returns: empty audit_profile.json template
  - Saves to DB
  
- [ ] Retrieve endpoint: Return audit_profile.json from DB
  
- [ ] Update endpoint: Merge input with existing profile
  - Allows user to manually edit account mappings, format preferences

**Response format:**
```json
{
  "profile_id": "uuid",
  "client_name": "Castle Plaza",
  "period": "2025",
  "profile_json": { /* full audit_profile from design doc */ }
}
```

**Acceptance:**
- Create profile → returns profile_id
- Retrieve profile → returns complete audit_profile.json
- Edit profile → updates DB, retrieves updated version

---

### **Task B1.6: Frontend: Document Upload Page**

**File:** `frontend/src/pages/DocumentUpload/DocumentUpload.tsx` (NEW)

**UI:**
- Input: engagement name, client name
- 5 file upload slots: Trial Balance, Prior Audit PDF, Template, Chart of Accounts, Custom
- Each shows upload status, extracted data preview, confidence score

**Subtasks:**
- [ ] Create page component
- [ ] File input handlers (drag-drop + click)
- [ ] Call `/upload-source-document` for each file
- [ ] Display extraction results
- [ ] "Next →" button to proceed to Phase 2

**Acceptance:**
- Can upload all 5 file types without errors
- Each shows preview of extracted data
- Confidence scores visible (e.g., "92% confident")
- Can proceed to next step

---

## Phase 2: Pattern Recognition (Days 2-3)

### **Task B2.1: Account Mapping UI**

**File:** `frontend/src/pages/AuditProfile/AccountMapping.tsx` (NEW)

**UI:**
- Left: List of all accounts from uploaded Chart of Accounts (or trial balance)
- Right: Dropdown to select target group (Revenue, Cost of Sales, Staff Costs, etc.)
- "Auto-map" button to use inferred mappings
- "Save" button to update profile

**Subtasks:**
- [ ] Fetch source documents (trial balance + Chart of Accounts)
- [ ] Extract account list
- [ ] Fetch current profile account_mapping
- [ ] Display UI with drag-and-drop (optional) or dropdowns
- [ ] Call `PUT /profiles/{id}` to save updates

**Acceptance:**
- Shows all 100+ accounts from trial balance
- Can see current group assignment for each
- Can click to change group
- Changes save to profile

---

### **Task B2.2: Format Template Editor**

**File:** `frontend/src/pages/AuditProfile/FormatCustomizer.tsx` (NEW)

**UI:**
- Preview of extracted format from uploaded template PDF
- Editable fields: columns (as JSON), page structure, statement groupings
- "Apply format to profile" button

**Subtasks:**
- [ ] Display extracted format from source documents
- [ ] Allow editing key fields: column names, page layout, statement groups
- [ ] Show live preview (if feasible)
- [ ] Save changes to profile

**Acceptance:**
- Shows format template extracted from Castle Plaza PDF
- Can edit column names, page counts, statement groupings
- Changes reflected in profile

---

### **Task B2.3: Profile Review Page**

**File:** `frontend/src/pages/AuditProfile/ProfileBuilder.tsx` (NEW)

**UI:**
- Show full audit_profile.json (formatted JSON view)
- Tabs: Overview, Financial Data, Format Template, Account Mappings, Custom Requirements
- Edit button for each section

**Subtasks:**
- [ ] Fetch profile from `/profiles/{id}`
- [ ] Display in readable format (not raw JSON)
- [ ] Allow editing each section
- [ ] Save changes to DB

**Acceptance:**
- Complete audit_profile.json visible and editable
- All sections can be reviewed/modified
- Changes persist after save

---

## Phase 3: Structured Report Generation (Day 4)

### **Task B3.1: Define Report JSON Schema**

**File:** `backend/schemas/audit_report.json` (NEW) or in code

**Schema:** Define audit_report.json structure (per design doc)

**Subtasks:**
- [ ] Define root fields: report_id, profile_id, metadata, sections
- [ ] Define sections: auditor_opinion, financial_statements, notes, findings
- [ ] Each section should have detailed sub-structure
- [ ] Create OpenAPI schema for validation

**Acceptance:**
- Schema is valid JSON Schema or OpenAPI spec
- Can validate sample audit_report.json against schema

---

### **Task B3.2: Implement Structured Report Generator**

**File:** `backend/core/structured_report_generator.py` (NEW)

**Functionality:** Takes trial balance + audit_profile → generates audit_report.json

**Subtasks:**
- [ ] Function `generate_audit_report(trial_balance: list[dict], profile: dict, company_info: dict) -> dict`
  - Inputs: Current year trial balance, audit_profile.json, company metadata
  - Process:
    1. Group trial balance using account_mapping from profile
    2. Calculate financial statements (SOFP, P&L, etc.)
    3. Generate audit opinion (based on profile custom_requirements)
    4. Generate notes sections (accounting policies, estimates, disclosures)
    5. Format as audit_report.json
  - Returns: Complete audit_report.json
  
- [ ] Sub-function `generate_financial_statements(grouped_tb: dict, profile: dict) -> dict`
  - Takes grouped trial balance + profile format template
  - Returns: statement_of_financial_position, statement_of_profit_loss, etc. as structured JSON
  
- [ ] Sub-function `generate_notes(profile: dict, tb_data: list[dict]) -> dict`
  - Takes profile notes_requirements
  - Generates accounting policies, critical estimates, disclosures
  - Uses LLM for content generation (via NVIDIA provider)
  - Returns: notes section of audit_report.json
  
- [ ] Sub-function `generate_auditor_opinion(profile: dict) -> dict`
  - Takes profile custom_requirements (going_concern, qualified/unqualified, etc.)
  - Generates opinion text
  - Returns: auditor_opinion section

**Acceptance:**
- Generate report from Castle Plaza trial balance + profile
- Output is valid audit_report.json (passes schema validation)
- All financial figures match trial balance (no data loss)
- Opinion text generated (not placeholder)

---

### **Task B3.3: Report Generation Endpoint**

**File:** `backend/api/report_generation.py` (NEW)

**Endpoint:** `POST /generate-report`

**Subtasks:**
- [ ] Accept: profile_id, trial_balance_file, company_info (optional)
- [ ] Validate inputs
- [ ] Call `generate_audit_report()` (Task B3.2)
- [ ] Save report to DB: `generated_reports` table
- [ ] Return: report_id + status (queued / processing / done)
- [ ] Implement async job (report generation can take minutes)

**Request:**
```json
{
  "profile_id": "uuid",
  "trial_balance_file": <multipart file>,
  "company_info": {
    "company_name": "Castle Plaza",
    "period_end": "2025-12-31",
    "auditor_name": "Ernst & Young"
  }
}
```

**Response:**
```json
{
  "report_id": "uuid",
  "status": "processing",
  "estimated_time_seconds": 120
}
```

**Acceptance:**
- Upload trial balance + profile → returns report_id
- Can poll `/report/{id}` to check status
- Report completes in <3 minutes
- Generated report is valid JSON

---

### **Task B3.4: Frontend: Report Generation Page**

**File:** `frontend/src/pages/ReportGenerator/ReportGeneration.tsx` (NEW)

**UI:**
- Select profile (dropdown)
- Upload trial balance file
- "Generate Report" button
- Shows progress/status
- "View Report" button when done

**Subtasks:**
- [ ] Fetch list of profiles (GET `/profiles`)
- [ ] File upload for trial balance
- [ ] Call `POST /generate-report`
- [ ] Poll status until complete
- [ ] Display "Generated!" message
- [ ] Link to report preview

**Acceptance:**
- Can select profile and upload trial balance
- Report generates without errors
- Progress shown (not stuck UI)
- Can view generated report

---

## Phase 4: Format Application (Day 5)

### **Task B4.1: Implement Format Applier**

**File:** `backend/core/format_applier.py` (NEW)

**Functionality:** Takes audit_report.json + format_template → formatted PDF/DOCX/Excel

**Subtasks:**
- [ ] Function `apply_format(report_json: dict, format_template: dict, output_format: str) -> bytes`
  - Inputs: audit_report.json, format_template (from profile), output format (pdf/docx/xlsx)
  - Applies layout, styling, page breaks, column widths
  - Returns: file bytes (can write to disk or return via HTTP)
  
- [ ] Sub-function `apply_pdf_format(report_json: dict, format_template: dict) -> bytes`
  - Uses reportlab or pypdf to create PDF
  - Applies format_template: columns, page structure, fonts, colors
  - Outputs PDF bytes
  
- [ ] Sub-function `apply_docx_format(report_json: dict, format_template: dict) -> bytes`
  - Uses python-docx to create DOCX
  - Applies format_template: styles, tables, heading hierarchy
  - Outputs DOCX bytes
  
- [ ] Sub-function `apply_xlsx_format(report_json: dict, format_template: dict) -> bytes`
  - Uses openpyxl to create Excel file
  - Extracts financial statements into sheets
  - Applies column widths, number formats from template
  - Outputs XLSX bytes

**Acceptance:**
- Convert audit_report.json to PDF using Castle Plaza format → matches expected layout (3 columns, Notes refs)
- Convert to DOCX → editable, preserves structure
- Convert to Excel → financial statements in separate sheets with proper formatting

---

### **Task B4.2: Export Endpoints**

**File:** `backend/api/report_generation.py` (add)

**Endpoints:**
- `GET /reports/{id}/export/pdf` — Download report as PDF
- `GET /reports/{id}/export/docx` — Download report as DOCX
- `GET /reports/{id}/export/xlsx` — Download report as Excel

**Subtasks:**
- [ ] Retrieve report from DB: `generated_reports` table
- [ ] Call `apply_format()` to generate file bytes
- [ ] Return file with proper MIME type + Content-Disposition header

**Response:**
```
Content-Type: application/pdf (or application/vnd.ms-word, application/vnd.ms-excel)
Content-Disposition: attachment; filename="audit_report.pdf"
<file bytes>
```

**Acceptance:**
- Download report as PDF → opens correctly in PDF viewer
- Download as DOCX → opens in Word, is editable
- Download as Excel → opens in Excel, tables are proper sheets

---

### **Task B4.3: Frontend: Report Export Page**

**File:** `frontend/src/pages/ReportGenerator/ReportExport.tsx` (NEW)

**UI:**
- Show generated report (inline preview or summary)
- 3 download buttons: PDF, DOCX, Excel
- Each button downloads file immediately

**Subtasks:**
- [ ] Fetch report from `/reports/{id}`
- [ ] Show report summary (company, period, opinion)
- [ ] Add download buttons
- [ ] Each button calls `/reports/{id}/export/{format}`

**Acceptance:**
- Can download generated report as PDF, DOCX, Excel
- Files download with correct names + format
- Can open each file in corresponding application

---

## Phase 5: Frontend UI (Days 3-6)

### **Task B5.1: Navigation & Routing**

**File:** `frontend/src/App.tsx` (modify) and routing config

**Subtasks:**
- [ ] Add routes:
  - `/documents/upload` → DocumentUpload page
  - `/profiles/:id` → ProfileBuilder page
  - `/profiles/:id/mapping` → AccountMapping page
  - `/profiles/:id/format` → FormatCustomizer page
  - `/generate` → ReportGeneration page
  - `/reports/:id` → ReportExport page
  
- [ ] Add navigation menu linking pages
- [ ] Keep existing `/wizard` route (backward compatibility)

**Acceptance:**
- All new pages are accessible via URL + navigation menu
- Routing works without errors

---

### **Task B5.2: Integration Flow**

**UI Flow:**
1. User lands on `/documents/upload`
2. Uploads 5 source files
3. System shows extracted data + confidence
4. "Next →" → `/profiles/new`
5. System auto-builds profile from uploaded files
6. User reviews account mappings, format template
7. "Save Profile" → profile_id
8. User goes to `/generate`
9. Selects profile, uploads trial balance
10. "Generate Report" → report generated
11. "Download PDF/DOCX/Excel" → files download

**Subtasks:**
- [ ] Implement above flow in frontend
- [ ] Add "Back" buttons, progress indicators
- [ ] Show status messages (loading, success, error)

**Acceptance:**
- Can flow through all steps without getting lost
- Each step shows clear instructions
- Status messages appear (not silent failures)

---

## Phase 6: Testing & Integration (Days 5-6)

### **Task B6.1: Unit Tests**

**Files:**
- `backend/tests/test_document_analyzer.py`
- `backend/tests/test_audit_profile_builder.py`
- `backend/tests/test_structured_report_generator.py`
- `backend/tests/test_format_applier.py`

**Subtasks:**
- [ ] Test `extract_from_pdf()` with Castle Plaza 2025.pdf
- [ ] Test `extract_from_excel()` with trial balance file
- [ ] Test `build_profile_from_documents()` with multiple source files
- [ ] Test `generate_audit_report()` produces valid JSON
- [ ] Test `apply_format()` produces valid PDF/DOCX/XLSX
- [ ] Run all tests: `pytest backend/tests/ -v`

**Acceptance:**
- All tests pass (100% pass rate)
- No warnings or errors
- Coverage > 80%

---

### **Task B6.2: Integration Tests**

**File:** `backend/tests/test_end_to_end.py`

**Scenario:**
1. Upload Castle Plaza 2025.pdf → extract format
2. Upload trial balance.xlsx → extract financial data
3. Build audit profile from extractions
4. Generate audit_report.json
5. Apply format to create PDF
6. Verify PDF matches expected structure

**Subtasks:**
- [ ] Write integration test
- [ ] Run end-to-end flow
- [ ] Verify outputs at each step
- [ ] Check final PDF visually (manual step)

**Acceptance:**
- End-to-end flow completes without errors
- Generated PDF matches Castle Plaza structure

---

### **Task B6.3: Performance Testing**

**Subtasks:**
- [ ] Measure time for: document analysis, profile building, report generation, format application
- [ ] Optimize if any step takes >10 seconds
- [ ] Goal: Full workflow completes in <3 minutes

**Acceptance:**
- Document upload + analysis: <30 sec
- Report generation: <2 min
- Format application: <10 sec
- Total: <3 min

---

## Phase 7: Deployment & Docs (Day 7)

### **Task B7.1: Database Migrations**

**Subtasks:**
- [ ] Create Alembic migration: `alembic revision --autogenerate -m "add audit profiles tables"`
- [ ] Review migration script
- [ ] Test migration: `alembic upgrade head`
- [ ] Verify tables created: `SELECT * FROM audit_profiles;`

**Acceptance:**
- Migration runs without errors
- All tables created with correct columns + indexes
- Rollback works: `alembic downgrade -1`

---

### **Task B7.2: API Documentation**

**File:** `docs/API.md` (NEW)

**Document:**
- All endpoints: `/upload-source-document`, `/profiles`, `/generate-report`, `/reports/{id}/export`
- Request/response examples
- Error codes + messages
- Rate limits (if any)

**Acceptance:**
- Documentation complete + accurate
- All endpoints documented with examples

---

### **Task B7.3: Deployment Playbook**

**File:** `docs/DEPLOYMENT.md` (NEW)

**Document:**
- Setup: install dependencies, configure env vars, run migrations
- Deploy backend: build Docker image, push to registry, deploy to K8s / EC2
- Deploy frontend: build React, push to CDN/S3
- Verify: smoke tests, check logs
- Rollback: instructions if something breaks

**Acceptance:**
- Clear deployment instructions for team
- Can deploy fresh instance without trial-and-error

---

### **Task B7.4: User Documentation**

**File:** `docs/USER_GUIDE.md` (NEW)

**Document:**
- Step-by-step guide for users
- Screenshots
- FAQ
- Troubleshooting

**Acceptance:**
- Users can understand system from documentation
- Screenshots show all UI screens

---

## Testing Checklist

Before shipping Phase 2 (Option B):

- [ ] All unit tests pass (100%)
- [ ] All integration tests pass
- [ ] End-to-end flow works: upload files → generate PDF
- [ ] Performance acceptable (<3 min total)
- [ ] No crashes or error states
- [ ] PDF output matches Castle Plaza format visually
- [ ] DOCX files are editable in Word
- [ ] Excel files open in Excel with proper structure
- [ ] Database migrations work cleanly
- [ ] API documentation complete
- [ ] Deployment playbook tested (fresh deploy works)

---

## Effort Breakdown (110 hours total)

| Phase | Component | Hours |
|-------|-----------|-------|
| 1 | Document Understanding | 28 |
| 2 | Pattern Recognition | 12 |
| 3 | Structured Report Generation | 14 |
| 4 | Format Application | 14 |
| 5 | Frontend UI | 24 |
| 6 | Testing | 20 |
| 7 | Deployment + Docs | 10 |
| **TOTAL** | | **110** |

---

## Next Steps

1. **Decide:** Option A only? Option B only? Or both (A now, then B later)?
2. **Plan sprint:** Break 110 hours into weekly sprints
3. **Assign:** Assign developers to phases
4. **Start:** Begin Phase 1 (Document Understanding)
5. **Review:** At each phase boundary, review progress + plan next phase

---

## Success Criteria (Full System)

- [ ] Users can upload any audit-related PDF/Excel/DOCX file
- [ ] System extracts data from each file (>90% confidence)
- [ ] System learns custom patterns (account groupings, format preferences)
- [ ] System generates perfect audit reports matching user's format
- [ ] Reports available as PDF, DOCX, Excel (all formats correct)
- [ ] Full workflow: Upload files → Generate PDF in <3 minutes
- [ ] No manual intervention needed (fully automated)
- [ ] Users can edit generated PDF/DOCX if needed
- [ ] System handles edge cases gracefully (missing data, ambiguous accounts, etc.)

