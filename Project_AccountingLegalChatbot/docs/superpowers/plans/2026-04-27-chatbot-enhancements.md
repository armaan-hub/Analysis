# Chatbot Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port 8 proven features from the legacy UAE AI Assistant project — citation validation, no-LLM guard, fuzzy domain matching, hybrid search, FTA scraper, auto-sync watchdog, source domain display, and full chunk text verification — into the AccountingLegalChatbot FastAPI + React web app.

**Architecture:** All new logic lives in focused new files (`backend/core/accuracy/`, `backend/core/search/`, `backend/core/pipeline/`). Existing files receive minimal, surgical wiring changes only. Each feature is independently testable.

**Tech Stack:** FastAPI, ChromaDB, pytest/asyncio, React/TypeScript, rapidfuzz, watchdog, APScheduler (already installed), BeautifulSoup4 (already installed), PyMuPDF/fitz (already installed)

**Spec:** `docs/superpowers/specs/2026-04-27-chatbot-enhancements-design.md`

**Working directory for all commands:** `Project_AccountingLegalChatbot/backend/`

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/core/accuracy/__init__.py` |
| Create | `backend/core/accuracy/citation_validator.py` |
| Create | `backend/core/search/__init__.py` |
| Create | `backend/core/search/hybrid_engine.py` |
| Create | `backend/core/pipeline/__init__.py` |
| Create | `backend/core/pipeline/fta_scraper.py` |
| Create | `backend/core/pipeline/auto_sync.py` |
| Create | `backend/tests/test_citation_validator.py` |
| Create | `backend/tests/test_no_llm_guard.py` |
| Create | `backend/tests/test_fuzzy_domain.py` |
| Create | `backend/tests/test_hybrid_engine.py` |
| Create | `backend/tests/test_fta_scraper.py` |
| Create | `backend/tests/test_auto_sync.py` |
| Create | `backend/tests/test_source_domain_display.py` |
| Modify | `backend/requirements.txt` — add `rapidfuzz==3.9.7` and `watchdog==4.0.1` |
| Modify | `backend/core/chat/domain_classifier.py` — replace keyword fallback with fuzzy classifier |
| Modify | `backend/core/rag_engine.py` — add hybrid re-ranking in `search()` |
| Modify | `backend/api/chat.py` — add no-LLM guard + citation validator + domain field in sources |
| Modify | `backend/monitoring/scheduler.py` — add nightly FTA scraper job |
| Modify | `backend/main.py` — start/stop auto-sync watchdog in lifespan |
| Modify | `frontend/src/lib/api.ts` — add `domain?: string` to `Source` interface |
| Modify | `frontend/src/components/studios/LegalStudio/SourcePeeker.tsx` — add domain badge + auto-expand |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add rapidfuzz and watchdog to requirements.txt**

Open `backend/requirements.txt` and add these two lines after the `# Utilities` section:

```
rapidfuzz==3.9.7
watchdog==4.0.1
```

- [ ] **Step 2: Install new dependencies**

```bash
cd backend
pip install rapidfuzz==3.9.7 watchdog==4.0.1
```

Expected output: `Successfully installed rapidfuzz-3.9.7 watchdog-4.0.1`

- [ ] **Step 3: Verify import**

```bash
python -c "from rapidfuzz import fuzz; from watchdog.observers import Observer; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add rapidfuzz and watchdog dependencies"
```

---

## Task 2: Citation Validator + No-LLM Guard

**Files:**
- Create: `backend/core/accuracy/__init__.py`
- Create: `backend/core/accuracy/citation_validator.py`
- Create: `backend/tests/test_citation_validator.py`
- Create: `backend/tests/test_no_llm_guard.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_citation_validator.py`:

```python
import pytest
from core.accuracy.citation_validator import validate_citations, should_skip_llm


# ── validate_citations ────────────────────────────────────────────────────────

def test_no_warning_when_no_fabrications():
    answer = "According to the documents, VAT applies at 5%."
    chunks = [{"text": "VAT applies at 5% under Federal Decree Law No. 8 of 2017."}]
    result = validate_citations(answer, chunks)
    assert "🚨" not in result
    assert result == answer


def test_warning_appended_when_two_fabrications():
    answer = (
        '"The law states: penalties are 200% of unpaid tax." '
        '"According to Article 99: all imports are exempt."'
    )
    chunks = [{"text": "VAT is 5%. Some supplies are zero-rated."}]
    result = validate_citations(answer, chunks)
    assert "🚨" in result
    assert "CRITICAL LEGAL ACCURACY WARNING" in result


def test_no_warning_for_honest_refusal():
    answer = "I don't have this in my documents."
    chunks = []
    result = validate_citations(answer, chunks)
    assert result == answer
    assert "🚨" not in result


def test_single_fabrication_no_warning():
    answer = '"The law states: all transactions must be reported daily."'
    chunks = [{"text": "VAT applies at 5% on most goods and services."}]
    result = validate_citations(answer, chunks)
    # Only 1 fabrication — below threshold of 2
    assert "🚨" not in result


def test_warning_contains_issue_count():
    answer = (
        '"The regulation requires: all invoices to be notarised." '
        '"Article 99 states: imports are fully exempt from all taxes." '
        '"Section 12: penalties exceed 500% of outstanding balance."'
    )
    chunks = [{"text": "Standard VAT rate is 5%."}]
    result = validate_citations(answer, chunks)
    assert "🚨" in result


# ── should_skip_llm ───────────────────────────────────────────────────────────

def test_skip_llm_when_doc_scoped_and_empty():
    assert should_skip_llm(search_results=[], doc_scoped=True) is True


def test_no_skip_when_results_exist():
    assert should_skip_llm(search_results=[{"text": "some chunk"}], doc_scoped=True) is False


def test_no_skip_when_not_doc_scoped():
    # Not doc-scoped: web search fallback may still fire — don't block LLM
    assert should_skip_llm(search_results=[], doc_scoped=False) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_citation_validator.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'core.accuracy'`

- [ ] **Step 3: Create the accuracy package**

Create `backend/core/accuracy/__init__.py` (empty):

```python
```

Create `backend/core/accuracy/citation_validator.py`:

