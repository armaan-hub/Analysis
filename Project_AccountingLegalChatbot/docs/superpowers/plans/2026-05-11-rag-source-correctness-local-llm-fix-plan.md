# RAG Source Correctness + Local LLM Hallucination Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs: (1) E-invoicing queries return irrelevant sources due to domain misclassification; (2) Local LLMs (Ollama/LM Studio) hallucinate instead of answering from RAG context.

**Architecture:** Three-layer e-invoicing classifier (exact keyword → fuzzy → LLM); `/api/debug/rag-inspect` diagnostic endpoint; local LLM context truncation + simplified system prompt; enhanced debug logging in chat pipeline.

**Tech Stack:** Python 3.11+, FastAPI, pytest, httpx, ChromaDB, SQLite (GraphRAG)

---

## File Map

| File | Action |
|---|---|
| `backend/api/debug.py` | **Create** — `/api/debug/rag-inspect` diagnostic endpoint |
| `backend/main.py` | **Modify** — register debug router |
| `backend/tests/api/test_debug_endpoint.py` | **Create** — tests for debug endpoint |
| `backend/core/chat/domain_classifier.py` | **Modify** — Layer 1 exact keyword for e-invoicing |
| `backend/tests/test_domain_classifier_einvoicing.py` | **Create** — tests for Layer 1 e-invoicing keywords |
| `backend/core/llm_manager.py` | **Modify** — local model context truncation helpers |
| `backend/tests/test_local_llm_context.py` | **Create** — tests for local LLM context safety |
| `backend/api/chat.py` | **Modify** — enhanced debug logging |

---

## Task 1: `/api/debug/rag-inspect` Diagnostic Endpoint

**Files:**
- Create: `backend/api/debug.py`
- Modify: `backend/main.py:222-236`
- Test: `backend/tests/api/test_debug_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_debug_endpoint.py`:

```python
"""Tests for /api/debug/rag-inspect endpoint."""
import pytest


@pytest.mark.asyncio
async def test_debug_endpoint_returns_200(client):
    """POST /api/debug/rag-inspect returns 200 with a valid query."""
    r = await client.post("/api/debug/rag-inspect", json={"query": "What is UAE e-invoicing?"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_debug_endpoint_returns_domain(client):
    """Response includes domain, confidence, rag_filter, and top results."""
    r = await client.post("/api/debug/rag-inspect", json={"query": "e-invoicing UAE"})
    assert r.status_code == 200
    data = r.json()
    assert "effective_domain" in data
    assert "domain_classifier_confidence" in data
    assert "rag_filter_applied" in data
    assert "top_rag_results" in data
    assert isinstance(data["top_rag_results"], list)


@pytest.mark.asyncio
async def test_debug_endpoint_domain_override(client):
    """domain_override forces a specific domain."""
    r = await client.post(
        "/api/debug/rag-inspect",
        json={"query": "e-invoicing", "domain_override": "vat"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["effective_domain"] == "vat"


@pytest.mark.asyncio
async def test_debug_endpoint_includes_context_size(client):
    """Response includes context_size_estimate_tokens and context_safe_for_local_llm."""
    r = await client.post("/api/debug/rag-inspect", json={"query": "corporate tax UAE"})
    assert r.status_code == 200
    data = r.json()
    assert "context_size_estimate_tokens" in data
    assert "context_safe_for_local_llm" in data
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/api/test_debug_endpoint.py -v 2>&1 | head -20
```
Expected: `ImportError` or `404` — endpoint doesn't exist yet.

- [ ] **Step 3: Create `backend/api/debug.py`**

