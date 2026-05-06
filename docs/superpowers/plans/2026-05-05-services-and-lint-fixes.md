# Services Restart + Pylance Hint Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restart backend (port 8002) and frontend (port 5173) services and clean up all Pylance unused-import hints in currently open VS Code files.

**Architecture:** The active running code lives at `~/chatbot_local/Project_AccountingLegalChatbot/`. VS Code opens files from `Main Branch/Project_AccountingLegalChatbot/` (same GitHub repo, different local clone). Fixes must be applied in **both** locations (Main Branch first, then chatbot_local), then pushed to GitHub.

**Tech Stack:** FastAPI + Python 3.14 (venv `~/chatbot_venv`), React/Vite, bash, pytest, Pylance/TypeScript

---

## File Map

| File | Action | Issue |
|------|--------|-------|
| `Main Branch/…/backend/core/export_converter.py` | Modify L10 | Remove unused `Optional` import |
| `Main Branch/…/backend/core/prior_year_extractor.py` | Modify L13-14 | Remove unused `asyncio` + `Optional` imports |
| `Main Branch/…/backend/core/document_analyzer.py` | Modify L162 | Remove duplicate `import re as _re` (overwritten at L213) |
| `~/chatbot_local/…/backend/core/export_converter.py` | Modify L10 | Same fix |
| `~/chatbot_local/…/backend/core/prior_year_extractor.py` | Modify L13-14 | Same fix |
| `~/chatbot_local/…/backend/core/document_analyzer.py` | Modify L162 | Same fix |

---

## Task 1: Restart Services

**Files:** None modified — runtime startup only

- [ ] **Step 1: Kill any stale processes on ports 8002 and 5173**

```bash
lsof -ti :8002 | xargs -r kill -9 2>/dev/null || true
lsof -ti :5173 | xargs -r kill -9 2>/dev/null || true
sleep 1
```

- [ ] **Step 2: Start backend**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/uvicorn main:app --host localhost --port 8002 --reload > /tmp/chatbot_backend.log 2>&1 &
echo "Backend PID: $!"
```

- [ ] **Step 3: Start frontend**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npm run dev > /tmp/chatbot_frontend.log 2>&1 &
echo "Frontend PID: $!"
```

- [ ] **Step 4: Wait and verify backend health**

```bash
sleep 6
curl -sf http://localhost:8002/health
# Expected: {"status":"ok"}
```

- [ ] **Step 5: Verify frontend responds**

```bash
curl -sf http://localhost:5173 > /dev/null 2>&1 && echo "Frontend OK" || echo "FAIL — check /tmp/chatbot_frontend.log"
```

Expected output: `Frontend OK`

---

## Task 2: Fix `export_converter.py` — Remove Unused `Optional` Import

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/core/export_converter.py:10`
- Modify: `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/export_converter.py:10`

**Root cause:** `Optional` is imported at L10 but is never referenced anywhere in the 300-line file. Python 3.10+ uses `X | None` syntax; `Optional` is not needed here.

- [ ] **Step 1: Write the test (verify import removal doesn't break the module)**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "
from core.export_converter import convert_to_format, convert_chat_to_pdf
print('export_converter imports OK')
"
```
Expected: `export_converter imports OK`

- [ ] **Step 2: Remove the unused import in Main Branch**

In `Main Branch/Project_AccountingLegalChatbot/backend/core/export_converter.py`, remove line 10:
```python
# DELETE THIS LINE:
from typing import Optional
```

The imports block should go from:
```python
import logging
import re
from typing import Optional
```
To:
```python
import logging
import re
```

- [ ] **Step 3: Remove the unused import in chatbot_local**

Same change in `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/export_converter.py` line 10.

- [ ] **Step 4: Verify the module still imports cleanly**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "
from core.export_converter import convert_to_format, convert_chat_to_pdf
print('export_converter imports OK after fix')
"
```
Expected: `export_converter imports OK after fix`

- [ ] **Step 5: Commit Main Branch fix**

```bash
cd "Main Branch/Project_AccountingLegalChatbot"
git add backend/core/export_converter.py
git commit -m "fix(lint): remove unused Optional import in export_converter.py

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Fix `prior_year_extractor.py` — Remove Unused `asyncio` + `Optional` Imports

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/core/prior_year_extractor.py:13-14`
- Modify: `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/prior_year_extractor.py:13-14`

**Root cause:** Both `asyncio` (L13) and `Optional` (L14) are imported but never referenced in the 441-line file.

- [ ] **Step 1: Write the test (verify import removal doesn't break the module)**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "
from core.prior_year_extractor import PriorYearExtractor
print('prior_year_extractor imports OK')
"
```
Expected: `prior_year_extractor imports OK`

- [ ] **Step 2: Remove the unused imports in Main Branch**

In `Main Branch/Project_AccountingLegalChatbot/backend/core/prior_year_extractor.py`, remove lines 13-14:
```python
# DELETE THESE TWO LINES:
import asyncio
from typing import Optional
```

The imports block goes from:
```python
import json
import logging
import re
import asyncio
from typing import Optional
```
To:
```python
import json
import logging
import re
```

- [ ] **Step 3: Remove the unused imports in chatbot_local**

Same change in `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/prior_year_extractor.py`.