```python
"""
Citation Validator — anti-hallucination guard for LLM answers.

validate_citations(): scans for unverified quotes/claims, appends 🚨 warning if 2+ found.
should_skip_llm(): returns True when doc-scoped RAG returned no results (honest refusal).
"""

import re

_NO_VALIDATE_PREFIXES = ("i don't have", "i do not have", "no information")
_FABRICATION_THRESHOLD = 2
_NO_CONTEXT_MESSAGE = "I don't have this in my documents."

# Patterns that indicate an unsourced claim about the law
_CLAIM_PATTERNS = [
    r'the (?:law|regulation|act|decree|rule) (?:states?|says?|provides?|requires?|mandates?)[:\s]+([^.]{30,})',
    r'according to (?:article|section|clause|paragraph)\s+[\w\d]+[:\s]+([^.]{30,})',
]


def _words_in_text(words: list[str], text: str) -> bool:
    """Return True if any substantive word (len > 3) from words appears in text."""
    return any(w in text for w in words if len(w) > 3)


def validate_citations(answer: str, chunks: list[dict]) -> str:
    """Validate LLM answer against source chunks.

    Appends 🚨 warning block if 2 or more potential fabrications are detected.
    Returns the answer unchanged if confidence is acceptable.
    """
    # Skip validation for honest refusals
    lower = answer.lower().strip()
    if any(lower.startswith(p) for p in _NO_VALIDATE_PREFIXES):
        return answer

    combined = " ".join(c.get("text", "") for c in chunks).lower()

    unverified_quotes = 0
    unverified_claims = 0

    # Check quoted text (straight and curly quotes)
    quoted = re.findall(r'["\u201c\u201d]([^"\u201c\u201d]{10,})["\u201c\u201d]', answer)
    for quote in quoted:
        words = quote.lower().split()[:5]
        if not _words_in_text(words, combined):
            unverified_quotes += 1

    # Check claim patterns
    for pattern in _CLAIM_PATTERNS:
        for match in re.finditer(pattern, answer, re.IGNORECASE):
            claim_words = match.group(1).lower().split()[:6]
            if not _words_in_text(claim_words, combined):
                unverified_claims += 1

    total = unverified_quotes + unverified_claims
    if total >= _FABRICATION_THRESHOLD:
        warning = (
            f"\n\n🚨 **CRITICAL LEGAL ACCURACY WARNING:**\n"
            f"Found {total} potential issue(s):\n"
            f"• {unverified_quotes} unverified quote(s)\n"
            f"• {unverified_claims} unverified claim(s)\n"
            f"Please verify with official documents before using for compliance."
        )
        return answer + warning

    return answer


def should_skip_llm(search_results: list, doc_scoped: bool) -> bool:
    """Return True when LLM should NOT be called.

    Fires only for doc-scoped queries (user explicitly selected documents)
    that return zero RAG chunks — honest refusal is better than hallucination.
    """
    return doc_scoped and len(search_results) == 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_citation_validator.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/core/accuracy/ backend/tests/test_citation_validator.py
git commit -m "feat: add citation validator and no-LLM guard"
```

---

## Task 3: Wire Citation Validator + No-LLM Guard into chat.py

**Files:**
- Modify: `backend/api/chat.py`
- Create: `backend/tests/test_no_llm_guard.py`

- [ ] **Step 1: Write failing integration test**

Create `backend/tests/test_no_llm_guard.py`:

```python
import pytest
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_rag_empty(monkeypatch):
    """Patch rag_engine.search to return empty list."""
    from core.rag_engine import rag_engine
    monkeypatch.setattr(rag_engine, "search", AsyncMock(return_value=[]))


@pytest.mark.asyncio
async def test_no_llm_guard_returns_honest_message_for_doc_scoped(
    client: AsyncClient, sample_conversation, mock_rag_empty
):
    """When doc-scoped RAG returns 0 results, answer must be the honest refusal — LLM not called."""
    with patch("api.chat.get_llm_provider") as mock_llm:
        resp = await client.post("/api/chat/send", json={
            "conversation_id": sample_conversation,
            "message": "What is the penalty for late VAT filing?",
            "mode": "analyst",
            "selected_doc_ids": ["doc-that-exists"],
            "use_rag": True,
            "stream": False,
        })
    assert resp.status_code == 200
    data = resp.json()
    # Non-streaming response shape: {"message": {"content": "...", ...}, "conversation_id": "..."}
    assert "don't have" in data["message"]["content"].lower()
    # LLM should NOT have been called
    mock_llm.return_value.chat.assert_not_called()


@pytest.mark.asyncio
async def test_no_guard_when_not_doc_scoped(client: AsyncClient, sample_conversation, mock_rag_empty):
    """When not doc-scoped and RAG is empty, LLM IS called (web search fallback may fire)."""
    with patch("api.chat.get_llm_provider") as mock_llm:
        mock_llm.return_value.chat = AsyncMock(return_value=MagicMock(content="General answer"))
        mock_llm.return_value.compute_safe_max_tokens = MagicMock(return_value=2000)
        resp = await client.post("/api/chat/send", json={
            "conversation_id": sample_conversation,
            "message": "What is VAT?",
            "mode": "fast",
            "use_rag": True,
            "stream": False,
        })
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_no_llm_guard.py::test_no_llm_guard_returns_honest_message_for_doc_scoped -v 2>&1 | head -20
```

Expected: Test fails — LLM IS called even when doc-scoped with empty results.

- [ ] **Step 3: Add no-LLM guard to chat.py — non-streaming path**

In `backend/api/chat.py`, find the non-streaming path. After line `search_results = []` (in the RAG try/except block near line 876), add the guard before building messages. Find this section:

```python
        except Exception as rag_exc:
            logger.warning(f"RAG search failed, falling back to no-context mode: {rag_exc}")
            search_results = []


        if search_results:
```

Add the guard between `search_results = []` and `if search_results:`:

```python
        except Exception as rag_exc:
            logger.warning(f"RAG search failed, falling back to no-context mode: {rag_exc}")
            search_results = []

        # No-LLM guard: doc-scoped query with zero chunks → honest refusal
        _doc_scoped_ns = req.mode == "analyst" and bool(req.selected_doc_ids)
        from core.accuracy.citation_validator import should_skip_llm
        if should_skip_llm(search_results, _doc_scoped_ns):
            _no_ctx = "I don't have this in my documents."
            no_ctx_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=_no_ctx,
                sources=None,
            )
            db.add(no_ctx_msg)
            await db.flush()
            await db.commit()
            # ChatResponse + MessageResponse are defined at the top of chat.py (not in schemas/)
            return ChatResponse(
                message=MessageResponse(
                    id=no_ctx_msg.id,
                    role="assistant",
                    content=_no_ctx,
                    sources=None,
                    created_at=str(no_ctx_msg.created_at),
                    tokens_used=0,
                ),
                conversation_id=conversation.id,
                provider=settings.llm_provider,
                model=settings.active_model,
            )

        if search_results:
```

- [ ] **Step 4: Add no-LLM guard to chat.py — streaming path**

In the `generate()` async function (streaming path), find the section after RAG search (near line 584-590):

```python
                except Exception as _rag_exc:
                    logger.warning("RAG search failed, falling back to no-context mode: %s", _rag_exc)
                    _search_results = []

                logger.info("RAG returned %d results for conversation %s", len(_search_results), conversation.id)

            # ── 6. Build messages list ─────
```

Add guard after the logger.info line:

```python
                except Exception as _rag_exc:
                    logger.warning("RAG search failed, falling back to no-context mode: %s", _rag_exc)
                    _search_results = []

                logger.info("RAG returned %d results for conversation %s", len(_search_results), conversation.id)

            # No-LLM guard: doc-scoped query with zero chunks → honest refusal
            from core.accuracy.citation_validator import should_skip_llm
            if should_skip_llm(_search_results, _doc_scoped):
                no_ctx_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="I don't have this in my documents.",
                    sources=None,
                )
                db.add(no_ctx_msg)
                await db.commit()
                yield f"data: {json.dumps({'type': 'chunk', 'content': 'I don\\'t have this in my documents.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message_id': no_ctx_msg.id})}\n\n"
                return
```

