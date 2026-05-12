# Pre-existing Test Failures Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 pre-existing test failures (3 entity extraction + 1 graph-RAG partial match) and sync the GoogleDrive copy of chat_history_viewer.py to eliminate the VS Code diagnostic.

**Architecture:** All test failures live in `backend/core/rag/graph_rag.py`. Task 1 adds missing e-invoicing terms to the keyword lookup table. Task 2 upgrades `search_by_entities` from exact `IN` matching to LIKE-based substring matching using a UNION sub-query so per-term match counts are computed correctly. Task 3 copies the updated viewer file from chatbot_local to the un-tracked GoogleDrive copy.

**Tech Stack:** Python 3, SQLite, pytest, pathlib

---

## File Map

| Task | File | Change |
|------|------|--------|
| 1 | `backend/core/rag/graph_rag.py` | Add 5 e-invoicing terms to `_FINANCE_TERMS` |
| 2 | `backend/core/rag/graph_rag.py` | Rewrite `search_by_entities` to use LIKE substring matching |
| 3 | `chat_history_viewer.py` (GoogleDrive copy) | Copy updated file from chatbot_local to GoogleDrive path |

**Live code root:** `~/chatbot_local/Project_AccountingLegalChatbot/`
**GoogleDrive copy (NOT git-tracked):** `/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/Main Branch/Project_AccountingLegalChatbot/`

---

### Task 1: Add E-Invoicing Terms to Entity Extraction

**Files:**
- Modify: `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/rag/graph_rag.py` lines 27–32

**Root cause:** `_FINANCE_TERMS` does not include "fta", "peppol", "e-invoicing", "electronic invoice", "invoice". The fallback ORG regex matches garbage like "the fta requires e" instead of the actual individual terms.

- [ ] **Step 1: Verify the tests currently fail**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_entity_extraction_uae.py::TestEInvoicingTerms -v --no-header
```
Expected: 3 FAILED

- [ ] **Step 2: Add e-invoicing terms to `_FINANCE_TERMS`**

In `backend/core/rag/graph_rag.py`, find the `_FINANCE_TERMS` frozenset (lines ~27–32) and add the 5 new terms:

```python
# BEFORE:
_FINANCE_TERMS = frozenset([
    "revenue", "ebitda", "net profit", "gross margin", "cash flow",
    "balance sheet", "income statement", "vat", "tax", "audit", "ifrs", "gaap",
    "amortisation", "depreciation", "provision", "asset",
    "equity", "dividend", "working capital", "free cash flow",
])

# AFTER:
_FINANCE_TERMS = frozenset([
    "revenue", "ebitda", "net profit", "gross margin", "cash flow",
    "balance sheet", "income statement", "vat", "tax", "audit", "ifrs", "gaap",
    "amortisation", "depreciation", "provision", "asset",
    "equity", "dividend", "working capital", "free cash flow",
    # E-invoicing domain terms
    "fta", "peppol", "e-invoicing", "electronic invoice", "invoice",
])
```

- [ ] **Step 3: Run the 3 entity tests to confirm they now pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_entity_extraction_uae.py::TestEInvoicingTerms -v --no-header
```
Expected: 3 PASSED

- [ ] **Step 4: Run full entity test class to confirm no regressions**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_entity_extraction_uae.py -v --no-header
```
Expected: 15 PASSED

- [ ] **Step 5: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/core/rag/graph_rag.py
git commit -m "fix: add e-invoicing domain terms (fta, peppol, e-invoicing, invoice) to entity extraction

Resolves TestEInvoicingTerms::test_einvoicing_term_extracted,
test_peppol_term_extracted, and test_invoice_term_extracted.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Fix Partial Entity Matching in search_by_entities

**Files:**
- Modify: `~/chatbot_local/Project_AccountingLegalChatbot/backend/core/rag/graph_rag.py` — `search_by_entities` method (lines ~215–255)

**Root cause:** Current SQL uses `WHERE LOWER(name) IN (placeholders)` — exact equality. Query term "invoicing" never equals stored entity "INVOICING SERVICE PROVIDERS", so 0 results are returned. Fix uses per-term LIKE UNION sub-queries so `graph_score` counts distinct matched terms correctly.

- [ ] **Step 1: Verify the test currently fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_graph_rag.py::test_search_by_entities_partial_match -v --no-header
```
Expected: FAILED — "Expected ≥2 partial matches, got 0: []"

- [ ] **Step 2: Replace `search_by_entities` with LIKE-based implementation**

In `backend/core/rag/graph_rag.py`, replace the entire `search_by_entities` method body:

```python
def search_by_entities(self, query_entities: list[str], top_k: int = 10) -> list[dict]:
    """Find chunks across the whole corpus that contain query entities.

    Matching is substring-based (LIKE %term%): a stored entity of
    "INVOICING SERVICE PROVIDERS" will match query term "invoicing".

    Returns list of dicts with keys: chunk_id, doc_id, chunk_index, graph_score.
    graph_score = distinct_matched_query_terms / total_query_terms (0.0–1.0).
    Results sorted descending by graph_score, limited to top_k.
    """
    if not query_entities:
        return []

    normalised = [e.lower().strip() for e in query_entities if e.strip()]
    if not normalised:
        return []

    # Build a UNION query — one branch per term — so COUNT(DISTINCT matched_term)
    # correctly scores how many query terms each chunk covers.
    union_parts = []
    params: list = []
    for term in normalised:
        union_parts.append(
            "SELECT doc_id, chunk_index, ? AS matched_term "
            "FROM entities WHERE LOWER(name) LIKE ?"
        )
        params.extend([term, f"%{term}%"])

    union_sql = " UNION ".join(union_parts)
    conn = self._connect()
    rows = conn.execute(
        f"""
        SELECT doc_id, chunk_index, COUNT(DISTINCT matched_term) AS match_count
        FROM ({union_sql})
        GROUP BY doc_id, chunk_index
        ORDER BY match_count DESC
        LIMIT ?
        """,
        params + [top_k],
    ).fetchall()
    if self._conn is None:
        conn.close()

    total = len(normalised)
    results = []
    for doc_id, chunk_index, match_count in rows:
        results.append({
            "chunk_id": f"{doc_id}_chunk_{chunk_index}",
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "graph_score": round(match_count / total, 4),
        })
    return results
```

- [ ] **Step 3: Run the partial match test to confirm it passes**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_graph_rag.py::test_search_by_entities_partial_match -v --no-header
```
Expected: PASSED

- [ ] **Step 4: Run the full graph_rag test file to confirm no regressions**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_graph_rag.py -v --no-header
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/core/rag/graph_rag.py
git commit -m "fix: use LIKE substring matching in search_by_entities for partial entity queries

Replaces exact IN-match SQL with per-term LIKE UNION sub-query so that
stored entity 'INVOICING SERVICE PROVIDERS' matches query term 'invoicing'.
graph_score computed via COUNT(DISTINCT matched_term) to avoid double-counting.

Resolves test_search_by_entities_partial_match.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Sync GoogleDrive chat_history_viewer.py

**Files:**
- Source: `~/chatbot_local/Project_AccountingLegalChatbot/chat_history_viewer.py`
- Destination: `/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/Main Branch/Project_AccountingLegalChatbot/chat_history_viewer.py`

**Root cause:** The GoogleDrive copy is NOT tracked by the GoogleDrive git repo (confirmed: "exists on disk, but not in HEAD"). It's the pre-fix version lacking `_find_db_path()` and `_get_db_candidates()`. The `import os` is unused there because `os.environ.get("CHATBOT_DB_PATH")` doesn't exist in the old version.

- [ ] **Step 1: Confirm the GoogleDrive copy is outdated**

```bash
grep -n "_find_db_path\|_get_db_candidates\|os.environ" \
  "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/Main Branch/Project_AccountingLegalChatbot/chat_history_viewer.py"
```
Expected: no output (those functions don't exist in the old copy)

- [ ] **Step 2: Copy the updated file**

```bash
cp ~/chatbot_local/Project_AccountingLegalChatbot/chat_history_viewer.py \
  "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/Main Branch/Project_AccountingLegalChatbot/chat_history_viewer.py"
```

- [ ] **Step 3: Verify the copy has the new functions**

```bash
grep -n "_find_db_path\|_get_db_candidates\|os.environ" \
  "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/Main Branch/Project_AccountingLegalChatbot/chat_history_viewer.py"
```
Expected: lines showing those function definitions and the `os.environ.get` call

---

### Task 4: Full Regression Suite + Push

**Preconditions:** Tasks 1, 2, and 3 all complete.

- [ ] **Step 1: Run the full test suite**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/ -q --no-header 2>&1 | tail -10
```
Expected: 0 failed (was 4 failed before this plan), ≥655 passed, 8 skipped

- [ ] **Step 2: If any new failures appear, do NOT push — debug first**

If the tail shows unexpected failures, run:
```bash
python3 -m pytest tests/ -v --no-header 2>&1 | grep FAILED
```
Report the failures before proceeding.

- [ ] **Step 3: Push to GitHub**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git push origin main
```
Expected: successful push showing 2 new commits

- [ ] **Step 4: Update PROJECT_JOURNAL.md**

In `/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/PROJECT_JOURNAL.md`, append a new entry under the Chronological Session Log section:

```markdown
### 2026-05-07 Session 2 — Pre-existing Test Failures Fixed

**Goal:** Fix 4 pre-existing test failures and sync GoogleDrive viewer copy.

**Fixes applied:**
- `graph_rag.py`: Added "fta", "peppol", "e-invoicing", "electronic invoice", "invoice" to `_FINANCE_TERMS` → fixes 3 entity extraction tests
- `graph_rag.py`: Rewrote `search_by_entities` to use LIKE substring matching (UNION sub-query) → fixes partial match test
- `chat_history_viewer.py`: Synced GoogleDrive copy from chatbot_local → fixes VS Code unused-import diagnostic

**Result:** 0 failures (was 4), 655+ passed, 8 skipped. Pushed to armaan-hub/Analysis main.
```

- [ ] **Step 5: Commit and push journal**

```bash
cd "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
git add PROJECT_JOURNAL.md
git commit -m "docs: session log — fix 4 pre-existing test failures in graph_rag

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

