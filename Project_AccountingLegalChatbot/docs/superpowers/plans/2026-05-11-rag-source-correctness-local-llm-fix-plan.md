# RAG Source Correctness + Local LLM Hallucination Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs: (1) E-invoicing queries return irrelevant sources due to domain misclassification; (2) Local LLMs (Ollama/LM Studio) hallucinate instead of answering from RAG context.

**Architecture:** `/api/debug/rag-inspect` diagnostic endpoint; Layer 1 exact e-invoicing keyword match before fuzzy/LLM; local LLM context truncation (max 3-5 chunks) via helper functions in llm_manager.py.

**Tech Stack:** Python 3.11+, FastAPI, pytest, httpx, ChromaDB, SQLite (GraphRAG)

---

## Confirmed Root Causes (from code analysis)

**Bug 1 — Wrong sources:**
- Domain classifier runs fuzzy matching then LLM classification, but `e-invoicing`, `DCTCE`, `243&244` may slip through and get classified as `commercial` or `general_law`
- `_DOMAIN_TO_DOC_DOMAINS` in chat.py already maps e_invoicing → [e_invoicing, peppol, vat, general] — this is fine
- Fix: add Layer 1 exact regex match before fuzzy/LLM so e-invoicing queries are caught with 0.9 confidence

**Bug 2 — Local LLM hallucination:**
- `build_augmented_prompt()` concatenates all RAG chunks into the system prompt
- For local 14B-32B models, this can overflow context windows or drown the instruction in noise
- Fix: add context truncation helpers in `llm_manager.py`, apply in chat.py streaming + non-streaming paths
- Do NOT add simplified system prompt — context truncation alone is sufficient per user decision

**Not root causes (per codebase analysis):**
- `rag_engine.py` does NOT have `compute_safe_max_tokens()` — removing from plan
- `config.py` does NOT need modification — `compute_llm_params()` already exists
- `build_local_system_suffix()` is dead code — not added to plan
- Task 4 (debug logging) is merged into Task 3 — no separate task needed

---

## File Map

| File | Action |
|---|---|
| `backend/api/debug.py` | **Create** — `/api/debug/rag-inspect` diagnostic endpoint |
| `backend/main.py` | **Modify** — register debug router (1 import + 1 router line) |
| `backend/tests/api/test_debug_endpoint.py` | **Create** — tests for debug endpoint |
| `backend/core/chat/domain_classifier.py` | **Modify** — Layer 1 exact regex for e-invoicing |
| `backend/tests/test_domain_classifier_einvoicing.py` | **Create** — Layer 1 tests |
| `backend/core/llm_manager.py` | **Modify** — `is_local_provider`, `truncate_for_local_model` helpers |
| `backend/tests/test_local_llm_context.py` | **Create** — local context truncation tests |
| `backend/api/chat.py` | **Modify** — apply truncation + debug logging (Tasks 3 & 4 merged) |

---

## Task 1: `/api/debug/rag-inspect` Diagnostic Endpoint

**Files:**
- Create: `backend/api/debug.py`
- Modify: `backend/main.py`
- Test: `backend/tests/api/test_debug_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_debug_endpoint.py`:

```python
"""Tests for /api/debug/rag-inspect endpoint."""
import pytest


@pytest.mark.asyncio
async def test_debug_endpoint_returns_200(client):
    r = await client.post("/api/debug/rag-inspect", json={"query": "What is UAE e-invoicing?"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_debug_response_contains_pipeline_fields(client):
    r = await client.post("/api/debug/rag-inspect", json={"query": "e-invoicing UAE"})
    assert r.status_code == 200
    data = r.json()
    assert "effective_domain" in data
    assert "domain_classifier_confidence" in data
    assert "rag_filter_applied" in data
    assert "top_rag_results" in data
    assert isinstance(data["top_rag_results"], list)


@pytest.mark.asyncio
async def test_debug_domain_override(client):
    r = await client.post(
        "/api/debug/rag-inspect",
        json={"query": "e-invoicing", "domain_override": "vat"}
    )
    assert r.status_code == 200
    assert r.json()["effective_domain"] == "vat"


@pytest.mark.asyncio
async def test_debug_includes_context_info(client):
    r = await client.post("/api/debug/rag-inspect", json={"query": "corporate tax UAE"})
    data = r.json()
    assert "context_size_estimate_tokens" in data
    assert "context_safe_for_local_llm" in data
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/api/test_debug_endpoint.py -v 2>&1 | head -10
```
Expected: `404 NOT FOUND` or `ImportError`.