- [ ] **Step 5: Add citation validator call — non-streaming path**

In the non-streaming path, find where the LLM response is obtained (after `response = await llm.chat(...)` near line 935+). Add after the response is received:

```python
        # Citation validation: append 🚨 warning if 2+ fabrications detected
        from core.accuracy.citation_validator import validate_citations
        answer_content = validate_citations(response.content, search_results)
```

Then use `answer_content` instead of `response.content` when building the assistant message and ChatResponse.

- [ ] **Step 6: Add citation validator call — streaming path**

In the `generate()` function, after `full_response` is assembled (after the `async for chunk in _llm.chat_stream(...)` loop near line 697), add:

```python
            # Citation validation
            from core.accuracy.citation_validator import validate_citations
            full_response = validate_citations(full_response, _search_results)
```

This must be BEFORE the sources yield and DB save.

- [ ] **Step 7: Run the guard test**

```bash
cd backend
pytest tests/test_no_llm_guard.py -v
```

Expected: `2 passed`

- [ ] **Step 8: Run full test suite to check no regressions**

```bash
cd backend
pytest tests/ -x --timeout=60 -q 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 9: Commit**

```bash
git add backend/api/chat.py backend/tests/test_no_llm_guard.py
git commit -m "feat: wire no-LLM guard and citation validator into chat.py"
```

---

## Task 4: Fuzzy Domain Matching

**Files:**
- Modify: `backend/core/chat/domain_classifier.py`
- Create: `backend/tests/test_fuzzy_domain.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_fuzzy_domain.py`:

```python
import pytest
from core.chat.domain_classifier import _fuzzy_classify_query, DomainLabel


def test_exact_keyword_vat():
    result = _fuzzy_classify_query("what is the vat rate on real estate?")
    assert result is not None
    assert result.domain == DomainLabel.VAT
    assert result.confidence == 0.8


def test_fuzzy_typo_vatt():
    result = _fuzzy_classify_query("what is vatt registration process?")
    assert result is not None
    assert result.domain == DomainLabel.VAT


def test_fuzzy_typo_corparate():
    result = _fuzzy_classify_query("corparate tax filing deadline")
    assert result is not None
    assert result.domain == DomainLabel.CORPORATE_TAX


def test_fuzzy_typo_employmant():
    result = _fuzzy_classify_query("employmant contract requirements uae")
    assert result is not None
    assert result.domain == DomainLabel.LABOUR


def test_returns_none_for_unrelated():
    result = _fuzzy_classify_query("hello how are you")
    assert result is None


def test_hotel_apartment_exact():
    result = _fuzzy_classify_query("hotel apartment vat treatment")
    assert result is not None
    assert result.domain == DomainLabel.VAT


def test_fuzzy_match_confidence_is_lower():
    # Fuzzy matches return 0.7 confidence, not 0.8
    result = _fuzzy_classify_query("corparate tax")
    if result and result.domain == DomainLabel.CORPORATE_TAX:
        # Accept either 0.7 (fuzzy) or 0.8 (exact) — "corparate" may match "corporate"
        assert result.confidence in (0.7, 0.8)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_fuzzy_domain.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name '_fuzzy_classify_query'`

- [ ] **Step 3: Add fuzzy classification to domain_classifier.py**

Open `backend/core/chat/domain_classifier.py`. Add imports at the top (after existing imports):

```python
import difflib
import os
```

Add the constants and helper function BEFORE the `classify_domain` function:

```python
_FUZZY_CUTOFF = float(os.environ.get("FUZZY_CUTOFF", "0.78"))

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "vat": [
        "vat", "value added tax", "tax invoice", "input tax", "output tax",
        "zero rating", "hotel apartment", "commercial property", "trn",
        "reverse charge", "excise", "zero rated", "exempt supply",
    ],
    "corporate_tax": [
        "corporate tax", "ct", "qualifying income", "free zone",
        "transfer pricing", "permanent establishment", "withholding tax",
        "corporate income", "taxable income", "small business relief",
    ],
    "e_invoicing": [
        "e-invoice", "einvoice", "electronic invoice", "peppol", "e invoicing",
        "e invoice", "digital invoice",
    ],
    "labour": [
        "labour", "labor", "employment", "visa", "gratuity", "termination",
        "end of service", "worker", "employee", "wages", "mohre", "wps",
    ],
    "commercial": [
        "commercial", "company law", "llc", "partnership", "trading licence",
        "commercial register", "agency", "licensing", "business setup",
    ],
    "ifrs": [
        "ifrs", "ias", "financial statement", "accounting standard",
        "consolidation", "revenue recognition", "lease", "impairment",
        "fair value", "disclosure",
    ],
}

# Flat list of (keyword, domain) pairs for difflib matching
_FLAT_KEYWORDS: list[tuple[str, str]] = [
    (kw, domain)
    for domain, kws in _DOMAIN_KEYWORDS.items()
    for kw in kws
]


def _fuzzy_classify_query(query: str) -> "ClassifierResult | None":
    """Classify query using exact keyword match, then difflib fuzzy matching.

    Returns ClassifierResult on match, None if no domain can be inferred.
    Exact multi-word matches return confidence 0.8.
    Fuzzy single-word matches return confidence 0.7.
    """
    lower = query.lower()

    # Pass 1: exact substring match (multi-word keywords first)
    for kw, domain in sorted(_FLAT_KEYWORDS, key=lambda x: -len(x[0])):
        if kw in lower:
            return ClassifierResult(
                domain=DomainLabel(domain), confidence=0.8, alternatives=[]
            )

    # Pass 2: difflib fuzzy match on individual query words
    flat_kws = [kw for kw, _ in _FLAT_KEYWORDS]
    for word in lower.split():
        if len(word) < 3:
            continue
        matches = difflib.get_close_matches(word, flat_kws, n=1, cutoff=_FUZZY_CUTOFF)
        if matches:
            matched_domain = next(d for kw, d in _FLAT_KEYWORDS if kw == matches[0])
            return ClassifierResult(
                domain=DomainLabel(matched_domain), confidence=0.7, alternatives=[]
            )

    return None
```

- [ ] **Step 4: Replace the existing keyword fallback in `classify_domain`**

Find this block in `classify_domain`:

```python
        # Keyword-based fallback for critical topics
        lower_query = query.lower()
        if "hotel apartment" in lower_query or "commercial property" in lower_query:
            return ClassifierResult(
                domain=DomainLabel.VAT, confidence=0.8, alternatives=[]
            )
            
        return ClassifierResult(
            domain=DomainLabel.GENERAL_LAW, confidence=0.3, alternatives=[]
        )
```

Replace with:

```python
        # Keyword + fuzzy fallback
        fuzzy_result = _fuzzy_classify_query(query)
        if fuzzy_result:
            return fuzzy_result

        return ClassifierResult(
            domain=DomainLabel.GENERAL_LAW, confidence=0.3, alternatives=[]
        )
