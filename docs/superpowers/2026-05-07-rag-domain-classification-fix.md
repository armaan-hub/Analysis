# RAG Domain Classification Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `_infer_domain_from_name()` keyword misclassifications, harden the cross-domain contamination guard, and provide a bulk re-tag script so CT/VAT documents route to correct domains and never contaminate unrelated query results.

**Architecture:** Four independent tasks: (1) write failing tests first (TDD), (2) fix the classifier keywords to make tests pass, (3) add unconditional post-search domain validation to the streaming + non-streaming RAG paths in `chat.py`, (4) create a `retag_domain.py` script for re-tagging existing ChromaDB chunks.

**Tech Stack:** Python 3.11, pytest / pytest-asyncio, ChromaDB (chromadb SDK), SQLAlchemy async, FastAPI (backend), existing `_infer_domain_from_name()` in `backend/core/rag_engine.py`.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| **Create** | `backend/tests/test_infer_domain_from_name.py` | Unit tests for the filename classifier (TDD) |
| **Modify** | `backend/core/rag_engine.py` lines 162–196 | Fix keyword lists in `_infer_domain_from_name()` |
| **Modify** | `backend/api/chat.py` lines 652–682 (streaming guard) | Add unconditional post-search domain validation |
| **Modify** | `backend/api/chat.py` lines 1100–1128 (non-streaming guard) | Same validation for non-streaming path |
| **Create** | `backend/retag_domain.py` | Bulk re-tag ChromaDB chunks with corrected `domain` metadata |

---

## Task 1 — Write Failing Tests for `_infer_domain_from_name`

> **Dispatcher note:** Use **Claude Opus 4.7** for this task (reasoning-heavy test design).

**Files:**
- Create: `backend/tests/test_infer_domain_from_name.py`

- [ ] **Step 1.1: Create the test file with all misclassification cases**