- [ ] **Step 3: Create `backend/api/debug.py`**

```python
"""
RAG Diagnostic Endpoint — inspects the full RAG pipeline decision tree for any query.
Diagnostic only: bypasses the LLM, returns domain + filter + results + context size.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.rag_engine import rag_engine, _normalize_chunk
from core.chat.domain_classifier import classify_domain, ClassifierResult, DomainLabel
from core.rag.hybrid_retriever import HybridRetriever
from core.rag.graph_rag import GraphRAG
from core.prompt_router import route_prompt
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["Debug"])

_DOMAIN_TO_DOC_DOMAINS: dict[str, list[str]] = {
    "e_invoicing": ["e_invoicing", "peppol", "vat", "general"],
    "vat": ["vat", "e_invoicing", "general"],
    "peppol": ["peppol", "e_invoicing", "vat", "general"],
    "corporate_tax": ["corporate_tax", "general"],
    "labour": ["labour", "general"],
    "commercial": ["commercial", "general"],
    "ifrs": ["ifrs", "general"],
    "general_law": ["general_law", "general"],
    "general": [],
    "": [],
}

_LAW_DOMAINS = {"general_law", "commercial", "labour", "e_invoicing", "peppol"}
_LOCAL_MAX_TOKENS = {"ollama": 6_000, "lmstudio": 8_000, "local": 8_000}


class RagInspectRequest(BaseModel):
    query: str
    domain_override: str | None = None


@router.post("/rag-inspect")
async def rag_inspect(req: RagInspectRequest):
    """Inspect RAG pipeline: domain, filter, results, context size. No LLM call."""
    # 1. Domain classification
    if req.domain_override:
        try:
            domain_label = DomainLabel(req.domain_override)
            classifier_result = ClassifierResult(domain=domain_label, confidence=1.0, alternatives=[])
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown domain: {req.domain_override!r}")
    else:
        classifier_result = await classify_domain(req.query)

    effective_domain = classifier_result.domain.value

    # 2. Build RAG filter
    doc_domains = _DOMAIN_TO_DOC_DOMAINS.get(effective_domain, [])
    if doc_domains:
        rag_filter = {"$and": [{"domain": {"$in": doc_domains}}, {"category": {"$in": ["law", "finance"]}}]}
    else:
        rag_filter = {"category": {"$in": ["law", "finance"]}}

    filter_explanation = (
        f"domain={effective_domain} → doc_domains {doc_domains}"
        if doc_domains
        else f"domain={effective_domain} → broad (no domain filter)"
    )

    # 3. RAG search
    graph_rag = GraphRAG(str(settings.graph_store_dir) / "graph.db")
    hybrid = HybridRetriever(rag_engine=rag_engine, graph_rag=graph_rag)
    try:
        rag_results_raw = await hybrid.retrieve(query=req.query, top_k=8, rag_filter=rag_filter)
    except Exception as exc:
        logger.warning("RAG search failed in debug endpoint: %s", exc)
        rag_results_raw = []

    # 4. Build top results
    top_results = []
    for r in rag_results_raw[:8]:
        norm = _normalize_chunk(r)
        top_results.append({
            "rank": len(top_results) + 1,
            "source_file": norm["source_file"],
            "domain": r.get("metadata", {}).get("domain", "unknown"),
            "score": round(r.get("score", 0.0), 3),
            "combined_score": round(r.get("combined_score", r.get("score", 0.0)), 3),
            "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
        })

    # 5. Context size estimate
    system_prompt = route_prompt(classifier_result.domain)
    rag_chars = sum(len(r["text"]) for r in rag_results_raw[:8])
    total_chars = len(system_prompt) + rag_chars + len(req.query)
    context_estimate = total_chars // 3
    max_local = max(_LOCAL_MAX_TOKENS.values())
    context_safe = context_estimate < max_local

    # 6. Web search trigger check
    is_law_domain = effective_domain in _LAW_DOMAINS
    no_rag = len(rag_results_raw) == 0
    web_triggered = no_rag and not is_law_domain
    web_reason = None
    if web_triggered:
        web_reason = "No RAG results + non-law domain → web search would be triggered"

    return {
        "query": req.query,
        "effective_domain": effective_domain,
        "domain_classifier_confidence": classifier_result.confidence,
        "domain_classifier_alternatives": [
            [alt.value, score] for alt, score in classifier_result.alternatives
        ],
        "rag_filter_applied": rag_filter,
        "rag_filter_applied_explanation": filter_explanation,
        "rag_results_count": len(rag_results_raw),
        "top_rag_results": top_results,
        "web_search_triggered": web_triggered,
        "web_search_reason": web_reason,
        "context_size_estimate_tokens": context_estimate,
        "context_safe_for_local_llm": context_safe,
    }
```

