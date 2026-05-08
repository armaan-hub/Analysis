# Fix UAE Entity Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix failing UAE entity extraction tests by adding missing keywords and refining the over-broad organization regex.

**Architecture:** 
1. Expand `_FINANCE_TERMS` keyword set in `core/rag/graph_rag.py`.
2. Restrict `_ORG_RE` regex in `core/rag/graph_rag.py` to avoid matching full sentences by requiring capitalized words.

**Tech Stack:** Python 3, Regex, Pytest

---

### Task 1: Update Keywords and Regex in `graph_rag.py`

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/core/rag/graph_rag.py`

- [ ] **Step 1: Add new terms to `_FINANCE_TERMS`**

Add `fta`, `peppol`, `e-invoicing`, `electronic invoice`, and `invoice` to the `_FINANCE_TERMS` frozenset.

- [ ] **Step 2: Refine `_ORG_RE` pattern**

Change the regex to ensure it only matches sequences of capitalized words, preventing it from capturing full sentences that happen to start with a capital letter.

Current: `r"\b([A-Z][a-zA-Z&,\.\s]{2,40}(?:Inc|Ltd|LLC|Corp|Co|Group|Holdings|FZE|PJSC)?)\b"`
New: `r"\b([A-Z][A-Za-z0-9&,\.]{1,30}(?:\s+[A-Z][A-Za-z0-9&,\.]{1,30}){0,4}(?:\s+(?:Inc|Ltd|LLC|Corp|Co|Group|Holdings|FZE|PJSC))?)\b"`

- [ ] **Step 3: Run the tests to verify the fix**

Run: `python3 -m pytest tests/test_entity_extraction_uae.py`
Expected: ALL 15 tests pass.

- [ ] **Step 4: Commit changes**

```bash
git add core/rag/graph_rag.py
git commit -m "fix(rag): improve entity extraction keywords and tighten ORG regex"
```