```python
"""
RAG Diagnostic Endpoint — inspects the full RAG pipeline decision tree for any query.
Used to diagnose wrong-source and hallucination bugs.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine, _normalize_chunk
from core.chat.domain_classifier import classify_domain, ClassifierResult, DomainLabel
from core.rag.hybrid_retriever import HybridRetriever
from core.rag.graph_rag import GraphRAG
from core.web_search import search_web
from core.prompt_router import route_prompt
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["Debug"])

_DOMAIN_TO_DOC_DOMAINS = {
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
_LOCAL_MAX_TOKENS = {
    "ollama": 6_000,
    "lmstudio": 8_000,
    "local": 8_000,
}


class RagInspectRequest(BaseModel):
    query: str
    domain_override: str | None = None


@router.post("/rag-inspect")
async def rag_inspect(req: RagInspectRequest):
    """Inspect the RAG pipeline for a query — returns domain, filter, results, context size."""
    # 1. Domain classification
    if req.domain_override:
        try:
            domain_label = DomainLabel(req.domain_override)
            classifier_result = ClassifierResult(domain=domain_label, confidence=1.0, alternatives=[])
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown domain: {req.domain_override}")
    else:
        classifier_result = await classify_domain(req.message if hasattr(req, "message") else req.query)
        # re-run since req has no message attr — classify_domain takes query directly
        classifier_result = await classify_domain(req.query)

    effective_domain = classifier_result.domain.value

    # 2. RAG filter
    doc_domains = _DOMAIN_TO_DOC_DOMAINS.get(effective_domain, [])
    if doc_domains:
        rag_filter = {"$and": [{"domain": {"$in": doc_domains}}, {"category": {"$in": ["law", "finance"]}}]}
    else:
        rag_filter = {"category": {"$in": ["law", "finance"]}}

    filter_explanation = (
        f"domain={effective_domain} → mapped to doc_domains {doc_domains}"
        if doc_domains
        else f"domain={effective_domain} → broad (no domain filter)"
    )

    # 3. RAG search via hybrid retriever
    graph_rag = GraphRAG(str(settings.graph_store_dir) + "/graph.db")
    hybrid = HybridRetriever(rag_engine=rag_engine, graph_rag=graph_rag)
    try:
        rag_results_raw = await hybrid.retrieve(
            query=req.query,
            top_k=8,
            rag_filter=rag_filter,
        )
    except Exception as exc:
        logger.warning("RAG search failed in debug endpoint: %s", exc)
        rag_results_raw = []

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

    # 4. Context size estimate
    system_prompt = route_prompt(classifier_result.domain)
    rag_context_chars = sum(len(r["text"]) for r in rag_results_raw[:8])
    history_chars = 0  # no history in debug mode
    total_chars = len(system_prompt) + rag_context_chars + history_chars + len(req.query)
    context_estimate = total_chars // 3  # ~3 chars per token

    # Check safety for local models
    max_local = max(_LOCAL_MAX_TOKENS.values())
    context_safe = context_estimate < max_local

    # 5. Web search check
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
        "graph_context_used": False,  # computed separately if needed
        "graph_entities_found": [],
    }
```

- [ ] **Step 4: Register router in `backend/main.py`**

After line 222 (existing imports), add:
```python
from api.debug import router as debug_router
```

After line 236 (existing `app.include_router` calls), add:
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
git commit -m "feat(debug): add /api/debug/rag-inspect endpoint for RAG pipeline diagnostics

Co-authored-by: Claude <noreply@anthropic.com>"
```

---

## Task 2: E-invoicing Layer 1 Exact Keyword Match

**Files:**
- Modify: `backend/core/chat/domain_classifier.py:1-131`
- Test: `backend/tests/test_domain_classifier_einvoicing.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_domain_classifier_einvoicing.py`:

```python
"""Tests for e-invoicing exact keyword classification (Layer 1)."""
import pytest
from core.chat.domain_classifier import classify_domain, _layer1_einvoicing_match


class TestLayer1Einvoicing:
    """Layer 1 exact keyword match for e-invoicing queries."""

    def test_einvoice_hyphenated(self):
        result = _layer1_einvoicing_match("e-invoicing UAE requirements")
        assert result is not None
        assert result.domain.value == "e_invoicing"
        assert result.confidence == 0.9

    def test_einvoice_no_hyphen(self):
        result = _layer1_einvoicing_match("einvoice mandate in uae")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_electronic_invoice(self):
        result = _layer1_einvoicing_match("electronic invoice DCTCE format")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_dctce_format(self):
        result = _layer1_einvoicing_match("what does DCTCE format require")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_peppol_bis_ae(self):
        result = _layer1_einvoicing_match("peppol bis AE access point registration")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_243_244(self):
        result = _layer1_einvoicing_match("UAE e-invoicing cabinet decision 243 and 244")
        assert result is not None
        assert result.domain.value == "e_invoicing"

    def test_no_match_returns_none(self):
        result = _layer1_einvoicing_match("what is the VAT rate on hotel apartments")
        assert result is None

    def test_implements_interface(self):
        """Layer 1 result conforms to ClassifierResult interface."""
        result = _layer1_einvoicing_match("electronic invoice uae")
        assert result is not None
        assert hasattr(result, "domain")
        assert hasattr(result, "confidence")
        assert hasattr(result, "alternatives")
        assert isinstance(result.confidence, float)
        assert isinstance(result.alternatives, list)