```python
# backend/tests/test_infer_domain_from_name.py
"""
TDD tests for _infer_domain_from_name() in core/rag_engine.py.

These tests MUST FAIL before the keyword fixes in Task 2 are applied,
and MUST PASS after. Regression tests ensure existing correct classifications
are not broken.
"""
import pytest
from core.rag_engine import _infer_domain_from_name


# ── Previously misclassified: commercial → corporate_tax ──────────────────────

def test_free_zone_persons_numbered_is_ct():
    """'17. Free Zone Persons 20052024.pdf' was tagged commercial; must be CT."""
    assert _infer_domain_from_name("17. Free Zone Persons 20052024.pdf") == "corporate_tax"


def test_free_zone_person_english_is_ct():
    """'1- Free Zone Person-English.pdf' was tagged commercial; must be CT."""
    assert _infer_domain_from_name("1- Free Zone Person-English.pdf") == "corporate_tax"


def test_fta_release_guide_free_zone_entities_is_ct():
    """'FTA_Release_Guide_on_Free_Zone_Entities_1716532174.pdf' was tagged commercial; must be CT."""
    assert _infer_domain_from_name("FTA_Release_Guide_on_Free_Zone_Entities_1716532174.pdf") == "corporate_tax"


# ── Previously misclassified: commercial → vat ────────────────────────────────

def test_vat_treatment_free_zone_mainland_is_vat():
    """'VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf' was commercial; must be vat."""
    assert _infer_domain_from_name(
        "VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf"
    ) == "vat"


# ── Previously misclassified: general → corporate_tax ─────────────────────────

def test_charities_guide_is_ct():
    """'20. Charities.pdf' (CT Guide #20) was tagged general; must be CT."""
    assert _infer_domain_from_name("20. Charities.pdf") == "corporate_tax"


def test_qualifying_activities_139_2023_is_ct():
    """Cabinet Decision 139-2023 on Qualifying Activities must be CT."""
    assert _infer_domain_from_name(
        "139-2023 Qualifying Activities and Excluded Activities.pdf"
    ) == "corporate_tax"


def test_qualifying_activities_229_2025_is_ct():
    """Cabinet Decision 229-2025 on Qualifying Activities must be CT."""
    assert _infer_domain_from_name(
        "229-of-2025-Qualifying-Activities-and-Excluded-Activities-EN.pdf"
    ) == "corporate_tax"


def test_qualifying_activities_265_is_ct():
    """Cabinet Decision 265 on Qualifying Activities must be CT."""
    assert _infer_domain_from_name("265 Qualifying Activities.pdf") == "corporate_tax"


def test_ct_amend_registration_is_ct():
    """'1.CT Amend Registration.pdf' was tagged general; must be CT."""
    assert _infer_domain_from_name("1.CT Amend Registration.pdf") == "corporate_tax"


def test_ct_deregistration_is_ct():
    """'5.CT De-Registration.pdf' was tagged general; must be CT."""
    assert _infer_domain_from_name("5.CT De-Registration.pdf") == "corporate_tax"


# ── New VAT keywords ──────────────────────────────────────────────────────────

def test_profit_margin_scheme_is_vat():
    """FTA VAT clarification on Profit Margin Scheme must be vat."""
    assert _infer_domain_from_name(
        "Public Clarification - Profit Margin Scheme.pdf"
    ) == "vat"


def test_togc_is_vat():
    """Transfer of Going Concern clarification must be vat."""
    assert _infer_domain_from_name(
        "FTA Public Clarification TOGC.pdf"
    ) == "vat"


def test_public_transportation_is_vat():
    """FTA clarification on public transportation must be vat."""
    assert _infer_domain_from_name(
        "VAT Public Clarification Public Transportation.pdf"
    ) == "vat"


def test_farms_is_vat():
    """FTA clarification on farms must be vat."""
    assert _infer_domain_from_name("FTA Clarification on Farms.pdf") == "vat"


def test_disbursements_is_vat():
    """FTA VAT disbursements clarification must be vat."""
    assert _infer_domain_from_name(
        "VAT Public Clarification - Disbursements and Reimbursements.pdf"
    ) == "vat"


def test_dubai_owners_association_is_vat():
    """FTA clarification on Dubai owners association must be vat."""
    assert _infer_domain_from_name(
        "FTA Clarification Dubai Owners Association.pdf"
    ) == "vat"


def test_manpower_vs_visa_is_vat():
    """FTA clarification on manpower vs visa must be vat."""
    assert _infer_domain_from_name(
        "FTA Clarification Manpower vs Visa Services.pdf"
    ) == "vat"


# ── Regression: correct classifications must not break ────────────────────────

def test_purchase_of_commercial_property_is_vat():
    """'Purchase of Commercial Property - General.docx' → vat (via 'property' keyword in VAT block).
    'commercial compan' is NOT a substring of 'commercial property', so commercial block doesn't match.
    'property' IS in the VAT block, so it correctly classifies as vat."""
    result = _infer_domain_from_name("Purchase of Commercial Property - General.docx")
    assert result == "vat"


def test_corporate_tax_guide_is_ct():
    """Files with 'corporate tax' in name must be CT."""
    assert _infer_domain_from_name("UAE Corporate Tax Guide 2023.pdf") == "corporate_tax"


def test_small_business_relief_is_ct():
    """Small Business Relief guide must be CT."""
    assert _infer_domain_from_name("Small Business Relief - CT Guide.pdf") == "corporate_tax"


def test_vat_federal_decree_is_vat():
    """Federal Decree Law No 8 of 2017 (VAT law) must be vat."""
    assert _infer_domain_from_name("Federal Decree Law No 8 of 2017.pdf") == "vat"


def test_peppol_is_e_invoicing():
    """Peppol implementation guide must be e_invoicing."""
    assert _infer_domain_from_name("Peppol UAE Implementation Guide.pdf") == "e_invoicing"


def test_labour_law_is_labour():
    """Labour law files must be labour."""
    assert _infer_domain_from_name("UAE Labour Law Federal Decree.pdf") == "labour"


def test_rakez_freezone_is_commercial():
    """RAKEZ documents must remain commercial (location-specific keyword preserved)."""
    assert _infer_domain_from_name("RAKEZ Business Setup Guide.pdf") == "commercial"


def test_dubai_south_is_commercial():
    """Dubai South documents must remain commercial."""
    assert _infer_domain_from_name("Dubai South Free Zone Company Formation.pdf") == "commercial"


def test_hamriyah_is_commercial():
    """Hamriyah Free Zone documents must remain commercial."""
    assert _infer_domain_from_name("Hamriyah Free Zone Business Registration.pdf") == "commercial"


def test_audit_report_is_ifrs():
    """Audit report files must be ifrs."""
    assert _infer_domain_from_name("Signed Audit Report FY2024.pdf") == "ifrs"


def test_unknown_doc_falls_to_general():
    """Unrecognised filenames must fall through to general."""
    assert _infer_domain_from_name("random-document-xyz.pdf") == "general"


def test_hyphen_normalisation_ct():
    """Hyphens are normalised to spaces before matching."""
    assert _infer_domain_from_name("Free-Zone-Person-Guide.pdf") == "corporate_tax"


def test_underscore_normalisation_ct():
    """Underscores are normalised to spaces before matching."""
    assert _infer_domain_from_name("Free_Zone_Person_Guide.pdf") == "corporate_tax"
```

