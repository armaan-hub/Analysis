# Remove OneDrive Path References Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all hardcoded Windows and macOS OneDrive paths from Python files and documentation to ensure project portability.

**Architecture:** Replace absolute OneDrive paths with portable alternatives:
- Python: Use `Path(__file__).resolve().parent` or `Path.cwd()`.
- Docs: Use relative paths or descriptive placeholders.

**Tech Stack:** Python (pathlib), Shell/PowerShell (for docs).

---

### Task 1: Fix backend/bulk_ingest.py

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/bulk_ingest.py`

- [ ] **Step 1: Read the file to identify exact lines**
- [ ] **Step 2: Replace hardcoded paths with portable ones**
```python
# From:
# finance_base = r"C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\..."
# To:
# finance_base = Path(__file__).resolve().parent.parent / "data_source_finance"
```
- [ ] **Step 3: Verify the change**
- [ ] **Step 4: Commit**
```bash
git add "Main Branch/Project_AccountingLegalChatbot/backend/bulk_ingest.py"
git commit -m "fix: make bulk_ingest.py paths portable"
```

### Task 2: Fix test files in Main Branch

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/tests/test_analyze_precise_columns.py`
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/tests/test_analyze_precise_fonts.py`
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/tests/test_analyze_precise_spacing.py`
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/tests/test_fingerprinter_gcc.py`
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/tests/test_template_analyzer.py`

- [ ] **Step 1: Read each test file**
- [ ] **Step 2: Replace hardcoded OneDrive base paths with relative ones**
- [ ] **Step 3: Verify no OneDrive strings remain in these files**
- [ ] **Step 4: Commit**
```bash
git add "Main Branch/Project_AccountingLegalChatbot/backend/tests/"
git commit -m "fix: remove hardcoded OneDrive paths from tests"
```

### Task 3: Fix Documentation and Plans

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/docs/superpowers/plans/2026-04-26-two-model-mode-routing.md`
- Modify: `Main Branch/Project_AccountingLegalChatbot/docs/superpowers/plans/2026-04-28-hybrid-vector-graph-rag.md`
- Modify: `Project_AccountingLegalChatbot/docs/superpowers/plans/2026-05-06-startup-script-and-ux.md`

- [ ] **Step 1: Replace absolute Windows paths with relative paths (e.g., `cd ./backend`)**
- [ ] **Step 2: Replace absolute macOS OneDrive paths with relative project paths**
- [ ] **Step 3: Verify no OneDrive strings remain in these files**
- [ ] **Step 4: Commit**
```bash
git add .
git commit -m "docs: remove hardcoded OneDrive paths from plans"
```

### Task 4: Final Verification

- [ ] **Step 1: Run grep to ensure no occurrences remain in the target files**
```bash
grep -r "OneDrive" "Main Branch/Project_AccountingLegalChatbot"
grep -r "OneDrive" "Project_AccountingLegalChatbot/docs"
```
- [ ] **Step 2: Ensure tests still pass (dry run if possible)**
