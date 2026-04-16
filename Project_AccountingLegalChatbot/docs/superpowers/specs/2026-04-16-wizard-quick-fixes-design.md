# Option A: Wizard Quick Fixes — Design & Plan

> **Scope:** Fix the 6 known bugs in the audit wizard (steps 1-10). Restore end-to-end functionality. No architecture changes.
> 
> **Timeline:** 1–2 hours implementation
> 
> **Goal:** Users can run a complete audit workflow: upload trial balance → extract prior year → generate draft → analyze → select format → export PDF

---

## Problem Statement

The audit wizard has 6 bugs preventing users from completing the workflow:

1. **Step 3 (Company Docs)**: "Could not extract prior year data" error — but extraction works
2. **Step 7 (Analysis Chat)**: Chat returns error on every message
3. **Step 6 (Draft Viewer)**: Raw markdown tables (pipes visible)
4. **Step 6 (Draft)**: 50+ ungrouped expense items in flat list
5. **Step 9 (Final PDF)**: Output format doesn't match Castle Plaza 2025 reference
6. **Step 8 (Format Selector)**: Cannot advance to final step

---

## Root Cause Analysis

| Issue | File | Root Cause |
|-------|------|-----------|
| #1, #2 | `CompanyDocuments.tsx`, `AuditAnalysisStep.tsx` | Use `fetch('/api/…')` (relative URL → Vite:5175 instead of backend:8001) → 404 |
| #3 | `App.css` | `.report-markdown` class has zero CSS styles; ReactMarkdown renders table but invisible |
| #4 | `reports.py` line 334 | `group_tb_for_ifrs()` function exists in `trial_balance_classifier.py` but **never called** in draft generation |
| #5 | `audit_formatter.py` | Outputs 5 columns (Account, CY, PY, Variance, % Change); Castle Plaza uses 3 (Notes, CY AED, PY AED) |
| #6 | Cascading | Analysis chat failure (#2) leaves wizard in bad state; also check `AuditFinalReport.tsx` for same URL bug |

---

## Architecture: No Changes

The system stays as-is:
- React frontend (steps 0-10)
- FastAPI backend `/api/reports/*` endpoints
- NVIDIA LLM provider (Mistral 119B) for vision & text
- PyMuPDF for PDF handling
- python-docx for DOCX generation

Only fixes applied — no new microservices, no database changes, no refactoring.

---

## Implementation Plan

### **Phase 1: URL Fixes (Issues #1, #2, #6)**

**File:** `frontend/src/components/studios/FinancialStudio/CompanyDocuments.tsx`

```typescript
// ADD import at top
import { API_BASE } from '../../../lib/api';

// FIND line 95 (handlePriorYearUpload)
// REPLACE: fetch('/api/reports/extract-prior-year', {
// WITH:    fetch(`${API_BASE}/api/reports/extract-prior-year`, {

// ALSO: line 100 fix data handling
// OLD: setPriorYearContext(data.context || '');
// NEW: const context = data.rows?.map(r => `${r.account}: ${r.amount}`).join('\n') || '';
//      setPriorYearContext(context);
```

**File:** `frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx`

```typescript
// ADD import at top
import { API_BASE } from '../../../lib/api';

// FIND line 64 (sendMessage function)
// REPLACE: fetch('/api/reports/analysis-chat', {
// WITH:    fetch(`${API_BASE}/api/reports/analysis-chat`, {

// ADD fallback button before "Continue →"
// <button className="btn-ghost" onClick={() => onComplete(messages)}>
//   Skip to Format →
// </button>
```

**File:** `frontend/src/components/studios/FinancialStudio/AuditFinalReport.tsx`

```typescript
// SEARCH for all fetch() calls
// REPLACE any fetch('/api/…') with fetch(`${API_BASE}/api/…`)
// Import { API_BASE } at top if not present
```

---

### **Phase 2: CSS Styles (Issue #3)**

**File:** `frontend/src/App.css`

Add at end of file:

```css
/* Markdown report rendering */
.report-markdown {
  font-family: var(--s-font-ui), -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  line-height: 1.6;
  color: var(--s-text-1);
}

.report-markdown h1 {
  font-size: 18px;
  font-weight: 700;
  margin: 16px 0 8px;
  color: var(--s-text-1);
}

.report-markdown h2 {
  font-size: 14px;
  font-weight: 700;
  margin: 12px 0 6px;
  color: var(--s-text-1);
}

.report-markdown h3, .report-markdown h4, .report-markdown h5, .report-markdown h6 {
  font-size: 12px;
  font-weight: 600;
  margin: 8px 0 4px;
  color: var(--s-text-1);
}

.report-markdown p {
  margin-bottom: 8px;
}

.report-markdown table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
  border: 1px solid var(--s-border);
  font-size: 12px;
}

.report-markdown th {
  background: var(--s-surface);
  border: 1px solid var(--s-border);
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  color: var(--s-text-1);
}

.report-markdown td {
  border: 1px solid var(--s-border);
  padding: 8px 10px;
  color: var(--s-text-1);
}

.report-markdown tr:nth-child(even) {
  background: rgba(255, 255, 255, 0.01);
}

.report-markdown code {
  background: var(--s-surface);
  border-radius: 4px;
  padding: 2px 6px;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 11px;
  color: var(--s-accent);
}

.report-markdown pre {
  background: var(--s-surface);
  border: 1px solid var(--s-border);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 8px 0;
}

.report-markdown pre code {
  background: none;
  padding: 0;
  color: var(--s-text-2);
}

.report-markdown blockquote {
  border-left: 3px solid var(--s-accent);
  padding-left: 12px;
  margin-left: 0;
  color: var(--s-text-2);
  font-style: italic;
}

.report-markdown ul, .report-markdown ol {
  margin-left: 20px;
  margin-bottom: 8px;
}

.report-markdown li {
  margin-bottom: 4px;
}
```