- [ ] **Step 4: Register router in `backend/main.py`**

After line 222 (existing imports section):
```python
from api.debug import router as debug_router
```

After line 236 (existing router registrations):
```python
app.include_router(debug_router)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/api/test_debug_endpoint.py -v
```
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/backend/api/debug.py Project_AccountingLegalChatbot/backend/main.py Project_AccountingLegalChatbot/backend/tests/api/test_debug_endpoint.py
git commit -m "feat(debug): add /api/debug/rag-inspect — RAG pipeline diagnostic endpoint

Co-authored-by: Claude <noreply@anthropic.com>"
```

---

## Task 2: E-invoicing Layer 1 Exact Keyword Match

**Files:**
- Modify: `backend/core/chat/domain_classifier.py`
- Test: `backend/tests/test_domain_classifier_einvoicing.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_domain_classifier_einvoicing.py`:

```python
"""Tests for Layer 1 e-invoicing exact keyword classification."""
import pytest
from core.chat.domain_classifier import classify_domain, _layer1_einvoicing_match


class TestLayer1EinvoicingMatch:
    def test_einvoice_hyphenated(self):
        result = _layer1_einvoicing_match("e-invoicing UAE requirements")
        assert result is not None
        assert result.domain.value == "e_invoicing"
        assert result.confidence == 0.9

    def test_einvoice_no_hyphen(self):
        result = _layer1_einvoicing_match("einvoice mandate uae")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_electronic_invoice(self):
        result = _layer1_einvoicing_match("electronic invoice DCTCE format")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_dctce_alone(self):
        result = _layer1_einvoicing_match("what does DCTCE format require")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_peppol_bis(self):
        result = _layer1_einvoicing_match("peppol bis AE access point")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_243_244_numbers(self):
        result = _layer1_einvoicing_match("UAE cabinet decision 243 and 244 e-invoicing")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_no_match_returns_none(self):
        result = _layer1_einvoicing_match("what is the VAT rate on hotel apartments")
        assert result is None

    def test_result_conforms_to_classifier_result(self):
        result = _layer1_einvoicing_match("electronic invoice uae")
        assert result is not None
        assert hasattr(result, "domain")
        assert hasattr(result, "confidence")
        assert hasattr(result, "alternatives")


@pytest.mark.asyncio
async def test_classify_domain_einvoice_via_layer1():
    """classify_domain() hits Layer 1 for e-invoicing queries."""
    result = await classify_domain("e-invoicing DCTCE requirements UAE")
    assert result.domain.value == "e_invoicing"
    assert result.confidence >= 0.9

    result2 = await classify_domain("electronic invoice mandate uae")
    assert result2.domain.value == "e_invoicing"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_domain_classifier_einvoicing.py -v 2>&1 | head -10
```
Expected: `ImportError` — `_layer1_einvoicing_match` doesn't exist yet.

- [ ] **Step 3: Read existing domain_classifier.py**

```bash
cat /Users/armaan/chatbot_local/Project_AccountingLegalChatbot/backend/core/chat/domain_classifier.py
```

- [ ] **Step 4: Add `import re`**

Add `import re` after the existing `from pydantic import BaseModel` import (line 8).

- [ ] **Step 5: Add Layer 1 function after `_FUZZY_STOPWORDS` definition (after line 41)**

```python
# ── Layer 1: Exact e-invoicing keyword match (runs before fuzzy + LLM) ──────
_EINVOICING_PATTERN = re.compile(
    r'\b(e-?invoic(e|ing|ed|er|ees?)|electronic\s+invoice|dctce|peppol\s*bis)\b',
    re.IGNORECASE,
)
_EINVOICING_NUMBERS = re.compile(
    r'\b(?:243|244|243\s*&\s*244|243\s*and\s*244)\b',
    re.IGNORECASE,
)


def _layer1_einvoicing_match(query: str) -> "ClassifierResult | None":
    """Return ClassifierResult if query matches e-invoicing keywords at Layer 1.

    Layer 1 runs before fuzzy matching and LLM classification.
    Returns None if no e-invoicing keyword is found.
    """
    if _EINVOICING_PATTERN.search(query) or _EINVOICING_NUMBERS.search(query):
        return ClassifierResult(
            domain=DomainLabel.E_INVOICING,
            confidence=0.9,
            alternatives=[],
        )
    return None