@pytest.mark.asyncio
async def test_classify_domain_einvoice_via_layer1():
    """classify_domain() returns e_invoicing for e-invoicing queries (Layer 1 hit)."""
    result = await classify_domain("e-invoicing DCTCE requirements UAE")
    assert result.domain.value == "e_invoicing"
    assert result.confidence >= 0.9

    result2 = await classify_domain("electronic invoice mandate")
    assert result2.domain.value == "e_invoicing"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_domain_classifier_einvoicing.py -v 2>&1 | head -20
```
Expected: `ImportError` or `TypeError` — `_layer1_einvoicing_match` doesn't exist yet.

- [ ] **Step 3: Add Layer 1 function to `backend/core/chat/domain_classifier.py`**

Read the full file first, then add this import and function:

After existing imports (after line 5), add:
```python
import re
```

Add this function AFTER the `_FUZZY_STOPWORDS` definition (after line 41), BEFORE `_word_boundary_match`:

```python
# ── Layer 1: Exact e-invoicing keyword match (highest priority) ─────────────
_EINVOICING_PATTERN = re.compile(
    r'\b(e-?invoic(e|ing|ed|er|ees?)|electronic\s+invoice|dctce|peppol\s*bis)\b',
    re.IGNORECASE,
)
# Numbers 243/244 are UAE e-invoicing cabinet decision references
_EINVOICING_NUMBERS = re.compile(r'\b(?:243|244|243\s*&\s*244|243\s*and\s*244)\b', re.IGNORECASE)


def _layer1_einvoicing_match(query: str) -> "ClassifierResult | None":
    """Return ClassifierResult if query matches e-invoicing keywords at Layer 1.

    Runs before fuzzy matching and LLM classification.
    Returns None if no e-invoicing keyword detected.
    """
    lower = query.lower()
    if _EINVOICING_PATTERN.search(query) or _EINVOICING_NUMBERS.search(query):
        return ClassifierResult(
            domain=DomainLabel.E_INVOICING,
            confidence=0.9,
            alternatives=[],
        )
    return None
```

Now modify `classify_domain()` to call Layer 1 first. Find the function starting at line 102 and add the Layer 1 call at the top:

```python
async def classify_domain(query: str) -> ClassifierResult:
    """Classify a user query into a UAE domain. Falls back to GENERAL_LAW on error."""
    # Layer 1: exact e-invoicing keyword match (highest priority, no LLM needed)
    layer1 = _layer1_einvoicing_match(query)
    if layer1 is not None:
        return layer1

    # Layer 2: fuzzy keyword matching
    fuzzy = _fuzzy_classify_query(query)
    if fuzzy is not None:
        return fuzzy

    # Layer 3: LLM classification (fallback)
    try:
        raw = await _llm_complete(query)
        # ... rest of existing function unchanged
```

- [ ] **Step 4: Run test — verify it passes**

```bash
python -m pytest tests/test_domain_classifier_einvoicing.py -v
```
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/backend/core/chat/domain_classifier.py Project_AccountingLegalChatbot/backend/tests/test_domain_classifier_einvoicing.py
git commit -m "feat(domain): add Layer 1 exact e-invoicing keyword classifier — catches 243/244, DCTCE, e-invoice variants before LLM

Co-authored-by: Claude <noreply@anthropic.com>"
```

---

## Task 3: Local LLM Context Safety

**Files:**
- Modify: `backend/core/llm_manager.py` (add local provider detection + context helpers)
- Modify: `backend/api/chat.py` (apply context truncation for local LLMs, add debug logging)
- Test: `backend/tests/test_local_llm_context.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_local_llm_context.py`:

