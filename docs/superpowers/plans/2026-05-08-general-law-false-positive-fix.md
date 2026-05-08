# General-Law False-Positive Source Suppression Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop VAT/finance-domain documents from appearing as sources for `general_law`/`general` classification queries by adding a per-result domain-aware filter in both streaming and non-streaming RAG paths.

**Architecture:** Extract the inline suppression logic in `chat.py` into a pure helper function `_filter_general_law_results()`. Add two new constants: a higher threshold (`0.55`) that strips finance-domain results specifically, and raise the existing overall floor from `0.35` → `0.40`. Both streaming (line ~695) and non-streaming (line ~1135) call sites are replaced with the helper. Write failing tests first (TDD).

**Tech Stack:** Python 3.11, FastAPI, pytest/asyncio, ChromaDB, SQLite (SQLAlchemy async)

---

## Root Cause

Query: *"tell me about UAE law on case of late payment for rent"* → classified as `general_law` → no ChromaDB domain filter applied → broad vector search → VAT real-estate docs (scores **0.418–0.441**) pass through the existing `_GENERAL_LAW_MIN_RELEVANCE_SCORE = 0.35` threshold → 15 wrong finance sources displayed.

Query: *"what are the fines and penalties for this?"* (follow-up) → same issue; `VATP035 Electronic Devices.pdf` appears 5× at score **0.390–0.394**.

Current suppression: "if TOP result < 0.35 → clear all". Fix: add per-result filter: finance-domain results below 0.55 are always stripped, then raise overall floor to 0.40.

---

## File Map

| Action | Path |
|--------|------|
| **Modify** | `~/chatbot_local/Project_AccountingLegalChatbot/backend/api/chat.py` |
| **Create** | `~/chatbot_local/Project_AccountingLegalChatbot/backend/tests/test_general_law_suppression.py` |

Only these two files change.

---

### Task 1: Write Failing Tests for `_filter_general_law_results`

**Assigned model:** GPT-5.3-Codex

**Files:**
- Create: `~/chatbot_local/Project_AccountingLegalChatbot/backend/tests/test_general_law_suppression.py`

The function does not exist yet — tests must FAIL initially.

- [ ] **Step 1.1: Create the test file**

