# RAG Domain Classification Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `_infer_domain_from_name` in `backend/core/rag_engine.py` to correctly classify documents according to the new keywords and priorities.

**Architecture:** Modify keyword sets in `_infer_domain_from_name` to improve precision and avoid cross-domain misclassification. Remove broad interceptors like bare "free zone" from the commercial block and add specific keywords to corporate tax and VAT blocks.

**Tech Stack:** Python

---

### Task 1: Update `corporate_tax` keywords

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/core/rag_engine.py:163-184`

- [ ] **Step 1: Add new corporate tax keywords**
Add keywords: `"free zone person"`, `"free zone entit"`, `"ctgfzp"`, `"qualifying activities"`, `"excluded activities"`, `"public benefit entit"`, `"charit"`, `"ct amend"`, `"ct de registr"`.

```python
    # Corporate Tax — must come BEFORE vat (many CT docs mention "tax" broadly)
    if any(kw in n for kw in [
        "corporate tax", "ctp0", "ct registration", "ct deregistr", "ct edit",
        # Federal Decree Law 47 of 2022 (the CT law) — works after hyphen normalisation
        "federal decree law no. 47", "law no. 47",
        # CT-specific concepts
        "small business relief", "qualifying free zone", "qualifying income",
        "participation exemption", "interest deduction", "transfer pricing",
        "tax group", "tax residency",
        # FTA numbered CT guide series (topics that only appear in CT guides)
        "taxation of", "taxable income",
        "business restructuring", "qualifying group", "foreign source income",
        "extractive", "registration of juridical person", "registration of natural person",
        "exempt person", "investment fund", "master guide",
        "accounting standards guide",  # CT accounting standards guide
        "explanatory guide",  # CT explanatory guide
        "determination of taxable", "automotive sector",
        "financial services",  # CT financial services sector guide
        "insurance",  # CT insurance sector guide (not VAT on insurance)
        "natural resource", "natural person",
        "qualifying public benefit", "public benefit entity",
        "free zone person", "free zone entit", "ctgfzp",
        "qualifying activities", "excluded activities",
        "public benefit entit", "charit", "ct amend", "ct de registr",
    ]):
        return "corporate_tax"
```

### Task 2: Update `commercial` keywords

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/core/rag_engine.py:192`

- [ ] **Step 1: Remove bare "free zone"**
Remove `"free zone"` from the list to prevent it from intercepting CT or VAT documents that mention free zones.

```python
    # Commercial / Company Law / Business Registration
    if any(kw in n for kw in [
        "commercial compan", "licensing", "rakez", "dwc",
        "hamriyah", "dubai south", "rak free",
    ]):
        return "commercial"
```

### Task 3: Update `vat` keywords

**Files:**
- Modify: `Project_AccountingLegalChatbot/backend/core/rag_engine.py` (near vat block)

- [ ] **Step 1: Add new VAT keywords**
Add keywords: `"profit margin scheme"`, `"togc"`, `"public transportation"`, `"farms"`, `"disbursement"`, `"reimbursement"`, `"dubai owners association"`, `"manpower vs visa"`, `"e-commerce vat"`, `"vat public clarif"`.

```python
    # VAT (Value Added Tax)
    if any(kw in n for kw in [
        "vat", "value added tax", "input tax", "output tax", "tax invoice",
        "zero rated", "exempt", "standard rated", "reverse charge",
        "profit margin scheme", "togc", "public transportation", "farms",
        "disbursement", "reimbursement", "dubai owners association",
        "manpower vs visa", "e-commerce vat", "vat public clarif",
    ]):
        return "vat"
```

### Task 4: Verification

- [ ] **Step 1: Run tests**
Run: `pytest Project_AccountingLegalChatbot/backend/tests/test_domain_classifier.py`
Expected: ALL 13 tests PASS.