- [ ] **Step 1.2: Run the tests and confirm they FAIL as expected**

Run from `backend/` directory using the venv:

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
pytest tests/test_infer_domain_from_name.py -v 2>&1 | head -80
```

Expected: Multiple FAILED results, specifically:
- `test_free_zone_persons_numbered_is_ct` → FAILED (currently returns `commercial`)
- `test_free_zone_person_english_is_ct` → FAILED (currently returns `commercial`)
- `test_fta_release_guide_free_zone_entities_is_ct` → FAILED (currently returns `commercial`)
- `test_vat_treatment_free_zone_mainland_is_vat` → FAILED (currently returns `commercial`)
- `test_charities_guide_is_ct` → FAILED (currently returns `general`)
- All `qualifying_activities` tests → FAILED (currently return `general`)
- `test_ct_amend_registration_is_ct` → FAILED (currently returns `general`)
- `test_ct_deregistration_is_ct` → FAILED (currently returns `general`)
- Regression tests should PASS

**Do NOT proceed to Task 2 until you see these failures.**

- [ ] **Step 1.3: Commit the failing tests**

```bash
git add tests/test_infer_domain_from_name.py
git commit -m "test: add failing TDD tests for _infer_domain_from_name misclassifications

Tests cover 10 confirmed misclassified filenames (commercial→CT, commercial→VAT,
general→CT) and regression tests for ~15 correct classifications.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2 — Fix `_infer_domain_from_name` Keywords

> **Dispatcher note:** Use **GPT-5.3-Codex** for this task (precise keyword editing).

**Files:**
- Modify: `backend/core/rag_engine.py` lines 162–216

- [ ] **Step 2.1: Open rag_engine.py and locate the CT keyword block (lines 162–184)**

The current CT block is:
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
]):
    return "corporate_tax"
```

Replace it with (adds 9 new keywords — add at end of list before closing bracket):

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
    # Free Zone Person/Entity CT guides — must be BEFORE commercial block's "free zone"
    "free zone person", "free zone entit", "ctgfzp",
    # Cabinet Decisions on CT Qualifying/Excluded Activities
    "qualifying activities", "excluded activities",
    # CT-specific guides that default to general without these keywords
    "charit",           # CT Guide #20: Charities
    "ct amend",         # CT Amendment Registration form/guide
    "ct de registr",    # CT De-Registration guide (hyphen normalised to space)
]):
    return "corporate_tax"
```

- [ ] **Step 2.2: Fix the commercial block — remove bare `"free zone"` (lines 190–196)**

Current commercial block:
```python
# Commercial / Company Law / Business Registration
if any(kw in n for kw in [
    "commercial compan", "licensing", "rakez", "free zone", "dwc",
    "hamriyah", "dubai south", "rak free",
    "list of activities", "activities description",
]):
    return "commercial"
```

Replace with (removes bare `"free zone"`, location-specific keywords preserved):
```python
# Commercial / Company Law / Business Registration
# NOTE: bare "free zone" removed — CT Free Zone Person/Entity guides must reach
# the CT block above. Location-specific FZ keywords (rakez, dwc, etc.) still catch
# commercial FZ documents.
if any(kw in n for kw in [
    "commercial compan", "licensing", "rakez", "dwc",
    "hamriyah", "dubai south", "rak free",
    "list of activities", "activities description",
]):
    return "commercial"
```

- [ ] **Step 2.3: Add keywords to the VAT block (lines 205–216)**

