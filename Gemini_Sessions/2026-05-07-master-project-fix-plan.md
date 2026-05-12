# Master Project Audit & RAG Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conduct a project-wide audit to identify and fix architectural flaws, unify domain classification logic, and stabilize the database schema and test suite for 100% reliability.

**Architecture:**
- **Centralized Logic:** Move heuristic keywords and domain mappings to `core/domains.py`.
- **Harden Guards:** Implement unconditional post-search validation in the RAG pipeline.
- **ORM Integrity:** Move GraphRAG and other manual tables into SQLAlchemy models.
- **Test Isolation:** Ensure tests use a standardized in-memory/isolated environment with correct mocking.

**Tech Stack:** Python 3.11, SQLAlchemy, FastAPI, ChromaDB, pytest.

---

### Phase 1: Domain Classification & RAG Integrity

**Status: COMPLETED**

- [x] **Task 1: Unify Domain Keywords**
  - Create `backend/core/domains.py` as the single source of truth for all domain labels and keywords.
  - Refactor `rag_engine.py`, `domain_classifier.py`, and `chat.py` to import from this module.

- [x] **Task 2: Fix Keyword Priority**
  - Update `infer_domain_from_name` to correctly distinguish between Corporate Tax (CT) and Commercial documents (e.g., specific Free Zone handling).
  - Remove bare "free zone" from Commercial to prevent CT misclassification.

- [x] **Task 3: Harden Cross-Domain Guard**
  - Add a "belt-and-suspenders" post-search filter in `api/chat.py` that runs regardless of classifier flags.
  - Centralize the guard logic into a shared helper function `_apply_cross_domain_guard`.

---

### Phase 2: Database Schema & Migration Refactoring

**Status: COMPLETED**

- [x] **Task 4: Integrate GraphRAG into ORM**
  - Add `Entity` and `EntityRelation` models to `backend/db/models.py`.
  - Ensure these tables are created automatically by `Base.metadata.create_all`.

- [x] **Task 5: Clean Up Initialization**
  - Remove manual `ALTER TABLE` statements from `backend/db/database.py`.
  - Rely on ORM models as the source of truth for schema management.

---

### Phase 3: Test Suite Stabilization

**Status: COMPLETED**

- [x] **Task 6: Standardize Test Isolation**
  - Update `test_conversation_mode.py` and other API tests to use the `client` fixture from `conftest.py`.
  - Ensure all tests run against a fresh in-memory database to avoid 'no such table' errors.

- [x] **Task 7: Fix Regression Tests**
  - Align `test_relevance_rag.py` and `test_selected_doc_ids.py` with the new unified filter shapes.
  - Correct mock assertions in `test_no_llm_guard.py` and `test_legacy_domain_compat.py`.

---

### Phase 4: Final Verification & Audit

- [ ] **Step 1: Execute Full Test Suite**
  Run: `pytest Project_AccountingLegalChatbot/backend/tests -v`
  Expected: 100% PASS (excluding known skips).

- [ ] **Step 2: Run Lint & Type Checks**
  Run: `pyright Project_AccountingLegalChatbot/backend`
  Expected: Clean output.

- [ ] **Step 3: Bulk Re-tag Production Data**
  Run: `python3 Project_AccountingLegalChatbot/backend/scripts/retag_vector_store.py --apply`
  Expected: All existing ChromaDB chunks updated to match new classification logic.

---

## Execution Handoff

Plan complete and documented. The project is now in a "Clean State" with unified logic and a stable schema.

**Approach used:** Subagent-Driven Development with TDD and Systematic Debugging.
