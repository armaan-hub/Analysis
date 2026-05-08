# Harden RAG Domain Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an unconditional post-search domain validation to `backend/api/chat.py` (both streaming and non-streaming paths) to prevent cross-domain contamination.

**Architecture:** Secondary "belt-and-suspenders" check that runs whenever the conversation has an explicit domain, filtering out results that don't match the expected document domains.

**Tech Stack:** Python (FastAPI/Backend)

---

### Task 1: Research and Preparation

- [ ] **Step 1: Verify current state of `backend/api/chat.py`**
    Already done. Found streaming guard around 660 and non-streaming around 1110.

### Task 2: Modify Streaming Path

- [ ] **Step 1: Insert unconditional validation block in streaming path**
    Modify `Project_AccountingLegalChatbot/backend/api/chat.py` around line 689 (after the existing guard).

**File:** `Project_AccountingLegalChatbot/backend/api/chat.py`
**Location:** Around line 689

```python
                # ------ unconditional domain validation (belt-and-suspenders) ------
                _conv_domain = _cls.domain.value
                if _conv_domain and _conv_domain not in ("general", "general_law") and _search_results:
                    _expected_domains = set(_DOMAIN_TO_DOC_DOMAINS.get(_conv_domain, [_conv_domain]))
                    _filtered = [
                        r for r in _search_results
                        if r.get("metadata", {}).get("domain") in _expected_domains
                        or r.get("metadata", {}).get("domain") is None
                    ]
                    if len(_filtered) < len(_search_results):
                        logger.info(
                            "Unconditional domain validation (stream): kept %d/%d results for %s",
                            len(_filtered), len(_search_results), _conv_domain
                        )
                        _search_results = _filtered
                # ------ end unconditional validation ------
```

### Task 3: Modify Non-Streaming Path

- [ ] **Step 1: Insert unconditional validation block in non-streaming path**
    Modify `Project_AccountingLegalChatbot/backend/api/chat.py` around line 1133 (after the existing guard).

**File:** `Project_AccountingLegalChatbot/backend/api/chat.py`
**Location:** Around line 1133

```python
        # ------ unconditional domain validation (belt-and-suspenders) ------
        _conv_domain_ns = classifier_result.domain.value
        if _conv_domain_ns and _conv_domain_ns not in ("general", "general_law") and search_results:
            _expected_domains_ns = set(_DOMAIN_TO_DOC_DOMAINS.get(_conv_domain_ns, [_conv_domain_ns]))
            _filtered_ns = [
                r for r in search_results
                if r.get("metadata", {}).get("domain") in _expected_domains_ns
                or r.get("metadata", {}).get("domain") is None
            ]
            if len(_filtered_ns) < len(search_results):
                logger.info(
                    "Unconditional domain validation (non-stream): kept %d/%d results for %s",
                    len(_filtered_ns), len(search_results), _conv_domain_ns
                )
                search_results = _filtered_ns
        # ------ end unconditional validation ------
```

### Task 4: Verification

- [ ] **Step 1: Verify syntax and linting**
    Run `ruff check Project_AccountingLegalChatbot/backend/api/chat.py` or similar if available.

- [ ] **Step 2: Run existing tests**
    Run `pytest Project_AccountingLegalChatbot/backend/tests/` to ensure no regressions.