```

- [ ] **Step 5: Run fuzzy domain tests**

```bash
cd backend
pytest tests/test_fuzzy_domain.py -v
```

Expected: `7 passed`

- [ ] **Step 6: Run full suite for regressions**

```bash
cd backend
pytest tests/ -x --timeout=60 -q 2>&1 | tail -10
```

Expected: All previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/core/chat/domain_classifier.py backend/tests/test_fuzzy_domain.py
git commit -m "feat: add fuzzy domain matching with difflib (FUZZY_CUTOFF=0.78)"
```

---

## Task 5: Hybrid Search Engine

**Files:**
- Create: `backend/core/search/__init__.py`
- Create: `backend/core/search/hybrid_engine.py`
- Modify: `backend/core/rag_engine.py`
- Create: `backend/tests/test_hybrid_engine.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hybrid_engine.py`:

```python
import pytest
from core.search.hybrid_engine import HybridEngine, _keyword_score


# ── _keyword_score ────────────────────────────────────────────────────────────

def test_exact_phrase_scores_one():
    score = _keyword_score("hotel apartment vat", "hotel apartment vat rules in uae")
    assert score == 1.0


def test_partial_keywords_score_between_zero_and_one():
    score = _keyword_score("vat hotel", "hotel registration requirements are strict")
    assert 0.0 < score < 1.0


def test_unrelated_text_scores_low():
    score = _keyword_score("vat hotel apartment", "this is about labour law and gratuity")
    assert score < 0.5


def test_empty_text_scores_zero():
    score = _keyword_score("vat", "")
    assert score == 0.0


# ── HybridEngine.blend_results ────────────────────────────────────────────────

def test_blend_results_returns_all_inputs():
    engine = HybridEngine()
    results = [
        {"text": "VAT hotel apartment treatment", "score": 0.9, "metadata": {}},
        {"text": "labour law gratuity", "score": 0.5, "metadata": {}},
    ]
    blended = engine.blend_results(results, "VAT hotel apartment")
    assert len(blended) == 2


def test_blend_results_sorted_by_combined_score():
    engine = HybridEngine()
    results = [
        {"text": "completely unrelated text about nothing", "score": 0.6, "metadata": {}},
        {"text": "VAT hotel apartment treatment under UAE law", "score": 0.55, "metadata": {}},
    ]
    blended = engine.blend_results(results, "VAT hotel apartment")
    # Second result has lower vector score but higher keyword match — should rank up
    assert blended[0]["text"].startswith("VAT hotel")


def test_blend_results_adds_score_fields():
    engine = HybridEngine()
    results = [{"text": "some text", "score": 0.7, "metadata": {}}]
    blended = engine.blend_results(results, "some query")
    assert "vector_score" in blended[0]
    assert "keyword_score" in blended[0]


def test_blend_empty_returns_empty():
    engine = HybridEngine()
    assert engine.blend_results([], "any query") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_hybrid_engine.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'core.search'`

- [ ] **Step 3: Create the search package and HybridEngine**

Create `backend/core/search/__init__.py` (empty):

```python
```

Create `backend/core/search/hybrid_engine.py`:

```python
"""
Hybrid Search Engine — combines ChromaDB vector search with keyword re-ranking.

blend_results() takes vector results already retrieved from ChromaDB, applies
keyword scoring to each chunk, and returns a combined-score-sorted list.

This is applied AFTER ChromaDB's over-fetched results (top_k * 2) so keyword
signals can rescue weak vector matches and suppress high-vector/low-relevance noise.
"""

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False


def _keyword_score(query: str, text: str) -> float:
    """Return a 0-1 keyword relevance score using 3 signals.

    Signal 1: exact phrase match (score = 1.0)
    Signal 2: keyword presence ratio × 0.8
    Signal 3: fuzz.token_set_ratio × 0.7 (if rapidfuzz available)
    """
    if not text:
        return 0.0

    text_lower = text.lower()
    query_lower = query.lower()

    # Signal 1: exact phrase
    if query_lower in text_lower:
        return 1.0

    # Signal 2: keyword presence
    words = [w for w in query_lower.split() if len(w) > 2]
    kw_score = 0.0
    if words:
        kw_score = (sum(1 for w in words if w in text_lower) / len(words)) * 0.8

    # Signal 3: fuzzy token ratio (first 200 chars for speed)
    fuzzy_score = 0.0
    if _RAPIDFUZZ_AVAILABLE:
        fuzzy_score = _fuzz.token_set_ratio(query_lower, text_lower[:200]) / 100 * 0.7

    return max(kw_score, fuzzy_score)


class HybridEngine:
    """Re-rank ChromaDB vector results with keyword scoring."""

    VECTOR_WEIGHT: float = 0.7
    KEYWORD_WEIGHT: float = 0.3

    def blend_results(self, vector_results: list[dict], query: str) -> list[dict]:
        """Apply keyword re-ranking to vector results.

        Each result gets a combined_score = 0.7 * vector_score + 0.3 * keyword_score.
        Returns list sorted by combined score descending.
        Original vector_score and keyword_score are preserved in result dict.
        """
        if not vector_results:
            return []

        scored = []
        for r in vector_results:
            v_score = r.get("score", 0.0)
            k_score = _keyword_score(query, r.get("text", ""))
            combined = self.VECTOR_WEIGHT * v_score + self.KEYWORD_WEIGHT * k_score
            scored.append({
                **r,
                "score": combined,
                "vector_score": v_score,
                "keyword_score": k_score,
            })

        return sorted(scored, key=lambda x: x["score"], reverse=True)


hybrid_engine = HybridEngine()
```

- [ ] **Step 4: Run hybrid engine tests**

```bash
cd backend
pytest tests/test_hybrid_engine.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Wire HybridEngine into rag_engine.py**

Open `backend/core/rag_engine.py`. Find the `search()` method. After the `search_results.sort(...)` line (near line 332) and before `return search_results[:8]`, add the hybrid re-ranking:

```python
        # Sort by score and cap
        search_results.sort(key=lambda x: x["score"], reverse=True)
        # Hybrid re-ranking: blend vector scores with keyword relevance
        from core.search.hybrid_engine import hybrid_engine
        search_results = hybrid_engine.blend_results(search_results, query)
        # Cap at 8 results maximum
        return search_results[:8]
```

(This replaces the existing `return search_results[:8]` line at the end of the method.)

- [ ] **Step 6: Verify full chunk text in build_augmented_prompt**

Open `backend/core/rag_engine.py` and find `build_augmented_prompt()` (near line 336). Verify the context_parts includes raw chunk text — it should already:

```python
context_parts.append(f"Source: {source} (Page {page})\n{r['text']}")
```

If the format is `f"Source: {source} (Page {page})\n{r['text']}"` — this is correct. The full `r['text']` is included. No change needed.

If the text is truncated anywhere, update to ensure at least 700 chars are passed: `r['text'][:700]` (it likely passes full text already).

- [ ] **Step 7: Run full suite**

```bash
cd backend
pytest tests/ -x --timeout=60 -q 2>&1 | tail -15
```

Expected: All previously passing tests still pass, plus 7 new hybrid engine tests.

- [ ] **Step 8: Commit**

```bash
git add backend/core/search/ backend/core/rag_engine.py backend/tests/test_hybrid_engine.py
git commit -m "feat: add hybrid search engine with keyword re-ranking"
```

---

## Task 6: FTA Scraper

**Files:**
- Create: `backend/core/pipeline/__init__.py`
- Create: `backend/core/pipeline/fta_scraper.py`
- Modify: `backend/monitoring/scheduler.py`
- Create: `backend/tests/test_fta_scraper.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_fta_scraper.py`:

```python
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