```python
"""Tests for local LLM context safety — truncation for Ollama/LM Studio."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.llm_manager import is_local_provider, local_max_context_tokens, truncate_for_local_model


class TestLocalProviderDetection:
    def test_ollama_is_local(self):
        assert is_local_provider("ollama") is True

    def test_lmstudio_is_local(self):
        assert is_local_provider("lmstudio") is True

    def test_local_is_local(self):
        assert is_local_provider("local") is True

    def test_nvidia_is_not_local(self):
        assert is_local_provider("nvidia") is False

    def test_openai_is_not_local(self):
        assert is_local_provider("openai") is False

    def test_claude_is_not_local(self):
        assert is_local_provider("claude") is False


class TestLocalMaxContextTokens:
    def test_ollama_max(self):
        assert local_max_context_tokens("ollama") == 6_000

    def test_lmstudio_max(self):
        assert local_max_context_tokens("lmstudio") == 8_000

    def test_local_max(self):
        assert local_max_context_tokens("local") == 8_000

    def test_nvidia_returns_none(self):
        assert local_max_context_tokens("nvidia") is None


class TestTruncateForLocalModel:
    def _make_chunks(self, n: int):
        return [{"text": f"chunk {i} " * 100, "chunk_id": str(i)} for i in range(n)]

    def test_truncates_top_k_for_ollama(self):
        chunks = self._make_chunks(10)
        truncated = truncate_for_local_model(chunks, "ollama")
        # Ollama: max 3 chunks
        assert len(truncated) <= 3

    def test_truncates_top_k_for_lmstudio(self):
        chunks = self._make_chunks(10)
        truncated = truncate_for_local_model(chunks, "lmstudio")
        # LM Studio: max 5 chunks
        assert len(truncated) <= 5

    def test_preserves_top_chunks(self):
        chunks = self._make_chunks(5)
        truncated = truncate_for_local_model(chunks, "ollama")
        assert truncated[0]["chunk_id"] == "0"  # highest ranked preserved

    def test_returns_all_if_not_local(self):
        chunks = self._make_chunks(10)
        result = truncate_for_local_model(chunks, "nvidia")
        assert len(result) == 10  # no truncation

    def test_empty_list_handled(self):
        result = truncate_for_local_model([], "ollama")
        assert result == []
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_local_llm_context.py -v 2>&1 | head -20
```
Expected: `ImportError` — functions don't exist yet.

- [ ] **Step 3: Add local provider helpers to `backend/core/llm_manager.py`**

Add these at the **end** of `llm_manager.py` (after the `list_available_providers` function, around line 1433):

```python
# ── Local provider detection ────────────────────────────────────────────────
_LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio", "local"})
_LOCAL_MAX_CONTEXT = {
    "ollama":    6_000,
    "lmstudio":  8_000,
    "local":     8_000,
}


def is_local_provider(provider_name: str) -> bool:
    """Return True if provider is a local inference server (Ollama/LM Studio)."""
    return provider_name.lower() in _LOCAL_PROVIDERS


def local_max_context_tokens(provider_name: str) -> int | None:
    """Return max safe context tokens for a local provider, or None for cloud."""
    return _LOCAL_MAX_CONTEXT.get(provider_name.lower())


def truncate_for_local_model(
    chunks: list[dict],
    provider_name: str,
    default_top_k: int = 3,
) -> list[dict]:
    """Truncate chunk list for local models that have smaller context windows.

    - ollama: max 3 chunks
    - lmstudio/local: max 5 chunks
    - cloud providers: no truncation
    """
    name = provider_name.lower()
    if name == "ollama":
        return chunks[:3]
    if name in ("lmstudio", "local"):
        return chunks[:5]
    return chunks  # no truncation for cloud


def build_local_system_suffix() -> str:
    """Return a stripped-down system prompt instruction for local LLMs."""
    return (
        "Answer ONLY using the provided documents below. "
        "Do not use information from your training data. "
        "Cite sources as [Source: filename]. "
        "If the documents do not contain the answer, say so."
    )
```

- [ ] **Step 4: Run test — verify it passes**

```bash
python -m pytest tests/test_local_llm_context.py -v
```
Expected: `14 passed`

- [ ] **Step 5: Apply context truncation in `backend/api/chat.py`**

Find where `_msgs` is built with `_search_results`. Around line 849-856 in the streaming path, and around line 1317-1323 in the non-streaming path.

**Streaming path (after line 849):**
After `_search_results` is populated but before building the augmented prompt, add:

```python
# ── Local LLM context truncation ─────────────────────────────────────────────
_local_provider_name = req.provider or settings.llm_provider
if is_local_provider(_local_provider_name) and _search_results:
    _truncated_results = truncate_for_local_model(_search_results, _local_provider_name)
    logger.info(
        "Local LLM context truncation: %d → %d chunks for provider %s",
        len(_search_results), len(_truncated_results), _local_provider_name,
    )
    _search_results = _truncated_results
```