Current VAT block:
```python
# VAT — broad bucket; check AFTER CT so CT docs don't fall here
if any(kw in n for kw in [
    "vat", "vatp", "tax invoice", "real estate", "property",
    "reverse charge", "refund", "electronic device", "gold",
    "zero rating", "input tax", "output tax", "excise",
    "no 8 of 2017",    # VAT Federal Decree Law No 8 of 2017
    "executive regulation of federal decree",  # VAT exec regulation
    "convert tin", " trn",   # TRN conversion guides
    "e services",            # FTA e-services VAT portal
    "tax procedures",        # Tax Procedures law/regulation
]):
    return "vat"
```

Replace with (adds 10 new VAT keywords):
```python
# VAT — broad bucket; check AFTER CT so CT docs don't fall here
if any(kw in n for kw in [
    "vat", "vatp", "tax invoice", "real estate", "property",
    "reverse charge", "refund", "electronic device", "gold",
    "zero rating", "input tax", "output tax", "excise",
    "no 8 of 2017",    # VAT Federal Decree Law No 8 of 2017
    "executive regulation of federal decree",  # VAT exec regulation
    "convert tin", " trn",   # TRN conversion guides
    "e services",            # FTA e-services VAT portal
    "tax procedures",        # Tax Procedures law/regulation
    # FTA Public Clarifications (numbered 01–43 series) with no VAT keyword in filename
    "profit margin scheme",   # FTA VAT clarification: Profit Margin Scheme
    "togc",                   # Transfer of Going Concern
    "public transportation",  # FTA VAT clarification: Public Transportation
    "farms",                  # FTA VAT clarification: Farms
    "disbursement",           # FTA VAT clarification: Disbursements
    "reimbursement",          # FTA VAT clarification: Reimbursements
    "dubai owners association",  # FTA VAT clarification: Dubai Owners Association
    "manpower vs visa",       # FTA VAT clarification: Manpower vs Visa Services
    "e commerce vat",         # VAT on e-commerce (space-normalised from "e-commerce vat")
    "vat public clarif",      # Catch-all for numbered FTA VAT clarification series
]):
    return "vat"
```

- [ ] **Step 2.4: Run the tests and confirm they PASS**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
pytest tests/test_infer_domain_from_name.py -v
```

Expected output: All tests PASS. Full run should show something like:
```
PASSED tests/test_infer_domain_from_name.py::test_free_zone_persons_numbered_is_ct
PASSED tests/test_infer_domain_from_name.py::test_free_zone_person_english_is_ct
PASSED tests/test_infer_domain_from_name.py::test_fta_release_guide_free_zone_entities_is_ct
PASSED tests/test_infer_domain_from_name.py::test_vat_treatment_free_zone_mainland_is_vat
... (all 28+ tests green)
```

If any test fails, re-read the keyword list carefully — the issue will be in the normalization (remember: hyphens/underscores → spaces, lowercase) or a missing keyword prefix.

- [ ] **Step 2.5: Run the full existing test suite to check regressions**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
pytest tests/ -x -q --timeout=60 2>&1 | tail -30
```

Expected: All previously-passing tests still pass. If a test that was previously passing now fails, it means a keyword change broke something. Fix the specific keyword before committing.

- [ ] **Step 2.6: Commit the keyword fixes**

