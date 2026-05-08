# Fix Regression Issues in Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all failing tests in the backend test suite by updating them to use `core.domains` and match the new filter shapes and logic.

**Architecture:** Update test expectations to align with the unified domain logic and new filter shapes. Fix incorrect mocks and investigate fuzzy matching behavior.

**Tech Stack:** Python, pytest

---

### Task 1: Fix `tests/test_vat_hotel_apt_scenario.py`

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_vat_hotel_apt_scenario.py`

- [ ] **Step 1: Update imports and references**
  Replace `from api.chat import _DOMAIN_TO_DOC_DOMAINS` with `from core.domains import DOMAIN_TO_DOC_DOMAINS`.
  Update all occurrences of `_DOMAIN_TO_DOC_DOMAINS` to `DOMAIN_TO_DOC_DOMAINS`.

- [ ] **Step 2: Verify fix**
  Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_vat_hotel_apt_scenario.py -v`

### Task 2: Fix `tests/test_selected_doc_ids.py`

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_selected_doc_ids.py`

- [ ] **Step 1: Update `expected_filter`**
  Update `expected_filter` in `test_selected_doc_ids_scopes_rag_filter` to include `e_invoicing` and `general` in the domain list.
  New filter: `{"domain": {"$in": ["vat", "e_invoicing", "general"]}}`.

- [ ] **Step 2: Verify fix**
  Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_selected_doc_ids.py -v`

### Task 3: Fix `tests/test_relevance_rag.py`

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_relevance_rag.py`

- [ ] **Step 1: Update expected filters for mode=deep_research and analyst**
  Update `_AND_FILTER` and expectations in `test_chat_filter_deep_mode_selected_docs_combines_and` and `test_chat_filter_analyst_no_docs_uses_law_finance` to match new `DOMAIN_TO_DOC_DOMAINS` mappings.

- [ ] **Step 2: Investigate and fix `general_law` suppression**
  Investigate why `test_general_law_suppresses_low_score_finance_sources` and `test_general_law_threshold_boundary` are failing. Check `api/chat.py` for threshold logic.

- [ ] **Step 3: Verify fix**
  Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_relevance_rag.py -v`

### Task 4: Fix `tests/test_no_llm_guard.py`

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_no_llm_guard.py`

- [ ] **Step 1: Remove `search_in_documents` mock**
  Remove the mock for `search_in_documents` as it no longer exists on `RAGEngine`.

- [ ] **Step 2: Verify fix**
  Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_no_llm_guard.py -v`

### Task 5: Fix `tests/test_fuzzy_domain.py`

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_fuzzy_domain.py`
- Modify: `Project_AccountingLegalChatbot/backend/core/chat/domain_classifier.py` (if needed)

- [ ] **Step 1: Investigate fuzzy matching failures**
  Check why `employmant` matches `general_law` and `peppl` matches `e_invoicing`.
  Adjust keywords in `core/domains.py` if necessary, or update test expectations if the new behavior is correct.

- [ ] **Step 2: Verify fix**
  Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_fuzzy_domain.py -v`

### Task 6: Fix `tests/test_legacy_domain_compat.py`

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/tests/test_legacy_domain_compat.py`

- [ ] **Step 1: Fix `general` domain case**
  Investigate why `mock_cls` was not called for `general`. Adjust test expectation or `api/chat.py` if `general` should still trigger classifier.

- [ ] **Step 2: Verify fix**
  Run: `cd Project_AccountingLegalChatbot/backend && pytest tests/test_legacy_domain_compat.py -v`
