# Relevance-First RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix RAG so only genuinely relevant documents appear as sources — no cross-conversation contamination, no irrelevant financial documents in legal answers.

**Architecture:** Three coordinated changes: (1) add a configurable relevance score threshold that drops low-quality chunks before they reach the LLM or source panel; (2) replace the broken domain/category RAG filter in chat.py with a smarter default that searches `category IN ["law","finance"]` (the pre-loaded professional knowledge base) unless the user has explicitly selected specific documents; (3) fix the root-cause ingestion bug in `bulk_ingest.py` and run a one-time migration to retag existing ChromaDB chunks with their correct content categories.

**Tech Stack:** Python 3.11, FastAPI, ChromaDB, SQLAlchemy async, pytest/asyncio, NVIDIA nv-embedqa-e5-v5 embeddings.

---

## File Map

| File | Change |
|---|---|
| `backend/config.py` | Add `rag_min_score: float = 0.45` |
| `backend/core/rag_engine.py` | `search()` — add `min_score` param, filter results after query |
| `backend/bulk_ingest.py` | Pass `category` + `original_name` to `ingest_chunks()` (root-cause bug fix) |
| `backend/bulk_retag.py` | NEW — one-time migration to retag existing ChromaDB chunks |
| `backend/api/chat.py` | Replace domain-filter logic with `{"category": {"$in": ["law","finance"]}}` default; apply threshold cap; applies to BOTH streaming (~line 492) and non-streaming (~line 733) paths |
| `backend/tests/test_relevance_rag.py` | NEW — tests for threshold, default filter, selected_doc override |

---

## Task 1: Config — Add `rag_min_score`

