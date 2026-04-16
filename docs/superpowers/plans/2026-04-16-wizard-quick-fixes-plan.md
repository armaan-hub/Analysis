# Option A: Wizard Quick Fixes — Implementation Plan

> **Goal:** Fix 6 bugs in the audit wizard end-to-end. Users can upload trial balance → extract prior year → analyze → generate PDF **without errors**.
>
> **Timeline:** 1–2 hours of implementation + 30 min testing
>
> **Status:** Ready to code

---

## Todo Breakdown

### **Task A1: Fix URL Bugs (Issues #1, #2, #6)**

**Files to edit:**
- `frontend/src/components/studios/FinancialStudio/CompanyDocuments.tsx`
- `frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx`
- `frontend/src/components/studios/FinancialStudio/AuditFinalReport.tsx`

**Subtasks:**
- [ ] Import `API_BASE` from `lib/api` in each file
- [ ] Replace `fetch('/api/reports/…')` with `fetch(API_BASE + '/api/reports/…')`
- [ ] **CompanyDocuments.tsx line 95:** Fix data parsing from `data.context` → `data.rows.map(r => …).join('\n')`
- [ ] **AuditAnalysisStep.tsx line 64:** Fix fetch URL
- [ ] **AuditAnalysisStep.tsx:** Add "Skip to Format →" fallback button
- [ ] **AuditFinalReport.tsx:** Search for all `fetch()` calls; fix URLs
- [ ] Test in browser: Step 3 prior year extraction no error, Step 7 chat works

**Acceptance:** 
- Step 3 shows "✓ Prior year data extracted successfully" (not error)
- Step 7 chat messages stream in (not error on first message)
- Step 8 buttons advance to step 9 (not stuck)

---

### **Task A2: Add CSS for Markdown Tables (Issue #3)**

**File:**
- `frontend/src/App.css`

**Subtasks:**
- [ ] Add `.report-markdown` table styles (border-collapse, th/td padding, borders)
- [ ] Add `.report-markdown` h1-h6 styles
- [ ] Add `.report-markdown` p, code, pre styles
- [ ] Add `.report-markdown` list styles
- [ ] Test in browser: Step 6 draft viewer shows tables with visible borders (not raw pipes)

**Acceptance:**
- Step 6 draft renders with: visible table borders, row padding, headings styled
- No raw `|` characters visible (markdown fully rendered)

---

### **Task A3: Wire Grouping Algorithm (Issue #4)**

**File:**
- `backend/api/reports.py`

**Subtasks:**
- [ ] Add import: `from core.agents.trial_balance_classifier import group_tb_for_ifrs, format_ifrs_for_llm`
- [ ] Find `generate_draft_report()` function, line ~328
- [ ] Replace flat loop with:
  ```python
  grouped = group_tb_for_ifrs(req.grouped_rows)
  tb_block = "\n\n**Grouped Trial Balance (Current Year):**\n" + format_ifrs_for_llm(grouped)
  ```
- [ ] Test: Generate draft from trial balance with 50+ items
- [ ] Verify: Output shows grouped sections (Revenue, Cost of Sales, Operating Expenses with subtotals)

**Acceptance:**
- Step 6 draft shows expenses grouped under parent headings (not flat list)
- Each group has subtotal row (not just line-by-line)

---

### **Task A4: Update PDF Format (Issue #5)**

**File:**
- `backend/core/audit_formatter.py`

**Subtasks:**
- [ ] Find balance sheet column definitions
- [ ] Remove columns: Variance, % Change
- [ ] Keep columns: Notes (reference), CY AED, PY AED
- [ ] Add Notes reference column logic (e.g., "[1]", "[2]" linking to notes section)
- [ ] Add subtotal rows with bold formatting
- [ ] Update P&L statement similarly
- [ ] Test: Generate PDF from draft
- [ ] Verify: PDF structure matches Castle Plaza (3 columns, Notes refs, subtotals, no Variance)

**Acceptance:**
- Generated PDF has exactly 3 statement columns (Notes | CY AED | PY AED)
- Notes section links from statement rows (e.g., "[1]" in Financial Position → detailed note)
- Subtotal rows present with bold formatting
- No Variance or % Change columns in final PDF

---

### **Task A5: Test End-to-End**

**Flow to test:**
1. [ ] Start backend on port 8001: `cd backend && python -m uvicorn app:app --port 8001`
2. [ ] Start frontend on port 5175: `cd frontend && npm run dev`
3. [ ] **Step 1:** Upload trial balance (test file: `Testing data/trial_balance.xlsx`)
4. [ ] **Step 2:** Review trial balance rows (should show without error)
5. [ ] **Step 3:** Upload prior year PDF (test file: `Testing data/audit_prior_year.pdf`)
   - [ ] Should show "✓ Prior year data extracted successfully" (not error)
6. [ ] **Step 4:** Fill company info (should populate automatically)
7. [ ] **Step 5:** CA Questions (answer all questions)
8. [ ] **Step 6:** View draft report
   - [ ] Tables should have visible borders (not raw pipes)
   - [ ] Expenses should be grouped (Revenue, Cost of Sales, Operating Expenses) with subtotals
9. [ ] **Step 7:** Send analysis chat message
   - [ ] Should receive response (not error)
   - [ ] Can send multiple messages
