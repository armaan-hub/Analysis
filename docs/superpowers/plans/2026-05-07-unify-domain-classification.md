# Unify Domain Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `backend/core/rag_engine.py` to use the centralized domain classification logic from `backend/core/domains.py`.

**Architecture:** Replace the redundant and divergent local `_infer_domain_from_name` function in `rag_engine.py` with the standardized `infer_domain_from_name` from `core.domains`. This ensures consistent domain tagging across the application.

**Tech Stack:** Python

---

### Task 1: Research and Baseline

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_domain_classifier.py`

- [ ] **Step 1: Run existing tests to establish baseline**

Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_domain_classifier.py -v`
Expected: Tests might fail or pass depending on current implementation, but we need to know the state.

- [ ] **Step 2: Commit baseline (if any changes were needed for research, otherwise skip)**

### Task 2: Refactor rag_engine.py

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/core/rag_engine.py`

- [ ] **Step 1: Update imports and replace local function**

Modify `Project_AccountingLegalChatbot/backend/core/rag_engine.py`:
1. Add `from core.domains import infer_domain_from_name`.
2. Delete the `_infer_domain_from_name` function definition.
3. Update the call in `ingest_chunks` from `_infer_domain_from_name(original_name)` to `infer_domain_from_name(original_name)`.

- [ ] **Step 2: Commit refactor**

```bash
git add Project_AccountingLegalChatbot/backend/core/rag_engine.py
git commit -m "refactor: use centralized domain inference in rag_engine"
```

### Task 3: Update and Verify Tests

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_domain_classifier.py`

- [ ] **Step 1: Update test imports**

Modify `Project_AccountingLegalChatbot/backend/tests/test_domain_classifier.py` to import `infer_domain_from_name` from `core.domains` instead of `_infer_domain_from_name` from `core.rag_engine`. Update function calls in the test.

- [ ] **Step 2: Run tests to verify fix**

Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_domain_classifier.py -v`
Expected: Tests PASS.

- [ ] **Step 3: Commit test updates**

```bash
git add Project_AccountingLegalChatbot/backend/tests/test_domain_classifier.py
git commit -m "test: update domain classifier tests to use centralized logic"
```