**Files:**
- Modify: `backend/config.py:75-83` (RAG Settings block)
- Test: `backend/tests/test_relevance_rag.py` (create new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_relevance_rag.py
"""Tests for relevance-first RAG: score threshold + default category filter."""
import pytest
from config import settings


def test_rag_min_score_default():
    """rag_min_score must exist and default to 0.45."""
    assert hasattr(settings, "rag_min_score")
    assert 0.0 < settings.rag_min_score < 1.0
    assert settings.rag_min_score == pytest.approx(0.45)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_relevance_rag.py::test_rag_min_score_default -v
```
Expected: `FAILED — AttributeError: 'Settings' object has no attribute 'rag_min_score'`

- [ ] **Step 3: Add `rag_min_score` to config.py**

In `backend/config.py`, inside the `# ── RAG Settings` block (after line `fast_max_tokens: int = 8192`), add:

```python
    rag_min_score: float = 0.45   # drop chunks below this cosine-similarity threshold
```

Full RAG Settings block after change:
```python
    # ── RAG Settings ─────────────────────────────────────────────────
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 8       # default for analyst / deep_research modes
    max_tokens: int = 4096       # default for analyst / deep_research modes
    fast_top_k: int = 15         # fast mode: higher retrieval budget
    fast_max_tokens: int = 8192  # fast mode: larger response window
    temperature: float = 0.7
    rag_min_score: float = 0.45  # drop chunks below this cosine-similarity threshold
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_relevance_rag.py::test_rag_min_score_default -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/test_relevance_rag.py
git commit -m "config: add rag_min_score threshold setting (default 0.45)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: RAG Engine — Apply Score Threshold in `search()`

**Files:**
- Modify: `backend/core/rag_engine.py:295-350` (`search()` method)
- Test: `backend/tests/test_relevance_rag.py` (extend)

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_relevance_rag.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from core.rag_engine import RAGEngine


def _make_engine_with_results(raw_results: list[dict]) -> RAGEngine:
    """Build a RAGEngine whose ChromaDB collection returns raw_results."""
    engine = object.__new__(RAGEngine)
    engine.embedding_provider = MagicMock()
    engine.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1024)

    mock_collection = MagicMock()
    mock_collection.count.return_value = 10
    # Convert score back to distance for ChromaDB format: distance = 1 - score
    mock_collection.query.return_value = {
        "documents": [[r["text"] for r in raw_results]],
        "metadatas": [[r["metadata"] for r in raw_results]],
        "distances": [[1 - r["score"] for r in raw_results]],
        "ids": [[f"chunk_{i}" for i in range(len(raw_results))]],
    }
    engine.collection = mock_collection
    return engine


@pytest.mark.asyncio
async def test_search_filters_below_threshold():
    """Chunks with score < rag_min_score must NOT appear in search results."""
    raw = [
        {"text": "VAT on hotel apartments is 5%.", "metadata": {"doc_id": "d1", "category": "finance"}, "score": 0.82},
        {"text": "Trail Balance debit total.", "metadata": {"doc_id": "d2", "category": "general"}, "score": 0.21},
    ]
    engine = _make_engine_with_results(raw)
    results = await engine.search("VAT hotel apartment", top_k=5, min_score=0.45)
    assert len(results) == 1
    assert results[0]["text"] == "VAT on hotel apartments is 5%."
    assert results[0]["score"] == pytest.approx(0.82)


@pytest.mark.asyncio
async def test_search_returns_empty_when_all_below_threshold():
    """If all chunks score below threshold, return empty list — never contaminate."""
    raw = [
        {"text": "Debit 1000 Credit 1000.", "metadata": {"doc_id": "d1", "category": "general"}, "score": 0.18},
        {"text": "Opening balance 50000.", "metadata": {"doc_id": "d1", "category": "general"}, "score": 0.22},
    ]
    engine = _make_engine_with_results(raw)
    results = await engine.search("VAT hotel apartment legal compliance", top_k=5, min_score=0.45)
    assert results == []


@pytest.mark.asyncio
async def test_search_respects_max_results_after_threshold():
    """After threshold filtering, cap at top 8 results by score."""
    raw = [
        {"text": f"Relevant chunk {i}", "metadata": {"doc_id": f"d{i}", "category": "law"}, "score": 0.90 - i * 0.02}
        for i in range(12)  # 12 chunks all above threshold
    ]
    engine = _make_engine_with_results(raw)
    results = await engine.search("law query", top_k=12, min_score=0.45)
    assert len(results) <= 8
    # Must be sorted by score descending
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_relevance_rag.py::test_search_filters_below_threshold \
       tests/test_relevance_rag.py::test_search_returns_empty_when_all_below_threshold \
       tests/test_relevance_rag.py::test_search_respects_max_results_after_threshold -v
```
Expected: all 3 `FAILED` — `search()` takes no `min_score` argument

- [ ] **Step 3: Update `rag_engine.search()` to accept and apply `min_score`**

In `backend/core/rag_engine.py`, replace the `search()` method signature and return block:

```python
async def search(
    self,
    query: str,
    top_k: int = 5,
    doc_id: Optional[str] = None,
    filter: Optional[dict] = None,
    min_score: Optional[float] = None,
) -> list[dict]:
    """
    Search the vector store for relevant chunks.

    Args:
        query: The search query.
        top_k: Number of candidates to retrieve from ChromaDB before filtering.
        doc_id: Optional filter to search within a specific document.
        filter: Optional metadata filter dict (e.g. {"category": {"$in": ["law","finance"]}}).
        min_score: If provided, drop chunks with cosine-similarity score below this value.
                   Remaining results are capped at 8 and sorted by score descending.

    Returns:
        List of results with text, metadata, and similarity score.
    """
    if self.collection.count() == 0:
        return []

    query_embedding = await self.embedding_provider.embed_query(query)

    where_filter = None
    if doc_id:
        where_filter = {"doc_id": doc_id}
    elif filter:
        where_filter = filter

    results = self.collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, self.collection.count()),
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    search_results = []
    if results and results["documents"]:
        for i, doc_text in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            score = 1 - results["distances"][0][i] if results["distances"] else 0
            search_results.append({
                "text": doc_text,
                "metadata": meta,
                "score": score,
                "source": meta.get("original_name") or meta.get("source", meta.get("filename", "Unknown")),
                "page": meta.get("page", meta.get("page_number", 1)),
                "excerpt": doc_text[:200],
            })

    # Apply relevance threshold and cap at 8 results sorted by score
    if min_score is not None:
        search_results = [r for r in search_results if r["score"] >= min_score]
    search_results.sort(key=lambda r: r["score"], reverse=True)
    return search_results[:8]
```

- [ ] **Step 4: Run new tests + full suite**

```bash
pytest tests/test_relevance_rag.py -v
pytest --tb=short -q
```
Expected: all 4 tests in `test_relevance_rag.py` pass; full suite still passes (all prior tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/core/rag_engine.py backend/tests/test_relevance_rag.py
git commit -m "rag: add min_score threshold + cap results at 8

- search() accepts optional min_score, drops chunks below threshold
- results sorted by score descending, capped at 8
- threshold + cap applied after ChromaDB query

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Fix `bulk_ingest.py` — Root-Cause Bug

**Files:**
- Modify: `backend/bulk_ingest.py:123`
- Test: `backend/tests/test_relevance_rag.py` (extend)

**Context:** `bulk_ingest.py` iterates `DIRS = {"finance": ..., "law": ...}` and knows each document's category, but never passes it to `ingest_chunks()`. Every chunk lands in ChromaDB with `category="general"`, making the professional knowledge base unsearchable by category.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_relevance_rag.py`:

```python
import ast
from pathlib import Path


def test_bulk_ingest_passes_category_to_ingest_chunks():
    """bulk_ingest.py must pass category= and original_name= to ingest_chunks()."""
    source = Path("bulk_ingest.py").read_text(encoding="utf-8")
    # The call must include the category variable, not just positional args
    assert "category=category" in source, (
        "bulk_ingest.py must pass category=category to ingest_chunks(). "
        "Without this, all pre-loaded documents get category='general' and become unsearchable."
    )
    assert "original_name=name" in source or "original_name=file_path.name" in source, (
        "bulk_ingest.py must pass original_name= to ingest_chunks() for readable source names."
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_relevance_rag.py::test_bulk_ingest_passes_category_to_ingest_chunks -v
```
Expected: `FAILED — AssertionError: bulk_ingest.py must pass category=category`

- [ ] **Step 3: Fix `bulk_ingest.py` line 123**

In `backend/bulk_ingest.py`, replace line 123:

```python
# BEFORE (bug):
count = await rag_engine.ingest_chunks(chunks, doc_id)

# AFTER (fixed):
count = await rag_engine.ingest_chunks(
    chunks,
    doc_id,
    original_name=name,
    category=category,
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_relevance_rag.py::test_bulk_ingest_passes_category_to_ingest_chunks -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/bulk_ingest.py backend/tests/test_relevance_rag.py
git commit -m "fix(bulk_ingest): pass category + original_name to ingest_chunks

Root-cause bug: all pre-loaded law/finance documents were ingested with
category='general', making them invisible to category-filtered searches.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Write `bulk_retag.py` Migration

**Files:**
- Create: `backend/bulk_retag.py`
- Test: `backend/tests/test_relevance_rag.py` (extend)

**Purpose:** All documents already in ChromaDB were indexed without correct category metadata. This script reads each Document record's `metadata_json.category` from the SQL DB and updates the corresponding ChromaDB chunks via `collection.update()`. Safe to re-run (idempotent).

- [ ] **Step 1: Write the test**

Add to `backend/tests/test_relevance_rag.py`:

```python
import importlib
import sys
from pathlib import Path


def test_bulk_retag_script_exists_and_is_importable():
    """bulk_retag.py must exist and define a main() coroutine."""
    retag_path = Path("bulk_retag.py")
    assert retag_path.exists(), "backend/bulk_retag.py must exist"
    source = retag_path.read_text(encoding="utf-8")
    assert "async def main" in source, "bulk_retag.py must define async def main()"
    assert "collection.update" in source, (
        "bulk_retag.py must call collection.update() to retag existing chunks"
    )
    assert "metadata_json" in source, (
        "bulk_retag.py must read category from Document.metadata_json"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_relevance_rag.py::test_bulk_retag_script_exists_and_is_importable -v
```
Expected: `FAILED — AssertionError: backend/bulk_retag.py must exist`

- [ ] **Step 3: Create `backend/bulk_retag.py`**

```python
"""
One-time migration: retag existing ChromaDB chunks with correct category metadata.

Reads every Document record's metadata_json.category from SQLite, then calls
ChromaDB collection.update() to stamp that category onto every chunk belonging
to that document.

Safe to re-run: documents already retagged are skipped (category != "general").

Usage (run from backend/ directory):
    python bulk_retag.py
"""

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
from core.rag_engine import rag_engine

_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_engine = create_async_engine(_db_url, echo=False, future=True, connect_args={"timeout": 60})
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def main() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    totals = {"retagged": 0, "skipped": 0, "no_chunks": 0, "error": 0}

    async with _session_factory() as db:
        result = await db.execute(select(Document).where(Document.status == "indexed"))
        docs = result.scalars().all()
        print(f"Found {len(docs)} indexed documents to check.\n")

        for doc in docs:
            meta = doc.metadata_json if isinstance(doc.metadata_json, dict) else {}
            category = meta.get("category", "general")

            if category == "general":
                print(f"  SKIP (no category)  {doc.original_name}")
                totals["skipped"] += 1
                continue

            # Get all chunk IDs for this document from ChromaDB
            try:
                existing = rag_engine.collection.get(
                    where={"doc_id": doc.id},
                    include=["metadatas"],
                )
            except Exception as exc:
                print(f"  ERR  (query)        {doc.original_name}: {exc}")
                totals["error"] += 1
                continue

            if not existing or not existing["ids"]:
                print(f"  SKIP (no chunks)    {doc.original_name}")
                totals["no_chunks"] += 1
                continue

            chunk_ids = existing["ids"]
            current_metas = existing["metadatas"]

            # Check if already correctly tagged (skip if all chunks already have correct category)
            already_tagged = all(m.get("category") == category for m in current_metas)
            if already_tagged:
                print(f"  SKIP (already ok)   {doc.original_name}  [{category}]")
                totals["skipped"] += 1
                continue

            # Build updated metadata list: preserve all existing fields, update category + original_name
            updated_metas = []
            for m in current_metas:
                updated = dict(m)
                updated["category"] = category
                updated["original_name"] = doc.original_name
                updated_metas.append(updated)

            try:
                rag_engine.collection.update(
                    ids=chunk_ids,
                    metadatas=updated_metas,
                )
                print(f"  OK   ({len(chunk_ids):>4} chunks)  {doc.original_name}  [{category}]")
                totals["retagged"] += 1
            except Exception as exc:
                print(f"  ERR  (update)       {doc.original_name}: {exc}")
                totals["error"] += 1

    print(
        f"\nDone.\n"
        f"  retagged  : {totals['retagged']}\n"
        f"  skipped   : {totals['skipped']}\n"
        f"  no chunks : {totals['no_chunks']}\n"
        f"  errors    : {totals['error']}\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_relevance_rag.py::test_bulk_retag_script_exists_and_is_importable -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/bulk_retag.py backend/tests/test_relevance_rag.py
git commit -m "feat: add bulk_retag.py migration for existing ChromaDB chunks

Retags all indexed documents with correct category from metadata_json.
Safe to re-run (idempotent). Run once after this PR is deployed.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Rewrite RAG Filter in `chat.py`

**Files:**
- Modify: `backend/api/chat.py` — streaming path (~line 492) and non-streaming path (~line 733)
- Test: `backend/tests/test_relevance_rag.py` (extend)

**Logic to implement:**
```
if selected_doc_ids:
    filter = {"doc_id": {"$in": selected_doc_ids}}
else:
    filter = {"category": {"$in": ["law", "finance"]}}   # professional knowledge base

results = search(..., filter=filter, min_score=settings.rag_min_score)
# threshold + cap already applied inside search()
```

No domain-based category detection. No fallback. No unfiltered search.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_relevance_rag.py`:

```python
from unittest.mock import AsyncMock, patch
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _classifier_law():
    return ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.9, alternatives=[])


def _classifier_general():
    return ClassifierResult(domain=DomainLabel.GENERAL, confidence=0.8, alternatives=[])


def _mock_llm_provider():
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value=LLMResponse(content="Answer.", tokens_used=10, provider="mock", model="m"))
    async def _stream(*a, **kw):
        yield "Answer."
    mock.chat_stream = _stream
    return mock


@pytest.mark.asyncio
async def test_chat_no_selection_uses_law_finance_filter(client):
    """Without selected_doc_ids, RAG must filter by category IN ['law','finance']."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter, "min_score": min_score})
        return []

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_classifier_general())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm_provider()),
        patch("api.chat.rag_engine.search", side_effect=_fake_search),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT on hotel apartments?", "use_rag": True, "stream": False},
        )

    assert resp.status_code == 200
    assert search_calls, "rag_engine.search must have been called"
    call = search_calls[0]
    assert call["filter"] == {"category": {"$in": ["law", "finance"]}}, (
        f"Expected category filter, got: {call['filter']}"
    )
    assert call["min_score"] == pytest.approx(0.45), (
        f"Expected min_score=0.45, got: {call['min_score']}"
    )


@pytest.mark.asyncio
async def test_chat_with_selection_uses_doc_id_filter(client):
    """With selected_doc_ids, RAG must filter by doc_id, overriding default category filter."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter})
        return []

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_classifier_law())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm_provider()),
        patch("api.chat.rag_engine.search", side_effect=_fake_search),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "Summarise my trail balance",
                "use_rag": True,
                "stream": False,
                "selected_doc_ids": ["doc-tb-001"],
            },
        )

    assert resp.status_code == 200
    assert search_calls
    assert search_calls[0]["filter"] == {"doc_id": {"$in": ["doc-tb-001"]}}, (
        f"Expected doc_id filter, got: {search_calls[0]['filter']}"
    )