**Non-streaming path (after line 1317):**
Same addition before `search_results` is used:
```python
_local_provider_name_ns = req.provider or settings.llm_provider
if is_local_provider(_local_provider_name_ns) and search_results:
    search_results = truncate_for_local_model(search_results, _local_provider_name_ns)
```

Also add the imports at the top of chat.py (near line 30):
```python
from core.llm_manager import is_local_provider, truncate_for_local_model
```

- [ ] **Step 6: Run tests — verify they still pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: All previously passing tests still pass + new tests pass.

- [ ] **Step 7: Commit**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/backend/core/llm_manager.py Project_AccountingLegalChatbot/backend/api/chat.py Project_AccountingLegalChatbot/backend/tests/test_local_llm_context.py
git commit -m "feat(llm): add local LLM context truncation — ollama max 3 chunks, lmstudio max 5 chunks

Co-authored-by: Claude <noreply@anthropic.com>"
```

---

## Task 4: Enhanced Debug Logging in Chat Pipeline

**Files:**
- Modify: `backend/api/chat.py` (add structured logger.info calls at key pipeline points)

- [ ] **Step 1: Add debug logging**

Add these logger calls at the specified locations in `backend/api/chat.py`:

**After domain classification (streaming path, ~line 626):**
```python
logger.info(
    "Domain classification: domain=%s confidence=%.2f query=%r",
    _cls.domain.value, _cls.confidence, req.message[:60],
)
```

**After RAG search completes (streaming path, ~line 828):**
```python
_top_domains = [r.get("metadata", {}).get("domain", "?") for r in _search_results[:5]]
_top_scores = [round(r.get("score", 0.0), 3) for r in _search_results[:5]]
_top_sources = [
    r.get("source") or r["metadata"].get("original_name", "?") for r in _search_results[:5]
]
logger.info(
    "RAG results: count=%d top_domains=%s top_scores=%s top_sources=%s provider=%s",
    len(_search_results), _top_domains, _top_scores, _top_sources,
    req.provider or settings.llm_provider,
)
```

**After LLM provider selected (streaming path, ~line 650):**
```python
_llm_provider_name = req.provider or settings.llm_provider
logger.info(
    "LLM call: provider=%s model=%s mode=%s context_estimate=%d",
    _llm_provider_name,
    settings.active_model,
    req.mode,
    _safe_max,
)
```

- [ ] **Step 2: Verify backend starts without errors**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -c "from api import chat; print('chat.py OK')" 2>&1
```

- [ ] **Step 3: Commit**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/backend/api/chat.py
git commit -m "feat(logging): add structured debug logging to chat pipeline — domain, RAG results, LLM provider

Co-authored-by: Claude <noreply@anthropic.com>"
```

---

## Task 5: End-to-End Verification

- [ ] **Step 1: Start backend and test debug endpoint**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m uvicorn main:app --port 8002 --reload &
sleep 5
curl -s -X POST http://localhost:8002/api/debug/rag-inspect \
  -H 'Content-Type: application/json' \
  -d '{"query": "e-invoicing UAE DCTCE requirements"}' | python3 -m json.tool
```

Expected: `effective_domain: "e_invoicing"`, `domain_classifier_confidence: 0.9`, RAG results from e_invoicing documents.

- [ ] **Step 2: Test via UI with NVIDIA — verify e-invoicing sources**

Ask the chatbot about e-invoicing via the UI with NVIDIA provider. Verify:
1. Sources shown are UAE e-invoicing documents (not AML/tax evasion)
2. Answer is accurate and cites sources

- [ ] **Step 3: Test via UI with Ollama — verify RAG context used**

Ask the same question via UI with Ollama provider. Verify:
1. Answer references actual RAG sources (not hallucinated)
2. Sources are from the e-invoicing document domain

- [ ] **Step 4: Run full test suite**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/ -q --tb=short 2>&1 | tail -20
```
Expected: All tests pass.

- [ ] **Step 5: Final commit + push**

```bash
cd ~/chatbot_local
git add -A
git commit -m "chore: RAG source correctness + local LLM hallucination fixes — all tasks complete

- Add /api/debug/rag-inspect diagnostic endpoint
- Layer 1 e-invoicing exact keyword classifier (0.9 confidence)
- Local LLM context truncation (ollama: 3 chunks, lmstudio: 5 chunks)
- Enhanced debug logging in chat pipeline

Co-authored-by: Claude <noreply@anthropic.com>"
git push origin main
```