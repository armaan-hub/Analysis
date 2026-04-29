# RAG Domain Adaptive Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix wrong RAG sources for wills/estate/general-law queries by correcting domain classification and adding a smart broad-search fallback when domain-filtered results score below 0.65.

**Architecture:** Four targeted changes: (1) add wills/inheritance examples to the LLM domain classifier prompt, (2) add `general_law` keywords to the keyword-fallback classifier, (3) add a broad-search retry in `chat.py` when domain-filtered RAG scores < 0.65, (4) add a ⚠️ low-confidence label in `chat_history_viewer.py` for sources scoring < 0.65.

**Tech Stack:** Python, FastAPI, ChromaDB, pytest, pytest-asyncio

---

## File Map

| File | Change |
|---|---|
| `backend/core/chat/prompts/domain_classifier.md` | Add 3 wills/inheritance → `general_law` examples |
| `backend/core/chat/domain_classifier.py` | Add `general_law` entry to `_DOMAIN_KEYWORDS` |
| `backend/api/chat.py` | Add `_BROAD_FALLBACK_THRESHOLD` constant + fallback block in streaming + non-streaming paths |
| `chat_history_viewer.py` | Add `⚠️ low-confidence` suffix for sources with score < 0.65 |
| `backend/tests/test_fuzzy_domain.py` | Add tests: wills/inheritance → `general_law` via keyword fallback |
| `backend/tests/test_domain_classifier.py` | Add test: `classify_domain` returns `general_law` for wills query (mocked LLM) |
| `backend/tests/test_relevance_rag.py` | Add tests: broad fallback triggers when top score < 0.65 |

---

## Task 1: Fix domain_classifier.md — Add wills/inheritance examples

**Files:**
- Modify: `backend/core/chat/prompts/domain_classifier.md`

- [ ] **Step 1: Open the classifier prompt and add 3 wills/estate examples**

  Open `backend/core/chat/prompts/domain_classifier.md`. After the existing example:
  ```
  Q: "What is the limitation period for civil claims in UAE?"
  A: {"domain": "general_law", "confidence": 0.9, "alternatives": [["commercial", 0.07]]}
  ```

  Add these three new examples immediately after it (before "Output rules:"):
  ```
  Q: "Draft a will for a 10 million estate and properties"
  A: {"domain": "general_law", "confidence": 0.92, "alternatives": [["commercial", 0.05]]}

  Q: "UAE inheritance law for expatriate with property in Dubai"
  A: {"domain": "general_law", "confidence": 0.93, "alternatives": [["commercial", 0.04]]}

  Q: "How to register a DIFC will for an estate worth 5 million dirhams"
  A: {"domain": "general_law", "confidence": 0.91, "alternatives": [["commercial", 0.06]]}
  ```

- [ ] **Step 2: Verify the file looks correct**

  Open `backend/core/chat/prompts/domain_classifier.md` and confirm:
  - The 3 new examples appear between the civil claims example and "Output rules:"
  - No existing examples were removed or duplicated