---

### **Phase 3: Wire Grouping Algorithm (Issue #4)**

**File:** `backend/api/reports.py`

```python
# ADD import at top of file (after existing imports)
from core.agents.trial_balance_classifier import group_tb_for_ifrs, format_ifrs_for_llm

# FIND generate_draft_report function, line ~328
# REPLACE lines 328-334:

# OLD:
# tb_block = ""
# if req.grouped_rows:
#     tb_block = "\n\n**Grouped Trial Balance (Current Year):**\n| Account | Category | Amount (AED) |\n|---------|----------|-------------|\n"
#     for r in req.grouped_rows:
#         amt = r.get("amount", 0)
#         fmt_amt = f"{amt:,.2f}" if isinstance(amt, (int, float)) else str(amt)
#         tb_block += f"| {r.get('account', '')} | {r.get('mappedTo', '')} | {fmt_amt} |\n"

# NEW:
tb_block = ""
if req.grouped_rows:
    grouped = group_tb_for_ifrs(req.grouped_rows)
    tb_block = "\n\n**Grouped Trial Balance (Current Year):**\n" + format_ifrs_for_llm(grouped)
```

---

### **Phase 4: Update PDF Format (Issue #5)**

**File:** `backend/core/audit_formatter.py`

Replace column definitions in the financial statement rendering:

```python
# FIND the section that builds balance sheet table
# REMOVE columns: Variance, % Change
# KEEP columns: Notes (ref), Current Year (AED), Prior Year (AED)

# Example change in statement_of_financial_position():
# OLD: cells = [["Account", "CY AED", "PY AED", "Variance", "% Change"]]
# NEW: cells = [["Notes", "31.12.2024 AED", "31.12.2023 AED"]]

# Add Notes reference column (e.g., "[1]", "[2]")
# Add subtotal rows with bold formatting
```

Full audit_formatter.py overhaul (see Implementation Plan Phase 4 details below).

---

## File Changes Summary

| File | Changes | Impact |
|------|---------|--------|
| `CompanyDocuments.tsx` | Import API_BASE; fix fetch URL; parse data.rows | Fix Issue #1 |
| `AuditAnalysisStep.tsx` | Import API_BASE; fix fetch URL; add Skip button | Fix Issue #2 #6 |
| `AuditFinalReport.tsx` | Audit fetch() calls; fix URLs | Fix Issue #6 |
| `App.css` | Add .report-markdown table/th/td/code/pre styles | Fix Issue #3 |
| `reports.py` | Import grouping functions; call in draft generation | Fix Issue #4 |
| `audit_formatter.py` | Remove Variance cols; add Notes; restructure | Fix Issue #5 |

---

## Testing

### Unit Tests (Backend)
```bash
# Test grouping is called
pytest backend/tests/test_report_generation.py::test_draft_uses_grouped_rows -v

# Test PDF format matches expectations
pytest backend/tests/test_audit_formatter.py::test_final_report_has_three_columns -v
```

### Integration Test (Frontend)
1. Upload trial balance → step 2 ✓
2. Upload prior year PDF → step 3 shows "✓ extracted" (not error) ✓
3. Run analysis chat → messages stream in (not error) ✓
4. View draft → tables render with borders/padding (not raw pipes) ✓
5. Select format → advance to step 9 ✓
6. Generate final PDF → matches Castle Plaza structure ✓

---

## Deployment Order

1. Deploy `App.css` (CSS only — no risk)
2. Deploy `reports.py` (backend — no frontend changes yet)
3. Deploy frontend: `CompanyDocuments.tsx`, `AuditAnalysisStep.tsx`, `AuditFinalReport.tsx`
4. Deploy `audit_formatter.py` (PDF generation overhaul)
5. Full end-to-end test
6. Commit: `git commit -m "fix: resolve 6 wizard bugs — URL fix, CSS, grouping, PDF format"`

---

## Success Criteria

- [ ] Step 3: No "could not extract" error when uploading prior year PDF
- [ ] Step 7: Analysis chat streams messages without error
- [ ] Step 6: Draft tables render with visible borders (not raw markdown)
- [ ] Step 6: Expense items grouped under parent categories (not flat list)
- [ ] Step 9: Generated PDF matches Castle Plaza 2025 format (3 cols, Notes ref, no Variance)
- [ ] Step 8→9: Format selector buttons advance user to final step
- [ ] Full workflow: Trial balance → final PDF in <5 minutes without errors

---

## Rollback Plan

Each commit is independent:
- Revert CSS: `git revert <commit-hash>` — users see unstyled tables (non-breaking)
- Revert URL fixes: old fetch() calls fail — but fallback buttons allow users to skip
- Revert grouping: goes back to flat list (quality issue, not breaking)
- Revert PDF format: old 5-column format (user-facing quality issue, not breaking)

No database migrations or schema changes — completely reversible.

---

## Effort Estimate

- Phase 1 (URL fixes): 15 min
- Phase 2 (CSS): 15 min
- Phase 3 (Grouping wire): 5 min
- Phase 4 (PDF format): 30 min
- Testing: 30 min
- **Total: ~1.5 hours**