```

- [ ] **Step 6: Modify `classify_domain()` — add Layer 1 call at top of function**

Read the file, then find `async def classify_domain(query: str) -> ClassifierResult:` and add the Layer 1 check as the first step before fuzzy and LLM:

```python
async def classify_domain(query: str) -> ClassifierResult:
    """Classify a user query into a UAE domain."""
    # Layer 1: exact e-invoicing keywords (highest priority, no LLM needed)
    layer1 = _layer1_einvoicing_match(query)
    if layer1 is not None:
        return layer1

    # Layer 2: fuzzy keyword matching
    fuzzy = _fuzzy_classify_query(query)
    if fuzzy is not None:
        return fuzzy

    # Layer 3: LLM classification (fallback)
    # ... rest of existing function unchanged ...
```

- [ ] **Step 7: Run test — verify it passes**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_domain_classifier_einvoicing.py -v
```
Expected: `9 passed`

- [ ] **Step 8: Commit**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/backend/core/chat/domain_classifier.py Project_AccountingLegalChatbot/backend/tests/test_domain_classifier_einvoicing.py
git commit -m "feat(domain): add Layer 1 exact e-invoicing keyword classifier — 0.9 confidence before LLM

Co-authored-by: Claude <noreply@anthropic.com>"
```

---

## Task 3: Local LLM Context Truncation (Tasks 3 + 4 merged)

**Files:**
- Modify: `backend/core/llm_manager.py` — add helpers
- Modify: `backend/api/chat.py` — apply truncation + debug logging
- Test: `backend/tests/test_local_llm_context.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_local_llm_context.py`:

```python
"""Tests for local LLM context truncation helpers."""
import pytest
from core.llm_manager import is_local_provider, truncate_for_local_model


class TestIsLocalProvider:
    def test_ollama_is_local(self):
        assert is_local_provider("ollama") is True

    def test_lmstudio_is_local(self):
        assert is_local_provider("lmstudio") is True

    def test_local_is_local(self):
        assert is_local_provider("local") is True

    def test_nvidia_not_local(self):
        assert is_local_provider("nvidia") is False

    def test_openai_not_local(self):
        assert is_local_provider("openai") is False


class TestTruncateForLocalModel:
    def _chunks(self, n: int):
        return [{"text": f"chunk {i} " * 100, "chunk_id": str(i)} for i in range(n)]

    def test_ollama_max_3_chunks(self):
        result = truncate_for_local_model(self._chunks(10), "ollama")
        assert len(result) <= 3

    def test_lmstudio_max_5_chunks(self):
        result = truncate_for_local_model(self._chunks(10), "lmstudio")
        assert len(result) <= 5

    def test_preserves_top_ranked(self):
        result = truncate_for_local_model(self._chunks(5), "ollama")
        assert result[0]["chunk_id"] == "0"

    def test_cloud_no_truncation(self):
        result = truncate_for_local_model(self._chunks(10), "nvidia")
        assert len(result) == 10

    def test_empty_list(self):
        result = truncate_for_local_model([], "ollama")
        assert result == []
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_local_llm_context.py -v 2>&1 | head -10
```
Expected: `ImportError`.

- [ ] **Step 3: Add helper functions to `backend/core/llm_manager.py`**

Add at the **end** of `llm_manager.py` (after `list_available_providers`):

```python
# ── Local LLM context safety helpers ────────────────────────────────────────
_LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio", "local"})


def is_local_provider(provider_name: str) -> bool:
    """Return True if provider is a local inference server (Ollama/LM Studio)."""
    return provider_name.lower() in _LOCAL_PROVIDERS


def truncate_for_local_model(
    chunks: list[dict],
    provider_name: str,
) -> list[dict]:
    """Truncate chunk list for local models with smaller context windows.

    - ollama: max 3 chunks
    - lmstudio/local: max 5 chunks
    - cloud providers: no truncation (return all)
    """
    name = provider_name.lower()
    if name == "ollama":
        return chunks[:3]
    if name in ("lmstudio", "local"):
        return chunks[:5]
    return chunks
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_local_llm_context.py -v
```
Expected: `8 passed`

- [ ] **Step 5: Apply truncation in `backend/api/chat.py` — streaming path**

Read `chat.py` lines 845-860, then add truncation AFTER `_search_results` is populated and BEFORE `_msgs` is built.

Add this block right before line 849 (`_msgs: list[dict] = []`):

```python
            # ── Local LLM context truncation ──────────────────────────────────────
            _local_pname = req.provider or settings.llm_provider
            if is_local_provider(_local_pname) and _search_results:
                _orig_count = len(_search_results)
                _search_results = truncate_for_local_model(_search_results, _local_pname)
                logger.info(
                    "Local LLM context truncation [%s]: %d → %d chunks",
                    _local_pname, _orig_count, len(_search_results),
                )