- [ ] **Step 3: Commit**

  ```
  git add backend/core/chat/prompts/domain_classifier.md
  git commit -m "fix(classifier): add wills/inheritance→general_law examples to domain_classifier prompt

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

## Task 2: Add `general_law` keywords to domain_classifier.py

**Files:**
- Modify: `backend/core/chat/domain_classifier.py`
- Modify: `backend/tests/test_fuzzy_domain.py`
- Modify: `backend/tests/test_domain_classifier.py`

- [ ] **Step 1: Write the failing tests**

  In `backend/tests/test_fuzzy_domain.py`, add at the end:

  ```python
  def test_wills_keyword_routes_to_general_law():
      """'wills' must route to GENERAL_LAW, not VAT, even though estate has VAT connotation."""
      result = _fuzzy_classify_query("draft wills for estate and properties")
      assert result is not None
      assert result.domain == DomainLabel.GENERAL_LAW


  def test_inheritance_keyword_routes_to_general_law():
      """'inheritance' must route to GENERAL_LAW."""
      result = _fuzzy_classify_query("uae inheritance law for expatriates")
      assert result is not None
      assert result.domain == DomainLabel.GENERAL_LAW


  def test_probate_keyword_routes_to_general_law():
      """'probate' must route to GENERAL_LAW."""
      result = _fuzzy_classify_query("probate process in dubai for non-muslims")
      assert result is not None
      assert result.domain == DomainLabel.GENERAL_LAW


  def test_estate_planning_keyword_routes_to_general_law():
      """'estate planning' multi-word must route to GENERAL_LAW, not VAT."""
      result = _fuzzy_classify_query("estate planning for high net worth individuals")
      assert result is not None
      assert result.domain == DomainLabel.GENERAL_LAW
  ```

  In `backend/tests/test_domain_classifier.py`, add at the end:

  ```python
  @pytest.mark.asyncio
  async def test_classify_wills_query_returns_general_law():
      """LLM path: 'Draft Wills for 10M Estate' must classify as general_law."""
      fake_json = '{"domain": "general_law", "confidence": 0.92, "alternatives": [["commercial", 0.05]]}'
      with patch("core.chat.domain_classifier._llm_complete", new=AsyncMock(return_value=fake_json)):
          r = await classify_domain("Draft Wills for 10 Million Estate and Properties")
      assert r.domain == DomainLabel.GENERAL_LAW
      assert r.confidence > 0.80


  def test_wills_keyword_fallback_not_vat():
      """Keyword fallback: 'wills' must NOT classify as VAT even though properties is mentioned."""
      from core.chat.domain_classifier import _fuzzy_classify_query
      result = _fuzzy_classify_query("draft wills for estate")
      # After the fix, this must be GENERAL_LAW (or None — not VAT)
      assert result is None or result.domain == DomainLabel.GENERAL_LAW
  ```

- [ ] **Step 2: Run the tests — confirm they fail**

  ```
  cd backend
  python -m pytest tests/test_fuzzy_domain.py::test_wills_keyword_routes_to_general_law tests/test_fuzzy_domain.py::test_inheritance_keyword_routes_to_general_law tests/test_fuzzy_domain.py::test_probate_keyword_routes_to_general_law tests/test_fuzzy_domain.py::test_estate_planning_keyword_routes_to_general_law tests/test_domain_classifier.py::test_wills_keyword_fallback_not_vat -v
  ```

  Expected: **FAIL** — `_fuzzy_classify_query("draft wills for estate and properties")` currently returns `None` or wrong domain.

- [ ] **Step 3: Add `general_law` to `_DOMAIN_KEYWORDS` in `domain_classifier.py`**

  Open `backend/core/chat/domain_classifier.py`. Find `_DOMAIN_KEYWORDS = {`. After the `"ifrs"` entry and before the closing `}`, add:

  ```python
      "general_law": [
          "wills", "will and testament", "inheritance", "inherit",
          "probate", "testator", "beneficiary", "estate planning",
          "succession", "guardian appointment",
      ],
  ```

  The full `_DOMAIN_KEYWORDS` block should now look like:

  ```python
  _DOMAIN_KEYWORDS: dict[str, list[str]] = {
      "vat": [
          "vat", "value added tax", "tax invoice", "input tax", "output tax",
          "zero rating", "hotel apartment", "commercial property", "trn",
          "reverse charge", "excise", "zero rated", "exempt supply",
      ],
      "corporate_tax": [
          "corporate tax", "corporate", "ct", "qualifying income", "free zone",
          "transfer pricing", "permanent establishment", "withholding tax",
          "corporate income", "taxable income", "small business relief",
      ],
      "peppol": [
          "peppol", "peppol bis", "peppol network", "access point", "peppol id",
      ],
      "e_invoicing": [
          "e-invoice", "einvoice", "electronic invoice", "e invoicing",
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
      "general_law": [
          "wills", "will and testament", "inheritance", "inherit",
          "probate", "testator", "beneficiary", "estate planning",
          "succession", "guardian appointment",
      ],
  }
  ```

  The `_FLAT_KEYWORDS_SORTED` list is built automatically from `_DOMAIN_KEYWORDS` and sorted by keyword length descending — "estate planning" (15 chars) and "will and testament" (17 chars) are longer than "vat" (3 chars) and will be checked first.

- [ ] **Step 4: Run the failing tests — confirm they pass**

  ```
  cd backend
  python -m pytest tests/test_fuzzy_domain.py::test_wills_keyword_routes_to_general_law tests/test_fuzzy_domain.py::test_inheritance_keyword_routes_to_general_law tests/test_fuzzy_domain.py::test_probate_keyword_routes_to_general_law tests/test_fuzzy_domain.py::test_estate_planning_keyword_routes_to_general_law tests/test_domain_classifier.py::test_wills_keyword_fallback_not_vat -v
  ```

  Expected: **PASS** for all 5 tests.

- [ ] **Step 5: Run the full fuzzy domain test suite to check no regressions**

  ```
  cd backend
  python -m pytest tests/test_fuzzy_domain.py tests/test_domain_classifier.py -v
  ```

  Expected: All existing tests still pass (none removed).

- [ ] **Step 6: Commit**

  ```
  git add backend/core/chat/domain_classifier.py backend/tests/test_fuzzy_domain.py backend/tests/test_domain_classifier.py
  git commit -m "fix(classifier): add general_law keywords (wills, inheritance, probate, estate planning)

  Prevents wills/estate queries from being silently routed to vat domain via
  keyword fallback. The sorted-by-length structure ensures multi-word keywords
  like 'estate planning' and 'will and testament' match before shorter vat terms.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

## Task 3: Add broad-search fallback in chat.py

**Files:**
- Modify: `backend/api/chat.py`
- Modify: `backend/tests/test_relevance_rag.py`

- [ ] **Step 1: Write the failing test**

  In `backend/tests/test_relevance_rag.py`, add at the end:

  ```python
  @pytest.mark.asyncio
  async def test_broad_fallback_triggered_when_domain_filter_returns_low_scores():
      """When domain-filtered RAG results all score < 0.65, broad fallback must be called."""
      from unittest.mock import AsyncMock, patch, MagicMock
      import json
      from httpx import AsyncClient, ASGITransport
      from main import app

      # Patch rag_engine.search so:
      # - First call (with domain filter {"$and": [..., {"domain": ...}]}) returns low-score results
      # - Second call (broad filter {"category": ...}) returns high-score results
      low_score_result = [{
          "id": "c1", "text": "Electronic devices VAT treatment.",
          "metadata": {"doc_id": "d1", "category": "law", "domain": "vat", "source": "VATP035.pdf"},
          "score": 0.61, "source": "VATP035.pdf",
      }]
      high_score_result = [{
          "id": "c2", "text": "UAE Civil Transactions Law inheritance provisions.",
          "metadata": {"doc_id": "d2", "category": "law", "domain": "general", "source": "Civil_Law.pdf"},
          "score": 0.82, "source": "Civil_Law.pdf",
      }]

      call_count = {"n": 0}
      async def mock_search(query, top_k=8, filter=None, min_score=0.30):
          call_count["n"] += 1
          # First call has domain filter (contains "$and") → return low scores
          if filter and "$and" in str(filter):
              return low_score_result
          # Second call is broad (no domain in filter) → return high scores
          return high_score_result

      with patch("api.chat.rag_engine.search", side_effect=mock_search), \
           patch("api.chat.classify_domain", new=AsyncMock(return_value=MagicMock(
               domain=MagicMock(value="vat"), confidence=0.85, alternatives=[],
               model_dump=lambda: {"domain": "vat", "confidence": 0.85, "alternatives": []}
           ))), \
           patch("api.chat.classify_intent", new=AsyncMock(return_value=MagicMock(
               output_type="draft", topic="wills"
           ))), \
           patch("api.chat.get_llm_provider") as mock_llm_factory:

          mock_llm = MagicMock()
          mock_llm.chat_stream = AsyncMock(return_value=aiter_strings(["Here is the will draft..."]))
          mock_llm.compute_safe_max_tokens = MagicMock(return_value=1000)
          mock_llm_factory.return_value = mock_llm

          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
              async with ac.stream("POST", "/api/chat/stream", json={
                  "message": "Draft Wills for 10 Million Estate and Properties",
                  "stream": True,
                  "use_rag": True,
                  "mode": "fast",
              }) as resp:
                  body = ""
                  async for line in resp.aiter_lines():
                      body += line + "\n"

      # Fallback must have been triggered (2 search calls total)
      assert call_count["n"] >= 2, f"Expected fallback search, got {call_count['n']} calls"
      # The sources in the final response must come from the broad search (Civil_Law.pdf)
      source_events = [line for line in body.split("\n") if '"sources"' in line]
      assert any("Civil_Law.pdf" in s for s in source_events), (
          f"Expected Civil_Law.pdf in sources after fallback, got: {source_events}"
      )


  def aiter_strings(strings):
      """Async generator helper for mock streaming."""
      async def _gen():
          for s in strings:
              yield s
      return _gen()
  ```

- [ ] **Step 2: Run the test — confirm it fails**

  ```
  cd backend
  python -m pytest tests/test_relevance_rag.py::test_broad_fallback_triggered_when_domain_filter_returns_low_scores -v
  ```

  Expected: **FAIL** — `call_count["n"]` will be 1 (no fallback call yet).

- [ ] **Step 3: Add the `_BROAD_FALLBACK_THRESHOLD` constant in chat.py**

  Open `backend/api/chat.py`. Find the block of module-level constants (around line 44–59, near `_DOMAIN_FILTER_MIN_CONFIDENCE`). After `_DOMAIN_FILTER_MIN_CONFIDENCE`, add:

  ```python
  # If the top RAG result scores below this after domain filtering, retry with a broad
  # category-only search (no domain restriction) to prevent misleading irrelevant sources.
  _BROAD_FALLBACK_THRESHOLD: float = 0.65
  ```

- [ ] **Step 4: Add fallback logic to the STREAMING path in chat.py**

  In the streaming `generate()` function, find the block that ends with:
  ```python
                  except Exception as _rag_exc:
                      logger.warning("RAG search failed, falling back to no-context mode: %s", _rag_exc)
                      _search_results = []

                  logger.info("RAG returned %d results for conversation %s", len(_search_results), conversation.id)
  ```

  Replace that `logger.info(...)` line and insert the fallback immediately after `_search_results = []` (inside the `if req.use_rag:` block, after the try/except):

  ```python
                  except Exception as _rag_exc:
                      logger.warning("RAG search failed, falling back to no-context mode: %s", _rag_exc)
                      _search_results = []

                  # Adaptive fallback: if domain-filtered results are poor, retry with broad search
                  if (
                      _rag_filter and not _doc_scoped
                      and _search_results
                      and max(r.get("score", 0) for r in _search_results) < _BROAD_FALLBACK_THRESHOLD
                  ):
                      _top_score = max(r.get("score", 0) for r in _search_results)
                      logger.info(
                          "RAG domain-filtered results below threshold %.2f (top=%.3f) — retrying with broad search",
                          _BROAD_FALLBACK_THRESHOLD, _top_score,
                      )
                      _broad_filter: dict = {"category": {"$in": ["law", "finance"]}}
                      try:
                          _broad_results = await rag_engine.search(
                              req.message,
                              top_k=settings.fast_top_k if req.mode == "fast" else settings.top_k_results,
                              filter=_broad_filter,
                              min_score=settings.rag_min_score,
                          )
                          if _broad_results and max(r.get("score", 0) for r in _broad_results) > _top_score:
                              _search_results = _broad_results
                              logger.info(
                                  "Broad fallback improved results — now using %d chunks (top=%.3f)",
                                  len(_search_results),
                                  max(r.get("score", 0) for r in _search_results),
                              )
                      except Exception as _fb_exc:
                          logger.warning("Broad fallback search failed (non-fatal): %s", _fb_exc)

                  logger.info("RAG returned %d results for conversation %s", len(_search_results), conversation.id)
  ```

- [ ] **Step 5: Add fallback logic to the NON-STREAMING path in chat.py**

  In the non-streaming path, find the block:
  ```python
          except Exception as rag_exc:
              logger.warning(f"RAG search failed, falling back to no-context mode: {rag_exc}")
              search_results = []

          # No-LLM guard: doc-scoped query with zero chunks → honest refusal
          _doc_scoped_ns = req.mode == "analyst" and bool(req.selected_doc_ids)
  ```

  Add the fallback between those blocks:

  ```python
          except Exception as rag_exc:
              logger.warning(f"RAG search failed, falling back to no-context mode: {rag_exc}")
              search_results = []

          # Adaptive fallback: if domain-filtered results are poor, retry with broad search
          _doc_scoped_ns = req.mode == "analyst" and bool(req.selected_doc_ids)
          if (
              rag_filter and not _doc_scoped_ns
              and search_results
              and max(r.get("score", 0) for r in search_results) < _BROAD_FALLBACK_THRESHOLD
          ):
              _top_score_ns = max(r.get("score", 0) for r in search_results)
              logger.info(
                  "RAG domain-filtered results below threshold %.2f (top=%.3f) — retrying with broad search",
                  _BROAD_FALLBACK_THRESHOLD, _top_score_ns,
              )
              _broad_filter_ns: dict = {"category": {"$in": ["law", "finance"]}}
              try:
                  _broad_results_ns = await rag_engine.search(
                      req.message,
                      top_k=settings.fast_top_k if req.mode == "fast" else settings.top_k_results,
                      filter=_broad_filter_ns,
                      min_score=settings.rag_min_score,
                  )
                  if _broad_results_ns and max(r.get("score", 0) for r in _broad_results_ns) > _top_score_ns:
                      search_results = _broad_results_ns
                      logger.info(
                          "Broad fallback improved results — now using %d chunks (top=%.3f)",
                          len(search_results),
                          max(r.get("score", 0) for r in search_results),
                      )
              except Exception as _fb_exc_ns:
                  logger.warning("Broad fallback search failed (non-fatal): %s", _fb_exc_ns)

          # No-LLM guard: doc-scoped query with zero chunks → honest refusal
  ```

  Note: Remove the separate `_doc_scoped_ns = req.mode == "analyst" and bool(req.selected_doc_ids)` line that was originally before "No-LLM guard" since we now set it inside the fallback block above. Make sure `_doc_scoped_ns` is not defined twice.

- [ ] **Step 6: Run the failing test — confirm it now passes**

  ```
  cd backend
  python -m pytest tests/test_relevance_rag.py::test_broad_fallback_triggered_when_domain_filter_returns_low_scores -v
  ```

  Expected: **PASS**

- [ ] **Step 7: Run the full test suite for chat and RAG tests**

  ```
  cd backend
  python -m pytest tests/test_relevance_rag.py tests/test_chat_endpoint_domain.py tests/test_chat_sources.py tests/test_category_isolation.py tests/test_no_llm_guard.py -v
  ```

  Expected: All pass. Pay attention to any tests that assert `rag_engine.search` is called exactly once — those may need updating to allow a second call.

- [ ] **Step 8: Commit**

  ```
  git add backend/api/chat.py backend/tests/test_relevance_rag.py
  git commit -m "feat(chat): add broad-search fallback when domain-filtered RAG scores < 0.65

  When a domain filter is applied (e.g. vat) but the top result scores below
  _BROAD_FALLBACK_THRESHOLD (0.65), automatically retry with a category-only
  filter across all law+finance documents. Only replaces results if the broad
  search finds strictly better results (higher top score).

  Applied to both streaming and non-streaming paths.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

## Task 4: Add low-confidence label in chat_history_viewer.py

**Files:**
- Modify: `chat_history_viewer.py`

- [ ] **Step 1: Find and update the source display block**

  Open `chat_history_viewer.py`. Find this block (around line 250):

  ```python
                      score_str = f"  score={score:.3f}" if score is not None else ""
                      domain_str = f"  [{domain}]" if domain else ""
                      print(c("gray", f"    {j}. {name}{domain_str}{score_str}"))
  ```

  Replace it with:

  ```python
                      score_str = f"  score={score:.3f}" if score is not None else ""
                      if score is not None and score < 0.65:
                          score_str += c("yellow", "  ⚠️ low-confidence")
                      domain_str = f"  [{domain}]" if domain else ""
                      print(c("gray", f"    {j}. {name}{domain_str}{score_str}"))
  ```

- [ ] **Step 2: Verify manually**

  Run the viewer against your database:
  ```
  python chat_history_viewer.py --list
  ```
  Then open the conversation with the wills query. Sources with score < 0.65 should now show `⚠️ low-confidence` in yellow.

- [ ] **Step 3: Commit**

  ```
  git add chat_history_viewer.py
  git commit -m "feat(viewer): add ⚠️ low-confidence label for RAG sources scoring < 0.65

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

## Task 5: Smoke test end-to-end

- [ ] **Step 1: Run the full backend test suite**

  ```
  cd backend
  python -m pytest tests/ -v --tb=short -q 2>&1 | tail -30
  ```

  Expected: All previously passing tests continue to pass. The new tests all pass.

- [ ] **Step 2: Manual smoke test (if backend is running)**

  If the backend is running at `http://localhost:8000`, send a test chat:
  ```
  curl -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Draft Wills for 10 Million Estate and Properties", "use_rag": true, "mode": "fast"}' 
  ```

  Verify in the response `sources` array:
  - Sources come from `category: "law"` documents (e.g., Civil Transactions Law, family company)
  - No `VATP035` or Electronic Devices documents appear
  - Source scores are ≥ 0.65

- [ ] **Step 3: Final commit (if any cleanup needed)**

  ```
  git add -A
  git commit -m "chore: finalize adaptive RAG retrieval for general-law queries

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```
