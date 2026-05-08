# RAG Domain Classification Fix — Design Spec
**Date:** 2026-05-07  
**Status:** Approved  
**Scope:** All domains (corporate_tax, vat, commercial, general)

---

## Problem Statement

The RAG pipeline uses `_infer_domain_from_name()` to assign a `domain` metadata tag to every document chunk at ingest time. When a user asks a question in a specific domain (e.g., "tell me corporate tax"), the search filter only returns chunks whose `domain` matches. If `_infer_domain_from_name()` misclassifies a document, those chunks are invisible to domain-filtered searches.

**Confirmed failure chain for "tell me corporate tax":**
1. Query classified as `corporate_tax` domain → filter `{"domain": {"$in": ["corporate_tax"]}}` applied
2. CT Free Zone Person guides were ingested with `domain=commercial` → filtered out → 0 results
3. `_top_score (0.0) < _BROAD_FALLBACK_THRESHOLD (0.39)` → broad fallback fires
4. Broad fallback (no domain filter) returns VAT/real-estate docs (scores 0.664–0.686)
5. Cross-domain contamination guard absent/broken at time of conversation → VAT docs stored as CT sources
6. `chat_history_viewer.py` confirms: all 15 sources show `⚠️ wrong-domain` (vat in corporate_tax conversation)

---

## Root Causes

### 1. `_infer_domain_from_name` keyword priority conflict

The function checks domains in order: `e_invoicing → corporate_tax → labour → commercial → ifrs → vat → general`.

The `commercial` block contains bare `"free zone"` which matches BEFORE the `vat` block, causing:
- **CT guides misclassified as `commercial`:** `"17. Free Zone Persons 20052024.pdf"`, `"1- Free Zone Person-English.pdf"`, `"FTA_Release_Guide_on_Free_Zone_Entities_1716532174.pdf"`
- **VAT guide misclassified as `commercial`:** `"VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf"`

### 2. Missing keywords for CT and VAT documents

Many CT and VAT documents contain no keywords from their correct domain block, defaulting to `general`:
- **CT:** Charities guide (`20. Charities.pdf`), Qualifying Activities Cabinet Decisions (`139-2023`, `229-2025`, `265`), CT form files (`1.CT Amend Registration.pdf`, `5.CT De-Registration.pdf`)
- **VAT:** Numbered FTA Public Clarifications (01–43 series) — Profit Margin Scheme, TOGC, Public Transportation, Farms, Disbursements/Reimbursements, Dubai Owners Association, Manpower vs Visa, E-Commerce

### 3. Cross-domain contamination guard reliability

The guard in `chat.py` (line ~660) only executes when `_domain_filter_applied` flag is set correctly. If the flag is wrong (or was absent in older code), wrong-domain fallback docs pass through unchecked.

---

## Three-Layer Fix Design

### Layer A — Fix `_infer_domain_from_name` (`rag_engine.py`)

#### A1: Remove bare `"free zone"` from commercial keywords
The specific FZ location keywords (Dubai South, Hamriyah, RAKEZ, RAK Free Zone, DWC, etc.) already catch real commercial FZ documents. Removing bare `"free zone"` prevents CT and VAT FZ guides from being intercepted by commercial.

#### A2: Add keywords to `corporate_tax` block (run BEFORE commercial)

New keywords to add to the CT detection block:

| Keyword | Catches |
|---|---|
| `"free zone person"` | `1- Free Zone Person-English.pdf`, `17. Free Zone Persons 20052024.pdf` |
| `"free zone entit"` | `FTA_Release_Guide_on_Free_Zone_Entities_1716532174.pdf` |
| `"ctgfzp"` | FTA CT Free Zone Person guide code documents |
| `"qualifying activities"` | `139-2023 Qualifying Activities and Excluded Activities.pdf`, `229-of-2025...Qualifying-Activities.pdf`, `265 Qualifying Activities.pdf` |
| `"excluded activities"` | Same docs as above |
| `"public benefit entit"` | CT Guide 9/37 on Public Benefit Entities |
| `"charit"` | `20. Charities.pdf` (CT Guide #20) |
| `"ct amend"` | `1.CT Amend Registration.pdf` |
| `"ct de registr"` | `5.CT De-Registration.pdf` |

These run before the `commercial` block, so they take priority.

#### A3: Add keywords to `vat` block

New keywords to add to the VAT detection block:

| Keyword | Catches |
|---|---|
| `"profit margin scheme"` | FTA VAT Public Clarification on Profit Margin Scheme |
| `"togc"` | Transfer of Going Concern VAT clarification |
| `"public transportation"` | FTA VAT clarification on public transport |
| `"farms"` | FTA VAT clarification on farms/agricultural exemptions |
| `"disbursement"` | VAT disbursements public clarification |
| `"reimbursement"` | VAT reimbursements public clarification |
| `"dubai owners association"` | FTA VAT clarification on Dubai owners associations |
| `"manpower vs visa"` | FTA VAT clarification on manpower vs visa services |
| `"e-commerce vat"` | VAT on e-commerce transactions guide |
| `"vat public clarif"` | Catch-all for numbered FTA VAT clarification series |

Note: VAT block still runs AFTER commercial, so these won't conflict. The `"free zone"` removal from commercial in A1 allows `"vat treatment on sale"` (already in VAT?) or a new prefix like `"vat treatment"` to catch the misclassified VAT FZ doc.

#### A4: No extra VAT keyword needed for the FZ VAT doc
`"vat"` is already in the VAT block (line 207 of rag_engine.py). After removing `"free zone"` from the commercial block in A1, `"VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf"` will normalize to `"vat treatment on sale..."` — which contains `"vat"` — and naturally fall through to the VAT block. No new keyword required.

---

### Layer B — Harden cross-domain contamination guard (`chat.py`)

#### Current guard (streaming path, line ~660):
```python
if (_domain_filter_applied and _broad_fallback_used 
    and _queried_doc_domains and _search_results):
    # filter out wrong-domain results
```

#### Problem: 
- Guard depends on `_domain_filter_applied` flag being set correctly
- Flag is set at line ~604 by checking if `$and` key exists in filter dict
- If this check has any bug, wrong-domain docs escape

#### Fix — Add explicit post-search domain validation:
After any search (with or without fallback), when the conversation has an explicit domain (`conv_domain`), add a secondary check:

```python
# Post-search domain validation (belt-and-suspenders)
if conv_domain and conv_domain != "general" and _search_results:
    expected_domains = _DOMAIN_TO_DOC_DOMAINS.get(conv_domain, [conv_domain])
    _search_results = [
        r for r in _search_results
        if r.get("metadata", {}).get("domain") in expected_domains
        or r.get("metadata", {}).get("domain") is None  # older chunks without domain tag
    ]
```

This guard runs unconditionally (not dependent on flag state) for non-general conversations.

Apply the same guard to the **non-streaming path** (lines ~1043–1116) which duplicates the RAG search logic.

#### Note on `domain is None` case:
Chunks ingested before the domain tagging feature was added have no `domain` metadata. These should be allowed through (not filtered out) to avoid breaking retrieval for legacy content. The validator only rejects chunks with an explicit wrong domain.

---

### Layer C — Bulk Re-tag Script

**File:** `backend/scripts/retag_vector_store.py`

**Purpose:** Update `domain` metadata on all existing ChromaDB chunks to match the fixed `_infer_domain_from_name()` logic.

**Algorithm:**
```
1. Connect to ChromaDB collection
2. Get all chunks with metadata (batch by 1000 to avoid memory issues)
3. For each chunk:
   a. Read original_name from metadata
   b. Run new _infer_domain_from_name(original_name)
   c. Compare to stored domain value
   d. If different → record as change needed
4. Dry-run mode: print summary of changes, exit
5. Apply mode: call collection.update() for changed chunks
6. Print final summary: N chunks retagged across M documents
```

**Usage:**
```bash
# Preview changes
python backend/scripts/retag_vector_store.py --dry-run

# Apply changes
python backend/scripts/retag_vector_store.py --apply
```

**Note:** Since the vector store is currently empty (0 embeddings confirmed 2026-05-07), the script is needed for after re-ingestion. It should be run once immediately after re-uploading documents.

---

### Layer D — Unit Tests

**File:** `backend/tests/test_domain_classifier.py`

Test cases covering all confirmed misclassifications:

| Filename | Expected domain | Previous wrong domain |
|---|---|---|
| `17. Free Zone Persons 20052024.pdf` | `corporate_tax` | `commercial` |
| `1- Free Zone Person-English.pdf` | `corporate_tax` | `commercial` |
| `FTA_Release_Guide_on_Free_Zone_Entities_1716532174.pdf` | `corporate_tax` | `commercial` |
| `VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf` | `vat` | `commercial` |
| `20. Charities.pdf` | `corporate_tax` | `general` |
| `139-2023 Qualifying Activities and Excluded Activities.pdf` | `corporate_tax` | `general` |
| `229-of-2025...Qualifying-Activities.pdf` | `corporate_tax` | `general` |
| `265 Qualifying Activities.pdf` | `corporate_tax` | `general` |
| `1.CT Amend Registration.pdf` | `corporate_tax` | `general` |
| `5.CT De-Registration.pdf` | `corporate_tax` | `general` |
| `Purchase of Commercial Property - General.docx` | `commercial` | (was correct, guard test) |
| `FTA_VAT_Profit_Margin_Scheme_Clarification.pdf` (numbered series) | `vat` | `general` |

Also test that existing correct classifications are not broken (regression tests for ~20 known-correct filenames).

---

## Files to Modify

| File | Layer | Change |
|---|---|---|
| `backend/core/rag_engine.py` | A | Fix `_infer_domain_from_name()` keywords |
| `backend/api/chat.py` | B | Harden cross-domain guard (streaming + non-streaming) |
| `backend/scripts/retag_vector_store.py` | C | New file — bulk re-tag script |
| `backend/tests/test_domain_classifier.py` | D | New file — unit tests for classifier |

---

## Success Criteria

1. `_infer_domain_from_name("17. Free Zone Persons 20052024.pdf")` returns `"corporate_tax"` ✓
2. `_infer_domain_from_name("VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf")` returns `"vat"` ✓
3. `_infer_domain_from_name("Purchase of Commercial Property - General.docx")` still returns `"commercial"` ✓
4. CT query "tell me corporate tax" — if CT docs are ingested, CT sources are returned (no VAT bleed)
5. Cross-domain guard: even if CT-tagged docs are unavailable, broad fallback results are cleared before being returned
6. `retag_vector_store.py --dry-run` correctly identifies all misclassified chunks and proposed re-tags
7. All existing backend tests continue to pass

---

## Out of Scope

- Changing the domain detection order (`e_invoicing → corporate_tax → labour → commercial → ifrs → vat → general`)
- Adding new domains
- Changing `_BROAD_FALLBACK_THRESHOLD` or `_DOMAIN_FILTER_MIN_CONFIDENCE`
- Re-ingesting documents (separate operational task)
