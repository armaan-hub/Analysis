# Template-Based Intelligent Reporting System

**Date:** 2026-04-15  
**Status:** Design Spec  
**Objective:** Extract prior year audit report structure and use it as a blueprint for current year reporting, with intelligent account placement and dynamic formatting.

---

## Problem Statement

Currently, the system generates audit reports by:
1. Using a simple keyword matcher to classify accounts (often wrong)
2. Applying generic formatting (no company-specific structure)
3. Losing the exact layout/terminology from the prior year signed audit

**Result:** Reports don't match the structure of prior year audits, leading to reviewer confusion and manual reformatting.

**Solution:** Extract the prior year audit PDF as a **structural and semantic template**, then intelligently generate the current year report to match it exactly.

---

## Core Design

### 1. Extract Everything from Prior Year PDF

**New backend module:** `DocumentFormatAnalyzer`

Input: Prior year audit PDF  
Output: Structured template with:

```python
{
  "document_structure": {
    "title": str,
    "date_range": str,
    "company_name": str,
    "auditor_name": str,
    "pages": int,
    "sections": [
      {
        "section_id": str,
        "title": str,
        "level": 1|2|3,
        "start_page": int,
        "estimated_position": "top|middle|bottom",
        "content_type": "heading|table|narrative|chart",
        "table_structure": {
          "columns": ["Account", "Current Year", "Prior Year"],
          "column_count": 3,
          "alignment": ["left", "right", "right"],
          "indentation_levels": 0|1|2,
        } or null,
      }
    ]
  },
  "account_grouping": {
    "section_title": [
      {
        "account_name": str,
        "account_code": str,
        "indent_level": 0|1|2,
        "is_subtotal": bool,
        "is_total": bool,
      }
    ]
  },
  "terminology": {
    "headings_seen": [...],      # e.g., "Non-Current Assets", "Statement of Financial Position"
    "common_phrases": [...],     # e.g., "As at", "Authorized but not issued"
    "currency": str,             # e.g., "AED"
  },
  "formatting_rules": {
    "page_break_after_sections": [list of section IDs],
    "table_formatting": {
      "currency_format": "1,234,567.89",
      "negative_number_format": "(1,234,567.89)" | "-1,234,567.89",
    },
    "font_hierarchy": {
      "heading_1_bold": bool,
      "table_header_bold": bool,
    }
  }
}
```

### 2. Updated Prior Year Extractor

**Enhance:** `backend/core/prior_year_extractor.py`

Current → Add:
- Extract account grouping from document sections (not just regex)
- Extract page layout and formatting metadata
- Store full template, not just account list

**Returns:**
```python
{
  "rows": [...],                       # (already working)
  "template": {                        # NEW
    "document_structure": {...},
    "account_grouping": {...},
    "terminology": {...},
    "formatting_rules": {...},
  },
  "extraction_method": "text|llm_text|vision|failed",
  "confidence": 0.85,
  "context": str,
}
```

### 3. LLM-Driven Account Placement

**New backend module:** `AccountPlacementEngine`

When processing current year trial balance:
1. Classify each account using prior year grouping as reference
2. For NEW accounts (not in prior year):
   - Ask LLM: "This account `<name>` with category `<category>` is new. Based on prior year structure, which section should it go in?"
   - LLM response: Section name + indent level
3. Return merged account list with section assignments

**Prompt example:**
```
Prior year structure had these sections:
- Non-Current Assets (indent 0)
  - Property, Plant & Equipment (indent 1)
    - Building (indent 2)
    - Equipment (indent 2)
- Current Assets (indent 0)
  - Trade Receivables (indent 1)
  - Cash (indent 1)

Current year has a NEW account: "Lease Right-of-Use Asset"
Category: Fixed Asset

Where should this go in the structure? Respond: {"section": "...", "indent_level": ...}
```

### 4. Template-Based Report Generator

**Enhance:** `backend/core/audit_formatter.py` → `backend/core/template_report_generator.py`

Input:
- Current year trial balance (with LLM-assigned sections)
- Prior year template
- Current financial data

Process:
1. **Clone structure**: Use prior year section layout, page breaks, terminology
2. **Generate content**: Replace account data, keep section titles and formatting
3. **Handle new accounts**: Insert at LLM-determined positions
4. **Dynamic sizing**: Adjust column widths for number variations (1M vs 100M)
5. **Preserve formatting**: Bold headings, currency format, negative number display

Output: DOCX with identical layout to prior year, but current year data

### 5. Updated Audit Wizard Flow

**Step 0 (NEW):** Select Report Format
- Options: Big 4, Local Standard, IFRS, Custom
- User can select based on their auditor's preference