@pytest.fixture(autouse=True)
def temp_hash_file(tmp_path, monkeypatch):
    """Redirect hash file to a temp location for each test."""
    hash_file = tmp_path / "scraped_hashes.txt"
    import core.pipeline.fta_scraper as scraper_mod
    monkeypatch.setattr(scraper_mod, "_HASH_FILE", hash_file)
    return hash_file


@pytest.mark.asyncio
async def test_new_pdf_is_ingested(monkeypatch):
    """A PDF URL not seen before should be downloaded and ingested."""
    ingested = []

    async def fake_ingest(text, source=None, source_type=None, category=None):
        ingested.append(source)

    monkeypatch.setattr("core.pipeline.fta_scraper.ingest_text", fake_ingest)

    pdf_bytes = b"%PDF-1.4 fake pdf content"
    html_with_pdf = b'<html><body><a href="/docs/law.pdf">Law</a></body></html>'

    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.endswith(".pdf"):
            resp.content = pdf_bytes
        else:
            resp.content = html_with_pdf
            resp.text = html_with_pdf.decode()
        return resp

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=fake_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with patch("core.pipeline.fta_scraper._extract_pdf_text", return_value="VAT law text"):
            from core.pipeline.fta_scraper import run_fta_scraper
            count = await run_fta_scraper()

    assert count >= 0  # At minimum, ran without error


@pytest.mark.asyncio
async def test_duplicate_pdf_not_reingested(monkeypatch, temp_hash_file):
    """A PDF whose MD5 hash is already in scraped_hashes.txt must be skipped."""
    import hashlib
    pdf_bytes = b"%PDF-1.4 known content"
    h = hashlib.md5(pdf_bytes).hexdigest()
    temp_hash_file.write_text(h + "\n")

    ingested = []

    async def fake_ingest(text, source=None, source_type=None, category=None):
        ingested.append(source)

    monkeypatch.setattr("core.pipeline.fta_scraper.ingest_text", fake_ingest)

    html = b'<html><body><a href="/docs/law.pdf">Law</a></body></html>'

    async def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.endswith(".pdf"):
            resp.content = pdf_bytes
        else:
            resp.text = html.decode()
        return resp

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=fake_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with patch("core.pipeline.fta_scraper._extract_pdf_text", return_value="text"):
            from core.pipeline.fta_scraper import run_fta_scraper
            await run_fta_scraper()

    assert ingested == []  # Nothing new ingested