@pytest.mark.asyncio
async def test_chat_no_rag_results_returns_no_sources(client):
    """When threshold filters out all results, response must have empty sources list."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_classifier_general())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm_provider()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "Random question", "use_rag": True, "stream": False},
        )

    assert resp.status_code == 200
    sources = resp.json()["message"].get("sources", [])
    assert sources == [], f"Expected empty sources, got: {sources}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_relevance_rag.py::test_chat_no_selection_uses_law_finance_filter \
       tests/test_relevance_rag.py::test_chat_with_selection_uses_doc_id_filter \
       tests/test_relevance_rag.py::test_chat_no_rag_results_returns_no_sources -v
```
Expected: all 3 `FAILED` — filter doesn't match expected values

- [ ] **Step 3: Rewrite RAG filter block in streaming path (~line 492)**

In `backend/api/chat.py`, find the streaming RAG block that currently reads:

```python
            if req.use_rag:
                if req.selected_doc_ids:
                    _rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
                    _doc_scoped = True
                elif req.mode != "analyst":
                    if req.domain in ("finance",):
                        _rag_filter = {"category": "finance"}
                    elif req.domain in ("law", "audit"):
                        _rag_filter = {"category": "law"}
```

Replace with:

```python
            if req.use_rag:
                if req.selected_doc_ids:
                    _rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
                    _doc_scoped = True
                else:
                    _rag_filter = {"category": {"$in": ["law", "finance"]}}
```

Then find the search calls in that same block and add `min_score=settings.rag_min_score` to each:

```python
                try:
                    if req.mode == "fast":
                        _all = await asyncio.gather(
                            *[rag_engine.search(
                                q,
                                top_k=settings.fast_top_k,
                                filter=_rag_filter,
                                min_score=settings.rag_min_score,
                            ) for q in _query_vars],
                            return_exceptions=True,
                        )
                        _search_results = _dedup_merge(_all, settings.fast_top_k)
                    else:
                        _search_results = await rag_engine.search(
                            req.message,
                            top_k=settings.top_k_results,
                            filter=_rag_filter,
                            min_score=settings.rag_min_score,
                        )
                except Exception as _rag_exc:
                    logger.warning("RAG search failed, falling back to no-context mode: %s", _rag_exc)
                    _search_results = []
```

- [ ] **Step 4: Rewrite RAG filter block in non-streaming path (~line 733)**

In `backend/api/chat.py`, find the non-streaming RAG block that currently reads:

```python
    if req.use_rag:
        rag_filter = None
        _doc_scoped = False
        if req.selected_doc_ids:
            rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
            _doc_scoped = True
        elif req.mode != "analyst":
            if req.domain in ("finance",):
                rag_filter = {"category": "finance"}
            elif req.domain in ("law", "audit"):
                rag_filter = {"category": "law"}
```

Replace with:

```python
    if req.use_rag:
        rag_filter = None
        _doc_scoped = False
        if req.selected_doc_ids:
            rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
            _doc_scoped = True
        else:
            rag_filter = {"category": {"$in": ["law", "finance"]}}
```

Then add `min_score=settings.rag_min_score` to the search calls in that block:

```python
        try:
            if req.mode == "fast":
                query_variations = await _get_query_variations(req.message, req.provider)
                all_results = await asyncio.gather(
                    *[
                        rag_engine.search(
                            q,
                            top_k=settings.fast_top_k,
                            filter=rag_filter,
                            min_score=settings.rag_min_score,
                        )
                        for q in query_variations
                    ],
                    return_exceptions=True,
                )
                search_results = _dedup_merge(all_results, settings.fast_top_k)
            else:
                search_results = await rag_engine.search(
                    req.message,
                    top_k=settings.top_k_results,
                    filter=rag_filter,
                    min_score=settings.rag_min_score,
                )
        except Exception as rag_exc:
            logger.warning(f"RAG search failed, falling back to no-context mode: {rag_exc}")
            search_results = []
```

- [ ] **Step 5: Run new tests + full suite**

```bash
pytest tests/test_relevance_rag.py -v
pytest --tb=short -q
```
Expected: all tests in `test_relevance_rag.py` pass; full suite still passes

- [ ] **Step 6: Commit**

```bash
git add backend/api/chat.py backend/tests/test_relevance_rag.py
git commit -m "feat: relevance-first RAG — category default filter + score threshold

- Default filter: category IN ['law','finance'] (professional knowledge base)
- Explicit selection: doc_id filter overrides default
- min_score=0.45 passed to search() — drops low-relevance chunks
- Applies to both streaming and non-streaming paths
- Removes broken domain-based category filter that returned 0 results

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Run `bulk_retag.py` Migration

**Purpose:** Apply the correct category metadata to every document already in ChromaDB. This is a one-time operational step, not a code change.

- [ ] **Step 1: Verify the server is stopped or note that the migration uses a 60s DB timeout**

The migration uses `connect_args={"timeout": 60}` to wait for the running server's DB lock. Either stop the server first or let it retry.

- [ ] **Step 2: Run the migration from the backend directory**

```bash
cd backend
python bulk_retag.py
```

Expected output (example):
```
Found 287 indexed documents to check.

  OK   ( 142 chunks)  VAT-Decree-Law-No-8-of-2017-English.pdf  [finance]
  OK   (  89 chunks)  Cabinet Decision No. 106 of 2022.pdf  [law]
  OK   (  54 chunks)  IFRS 2024.pdf  [finance]
  SKIP (already ok)   Trail Balance.xlsx
  SKIP (already ok)   TL-2024-25.pdf
  ...

Done.
  retagged  : 243
  skipped   : 44
  no chunks : 0
  errors    : 0
```

If errors > 0, review the error lines and re-run (idempotent).

- [ ] **Step 3: Verify in ChromaDB that retagging worked**

```bash
python - <<'EOF'
from core.rag_engine import rag_engine
# Check a law document chunk
r = rag_engine.collection.get(where={"category": "law"}, limit=3, include=["metadatas"])
print("LAW chunks found:", len(r["ids"]))
print("Sample:", r["metadatas"][0] if r["metadatas"] else "none")

# Check finance
r2 = rag_engine.collection.get(where={"category": "finance"}, limit=3, include=["metadatas"])
print("\nFINANCE chunks found:", len(r2["ids"]))
print("Sample:", r2["metadatas"][0] if r2["metadatas"] else "none")

# Confirm general (client docs) still general
r3 = rag_engine.collection.get(where={"category": "general"}, limit=3, include=["metadatas"])
print("\nGENERAL chunks (client docs):", len(r3["ids"]))
EOF
```

Expected: law and finance chunks > 0 with correct `original_name`; general chunks = only client-uploaded docs (Trail Balance etc.)

- [ ] **Step 4: Run the VAT Hotel Apartment test query manually**

```bash
python - <<'EOF'
import asyncio
from core.rag_engine import rag_engine

async def test():
    results = await rag_engine.search(
        "hotel apartment sold FTA VAT notice payment portal",
        top_k=10,
        filter={"category": {"$in": ["law", "finance"]}},
        min_score=0.45,
    )
    print(f"Results: {len(results)}")
    for r in results:
        print(f"  [{r['score']:.2f}] {r['source']} p.{r['page']}")

asyncio.run(test())
EOF
```

Expected: 3–6 results from UAE VAT law documents with scores ≥ 0.45; Trail Balance / TL-2024-25 must NOT appear.

- [ ] **Step 5: Commit migration result note**

```bash
git add backend/bulk_retag.py
git commit -m "ops: run bulk_retag migration — chromadb chunks retagged with correct categories

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final Verification

- [ ] Run the complete test suite one final time:

```bash
cd backend
pytest --tb=short -q
```
Expected: all tests pass, no regressions.

- [ ] Manual smoke test: Start the server, open Legal Studio, ask "hotel apartment VAT FTA notice" in a fresh chat (no docs selected). Verify:
  - Sources shown are from UAE VAT law / FTA guides
  - Trail Balance.xlsx and TL-2024-25.pdf do NOT appear
  - Each source card shows document name, page, score %, and the matching excerpt