```python
# backend/tests/test_general_law_suppression.py
"""TDD tests for _filter_general_law_results — general_law false-positive suppression.

Tests written BEFORE the implementation exists (TDD).
The function lives at backend.api.chat._filter_general_law_results.
"""
import pytest
from api.chat import _filter_general_law_results


def _make_result(domain: str, score: float) -> dict:
    """Helper — build a minimal RAG result dict."""
    return {"source": f"{domain}_doc.pdf", "domain": domain, "score": score, "combined_score": score}


# ── Finance domain stripping ──────────────────────────────────────────────────

def test_vat_result_below_finance_threshold_is_stripped():
    """VAT doc at 0.441 (below 0.55 finance threshold) must be removed."""
    results = [_make_result("vat", 0.441)]
    assert _filter_general_law_results(results) == []


def test_corporate_tax_result_below_finance_threshold_is_stripped():
    results = [_make_result("corporate_tax", 0.430)]
    assert _filter_general_law_results(results) == []


def test_ifrs_result_below_finance_threshold_is_stripped():
    results = [_make_result("ifrs", 0.418)]
    assert _filter_general_law_results(results) == []


def test_e_invoicing_result_below_finance_threshold_is_stripped():
    results = [_make_result("e_invoicing", 0.440)]
    assert _filter_general_law_results(results) == []


def test_all_15_vat_results_stripped_real_q1_scores():
    """Reproduces Q1 scenario: 15 VAT docs at 0.418–0.441 → all stripped."""
    results = [_make_result("vat", s) for s in [0.441, 0.438, 0.435, 0.431, 0.428,
                                                  0.425, 0.422, 0.420, 0.419, 0.418,
                                                  0.418, 0.418, 0.418, 0.418, 0.418]]
    assert _filter_general_law_results(results) == []


def test_all_15_vat_results_stripped_real_q2_scores():
    """Reproduces Q2 scenario: VAT/commercial docs at 0.390–0.394 → all stripped."""
    results = (
        [_make_result("vat", s) for s in [0.394, 0.393, 0.392, 0.391, 0.390]] +
        [_make_result("corporate_tax", 0.392)] +
        [_make_result("commercial", s) for s in [0.392, 0.391, 0.390]]
    )
    assert _filter_general_law_results(results) == []


# ── Finance domain kept when genuinely relevant (high score) ─────────────────

def test_vat_result_above_finance_threshold_is_kept():
    """VAT doc at 0.60 (above 0.55) should be kept — genuinely relevant."""
    r = _make_result("vat", 0.60)
    assert _filter_general_law_results([r]) == [r]


def test_corporate_tax_result_at_0_55_boundary_is_kept():
    """Exact boundary: score == 0.55 should be KEPT (not stripped)."""
    r = _make_result("corporate_tax", 0.55)
    result = _filter_general_law_results([r])
    assert result == [r]


def test_ifrs_result_above_finance_threshold_is_kept():
    r = _make_result("ifrs", 0.70)
    assert _filter_general_law_results([r]) == [r]


# ── Non-finance domains — lower threshold applies ────────────────────────────

def test_labour_result_above_overall_minimum_is_kept():
    """Labour doc at 0.42 → NOT a finance domain → passes finance filter; 0.42 > 0.40 overall min → kept."""
    r = _make_result("labour", 0.42)
    assert _filter_general_law_results([r]) == [r]


def test_commercial_result_above_overall_minimum_is_kept():
    r = _make_result("commercial", 0.45)
    assert _filter_general_law_results([r]) == [r]


def test_general_result_above_overall_minimum_is_kept():
    r = _make_result("general", 0.50)
    assert _filter_general_law_results([r]) == [r]


def test_non_finance_result_below_overall_minimum_is_stripped():
    """Labour doc at 0.35 → below raised overall minimum (0.40) → stripped."""
    results = [_make_result("labour", 0.35)]
    assert _filter_general_law_results(results) == []


def test_non_finance_result_at_exact_overall_minimum_boundary():
    """Score == 0.40 is KEPT (not below minimum)."""
    r = _make_result("commercial", 0.40)
    assert _filter_general_law_results([r]) == [r]


# ── Mixed results ─────────────────────────────────────────────────────────────

def test_mixed_finance_and_law_results_strips_only_finance_false_positives():
    """Finance at 0.44 stripped; labour at 0.50 kept."""
    vat = _make_result("vat", 0.44)
    labour = _make_result("labour", 0.50)
    result = _filter_general_law_results([vat, labour])
    assert result == [labour]


def test_mixed_high_finance_and_law_results_keeps_both():
    """Finance at 0.60 (above finance threshold) and labour at 0.50 both kept."""
    vat = _make_result("vat", 0.60)
    labour = _make_result("labour", 0.50)
    result = _filter_general_law_results([vat, labour])
    assert vat in result
    assert labour in result


def test_result_order_preserved_after_filtering():
    """The order of kept results must not change."""
    a = _make_result("labour", 0.55)
    b = _make_result("commercial", 0.50)
    c = _make_result("general", 0.45)
    result = _filter_general_law_results([a, b, c])
    assert result == [a, b, c]


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_input_returns_empty():
    assert _filter_general_law_results([]) == []


def test_result_with_only_score_key_not_combined_score():
    """Handles results with 'score' instead of 'combined_score'."""
    r = {"source": "law.pdf", "domain": "labour", "score": 0.50}
    assert _filter_general_law_results([r]) == [r]


def test_result_with_missing_domain_is_kept():
    """Result with no 'domain' key is not in finance set → not stripped by finance filter."""
    r = {"source": "unknown.pdf", "score": 0.45}
    assert _filter_general_law_results([r]) == [r]


def test_result_with_missing_domain_below_overall_minimum_is_stripped():
    """Result with no domain and score 0.38 → below overall min 0.40 → stripped."""
    r = {"source": "unknown.pdf", "score": 0.38}
    assert _filter_general_law_results([r]) == []


def test_finance_result_exactly_at_finance_threshold_is_kept():
    """VAT at exactly 0.55 is NOT stripped (not below threshold)."""
    r = _make_result("vat", 0.55)
    assert _filter_general_law_results([r]) == [r]


def test_all_stripped_returns_empty_list_not_none():
    results = [_make_result("vat", 0.30)]
    out = _filter_general_law_results(results)
    assert out == []
    assert out is not None
```