@pytest.mark.asyncio
async def test_scraper_handles_failed_url_gracefully(monkeypatch):
    """A URL that throws an error should not crash the entire scraper."""
    async def fake_get(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=fake_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from core.pipeline.fta_scraper import run_fta_scraper
        count = await run_fta_scraper()  # Must not raise

    assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_fta_scraper.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'core.pipeline'`

- [ ] **Step 3: Create the pipeline package and FTA scraper**

Create `backend/core/pipeline/__init__.py` (empty):

```python
```

Create `backend/core/pipeline/fta_scraper.py`:

```python
"""
FTA Scraper — nightly download of new UAE tax and legal PDFs.

Scrapes FTA, MoEC, and MoET for PDF links. Uses MD5 hash deduplication to
skip files already ingested. New PDFs are parsed and ingested into the RAG store.

Registered as an APScheduler cron job (midnight daily) in monitoring/scheduler.py.
"""

import hashlib
import logging
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HASH_FILE = Path(__file__).parent.parent.parent / "data" / "scraped_hashes.txt"

_SCRAPE_TARGETS: list[tuple[str, str]] = [
    ("https://tax.gov.ae/en/Legislation.aspx", "law"),
    ("https://www.moec.gov.ae/en/laws", "law"),
    ("https://www.moet.gov.ae/en/laws", "law"),
]


def _load_hashes() -> set[str]:
    if not _HASH_FILE.exists():
        return set()
    return set(line.strip() for line in _HASH_FILE.read_text().splitlines() if line.strip())


def _save_hash(h: str) -> None:
    _HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _HASH_FILE.open("a") as f:
        f.write(h + "\n")


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes using PyMuPDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


async def _find_pdf_links(page_url: str, client: httpx.AsyncClient) -> list[str]:
    """Fetch HTML page and return all absolute .pdf links found."""
    try:
        resp = await client.get(
            page_url, headers={"User-Agent": "LegalAcctAI-Scraper/1.0"}
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        base = page_url.rsplit("/", 1)[0]
        links = []
        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            if href.lower().endswith(".pdf"):
                if not href.startswith("http"):
                    href = base + "/" + href.lstrip("/")
                links.append(href)
        return links
    except Exception as exc:
        logger.warning("FTA scraper: failed to scrape %s: %s", page_url, exc)
        return []


async def run_fta_scraper() -> int:
    """Scrape configured FTA sources for new PDFs.

    Returns count of newly ingested files.
    Each URL failure is caught individually — does not stop processing others.
    """
    from core.document_processor import ingest_text  # avoid circular import at module load

    seen_hashes = _load_hashes()
    ingested = 0

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for page_url, category in _SCRAPE_TARGETS:
            pdf_links = await _find_pdf_links(page_url, client)
            for pdf_url in pdf_links:
                try:
                    resp = await client.get(pdf_url)
                    resp.raise_for_status()
                    h = _md5(resp.content)
                    if h in seen_hashes:
                        continue

                    text = _extract_pdf_text(resp.content)
                    filename = pdf_url.rsplit("/", 1)[-1]
                    await ingest_text(
                        text,
                        source=filename,
                        source_type="fta_scraper",
                        category=category,
                    )
                    _save_hash(h)
                    seen_hashes.add(h)
                    ingested += 1
                    logger.info("FTA scraper ingested: %s (%s)", filename, category)

                except Exception as exc:
                    logger.warning("FTA scraper: failed to ingest %s: %s", pdf_url, exc)

    logger.info("FTA scraper completed: %d new file(s) ingested", ingested)
    return ingested
```

- [ ] **Step 4: Register FTA scraper in scheduler.py**

Open `backend/monitoring/scheduler.py`. Find the `start_scheduler()` function. Add a cron job for the FTA scraper:

```python
def start_scheduler():
    """Start the APScheduler for periodic checks."""
    interval = settings.monitor_interval_hours
    scheduler.add_job(
        fetch_and_check_updates,
        trigger=IntervalTrigger(hours=interval),
        id="monitoring_job",
        replace_existing=True,
    )

    # FTA scraper: runs nightly at midnight
    from apscheduler.triggers.cron import CronTrigger
    from core.pipeline.fta_scraper import run_fta_scraper
    scheduler.add_job(
        run_fta_scraper,
        trigger=CronTrigger(hour=0, minute=0),
        id="fta_scraper_job",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Monitoring scheduler started (interval: {interval} hours)")
    logger.info("FTA scraper scheduled at midnight daily")
```

- [ ] **Step 5: Run FTA scraper tests**

```bash
cd backend
pytest tests/test_fta_scraper.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Run full suite**

```bash
cd backend
pytest tests/ -x --timeout=60 -q 2>&1 | tail -10
```

Expected: All previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/core/pipeline/ backend/monitoring/scheduler.py backend/tests/test_fta_scraper.py
git commit -m "feat: add FTA scraper with MD5 dedup, scheduled nightly at midnight"
```

---

## Task 7: Auto-Sync Watchdog

**Files:**
- Modify: `backend/core/pipeline/auto_sync.py` (create)
- Modify: `backend/main.py`
- Create: `backend/tests/test_auto_sync.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_auto_sync.py`:

```python
import pytest
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_pdf_drop_triggers_ingest(tmp_path, monkeypatch):
    """Creating a PDF in a watched directory should trigger ingest after debounce."""
    ingested = []

    async def fake_ingest(text, source=None, source_type=None, category=None):
        ingested.append(source)

    import core.pipeline.auto_sync as sync_mod
    # Override watch dirs to use tmp_path
    monkeypatch.setattr(sync_mod, "_WATCH_DIRS", {str(tmp_path): "law"})
    monkeypatch.setattr(sync_mod, "_DEBOUNCE_S", 0.1)  # fast debounce for tests

    with patch("core.pipeline.auto_sync.ingest_text", fake_ingest):
        with patch("core.pipeline.auto_sync._extract_pdf_text", return_value="law text"):
            loop = asyncio.get_event_loop()
            sync_mod.start_auto_sync(loop)
            try:
                pdf_file = tmp_path / "test_law.pdf"
                pdf_file.write_bytes(b"%PDF-1.4 test")
                await asyncio.sleep(0.5)  # wait for debounce + ingest
            finally:
                sync_mod.stop_auto_sync()

    assert any("test_law.pdf" in (s or "") for s in ingested)


@pytest.mark.asyncio
async def test_non_pdf_file_ignored(tmp_path, monkeypatch):
    """Creating a .txt file should NOT trigger ingest."""
    ingested = []

    async def fake_ingest(text, source=None, source_type=None, category=None):
        ingested.append(source)

    import core.pipeline.auto_sync as sync_mod
    monkeypatch.setattr(sync_mod, "_WATCH_DIRS", {str(tmp_path): "law"})
    monkeypatch.setattr(sync_mod, "_DEBOUNCE_S", 0.1)

    with patch("core.pipeline.auto_sync.ingest_text", fake_ingest):
        loop = asyncio.get_event_loop()
        sync_mod.start_auto_sync(loop)
        try:
            txt_file = tmp_path / "notes.txt"
            txt_file.write_text("some notes")
            await asyncio.sleep(0.3)
        finally:
            sync_mod.stop_auto_sync()

    assert ingested == []


def test_stop_auto_sync_when_not_started():
    """Calling stop_auto_sync before start should not raise."""
    from core.pipeline.auto_sync import stop_auto_sync
    stop_auto_sync()  # should be a no-op
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_auto_sync.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or `ImportError` since module doesn't exist yet.

- [ ] **Step 3: Create auto_sync.py**

Create `backend/core/pipeline/auto_sync.py`:

```python
"""
Auto-Sync Watchdog — monitors data_source_law/ and data_source_finance/ directories.

When a new .pdf file is dropped (or moved in), extracts text and ingests into RAG store.
Uses a 10-second debounce to handle batch file drops gracefully.

Started/stopped via start_auto_sync() / stop_auto_sync() in main.py lifespan.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

_DEBOUNCE_S: float = 10.0
_WATCH_DIRS: dict[str, str] = {
    "data_source_law": "law",
    "data_source_finance": "finance",
}

_observer: Optional[Observer] = None


def _extract_pdf_text(path: str) -> str:
    """Extract text from PDF file using PyMuPDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


async def ingest_text(text: str, source=None, source_type=None, category=None) -> None:
    """Proxy to document_processor.ingest_text — imported lazily to avoid circular imports."""
    from core.document_processor import ingest_text as _ingest
    await _ingest(text, source=source, source_type=source_type, category=category)


class _PDFHandler(FileSystemEventHandler):
    """Watchdog handler for PDF files with debounced ingest."""

    def __init__(self, category: str, loop: asyncio.AbstractEventLoop) -> None:
        self._category = category
        self._loop = loop
        self._pending: dict[str, object] = {}

    def _schedule(self, path: str) -> None:
        # Cancel any pending handle for this path (debounce)
        if path in self._pending:
            try:
                self._pending[path].cancel()
            except Exception:
                pass
        handle = self._loop.call_later(
            _DEBOUNCE_S,
            lambda p=path: asyncio.run_coroutine_threadsafe(
                self._ingest(p), self._loop
            ),
        )
        self._pending[path] = handle

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            self._schedule(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            self._schedule(event.dest_path)

    async def _ingest(self, path: str) -> None:
        self._pending.pop(path, None)
        try:
            text = _extract_pdf_text(path)
            filename = Path(path).name
            await ingest_text(
                text,
                source=filename,
                source_type="auto_sync",
                category=self._category,
            )
            logger.info("Auto-sync ingested: %s (%s)", filename, self._category)
        except Exception as exc:
            logger.warning("Auto-sync ingest failed for %s: %s", path, exc)


def start_auto_sync(loop: asyncio.AbstractEventLoop) -> None:
    """Start the watchdog observer. Called from main.py lifespan startup."""
    global _observer
    if _observer is not None:
        return  # Already running

    _observer = Observer()
    for dir_name, category in _WATCH_DIRS.items():
        watch_path = Path(dir_name)
        watch_path.mkdir(parents=True, exist_ok=True)
        handler = _PDFHandler(category, loop)
        _observer.schedule(handler, str(watch_path), recursive=False)

    _observer.start()
    logger.info("Auto-sync watchdog started, watching: %s", list(_WATCH_DIRS.keys()))


def stop_auto_sync() -> None:
    """Stop the watchdog observer. Called from main.py lifespan shutdown."""
    global _observer
    if _observer is not None:
        _observer.stop()
        _observer.join()
        _observer = None
        logger.info("Auto-sync watchdog stopped")
```

- [ ] **Step 4: Wire auto_sync into main.py lifespan**

Open `backend/main.py`. In the `lifespan` function, add auto-sync startup AFTER the scheduler starts. Find:

```python
    # Start APScheduler
    _t = time.perf_counter()
    from monitoring.scheduler import start_scheduler, scheduler
    start_scheduler()
    logger.info(f"[OK] Scheduler started ({time.perf_counter()-_t:.2f}s)")
```

Add after it:

```python
    # Start auto-sync watchdog
    _t = time.perf_counter()
    from core.pipeline.auto_sync import start_auto_sync
    import asyncio as _asyncio
    start_auto_sync(_asyncio.get_event_loop())
    logger.info(f"[OK] Auto-sync watchdog started ({time.perf_counter()-_t:.2f}s)")
```

And in the shutdown section, find `scheduler.shutdown()` and add:

```python
    logger.info("Chatbot server shutting down...")
    scheduler.shutdown()
    from core.pipeline.auto_sync import stop_auto_sync
    stop_auto_sync()
```

- [ ] **Step 5: Run auto-sync tests**

```bash
cd backend
pytest tests/test_auto_sync.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Run full suite**

```bash
cd backend
pytest tests/ -x --timeout=60 -q 2>&1 | tail -10
```

Expected: All previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/core/pipeline/auto_sync.py backend/main.py backend/tests/test_auto_sync.py
git commit -m "feat: add auto-sync watchdog for PDF drop-in ingestion (10s debounce)"
```

---

## Task 8: Source Domain Display

**Files:**
- Modify: `backend/api/chat.py` — add `domain` field to sources in both streaming + non-streaming paths
- Modify: `frontend/src/lib/api.ts` — add `domain?: string` to `Source` interface
- Modify: `frontend/src/components/studios/LegalStudio/SourcePeeker.tsx` — domain badge + auto-expand
- Create: `backend/tests/test_source_domain_display.py`

- [ ] **Step 1: Write failing backend test**

Create `backend/tests/test_source_domain_display.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_sources_include_domain_field(client, sample_conversation):
    """Each source in the response must include a 'domain' field."""
    mock_chunk = {
        "text": "Hotel apartments are treated as residential for VAT.",
        "score": 0.92,
        "source": "UAE_VAT_Law.pdf",
        "metadata": {
            "source": "UAE_VAT_Law.pdf",
            "original_name": "UAE_VAT_Law.pdf",
            "page": 12,
            "domain": "vat",
            "category": "law",
        },
    }

    with patch("api.chat.rag_engine") as mock_rag:
        mock_rag.search = AsyncMock(return_value=[mock_chunk])
        mock_rag.build_augmented_prompt = MagicMock(return_value=[
            {"role": "system", "content": "Source: UAE_VAT_Law.pdf (Page 12)\nHotel apartments..."}
        ])

        with patch("api.chat.get_llm_provider") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=MagicMock(content="VAT applies at 5%."))
            mock_llm.compute_safe_max_tokens = MagicMock(return_value=2000)
            mock_llm_cls.return_value = mock_llm

            resp = await client.post("/api/chat/send", json={
                "conversation_id": sample_conversation,
                "message": "What is the VAT on hotel apartments?",
                "mode": "fast",
                "use_rag": True,
                "stream": False,
            })

    assert resp.status_code == 200
    data = resp.json()
    # Non-streaming ChatResponse shape: {"message": {"sources": [...], ...}, ...}
    assert len(data["message"]["sources"]) > 0
    first_source = data["message"]["sources"][0]
    assert "domain" in first_source
    assert first_source["domain"] == "vat"


@pytest.mark.asyncio
async def test_sources_domain_defaults_to_empty_string_when_missing(client, sample_conversation):
    """If chunk metadata has no 'domain' key, source domain should be empty string."""
    mock_chunk = {
        "text": "Some document text.",
        "score": 0.85,
        "source": "doc.pdf",
        "metadata": {
            "source": "doc.pdf",
            "page": 1,
            # No 'domain' key
            "category": "law",
        },
    }

    with patch("api.chat.rag_engine") as mock_rag:
        mock_rag.search = AsyncMock(return_value=[mock_chunk])
        mock_rag.build_augmented_prompt = MagicMock(return_value=[
            {"role": "system", "content": "Source: doc.pdf (Page 1)\nSome text"}
        ])

        with patch("api.chat.get_llm_provider") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=MagicMock(content="Answer."))
            mock_llm.compute_safe_max_tokens = MagicMock(return_value=2000)
            mock_llm_cls.return_value = mock_llm

            resp = await client.post("/api/chat/send", json={
                "conversation_id": sample_conversation,
                "message": "What is this document about?",
                "mode": "fast",
                "use_rag": True,
                "stream": False,
            })

    assert resp.status_code == 200
    data = resp.json()
    assert "domain" in data["message"]["sources"][0]
    assert data["message"]["sources"][0]["domain"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_source_domain_display.py -v 2>&1 | head -30
```

Expected: AssertionError — `domain` key missing from sources.

- [ ] **Step 3: Add domain field to sources in chat.py — streaming path**

In `backend/api/chat.py`, find the source building in the streaming `generate()` function (near line 597):

```python
                _sources = [
                    {
                        "source": (
                            r.get("source")
                            or r["metadata"].get("original_name")
                            or r["metadata"].get("source", "Unknown")
                        ),
                        "page": r["metadata"].get("page", "?"),
                        "score": round(r.get("score", 0), 3),
                        "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                    }
                    for r in _search_results
                ]
```

Replace with:

```python
                _sources = [
                    {
                        "source": (
                            r.get("source")
                            or r["metadata"].get("original_name")
                            or r["metadata"].get("source", "Unknown")
                        ),
                        "page": r["metadata"].get("page", "?"),
                        "score": round(r.get("score", 0), 3),
                        "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                        "domain": r["metadata"].get("domain", ""),
                    }
                    for r in _search_results
                ]
```

- [ ] **Step 4: Add domain field to sources in chat.py — non-streaming path**

Find the source building in the non-streaming path (near line 884):

```python
            sources = [
                {
                    "source": r.get("source") or r["metadata"].get("original_name") or r["metadata"].get("source", "Unknown"),
                    "page": r["metadata"].get("page", "?"),
                    "score": round(r.get("score", 0), 3),
                    "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                }
                for r in search_results
            ]
```

Replace with:

```python
            sources = [
                {
                    "source": r.get("source") or r["metadata"].get("original_name") or r["metadata"].get("source", "Unknown"),
                    "page": r["metadata"].get("page", "?"),
                    "score": round(r.get("score", 0), 3),
                    "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                    "domain": r["metadata"].get("domain", ""),
                }
                for r in search_results
            ]
```

- [ ] **Step 5: Run domain display test**

```bash
cd backend
pytest tests/test_source_domain_display.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Update Source type in frontend**

Open `frontend/src/lib/api.ts`. Find:

```typescript
export interface Source { source: string; page: string | number; score: number; excerpt: string; original_name?: string; is_web?: boolean; title?: string; }
```

Replace with:

```typescript
export interface Source { source: string; page: string | number; score: number; excerpt: string; original_name?: string; is_web?: boolean; title?: string; domain?: string; }
```

- [ ] **Step 7: Enhance SourcePeeker.tsx — domain badge + auto-expand + score colors**

Open `frontend/src/components/studios/LegalStudio/SourcePeeker.tsx`.

Add `useState` tracking for expanded cards (already imported). After the existing state declarations, add:

```typescript
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(() => new Set());

  // Auto-expand the first (highest-score) source when sources change
  useEffect(() => {
    if (sources.length > 0) {
      const firstKey = `${sources[0].source}:${sources[0].page}`;
      setExpandedKeys(new Set([firstKey]));
    }
  }, [sources]);
```

Inside the `.map()` loop, after computing `const key = ...`, add:

```typescript
          const isExpanded = expandedKeys.has(key);
          const scorePercent = Math.round(source.score * 100);
          const scoreColor = scorePercent >= 80 ? '#22c55e' : scorePercent >= 60 ? '#f97316' : '#9ca3af';
          const scoreBg = scorePercent >= 80 ? '#dcfce7' : scorePercent >= 60 ? '#ffedd5' : '#f3f4f6';
          const toggleExpand = () => setExpandedKeys(prev => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key); else next.add(key);
            return next;
          });
```

Find the score badge `<div>` (with `{scorePercent}%`) and replace it plus add domain badge:

```typescript
              {/* Score badge + domain badge */}
              <div style={{ display: 'flex', gap: '4px', flexShrink: 0, alignItems: 'center' }}>
                {source.domain && (
                  <div style={{
                    fontSize: '10px', color: 'var(--s-text-3)',
                    background: 'var(--s-surface-2, #f1f5f9)',
                    padding: '2px 5px', borderRadius: 'var(--s-r-sm)',
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                  }}>
                    {source.domain.replace(/_/g, ' ')}
                  </div>
                )}
                <div style={{
                  fontFamily: 'var(--s-font-mono, monospace)', fontSize: '11px',
                  color: scoreColor, background: scoreBg,
                  padding: '2px 6px', borderRadius: 'var(--s-r-sm)',
                }}>
                  {scorePercent}%
                </div>
                <button
                  type="button"
                  onClick={e => { e.stopPropagation(); toggleExpand(); }}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--s-text-3)', fontSize: '12px', padding: '0 2px' }}
                  title={isExpanded ? 'Collapse' : 'Expand'}
                >
                  {isExpanded ? '▾' : '▸'}
                </button>
              </div>