- [ ] **Step 4: Verify the module still imports cleanly**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "
from core.prior_year_extractor import PriorYearExtractor
print('prior_year_extractor imports OK after fix')
"
```
Expected: `prior_year_extractor imports OK after fix`

- [ ] **Step 5: Commit Main Branch fix**

```bash
cd "Main Branch/Project_AccountingLegalChatbot"
git add backend/core/prior_year_extractor.py
git commit -m "fix(lint): remove unused asyncio + Optional imports in prior_year_extractor.py

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Fix `document_analyzer.py` — Remove Duplicate `import re as _re` at L162

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/core/document_analyzer.py:162`
- Modify: `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/document_analyzer.py:162`

**Root cause:** Inside the `_ocr_extract_pdf()` function:
- L162: `import re as _re` (at function scope, before try block)
- L213: `import re as _re` (inside the try block, before first use at L216)

L162's `_re` is never used before L213 re-imports it. L213 is the one that matters.

- [ ] **Step 1: Verify the structure before changing**

```bash
sed -n '159,220p' ~/chatbot_local/Project_AccountingLegalChatbot/backend/core/document_analyzer.py
```
Confirm: line 162 is `    import re as _re` standalone, and line 213 is `    import re as _re` inside the try block followed by `_re.compile(...)` at ~216.

- [ ] **Step 2: Write the test**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "
from core.document_analyzer import DocumentAnalyzer
print('document_analyzer imports OK')
"
```
Expected: `document_analyzer imports OK`

- [ ] **Step 3: Remove the duplicate import in Main Branch**

In `Main Branch/Project_AccountingLegalChatbot/backend/core/document_analyzer.py`:

Find and remove ONLY the first `import re as _re` (the one at function scope before the try block, around L162). The try-block import at ~L213 must remain.

Before:
```python
def _ocr_extract_pdf(file_path: str, page_count: int) -> tuple:
    """OCR fallback for scanned/image-based PDFs using tesseract."""
    import re as _re

    try:
```
After:
```python
def _ocr_extract_pdf(file_path: str, page_count: int) -> tuple:
    """OCR fallback for scanned/image-based PDFs using tesseract."""
    try:
```

- [ ] **Step 4: Remove the duplicate import in chatbot_local**

Same change in `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/document_analyzer.py`.

- [ ] **Step 5: Re-verify module imports**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "
from core.document_analyzer import DocumentAnalyzer
print('document_analyzer imports OK after fix')
"
```
Expected: `document_analyzer imports OK after fix`

- [ ] **Step 6: Commit Main Branch fix**

```bash
cd "Main Branch/Project_AccountingLegalChatbot"
git add backend/core/document_analyzer.py
git commit -m "fix(lint): remove duplicate import re as _re in document_analyzer._ocr_extract_pdf

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Push to GitHub + Sync chatbot_local

**Files:** None modified — git operations only

- [ ] **Step 1: Push Main Branch fixes to GitHub**

```bash
cd "/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
git push origin main
```

Expected: `main -> main` with no errors.

- [ ] **Step 2: Verify chatbot_local has the same fixes applied**

```bash
grep -n "Optional\|asyncio" ~/chatbot_local/Project_AccountingLegalChatbot/backend/core/export_converter.py
# Expected: no output (import removed)

grep -n "asyncio\|Optional" ~/chatbot_local/Project_AccountingLegalChatbot/backend/core/prior_year_extractor.py
# Expected: no output (both imports removed)

grep -n "import re as _re" ~/chatbot_local/Project_AccountingLegalChatbot/backend/core/document_analyzer.py
# Expected: exactly ONE line (the one inside try: block at ~213)
```

- [ ] **Step 3: Commit chatbot_local fixes**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/backend/core/export_converter.py \
        Project_AccountingLegalChatbot/backend/core/prior_year_extractor.py \
        Project_AccountingLegalChatbot/backend/core/document_analyzer.py
git commit -m "fix(lint): remove unused imports (Optional, asyncio, duplicate _re)

Mirrors fixes from Main Branch. Pylance hints cleared in:
- core/export_converter.py
- core/prior_year_extractor.py
- core/document_analyzer.py

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Task 6: Final Verification + Journal Update

- [ ] **Step 1: Confirm both services are running**

```bash
curl -sf http://localhost:8002/health && echo "Backend ✅" || echo "Backend ❌"
curl -sf http://localhost:5173 > /dev/null 2>&1 && echo "Frontend ✅" || echo "Frontend ❌"
```

- [ ] **Step 2: Confirm zero Pylance hints remain**

Verify VS Code shows no hints in:
- `export_converter.py`
- `prior_year_extractor.py`
- `document_analyzer.py`

- [ ] **Step 3: Update PROJECT_JOURNAL.md**

Append to the session log:
```
### Session: 2026-05-06 — Pylance Hint Cleanup
- Removed unused Optional from export_converter.py
- Removed unused asyncio + Optional from prior_year_extractor.py  
- Removed duplicate import re as _re from document_analyzer.py
- Both services confirmed running: backend :8002, frontend :5173
```

- [ ] **Step 4: Commit journal**

```bash
git add PROJECT_JOURNAL.md
git commit -m "docs: session log — Pylance lint cleanup + services restart"
git push origin main
```