```bash
git add core/rag_engine.py
git commit -m "fix: correct _infer_domain_from_name keyword misclassifications

- Remove bare 'free zone' from commercial block (CT/VAT FZ guides were
  intercepted before reaching their correct domain block)
- Add 9 CT keywords: free zone person/entit, ctgfzp, qualifying/excluded
  activities, charit, ct amend, ct de registr
- Add 10 VAT keywords: profit margin scheme, togc, public transportation,
  farms, disbursement, reimbursement, dubai owners association,
  manpower vs visa, e commerce vat, vat public clarif

Fixes: 17. Free Zone Persons, 1- Free Zone Person-English,
FTA_Release_Guide_on_Free_Zone_Entities, VAT Treatment on Sale Free Zone,
20. Charities, 139-2023/229-2025/265 Qualifying Activities,
1.CT Amend Registration, 5.CT De-Registration

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3 — Harden Cross-Domain Contamination Guard in `chat.py`

> **Dispatcher note:** Use **GPT-5.5** for this task (complex async logic in large file).

**Files:**
- Modify: `backend/api/chat.py` (streaming guard ~line 652–682, non-streaming guard ~line 1100–1128)

**Context for subagent:** The file has two parallel RAG paths — streaming (around line 590–700) and non-streaming (around line 1040–1130). Each has a broad-search fallback followed by a cross-domain contamination guard. The current guard only runs when `_domain_filter_applied=True` AND `_broad_fallback_used=True`. We need to add an **unconditional** post-search validation that runs whenever `conv_domain` is a specific (non-general) domain, regardless of flag state.

- [ ] **Step 3.1: Write the new guard tests first**

Open `backend/tests/test_cross_domain_guard.py` and add two new test cases at the end of the file (do NOT replace existing tests):

```python
@pytest.mark.asyncio
async def test_guard_fires_even_without_broad_fallback_streaming(client):
    """
    Unconditional guard (belt-and-suspenders): even when broad fallback was NOT
    triggered, VAT results must not appear in a corporate_tax response.
    This covers the edge case where _domain_filter_applied was incorrectly False.
    """
    mock_llm = _make_llm_mock()
    # _hybrid_retriever.retrieve returns VAT results directly (simulates flag bug)
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("corporate_tax"))),
        patch("api.chat.get_llm_provider", return_value=mock_llm),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[_vat_result(0.72)])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "corporate tax free zone persons", "stream": True, "use_rag": True},
        )

    assert resp.status_code == 200
    for line in resp.text.split("\n"):
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:])
                if data.get("type") == "sources":
                    src_domains = {s.get("domain") for s in data.get("sources", [])}
                    assert "vat" not in src_domains, \
                        f"Unconditional guard failed: VAT leaked into CT streaming response: {data['sources']}"
            except json.JSONDecodeError:
                pass


@pytest.mark.asyncio
async def test_guard_fires_even_without_broad_fallback_non_streaming(client):
    """
    Unconditional guard (belt-and-suspenders): non-streaming path must also
    filter wrong-domain results even when broad fallback was not triggered.
    """
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("corporate_tax"))),
        patch("api.chat.get_llm_provider", return_value=_make_llm_mock()),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[_vat_result(0.72)])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "corporate tax free zone persons", "stream": False, "use_rag": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    sources = (data.get("message") or {}).get("sources") or []
    vat_sources = [s for s in sources if (s.get("metadata") or s).get("domain") == "vat"]
    assert not vat_sources, \
        f"Unconditional guard failed: VAT leaked into CT non-streaming response: {vat_sources}"
```

- [ ] **Step 3.2: Run the new tests to confirm they FAIL**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
pytest tests/test_cross_domain_guard.py::test_guard_fires_even_without_broad_fallback_streaming \
       tests/test_cross_domain_guard.py::test_guard_fires_even_without_broad_fallback_non_streaming \
       -v 2>&1 | tail -30
```