**Step 1 (CHANGED):** Upload Prior Year Audit PDF
- System extracts template (structure + terminology + formatting)
- Shows extracted sections for user confirmation

**Step 2 (EXISTING):** Upload Current Year Trial Balance
- System uses extracted template for account classification
- LLM places new accounts into prior year section structure

**Steps 3-10:** Unchanged

---

## Data Flow

```
┌─ User uploads prior year audit PDF
└─→ DocumentFormatAnalyzer
    ├─ Extract document structure (sections, pages, layout)
    ├─ Extract account grouping (which accounts in which sections)
    ├─ Extract terminology (section titles, common phrases)
    └─→ Store as TEMPLATE

┌─ User uploads current year trial balance
└─→ TrialBalanceMapper
    └─→ AccountPlacementEngine (LLM)
        ├─ Classify each account using prior year template
        ├─ For new accounts, ask LLM where they belong
        └─→ Return accounts with section assignments

┌─ Generate report
└─→ TemplateReportGenerator
    ├─ Clone prior year structure & formatting
    ├─ Insert current year data
    ├─ Adjust column widths for number variance
    ├─ Apply formatting rules (currency, negatives)
    └─→ Output DOCX identical to prior year layout
```

---

## Implementation Phases

### Phase 1: Document Structure Extraction
- Build `DocumentFormatAnalyzer` to parse prior year PDF
- Extract sections, pages, layout metadata
- Store template in database

### Phase 2: LLM-Based Account Placement
- Build `AccountPlacementEngine` with smart LLM prompts
- Handle new accounts by asking LLM where they belong
- Merge into TrialBalanceMapper workflow

### Phase 3: Template-Based Generation
- Build `TemplateReportGenerator` using prior year structure
- Clone formatting, section layout, terminology
- Dynamic column sizing

### Phase 4: Wire into Audit Wizard
- Add "Select Format" step at wizard start
- Update upload flow to extract and confirm template
- Update report generation to use template

---

## Key Design Decisions

**1. Why extract everything, not just accounts?**
- Auditors need **consistent formatting** year-over-year
- Page layout, terminology, and structure are part of the audit trail
- Client recognizes their report format

**2. Why LLM for new account placement?**
- Keyword matching fails for new/unfamiliar account names
- LLM understands financial semantics better than regex
- Human review still needed if LLM is unsure

**3. Why clone template instead of generate from scratch?**
- Preserves auditor's intended structure and narrative
- Reduces manual review/reformatting
- Ensures consistency with prior year

**4. Why dynamic column sizing?**
- Financial statements need to handle variance in number magnitude
- Fixed widths break when numbers grow (1M → 100M)
- Smart alignment needed for readability

---

## Success Criteria

- ✅ Generated current year report matches prior year layout (page-to-page, section-to-section)
- ✅ Account grouping is correct (no more keyword-matching errors)
- ✅ New accounts are placed intelligently (LLM determines section)
- ✅ Formatting preserved (bold, currency, negative numbers)
- ✅ Column widths adjust for number variance
- ✅ User can review + edit template before report generation
- ✅ No manual reformatting needed

---

## Design Decisions (User-Confirmed)

1. **New account placement:** Synchronous LLM classification during upload with "Analyzing accounts..." message
2. **Template storage:** Both historical (per company across years) AND per-cycle (snapshot of structure at audit date) — enables tracking evolution
3. **Template review:** User reviews extracted sections in a detailed list before proceeding (not auto-accepted)
4. **LLM confidence:** If <80% confident in account placement, flag for manual review; ≥80% auto-place with confidence badge

## Open Questions

1. **Should templates be user-editable?** (Can they manually adjust section structure after review?)
2. **How to handle PDF → DOCX fidelity?** (Some formatting may not translate perfectly)
3. **Should rejected templates be archived or discarded?**

---

## Dependencies

- `PyMuPDF` (fitz) — already installed
- `python-docx` — already installed
- LLM provider for account classification — already available
- Database schema to store templates (may need migration)

---

## Files to Create/Modify

**New:**
- `backend/core/document_format_analyzer.py`
- `backend/core/account_placement_engine.py`
- `backend/core/template_report_generator.py` (refactored from audit_formatter)

**Modify:**
- `backend/core/prior_year_extractor.py` — add template extraction
- `backend/api/reports.py` — new endpoints for template extraction + confirmation
- `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx` — add step 0 for format selection
- `frontend/src/components/studios/FinancialStudio/ReportRequirements.tsx` — add template review UI

**Database:**
- Add table `audit_templates` to store extracted templates per company/date