```

- [ ] **Step 6: Apply truncation in `backend/api/chat.py` — non-streaming path**

Read `chat.py` lines 1315-1330, then add truncation AFTER `search_results` is populated and BEFORE `_msgs` is built.

Find `if search_results:` around line 1317 and add truncation before it:

```python
            _local_pname_ns = req.provider or settings.llm_provider
            if is_local_provider(_local_pname_ns) and search_results:
                _orig = len(search_results)
                search_results = truncate_for_local_model(search_results, _local_pname_ns)
                logger.info(
                    "Local LLM context truncation [%s]: %d → %d chunks (non-stream)",
                    _local_pname_ns, _orig, len(search_results),
                )
```

- [ ] **Step 7: Add debug logging for RAG results (merged from original Task 4)**

Add this log AFTER the existing `logger.info("RAG returned %d results for conversation %s", ...)` around line 828:

```python
            _top_sources = [
                r.get("source") or r["metadata"].get("original_name", "?")
                for r in _search_results[:5]
            ]
            _top_scores = [round(r.get("score", 0.0), 3) for r in _search_results[:5]]
            _top_domains = [r.get("metadata", {}).get("domain", "?") for r in _search_results[:5]]
            logger.info(
                "RAG pipeline: domain=%s confidence=%.2f results=%d "
                "top_sources=%s top_scores=%s provider=%s",
                _cls.domain.value, _cls.confidence, len(_search_results),
                _top_sources[:3], _top_scores[:3], _local_pname,
            )
```

- [ ] **Step 8: Add import at top of `chat.py`**

Find the `from core.llm_manager import get_llm_provider` line (line 21) and add `is_local_provider, truncate_for_local_model`:

```python
from core.llm_manager import get_llm_provider, is_local_provider, truncate_for_local_model
```

- [ ] **Step 9: Verify backend starts**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -c "from api import chat; print('chat.py OK')" 2>&1
```

- [ ] **Step 10: Run full test suite**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/ -x -q 2>&1 | tail -10
```
Expected: All previously passing tests still pass.

- [ ] **Step 11: Commit**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/backend/core/llm_manager.py Project_AccountingLegalChatbot/backend/api/chat.py Project_AccountingLegalChatbot/backend/tests/test_local_llm_context.py
git commit -m "feat(llm): add local LLM context truncation + debug logging — ollama max 3 chunks, lmstudio max 5 chunks

Co-authored-by: Claude <noreply@anthropic.com>"
```

---

## Task 4: End-to-End Verification

- [ ] **Step 1: Start backend and test debug endpoint**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m uvicorn main:app --port 8002 --reload &
sleep 5
curl -s -X POST http://localhost:8002/api/debug/rag-inspect \
  -H 'Content-Type: application/json' \
  -d '{"query": "e-invoicing UAE DCTCE requirements"}' | python3 -m json.tool
```

Expected: `effective_domain: "e_invoicing"`, `domain_classifier_confidence: 0.9`, RAG results from e_invoicing docs.

- [ ] **Step 2: Test via UI — NVIDIA provider**

Ask about e-invoicing. Verify sources are UAE e-invoicing documents, not AML/tax evasion.

- [ ] **Step 3: Test via UI — Ollama provider**

Same question with Ollama. Verify answer cites actual RAG sources, not hallucinated content.

- [ ] **Step 4: Run full test suite**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```
Expected: All tests pass.

- [ ] **Step 5: Final commit + push**

```bash
cd ~/chatbot_local
git add -A
git commit -m "chore: RAG source correctness + local LLM hallucination fixes — all tasks complete

- /api/debug/rag-inspect diagnostic endpoint
- Layer 1 e-invoicing exact keyword classifier (0.9 confidence)
- Local LLM context truncation (ollama: 3 chunks, lmstudio: 5 chunks)
- Debug logging in chat pipeline

Co-authored-by: Claude <noreply@anthropic.com>"
git push origin main
```