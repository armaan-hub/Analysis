# Template-Based Intelligent Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract prior year audit report structure as a template and use it to generate the current year report with identical page-to-page layout, account grouping, and formatting.

**Architecture:** 
- Extract template from prior year PDF (sections, account grouping, formatting rules, terminology)
- Store template with company metadata and version history (both per-company and per-cycle)
- Use LLM to classify new accounts into prior year's section structure (synchronous, with confidence scoring)
- Generate current year report by cloning prior year template and filling with current data
- Integrate into audit wizard with new "Select Format" step and template review UI

**Tech Stack:** 
- Backend: Python, FastAPI, PyMuPDF (fitz), python-docx, LLM provider
- Frontend: React, TypeScript
- Database: SQLAlchemy (add audit_templates table)
- Testing: pytest (backend), Vitest (frontend)

---

## File Structure

### Backend (Core Services)

**`backend/core/document_format_analyzer.py`** (NEW)
- Responsibility: Parse prior year PDF and extract structural metadata
- Public API: `analyze_audit_document(file_path: str) -> DocumentTemplate`

**`backend/core/account_placement_engine.py`** (NEW)
- Responsibility: Classify accounts using prior year template; place new accounts with LLM
- Public API: `place_accounts_with_template(accounts: list, template: DocumentTemplate) -> list`

**`backend/core/template_report_generator.py`** (NEW)
- Responsibility: Generate DOCX by cloning prior year template structure
- Public API: `generate_from_template(current_data, template) -> bytes`

**`backend/core/prior_year_extractor.py`** (MODIFY)
- Add template extraction to existing function
- Return both `rows` and `template` in response

### Backend (Database/API)

**`backend/models/audit_template.py`** (NEW)
- SQLAlchemy models for `AuditTemplate`, `TemplateReview`

**`backend/api/reports.py`** (MODIFY)
- Add `/extract-template`, `/review-template`, `/template/{template_id}` endpoints
- Modify `/export-docx` to use template if available

### Frontend (UI)

**`frontend/src/components/studios/FinancialStudio/FormatSelector.tsx`** (NEW)
- Step 0: Select audit format

**`frontend/src/components/studios/FinancialStudio/TemplateReviewStep.tsx`** (NEW)
- Template review and approval UI

**`frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx`** (MODIFY)
- Add step 0, integrate template extraction flow

---

## Task 1: Database Schema for Templates

- [ ] Create `backend/models/audit_template.py` with SQLAlchemy models
- [ ] Create `backend/db/migrations/002_add_audit_templates.py`
- [ ] Run migration
- [ ] Commit

---

## Task 2: Document Format Analyzer

- [ ] Write test in `backend/tests/test_document_format_analyzer.py`
- [ ] Implement `backend/core/document_format_analyzer.py`
- [ ] Run tests and verify pass
- [ ] Commit

---

## Task 3: Account Placement Engine with LLM

- [ ] Write tests in `backend/tests/test_account_placement_engine.py`
- [ ] Implement `backend/core/account_placement_engine.py` with LLM fallback
- [ ] Run tests and verify pass
- [ ] Commit

---

## Task 4: Template Report Generator

- [ ] Write tests in `backend/tests/test_template_report_generator.py`
- [ ] Implement `backend/core/template_report_generator.py`
- [ ] Run tests and verify pass
- [ ] Commit

---

## Task 5: Enhance Prior Year Extractor

- [ ] Modify `backend/core/prior_year_extractor.py` to call DocumentFormatAnalyzer
- [ ] Return template in response dict
- [ ] Run existing tests to verify no regression
- [ ] Commit

---

## Task 6: Backend API Endpoints

- [ ] Add request/response schemas to `backend/api/reports.py`
- [ ] Add `/extract-template` endpoint
- [ ] Add `/review-template/{template_id}` endpoint
- [ ] Add `/template/{template_id}` GET endpoint
- [ ] Modify `/export-docx` to use template if available
- [ ] Run existing tests to verify no regression
- [ ] Commit

---

## Task 7: Frontend — Format Selector

- [ ] Create `FormatSelector.tsx` component
- [ ] Update `FinancialStudio.tsx` to add FormatSelector at step 0
- [ ] Renumber all step labels (now 11 steps)
- [ ] Test in browser
- [ ] Commit

---

## Task 8: Frontend — Template Review

- [ ] Create `TemplateReviewStep.tsx` component
- [ ] Integrate into FinancialStudio prior year upload flow
- [ ] Wire approve/reject handlers to backend
- [ ] Test end-to-end
- [ ] Commit

---

## Execution Options

Plan is complete. Choose your approach:

**Option 1: Subagent-Driven (Recommended)**
- I dispatch fresh subagent per task
- Review between tasks for integration
- Fast iteration, parallel exploration

**Option 2: Inline Execution**
- Execute tasks in this session sequentially
- Batch checkpoints for code review
- Slower but contained in one conversation

Which would you prefer?