Expected: Both tests FAIL (VAT results not being filtered when broad fallback wasn't triggered).

- [ ] **Step 3.3: Add unconditional guard to the STREAMING path in chat.py**

Locate the end of the existing cross-domain contamination guard block in the streaming path (after line ~682, before the `# general_law false-positive suppression` comment). The current code ends with:

```python
                elif len(_domain_matching) < len(_search_results):
                    logger.info(
                        "Cross-domain partial filter (stream): kept %d/%d results for %s",
                        len(_domain_matching), len(_search_results), _cls.domain.value,
                    )
                    _search_results = _domain_matching
                # ------ end cross-domain guard ------
```

Immediately AFTER the `# ------ end cross-domain guard ------` comment line and BEFORE the `# ------ general_law false-positive suppression ------` line, add:

```python
                # ------ unconditional domain validation (belt-and-suspenders) ------
                # Runs regardless of _domain_filter_applied / _broad_fallback_used flags.
                # Clears any results whose domain is explicitly wrong for this conversation.
                # Allows: results with matching domain, results with no domain tag (legacy chunks).
                _conv_domain = _cls.domain.value
                if _conv_domain and _conv_domain not in {"general", "general_law"} and _search_results:
                    _expected_domains = set(_DOMAIN_TO_DOC_DOMAINS.get(_conv_domain, [_conv_domain]))
                    _UNTAGGED = {None, ""}  # legacy chunks with no domain tag — allow through
                    _validated = [
                        r for r in _search_results
                        if r.get("metadata", {}).get("domain") in _expected_domains
                        or r.get("metadata", {}).get("domain") in _UNTAGGED
                    ]
                    if len(_validated) < len(_search_results):
                        logger.info(
                            "Unconditional domain validation (stream): removed %d/%d wrong-domain results "
                            "for %s query (expected domains: %s)",
                            len(_search_results) - len(_validated),
                            len(_search_results),
                            _conv_domain,
                            _expected_domains,
                        )
                        _search_results = _validated
                # ------ end unconditional domain validation ------
```

- [ ] **Step 3.4: Add unconditional guard to the NON-STREAMING path in chat.py**

Locate the end of the existing cross-domain contamination guard block in the non-streaming path (after line ~1120, before the next comment). The current code ends with:

```python
            elif len(_domain_matching_ns) < len(search_results):
                logger.info(
                    "Cross-domain partial filter (non-stream): kept %d/%d results for %s",
                    len(_domain_matching_ns), len(search_results), classifier_result.domain.value,
                )
                search_results = _domain_matching_ns
        # ------ end cross-domain guard ------
```

Immediately AFTER the `# ------ end cross-domain guard ------` comment, add:

```python
        # ------ unconditional domain validation (belt-and-suspenders) ------
        _conv_domain_ns = classifier_result.domain.value
        if _conv_domain_ns and _conv_domain_ns not in {"general", "general_law"} and search_results:
            _expected_domains_ns = set(_DOMAIN_TO_DOC_DOMAINS.get(_conv_domain_ns, [_conv_domain_ns]))
            _UNTAGGED_NS = {None, ""}
            _validated_ns = [
                r for r in search_results
                if r.get("metadata", {}).get("domain") in _expected_domains_ns
                or r.get("metadata", {}).get("domain") in _UNTAGGED_NS
            ]
            if len(_validated_ns) < len(search_results):
                logger.info(
                    "Unconditional domain validation (non-stream): removed %d/%d wrong-domain results "
                    "for %s query (expected domains: %s)",
                    len(search_results) - len(_validated_ns),
                    len(search_results),
                    _conv_domain_ns,
                    _expected_domains_ns,
                )
                search_results = _validated_ns
        # ------ end unconditional domain validation ------
```

- [ ] **Step 3.5: Run the new guard tests — confirm they PASS**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
pytest tests/test_cross_domain_guard.py -v 2>&1 | tail -30
```

Expected: ALL 7 tests in `test_cross_domain_guard.py` PASS (5 original + 2 new).

- [ ] **Step 3.6: Run the full test suite for regressions**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
pytest tests/ -x -q --timeout=60 2>&1 | tail -30
```

Expected: All previously-passing tests still pass.

- [ ] **Step 3.7: Commit the guard hardening**

```bash
git add api/chat.py tests/test_cross_domain_guard.py
git commit -m "fix: add unconditional post-search domain validation to RAG pipeline

Belt-and-suspenders guard that runs regardless of _domain_filter_applied /
_broad_fallback_used flags. Filters results whose domain explicitly doesn't
match the conversation domain. Allows legacy chunks without domain tags.

Applied to both streaming and non-streaming paths in chat.py.
Tests verify guard fires even when broad fallback was not triggered.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4 — Bulk Re-tag Script for ChromaDB Domain Metadata

> **Dispatcher note:** Use **Claude Opus 4.7** for this task (careful migration script writing).

**Files:**
- Create: `backend/retag_domain.py`

**Context for subagent:** There is already a `backend/bulk_retag.py` that updates the `category` metadata field. This new script updates the `domain` field using the corrected `_infer_domain_from_name()`. Follow the same pattern (async SQLAlchemy, same session setup, same ChromaDB access via `rag_engine.collection`). The script needs `--dry-run` and `--apply` modes. The vector store is currently empty but the script is needed for after re-ingestion.

- [ ] **Step 4.1: Create `backend/retag_domain.py`**

```python
"""
Migration utility: retag existing ChromaDB chunks with corrected `domain` metadata.

Uses the fixed _infer_domain_from_name() to compute the correct domain for each
document, then updates all chunks belonging to that document.

Safe to re-run: chunks already correctly tagged are skipped.

Usage (run from backend/ directory):
    python retag_domain.py --dry-run   # Preview changes, no writes
    python retag_domain.py --apply     # Apply changes to ChromaDB
"""

import argparse
import asyncio
import io
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings
from db.database import Base
from db.models import Document
from core.rag_engine import rag_engine, _infer_domain_from_name

_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_engine = create_async_engine(_db_url, echo=False, future=True, connect_args={"timeout": 60})
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def main(dry_run: bool) -> None:
    mode_label = "DRY RUN" if dry_run else "APPLY"
    print(f"\n{'='*60}")
    print(f"  retag_domain.py — {mode_label}")
    print(f"{'='*60}\n")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    totals = {"retagged": 0, "skipped_correct": 0, "skipped_no_chunks": 0, "error": 0}
    changes: list[tuple[str, str, str]] = []  # (doc_name, old_domain, new_domain)

    async with _session_factory() as db:
        result = await db.execute(select(Document).where(Document.status == "indexed"))
        docs = result.scalars().all()
        print(f"Found {len(docs)} indexed documents to check.\n")

        for doc in docs:
            original_name = str(doc.original_name)
            correct_domain = _infer_domain_from_name(original_name)

            # Fetch all chunks for this document
            try:
                existing = rag_engine.collection.get(
                    where={"original_name": original_name},
                    include=["metadatas"],
                )
                if not existing or not existing["ids"]:
                    # Fallback: old chunks indexed by doc_id
                    existing = rag_engine.collection.get(
                        where={"doc_id": str(doc.id)},
                        include=["metadatas"],
                    )
            except Exception as exc:
                print(f"  ERR  (query)         {original_name}: {exc}")
                totals["error"] += 1
                continue

            if not existing or not existing["ids"]:
                print(f"  SKIP (no chunks)     {original_name}")
                totals["skipped_no_chunks"] += 1
                continue

            chunk_ids = existing["ids"]
            current_metas = existing["metadatas"] or []

            # Determine current domain (use first chunk as representative)
            current_domain = current_metas[0].get("domain", "") if current_metas else ""

            if current_domain == correct_domain:
                print(f"  OK   (already {correct_domain:<15})  {original_name}")
                totals["skipped_correct"] += 1
                continue

            # Record the change
            changes.append((original_name, current_domain or "(none)", correct_domain))
            print(
                f"  {'WOULD RETAG' if dry_run else 'RETAGGING'}"
                f"  ({len(chunk_ids):>4} chunks)  "
                f"{original_name}  "
                f"[{current_domain or '(none)'} → {correct_domain}]"
            )

            if dry_run:
                totals["retagged"] += 1
                continue

            # Apply the update
            updated_metas = []
            for m in current_metas:
                updated = dict(m)
                updated["domain"] = correct_domain
                updated_metas.append(updated)

            try:
                rag_engine.collection.update(ids=chunk_ids, metadatas=updated_metas)
                totals["retagged"] += 1
            except Exception as exc:
                print(f"  ERR  (update)        {original_name}: {exc}")
                totals["error"] += 1

    print(f"\n{'='*60}")
    print(f"  Summary ({mode_label})")
    print(f"{'='*60}")
    if changes:
        print(f"\n  Domain changes {'(would be applied)' if dry_run else 'applied'}:")
        for doc_name, old, new in changes:
            print(f"    {old:<20} → {new:<20}  {doc_name}")
    print(
        f"\n  {'would retag' if dry_run else 'retagged'}  : {totals['retagged']}\n"
        f"  already correct : {totals['skipped_correct']}\n"
        f"  no chunks       : {totals['skipped_no_chunks']}\n"
        f"  errors          : {totals['error']}\n"
    )
    if dry_run and totals["retagged"] > 0:
        print("  Re-run with --apply to commit these changes.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retag ChromaDB domain metadata using fixed classifier.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    group.add_argument("--apply", action="store_true", help="Apply domain retag to ChromaDB")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
```

- [ ] **Step 4.2: Test the script syntax and imports (vector store is empty — that's OK)**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
python retag_domain.py --dry-run 2>&1 | head -20
```

Expected output (vector store empty, so 0 chunks but no errors):
```
============================================================
  retag_domain.py — DRY RUN
============================================================

Found N indexed documents to check.
  SKIP (no chunks)     <doc names...>
  ...
============================================================
  Summary (DRY RUN)
```

If you see `ImportError` or `ModuleNotFoundError`, check that the venv is activated and that `sys.path.insert(0, ...)` is pointing to the backend root.

- [ ] **Step 4.3: Commit the retag script**

```bash
git add retag_domain.py
git commit -m "feat: add retag_domain.py script for bulk ChromaDB domain metadata fix

Iterates all indexed documents, computes correct domain via fixed
_infer_domain_from_name(), updates all chunks for misclassified docs.

--dry-run: preview changes with old→new domain summary
--apply: commit changes to ChromaDB

Follows same pattern as bulk_retag.py (which retags 'category' field).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5 — Final Verification

> **Dispatcher note:** Use **GPT-5.5** for this task (full test suite run + debugging).

**Files:** None new — verification only.

- [ ] **Step 5.1: Run full test suite**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
pytest tests/ -q --timeout=60 2>&1 | tail -40
```

Expected: All tests pass. Zero failures. If there are failures, read the error output carefully before fixing — do not guess.

- [ ] **Step 5.2: Spot-check all success criteria from the spec**

Run these spot-checks manually in Python:

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source venv_py311/bin/activate
python -c "
from core.rag_engine import _infer_domain_from_name as f
checks = [
    ('17. Free Zone Persons 20052024.pdf',                               'corporate_tax'),
    ('1- Free Zone Person-English.pdf',                                  'corporate_tax'),
    ('FTA_Release_Guide_on_Free_Zone_Entities_1716532174.pdf',           'corporate_tax'),
    ('VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf','vat'),
    ('20. Charities.pdf',                                                'corporate_tax'),
    ('139-2023 Qualifying Activities and Excluded Activities.pdf',       'corporate_tax'),
    ('RAKEZ Business Setup Guide.pdf',                                   'commercial'),
    ('Dubai South Free Zone Company Formation.pdf',                      'commercial'),
    ('Hamriyah Free Zone Business Registration.pdf',                     'commercial'),
    ('Purchase of Commercial Property - General.docx',                   'vat'),
    ('UAE Corporate Tax Guide 2023.pdf',                                 'corporate_tax'),
    ('random-document-xyz.pdf',                                          'general'),
]
all_ok = True
for name, expected in checks:
    got = f(name)
    status = '✓' if got == expected else '✗'
    if got != expected:
        all_ok = False
    print(f'  {status}  {got:<20} expected={expected:<20} | {name}')
print()
print('ALL OK' if all_ok else 'FAILURES DETECTED — see above')
"
```

Expected: All lines show `✓` and final line is `ALL OK`.

- [ ] **Step 5.3: Push to GitHub**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git push origin main
```

- [ ] **Step 5.4: Update PROJECT_JOURNAL.md**

Add a session entry under the Chronological Session Log:

```markdown
### Session: 2026-05-07 — RAG Domain Classification Fix

**Problem solved:** CT and VAT documents were misclassified at ingest time, causing broad
fallback searches to return wrong-domain sources (VAT real-estate docs appearing in CT answers).

**Root cause:** Bare `"free zone"` keyword in the `commercial` block of `_infer_domain_from_name()`
ran before the VAT block, misclassifying CT Free Zone guides and one VAT FZ guide.

**Changes:**
- `backend/core/rag_engine.py`: Removed bare `"free zone"` from commercial, added 9 CT keywords,
  10 VAT keywords
- `backend/api/chat.py`: Added unconditional post-search domain validation to both streaming and
  non-streaming RAG paths
- `backend/retag_domain.py`: New bulk re-tag script for existing ChromaDB chunks
- `backend/tests/test_infer_domain_from_name.py`: 28 TDD tests covering all misclassifications

**Verified:** All 28 new tests pass, full test suite green.
```

Then commit and push:
```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add PROJECT_JOURNAL.md
git commit -m "docs: update PROJECT_JOURNAL for RAG domain classification fix

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Quick Reference

| Task | Model | Files |
|---|---|---|
| Task 1: Write failing tests | Claude Opus 4.7 | `tests/test_infer_domain_from_name.py` (create) |
| Task 2: Fix keywords | GPT-5.3-Codex | `core/rag_engine.py` (modify) |
| Task 3: Harden guard | GPT-5.5 | `api/chat.py` + `tests/test_cross_domain_guard.py` (modify) |
| Task 4: Retag script | Claude Opus 4.7 | `retag_domain.py` (create) |
| Task 5: Verification | GPT-5.5 | No files — tests + spot-checks |