10. [ ] **Step 8:** Select format (should enable all buttons, advance to step 9)
11. [ ] **Step 9:** Generate final PDF
    - [ ] Should complete without error
    - [ ] PDF should match Castle Plaza format (3 columns, Notes refs, subtotals, no Variance)
12. [ ] Download PDF and verify visually

**Acceptance:**
- All 10 steps complete without errors
- Prior year extraction works (shows data)
- Analysis chat works (receives responses)
- Draft renders correctly (grouped, styled tables)
- PDF matches Castle Plaza format

---

### **Task A6: Commit & Deploy**

**Subtasks:**
- [ ] `git status` — verify only intended files changed
- [ ] `git diff` — review all changes
- [ ] `git add frontend/src/components/studios/FinancialStudio/*.tsx frontend/src/App.css backend/api/reports.py backend/core/audit_formatter.py`
- [ ] `git commit -m "fix: resolve 6 wizard bugs — URL fix, CSS, grouping, PDF format"`
- [ ] `git push origin main`
- [ ] Wait for CI/CD to pass (if present)
- [ ] Verify on staging/production

**Acceptance:**
- All files committed
- No merge conflicts
- CI tests pass (or manually run backend + frontend tests)

---

## Per-File Checklist

### `CompanyDocuments.tsx`
```typescript
// Line 1-4: Add import
import { API_BASE } from '../../../lib/api';

// Line 95: Change fetch URL
// OLD: const res = await fetch('/api/reports/extract-prior-year', {
// NEW: const res = await fetch(API_BASE + '/api/reports/extract-prior-year', {

// Line 100-101: Fix data parsing
// OLD: setPriorYearContext(data.context || '');
// NEW:
const rows = data.rows || [];
const context = rows.map(r => `${r.account}: AED ${r.amount}`).join('\n');
setPriorYearContext(context);
```

### `AuditAnalysisStep.tsx`
```typescript
// Line 1-4: Add import
import { API_BASE } from '../../../lib/api';

// Line 64: Change fetch URL
// OLD: const res = await fetch('/api/reports/analysis-chat', {
// NEW: const res = await fetch(API_BASE + '/api/reports/analysis-chat', {

// BEFORE onComplete button (around line 230), add:
<button className="btn-ghost" onClick={() => onComplete(messages)}>
  Skip to Format →
</button>
```

### `AuditFinalReport.tsx`
```typescript
// Search for all fetch() calls
// Replace: fetch('/api/...')
// With: fetch(API_BASE + '/api/...')
// Add import { API_BASE } at top if not present
```

### `App.css`
```css
/* Add at end of file */

.report-markdown {
  font-family: var(--s-font-ui), -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  line-height: 1.6;
  color: var(--s-text-1);
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

/* ... other styles from design doc ... */
```

### `reports.py` (generate_draft_report function)
```python
# Line ~5 (top imports)
from core.agents.trial_balance_classifier import group_tb_for_ifrs, format_ifrs_for_llm

# Line ~328 (in generate_draft_report function)
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

### `audit_formatter.py`
See detailed instructions in design doc (Phase 4). Main changes:
- Remove Variance, % Change columns from statement table definitions
- Add Notes reference column
- Add subtotal rows with bold formatting
- Update SOFP and SOPL rendering to match Castle Plaza structure

---

## Verification Checklist

After implementing each task:

- [ ] **Task A1:** Manually test Step 3 & 7 → no errors
- [ ] **Task A2:** Manually test Step 6 → tables render with borders (not raw pipes)
- [ ] **Task A3:** Manually test Step 6 → expenses grouped under parent headings
- [ ] **Task A4:** Manually test Step 9 → PDF has 3 columns, Notes refs, subtotals, no Variance
- [ ] **Task A5:** Full end-to-end test → all 10 steps complete without errors
- [ ] **Task A6:** Commit & push → CI passes (or manual tests pass)

---

## Rollback Instructions

If any step fails after deployment:

```bash
# Revert last commit
git revert HEAD

# Or revert specific file
git checkout HEAD~1 -- frontend/src/components/studios/FinancialStudio/CompanyDocuments.tsx

# Push changes
git push origin main
```

Since all changes are code (no migrations), rollback is safe and doesn't require data fixes.

---

## Estimated Timeline

| Task | Effort |
|------|--------|
| A1 (URL fixes) | 15 min |
| A2 (CSS) | 15 min |
| A3 (Grouping wire) | 5 min |
| A4 (PDF format) | 30 min |
| A5 (Testing) | 30 min |
| A6 (Commit/deploy) | 10 min |
| **TOTAL** | **105 min (1h 45min)** |

---

## Next Steps

1. **Review:** User/PM reviews design + plan
2. **Approve:** Get sign-off on approach
3. **Implement:** Execute tasks A1-A6
4. **Test:** Run end-to-end flow
5. **Deploy:** Merge to main, deploy to staging/prod

---

## Post-Implementation

Once this is done, the wizard is **production-ready**. Users can:
- Upload trial balance files
- Extract prior year financial data from scanned PDFs
- Analyze & discuss findings
- Generate professional audit reports
- Export to PDF, DOCX, Excel

Then **Option B** (NotebookLM system) becomes the next phase for custom pattern learning and format flexibility.