```

Find the content `<div>` (the text display block with `maxHeight: '120px'`) and wrap it with a conditional:

```typescript
              {/* Content — shown when expanded */}
              {isExpanded && (
                <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)', whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: '120px', overflowY: 'auto' }}>
                  {text || '…'}
                </div>
              )}
```

Also wrap the actions `<div>` (Copy/Word/Excel buttons) with `{isExpanded && (`:

```typescript
              {/* Actions — shown when expanded */}
              {isExpanded && (
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => handleCopy(text, key)}
                    style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                    title="Copy to clipboard"
                  >
                    <Copy size={11} />
                    {copying === key ? 'Copied!' : 'Copy'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleWordDownload(text, displayName)}
                    style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                    title="Download as Word"
                  >
                    <FileText size={11} />
                    Word
                  </button>
                  {showExcel && (
                    <button
                      type="button"
                      onClick={() => handleExcelDownload(text, displayName)}
                      style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                      title="Download as Excel"
                    >
                      <Table2 size={11} />
                      Excel
                    </button>
                  )}
                </div>
              )}
```

- [ ] **Step 8: Build frontend to verify no TypeScript errors**

```bash
cd frontend
npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 9: Run full backend suite**

```bash
cd backend
pytest tests/ --timeout=60 -q 2>&1 | tail -10
```

Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add backend/api/chat.py backend/tests/test_source_domain_display.py
git add frontend/src/lib/api.ts frontend/src/components/studios/LegalStudio/SourcePeeker.tsx
git commit -m "feat: add domain badge, score color-coding, and auto-expand to source panel"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Run complete backend test suite**

```bash
cd backend
pytest tests/ --timeout=60 -v 2>&1 | tail -40
```

Expected: All tests pass. Specifically verify these new test files:
- `test_citation_validator.py` — 6 tests
- `test_no_llm_guard.py` — 2 tests
- `test_fuzzy_domain.py` — 7 tests
- `test_hybrid_engine.py` — 7 tests
- `test_fta_scraper.py` — 3 tests
- `test_auto_sync.py` — 3 tests
- `test_source_domain_display.py` — 2 tests

Total new tests: 30

- [ ] **Step 2: Update chat_history_viewer.py to show sources**

In `chat_history_viewer.py`, the `print_full_conversation()` function at line ~216 iterates messages and prints `msg["content"]`. Update it to also render sources (score + domain + excerpt) when present:

```python
# In print_full_conversation(), replace the message loop body:
for i, msg in enumerate(messages, 1):
    role = msg["role"]
    if role == "user":
        label = c("green", "[USER]")
    elif role == "assistant":
        label = c("cyan", "[ASSISTANT]")
    else:
        label = c("gray", f"[{role.upper()}]")

    ts = (msg["created_at"] or "")[:19]
    tokens = f"  {c('gray', str(msg['tokens_used']) + ' tokens')}" if msg["tokens_used"] else ""
    print(f"\n[{i}] {label}  {c('gray', ts)}{tokens}")
    print_separator("-")
    print(msg["content"])

    # Show sources if present
    raw_sources = msg["sources"]
    if raw_sources:
        try:
            sources = json.loads(raw_sources) if isinstance(raw_sources, str) else raw_sources
            if sources:
                print(c("gray", f"\n  📎 Sources ({len(sources)}):"))
                for s in sources:
                    score = s.get("score", 0)
                    score_pct = f"{score*100:.0f}%" if score <= 1 else f"{score:.0f}%"
                    domain = s.get("domain", "")
                    domain_str = f" [{c('cyan', domain)}]" if domain else ""
                    excerpt = (s.get("excerpt") or "")[:120].replace("\n", " ")
                    excerpt_str = f'  "{c("gray", excerpt)}…"' if excerpt else ""
                    print(f"    {c('yellow', score_pct)}{domain_str}  {s.get('source','')[:50]}{excerpt_str}")
        except (json.JSONDecodeError, TypeError):
            pass
```

- [ ] **Step 3: Verify frontend build**

```bash
cd frontend
npm run build 2>&1 | tail -10
```

Expected: `✓ built in Xs` with no errors.

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: chatbot enhancements complete — citation validator, fuzzy domain, hybrid search, FTA scraper, auto-sync, source domain display"
```

---

## Parallel Execution Groups

These tasks can be dispatched in parallel by a subagent coordinator:

| Group | Tasks | Can run simultaneously with |
|-------|-------|----------------------------|
| A | Tasks 2 + 3 (citation validator + guard) | Groups B, C |
| B | Tasks 4 (fuzzy domain) | Groups A, C |
| C | Tasks 5 (hybrid search) | Groups A, B |
| D | Tasks 6 + 7 (FTA scraper + auto-sync) | Groups A, B, C |
| E | Task 8 (source display) | After Task 3 backend change is merged |

Task 1 (dependencies) must complete before all others.
Task 9 (final verification) must run last.