- [ ] **Step 1.2: Run tests to confirm they ALL FAIL (function doesn't exist yet)**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_general_law_suppression.py -v 2>&1 | head -40
```

Expected: `ImportError: cannot import name '_filter_general_law_results' from 'api.chat'`
or `AttributeError`. All 22 tests must fail — if any pass, the function already partially exists and tests need updating.

---

### Task 2: Implement `_filter_general_law_results` and Update Both Call Sites

**Assigned model:** Claude Opus 4.7

**Files:**
- Modify: `~/chatbot_local/Project_AccountingLegalChatbot/backend/api/chat.py`

- [ ] **Step 2.1: Add two new constants after line 71 (`_GENERAL_LAW_MIN_RELEVANCE_SCORE`)**

Current lines 67–71:
```python
# Minimum relevance score for general_law/general queries (no domain filter applied).
# Below this, finance-corpus results are likely false positives — e.g., VAT real-estate
# docs scoring ~0.69 on "draft wills for estate" because "estate/properties" match.
# Suppressing them lets the LLM answer from general legal knowledge instead.
_GENERAL_LAW_MIN_RELEVANCE_SCORE: float = 0.35  # law docs score 0.40-0.57 combined; 0.35 allows genuine results through while blocking truly irrelevant results
```

Replace with:
```python
# Minimum relevance score for general_law/general queries (no domain filter applied).
# Below this, all remaining results are treated as false positives and cleared so the
# LLM answers from general legal knowledge.
# Raised from 0.35 → 0.40: VAT/commercial false-positives for tenancy queries score
# 0.390-0.441, which are now stripped by the per-result finance filter first; the 0.40
# floor then catches any non-finance stragglers that are also irrelevant.
_GENERAL_LAW_MIN_RELEVANCE_SCORE: float = 0.40

# Finance-domain results for general_law queries must score at least this to be kept.
# VAT real-estate docs scoring 0.41-0.44 on tenancy-law questions are false positives.
# A genuine finance answer to a legal question (e.g., "What VAT applies to rent?")
# scores 0.55+ and is correctly allowed through.
_GENERAL_LAW_FINANCE_THRESHOLD: float = 0.55

# Domains considered finance-only for the purpose of general_law suppression.
_FINANCE_ONLY_DOMAINS: frozenset[str] = frozenset({"vat", "corporate_tax", "e_invoicing", "ifrs"})
```

- [ ] **Step 2.2: Add the helper function just before `_build_rag_domain_filter` (around line 86)**

Insert this function between `_FINANCE_ONLY_DOMAINS` definition and `_build_rag_domain_filter`:

```python
def _filter_general_law_results(
    results: list[dict],
    *,
    finance_domains: frozenset[str] = _FINANCE_ONLY_DOMAINS,
    finance_threshold: float = _GENERAL_LAW_FINANCE_THRESHOLD,
    min_relevance: float = _GENERAL_LAW_MIN_RELEVANCE_SCORE,
) -> list[dict]:
    """Filter RAG results for general_law / general domain queries.

    Two-stage:
    1. Strip finance-domain results scoring below *finance_threshold* (0.55).
       These are false positives — e.g., VAT real-estate docs scoring 0.41-0.44
       on tenancy-law queries because of "rent/estate/property" lexical overlap.
    2. If the highest-scoring remaining result is below *min_relevance* (0.40),
       clear everything so the LLM answers from general legal knowledge.
    """
    def _score(r: dict) -> float:
        return r.get("combined_score", r.get("score", 0.0))

    # Stage 1: strip finance false-positives
    filtered = [
        r for r in results
        if not (r.get("domain") in finance_domains and _score(r) < finance_threshold)
    ]

    # Stage 2: overall floor — if nothing meaningful remains, clear all
    if filtered and max(_score(r) for r in filtered) < min_relevance:
        return []

    return filtered
```

- [ ] **Step 2.3: Replace the streaming suppression block (lines ~695–709)**

Locate the streaming suppression block — it looks like:
```python
                # ------ general_law false-positive suppression ------
                # When domain=general_law the filter has no domain clause, so finance-corpus
                # docs (VAT real-estate, etc.) can score ~0.40-0.41 on legal queries simply
                # because of overlapping words like "estate/properties/million".
                # Law docs (post re-ingest) score 0.40-0.57 combined_score and rank #1 above
                # finance false-positives; threshold 0.35 lets genuine law results through
                # while still suppressing truly irrelevant results (score < 0.35).
                # If every result is below _GENERAL_LAW_MIN_RELEVANCE_SCORE we treat them
                # as false positives and clear them so the LLM answers from general knowledge.
                if (
                    not _doc_scoped
                    and not _domain_filter_applied
                    and _cls.domain.value in ("general_law", "general")
                    and _search_results
                ):
                    _gl_top = max((r.get("combined_score", r.get("score", 0)) for r in _search_results), default=0.0)
                    if _gl_top < _GENERAL_LAW_MIN_RELEVANCE_SCORE:
                        logger.info(
                            f"Suppressing {len(_search_results)} low-relevance finance sources "
                            f"for {_cls.domain.value} query (top score {_gl_top:.2f} < "
                            f"{_GENERAL_LAW_MIN_RELEVANCE_SCORE})"
                        )
                        _search_results = []
                # ------ end suppression ------
```

Replace with:
```python
                # ------ general_law false-positive suppression ------
                if (
                    not _doc_scoped
                    and not _domain_filter_applied
                    and _cls.domain.value in ("general_law", "general")
                    and _search_results
                ):
                    _before = len(_search_results)
                    _search_results = _filter_general_law_results(_search_results)
                    if len(_search_results) < _before:
                        logger.info(
                            "general_law suppression (stream): %d → %d results for domain=%s",
                            _before, len(_search_results), _cls.domain.value,
                        )
                # ------ end suppression ------
```

- [ ] **Step 2.4: Replace the non-streaming suppression block (lines ~1133–1149)**

Locate:
```python
        # ------ general_law false-positive suppression ------
        # Same logic as streaming path — see comment there for rationale.
        if (
            not _doc_scoped_ns
            and not _domain_filter_applied
            and classifier_result.domain.value in ("general_law", "general")
            and search_results
        ):
            _gl_top = max((r.get("combined_score", r.get("score", 0)) for r in search_results), default=0.0)
            if _gl_top < _GENERAL_LAW_MIN_RELEVANCE_SCORE:
                logger.info(
                    f"Suppressing {len(search_results)} low-relevance finance sources "
                    f"for {classifier_result.domain.value} query (top score {_gl_top:.2f} < "
                    f"{_GENERAL_LAW_MIN_RELEVANCE_SCORE})"
                )
                search_results = []
        # ------ end suppression ------
```

Replace with:
```python
        # ------ general_law false-positive suppression ------
        if (
            not _doc_scoped_ns
            and not _domain_filter_applied
            and classifier_result.domain.value in ("general_law", "general")
            and search_results
        ):
            _before_ns = len(search_results)
            search_results = _filter_general_law_results(search_results)
            if len(search_results) < _before_ns:
                logger.info(
                    "general_law suppression (non-stream): %d → %d results for domain=%s",
                    _before_ns, len(search_results), classifier_result.domain.value,
                )
        # ------ end suppression ------
```

- [ ] **Step 2.5: Run the 22 failing tests — they must ALL PASS now**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_general_law_suppression.py -v
```

Expected output: `22 passed` — zero failures, zero errors.

- [ ] **Step 2.6: Run the full test suite to check for regressions**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all previously passing tests still pass. If any test fails, investigate and fix before proceeding.

- [ ] **Step 2.7: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/api/chat.py backend/tests/test_general_law_suppression.py
git commit -m "fix: strip finance-domain false positives for general_law RAG queries

- Add _filter_general_law_results() pure helper — two-stage filter:
  1. Finance-domain results (vat/ct/ifrs/e-invoicing) below 0.55 stripped
  2. Remaining results with top score < 0.40 cleared (floor raised from 0.35)
- Replace inline suppression in streaming + non-streaming paths with helper
- 22 new TDD tests in test_general_law_suppression.py (all passing)

Fixes: 'tell me about UAE law on late payment for rent' returning 15 VAT docs
Fixes: follow-up 'fines and penalties' returning VATP035 Electronic Devices 5×

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Integration Verification — Live Query Test

**Assigned model:** GPT-5.5

**Files:** No code changes — read-only verification.

- [ ] **Step 3.1: Confirm backend is running**

```bash
curl -s http://localhost:8002/health | python3 -m json.tool
```

Expected: `{"status": "ok", ...}` with HTTP 200. If not running:
```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
./start-dev.sh &
sleep 5
curl -s http://localhost:8002/health
```

- [ ] **Step 3.2: Create a fresh conversation**

```bash
CONV=$(curl -s -X POST http://localhost:8002/api/chat/conversations \
  -H "Content-Type: application/json" \
  -d '{"title":"Integration Test - UAE Tenancy Law"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Conversation ID: $CONV"
```

Expected: UUID printed.

- [ ] **Step 3.3: Send Q1 and capture the response**

```bash
curl -s -X POST http://localhost:8002/api/chat/send \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\": \"$CONV\", \"message\": \"tell me about UAE law on case of late payment for rent\", \"stream\": false}" \
  | python3 -m json.tool | head -60
```

Expected output:
- The LLM response discusses UAE tenancy law concepts from general knowledge
- Sources array is **empty (`[]`)** OR contains only labour/commercial/general domain docs — NO vat/corporate_tax/ifrs documents

- [ ] **Step 3.4: Check sources explicitly**

```bash
curl -s "http://localhost:8002/api/chat/conversations/$CONV/messages" \
  | python3 -c "
import sys, json
msgs = json.load(sys.stdin)
for m in msgs:
    if m.get('role') == 'assistant' and m.get('sources'):
        print('Sources found:')
        for s in m['sources']:
            print(f\"  domain={s.get('domain','?')} score={s.get('score','?'):.3f} file={s.get('source','?')}\")
    elif m.get('role') == 'assistant':
        print('No sources (expected for general_law with no law docs in KB)')
"
```

**PASS criteria:** Zero finance-domain sources (vat, corporate_tax, ifrs, e_invoicing) in the output.

- [ ] **Step 3.5: Send Q2 (follow-up fines/penalties question)**

```bash
curl -s -X POST http://localhost:8002/api/chat/send \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\": \"$CONV\", \"message\": \"what are the fines and penalties for this?\", \"stream\": false}" \
  | python3 -m json.tool | head -40
```

Check sources again with the Step 3.4 command. Expected: **no VATP035 Electronic Devices** source, no VAT docs.

- [ ] **Step 3.6: Verify a legitimate finance query still returns finance sources**

Create a new conversation and ask a VAT question — confirm finance sources ARE returned for on-domain queries:

```bash
CONV2=$(curl -s -X POST http://localhost:8002/api/chat/conversations \
  -H "Content-Type: application/json" \
  -d '{"title":"Integration Test - VAT Sanity Check"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST http://localhost:8002/api/chat/send \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\": \"$CONV2\", \"message\": \"what is the VAT rate on commercial real estate rent in UAE?\", \"stream\": false}" \
  | python3 -m json.tool | head -40
```

**PASS criteria:** Response includes VAT real-estate sources (confirms the finance filter did not break on-domain VAT queries — because VAT queries use `domain=vat` filter, not `domain=general_law`, so `_filter_general_law_results` is never called).

- [ ] **Step 3.7: Push to GitHub**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git push origin main
```

Expected: `main -> main` pushed successfully.

- [ ] **Step 3.8: Update PROJECT_JOURNAL.md**

Append to `/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/PROJECT_JOURNAL.md`:

```markdown
### Session: 2026-05-08 — General-Law False-Positive RAG Fix

**Problem:** "tell me about UAE law on late payment for rent" returned 15 VAT real-estate docs as sources. Follow-up "fines and penalties" returned VATP035 Electronic Devices 5×.

**Root cause:** `_GENERAL_LAW_MIN_RELEVANCE_SCORE = 0.35` used only an all-or-nothing top-score check. VAT docs scoring 0.418–0.441 on tenancy queries passed through undetected.

**Fix:** Added `_filter_general_law_results()` helper in `chat.py`:
1. Strips finance-domain (vat/ct/ifrs/e-invoicing) results below 0.55
2. Raises overall floor from 0.35 → 0.40 for remaining results
Both streaming and non-streaming paths updated.

**Tests:** 22 new TDD tests in `test_general_law_suppression.py` (all green).
**Verification:** Q1 and Q2 return zero finance sources. VAT on-domain query unaffected.
```

Then commit:
```bash
cd "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
git add PROJECT_JOURNAL.md "docs/superpowers/plans/2026-05-08-general-law-false-positive-fix.md"
git commit -m "docs: journal + plan for general_law false-positive fix

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Self-Review Checklist

✅ **Spec coverage:**
- Q1 wrong sources (VAT at 0.418–0.441) → Task 2 stage-1 finance filter strips them
- Q2 wrong sources (VAT+commercial at 0.390–0.394) → stage-1 strips VAT; stage-2 strips commercial at 0.392 < 0.40 floor
- VAT on-domain queries unaffected → `_filter_general_law_results` only called for `general_law`/`general` domains (Task 3.6 verifies)
- Both streaming and non-streaming paths → Task 2.3 and 2.4
- TDD → Task 1 written before Task 2

✅ **Placeholder scan:** No TBDs, no "add appropriate logic". All code blocks complete.

✅ **Type consistency:** `_filter_general_law_results(results: list[dict]) -> list[dict]` consistent across Task 1 (import) and Task 2 (definition).

✅ **Score semantics:** `_score(r)` helper prefers `combined_score`, falls back to `score` — matches existing code pattern in both suppression blocks.
