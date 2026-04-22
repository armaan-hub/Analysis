# Chatbot Bug Fixes & Feature Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 groups of bugs (multi-select delete, deep research quality, analyst mode, all-report intelligence, light mode) while overhauling the RAG pipeline with hybrid vector+graph retrieval and a report-intelligence layer that downloads public Big4/ISA/FTA templates.

**Architecture:** Three layers of work — (1) a foundation layer fixes the DB, dedup, and chunk metadata; (2) a feature layer adds hybrid RAG, report intelligence with template download, a new deep-research SSE endpoint, and analyst mode doc-filtering; (3) a quick-fix layer patches multi-select, thumbnails, and light-mode CSS.

**Tech Stack:** FastAPI, SQLAlchemy async (SQLite), ChromaDB, NetworkX, HTTPX, React 18, TypeScript, Tailwind/CSS-variables, NVIDIA NIM (mistralai/mistral-small-4-119b-2603), pytest + httpx.AsyncClient.

**Spec:** `docs/superpowers/specs/2026-04-22-chatbot-bugs-design.md`

---

## File Map (what is created or modified)

| Path | Action | Purpose |
|---|---|---|
| `backend/db/migrations/add_content_hash.py` | **Create** | Add `content_hash VARCHAR(64)` to `documents` table |
| `backend/db/migrations/add_entities_tables.py` | **Create** | Add `entities` + `entity_relations` tables for graph RAG |
| `backend/db/models.py` | **Modify** | Add `content_hash` field to `Document` model |
| `backend/api/documents.py` | **Modify** | SHA-256 dedup on upload; pass `original_name` to ingest |
| `backend/core/rag_engine.py` | **Modify** | Store `original_name` in chunk metadata; add doc resolver |
| `backend/core/rag/graph_rag.py` | **Create** | Entity extraction, SQLite storage, NetworkX graph traversal |
| `backend/core/rag/hybrid_retriever.py` | **Create** | Combine ChromaDB + graph results, deduplicate, re-rank |
| `backend/core/report_templates/report_intel.py` | **Create** | `REPORT_INTEL` dict — audience, purpose, key points per report type |
| `backend/core/report_templates/template_manager.py` | **Create** | Download, cache, and refresh public Big4/ISA/FTA report templates |
| `backend/api/reports.py` | **Modify** | Inject `REPORT_INTEL` + template + period enforcement into system prompt |
| `backend/api/chat.py` | **Modify** | Add `selected_doc_ids` to `ChatRequest`; add `/api/chat/deep-research` SSE endpoint |
| `backend/core/prompt_router.py` | **Modify** | Remove duplicate `ANALYST_SYSTEM_PREFIX` definition |
| `frontend/src/components/studios/LegalStudio/reportConfigs.ts` | **Modify** | Add `audience`/`purpose`/`keyPoints` to `ReportConfig`, fix duplicate property blocks |
| `frontend/src/components/studios/LegalStudio/ConfirmReportCard.tsx` | **Modify** | Show audience pill before generation |
| `frontend/src/hooks/useDeepResearch.ts` | **Modify** | Handle `conversation_id` from `done` event |
| `frontend/src/lib/useDocumentResolver.ts` | **Create** | Hook that maps UUID source names → human-readable original names |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | **Modify** | Use `useDocumentResolver` to resolve source names |
| `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx` | **Modify** | Use `useDocumentResolver` for source name display |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | **Modify** | Pass `selected_doc_ids` in chat body; route audit result to ArtifactPanel |
| `frontend/src/pages/HomePage.tsx` | **Modify** | Fix card click in selection mode to toggle instead of open |
| `frontend/src/components/common/NotebookCard.tsx` | **Modify** | Use domain emoji in thumbnail instead of text initials |
| `frontend/src/index.css` | **Modify** | Define `--s-*` CSS variables in `:root` + `[data-theme="light"]` |

---

## Phase 1 — Foundation (DB + RAG Metadata)

### Task 1: Add `content_hash` column to `documents` table

**Files:**
- Create: `backend/db/migrations/add_content_hash.py`
- Modify: `backend/db/models.py`
- Test: `backend/tests/test_migrations.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migrations.py
import sqlite3, os, pytest

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'chatbot.db')

def test_content_hash_column_exists():
    """Migration must add content_hash VARCHAR(64) to documents."""
    conn = sqlite3.connect(DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    conn.close()
    assert 'content_hash' in cols
```

- [ ] **Step 2: Run to confirm it fails**

```
cd backend
python -m pytest tests/test_migrations.py::test_content_hash_column_exists -v
```
Expected: `FAILED — AssertionError` (column does not yet exist).

- [ ] **Step 3: Create the migration**

```python
# backend/db/migrations/add_content_hash.py
"""
Migration: add content_hash VARCHAR(64) NULL to documents table.
Safe to run multiple times (checks PRAGMA first).
"""
import sqlite3, os, pathlib

DB_PATH = pathlib.Path(__file__).parent.parent / "chatbot.db"


def run():
    conn = sqlite3.connect(DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "content_hash" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN content_hash VARCHAR(64) NULL")
        conn.commit()
        print("[migration] added content_hash to documents")
    else:
        print("[migration] content_hash already present — skipped")
    conn.close()


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run the migration**

```
cd backend
python db/migrations/add_content_hash.py
```
Expected output: `[migration] added content_hash to documents`

- [ ] **Step 5: Add the column to the SQLAlchemy model**

In `backend/db/models.py`, find the `Document` model and add the column after `created_at`:

```python
# in class Document(Base):   — add after existing columns
content_hash = Column(String(64), nullable=True, index=True)
```

- [ ] **Step 6: Run the test — it should now pass**

```
cd backend
python -m pytest tests/test_migrations.py::test_content_hash_column_exists -v
```
Expected: `PASSED`

- [ ] **Step 7: Commit**

```
git add backend/db/migrations/add_content_hash.py backend/db/models.py backend/tests/test_migrations.py
git commit -m "feat(db): add content_hash column to documents for dedup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Add `entities` + `entity_relations` tables

**Files:**
- Create: `backend/db/migrations/add_entities_tables.py`
- Test: `backend/tests/test_migrations.py` (extend)

- [ ] **Step 1: Append the failing test**

```python
# append to backend/tests/test_migrations.py

def test_entities_tables_exist():
    """Migration must add entities and entity_relations tables."""
    conn = sqlite3.connect(DB_PATH)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert 'entities' in tables
    assert 'entity_relations' in tables
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_migrations.py::test_entities_tables_exist -v
```
Expected: `FAILED`

- [ ] **Step 3: Create the migration**

```python
# backend/db/migrations/add_entities_tables.py
"""
Migration: add entities and entity_relations tables for graph RAG.
"""
import sqlite3, pathlib

DB_PATH = pathlib.Path(__file__).parent.parent / "chatbot.db"


def run():
    conn = sqlite3.connect(DB_PATH)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    if "entities" not in tables:
        conn.execute("""
            CREATE TABLE entities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT    NOT NULL,
                chunk_index INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                entity_type TEXT    NOT NULL DEFAULT 'GENERAL',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX idx_entities_doc_id ON entities(doc_id)")
        print("[migration] created entities table")

    if "entity_relations" not in tables:
        conn.execute("""
            CREATE TABLE entity_relations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT NOT NULL,
                source_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                relation    TEXT NOT NULL DEFAULT 'RELATED_TO',
                weight      REAL NOT NULL DEFAULT 1.0
            )
        """)
        conn.execute("CREATE INDEX idx_er_doc_id ON entity_relations(doc_id)")
        print("[migration] created entity_relations table")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run the migration**

```
cd backend
python db/migrations/add_entities_tables.py
```
Expected: tables created messages.

- [ ] **Step 5: Run the tests — both should pass**

```
cd backend
python -m pytest tests/test_migrations.py -v
```
Expected: `2 PASSED`

- [ ] **Step 6: Commit**

```
git add backend/db/migrations/add_entities_tables.py backend/tests/test_migrations.py
git commit -m "feat(db): add entities and entity_relations tables for graph RAG

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: SHA-256 dedup on upload + `original_name` in chunk metadata

**Files:**
- Modify: `backend/api/documents.py` (around lines 63–170)
- Modify: `backend/core/rag_engine.py` (around lines 229–260)
- Test: extend `backend/tests/test_documents.py` (or create it)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_documents.py
import pytest, io
from httpx import AsyncClient, ASGITransport
from backend.main import app   # adjust if your app factory differs

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_duplicate_upload_returns_existing(client):
    """Uploading the same PDF twice must return the existing document, not create a new row."""
    pdf_bytes = b"%PDF-1.4 test content for dedup"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r1 = await client.post("/api/documents/upload", files=files,
                           data={"conversation_id": "test-conv-1"})
    assert r1.status_code == 200
    doc_id_1 = r1.json()["document"]["id"]

    files2 = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r2 = await client.post("/api/documents/upload", files=files2,
                           data={"conversation_id": "test-conv-2"})
    assert r2.status_code == 200
    doc_id_2 = r2.json()["document"]["id"]

    assert doc_id_1 == doc_id_2, "Duplicate upload should return same doc_id"
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_documents.py::test_duplicate_upload_returns_existing -v
```
Expected: `FAILED` (no dedup yet).

- [ ] **Step 3: Add SHA-256 dedup in `documents.py`**

Find the block starting at line 82 (`doc_id = str(uuid.uuid4())`). Replace the section from `content = await file.read()` through the first DB flush with:

```python
import hashlib  # add to top-of-file imports if not present

# ── inside the upload handler, after:  content = await file.read() ──
content_hash = hashlib.sha256(content).hexdigest()

# Check if an identical file already exists for this workspace
existing = await db.execute(
    select(Document).where(Document.content_hash == content_hash)
)
existing_doc = existing.scalars().first()
if existing_doc:
    return UploadResponse(document=existing_doc)

doc_id = str(uuid.uuid4())
```

- [ ] **Step 4: Store hash in new Document row**

Find where `Document(...)` is instantiated and add `content_hash=content_hash`:

```python
doc = Document(
    id=doc_id,
    filename=file.filename,
    original_name=file.filename,
    content_hash=content_hash,    # ← new
    # ... keep all other existing fields unchanged
)
```

- [ ] **Step 5: Store `original_name` in chunk metadata inside `rag_engine.py`**

In `backend/core/rag_engine.py`, find `ingest_chunks`:

```python
async def ingest_chunks(self, chunks: list[DocumentChunk], doc_id: str,
                        original_name: str | None = None) -> None:
    """Upsert chunks into ChromaDB. original_name is stored per-chunk."""
    if not chunks:
        return
    ids, docs, metas = [], [], []
    for i, c in enumerate(chunks):
        ids.append(f"{doc_id}_chunk_{i}")
        docs.append(c.text)
        meta = dict(c.metadata)            # copy so we don't mutate caller's data
        meta["doc_id"] = doc_id
        if original_name:
            meta["original_name"] = original_name   # ← store human-readable name
        metas.append(meta)
    self.collection.upsert(ids=ids, documents=docs, metadatas=metas)
```

- [ ] **Step 6: Add `resolve_doc_names` helper to `rag_engine.py`**

At the bottom of the `RAGEngine` class, add:

```python
def resolve_doc_names(self, source_ids: list[str]) -> dict[str, str]:
    """
    Given a list of UUID source strings (e.g. "abc123_chunk_0"),
    return a mapping {source_id: original_name}.
    Falls back to the source_id itself when original_name is absent.
    """
    if not source_ids:
        return {}
    try:
        results = self.collection.get(ids=source_ids, include=["metadatas"])
        mapping: dict[str, str] = {}
        for sid, meta in zip(results["ids"], results["metadatas"]):
            mapping[sid] = meta.get("original_name", sid)
        return mapping
    except Exception:
        return {s: s for s in source_ids}
```

- [ ] **Step 7: Update upload handler call to `ingest_chunks` to pass `original_name`**

Find the call to `rag_engine.ingest_chunks(...)` in `documents.py` and add the kwarg:

```python
await rag_engine.ingest_chunks(chunks, doc_id=doc_id, original_name=file.filename)
```

- [ ] **Step 8: Run the dedup test — should now pass**

```
cd backend
python -m pytest tests/test_documents.py::test_duplicate_upload_returns_existing -v
```
Expected: `PASSED`

- [ ] **Step 9: Commit**

```
git add backend/api/documents.py backend/core/rag_engine.py backend/tests/test_documents.py
git commit -m "feat(rag): SHA-256 dedup on upload + original_name in chunk metadata

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2 — Hybrid RAG (Graph + Vector)

### Task 4: Graph RAG — entity extraction + NetworkX traversal

**Files:**
- Create: `backend/core/rag/graph_rag.py`
- Create: `backend/core/rag/__init__.py` (empty)
- Test: `backend/tests/test_graph_rag.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_graph_rag.py
import pytest
from backend.core.rag.graph_rag import GraphRAG

@pytest.fixture
def graph():
    return GraphRAG(db_path=":memory:")

def test_store_and_retrieve_entities(graph):
    """Entities stored for a doc_id should be retrievable."""
    graph.store_entities("doc1", chunk_index=0,
                         entities=[("Apple Inc", "ORG"), ("Revenue", "METRIC")])
    result = graph.get_entities_for_doc("doc1")
    names = [r["name"] for r in result]
    assert "Apple Inc" in names
    assert "Revenue" in names

def test_related_chunks(graph):
    """Chunks related via shared entity should be returned."""
    graph.store_entities("doc1", chunk_index=0, entities=[("VAT", "TAX")])
    graph.store_entities("doc1", chunk_index=1, entities=[("VAT", "TAX")])
    related = graph.find_related_chunks("doc1", seed_chunk_indices=[0], depth=1)
    assert 1 in related
```

- [ ] **Step 2: Run to confirm failures**

```
cd backend
python -m pytest tests/test_graph_rag.py -v
```
Expected: `FAILED` (module not found).

- [ ] **Step 3: Create `backend/core/rag/__init__.py`**

Empty file — just creates the package.

```python
# backend/core/rag/__init__.py
```

- [ ] **Step 4: Create `backend/core/rag/graph_rag.py`**

```python
"""
Graph RAG layer.

Stores named entities extracted from document chunks into SQLite, then uses
NetworkX to traverse the entity graph and return related chunk indices.
Entity extraction is done with a lightweight regex heuristic to avoid extra
LLM calls during ingestion — entities are capitalised noun phrases + known
accounting/legal keywords.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Sequence

import networkx as nx

# ── Simple keyword-based entity recogniser ───────────────────────────────────
_ACCOUNTING_TERMS = frozenset([
    "revenue", "ebitda", "net profit", "gross margin", "cash flow",
    "balance sheet", "income statement", "vat", "tax", "audit", "ifrs", "gaap",
    "amortisation", "depreciation", "provision", "liability", "asset",
    "equity", "dividend", "working capital", "free cash flow",
])

_ENT_RE = re.compile(
    r"\b([A-Z][a-zA-Z&,\.\s]{2,40}(?:Inc|Ltd|LLC|Corp|Co|Group|Holdings|FZE|PJSC)?)\b"
)


def _extract_entities(text: str) -> list[tuple[str, str]]:
    """Return list of (name, type) tuples from raw chunk text."""
    entities: list[tuple[str, str]] = []
    lower = text.lower()
    for term in _ACCOUNTING_TERMS:
        if term in lower:
            entities.append((term.title(), "METRIC"))
    for m in _ENT_RE.finditer(text):
        name = m.group(1).strip().rstrip(",.")
        if 3 <= len(name) <= 60 and name.lower() not in _ACCOUNTING_TERMS:
            entities.append((name, "ORG"))
    # deduplicate preserving order
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for n, t in entities:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            out.append((n, t))
    return out[:30]  # cap per chunk


class GraphRAG:
    """Manages entity storage and graph traversal for a single SQLite database."""

    def __init__(self, db_path: str | Path = "chatbot.db"):
        self._db_path = str(db_path)
        self._init_db()

    # ── DB init ──────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT    NOT NULL,
                chunk_index INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                entity_type TEXT    NOT NULL DEFAULT 'GENERAL'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_doc ON entities(doc_id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_relations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT NOT NULL,
                source_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                relation    TEXT NOT NULL DEFAULT 'RELATED_TO',
                weight      REAL NOT NULL DEFAULT 1.0
            )
        """)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    # ── Public API ───────────────────────────────────────────────────────────

    def extract_and_store(self, doc_id: str, chunk_index: int, text: str) -> None:
        """Extract entities from text and persist to DB."""
        entities = _extract_entities(text)
        self.store_entities(doc_id, chunk_index, entities)

    def store_entities(self, doc_id: str, chunk_index: int,
                       entities: Sequence[tuple[str, str]]) -> None:
        """Persist pre-computed entities."""
        conn = self._connect()
        conn.executemany(
            "INSERT INTO entities (doc_id, chunk_index, name, entity_type) VALUES (?,?,?,?)",
            [(doc_id, chunk_index, name, etype) for name, etype in entities],
        )
        conn.commit()
        conn.close()

    def get_entities_for_doc(self, doc_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT chunk_index, name, entity_type FROM entities WHERE doc_id=?",
            (doc_id,),
        ).fetchall()
        conn.close()
        return [{"chunk_index": r[0], "name": r[1], "entity_type": r[2]} for r in rows]

    def build_graph(self, doc_id: str) -> nx.Graph:
        """Build an in-memory co-occurrence graph for one document."""
        rows = self.get_entities_for_doc(doc_id)
        G = nx.Graph()
        chunk_to_entities: dict[int, list[str]] = {}
        for row in rows:
            chunk_to_entities.setdefault(row["chunk_index"], []).append(row["name"])
        for chunk_idx, names in chunk_to_entities.items():
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    u, v = names[i], names[j]
                    if G.has_edge(u, v):
                        G[u][v]["weight"] += 1
                    else:
                        G.add_edge(u, v, weight=1, chunks={chunk_idx})
                    G[u][v].setdefault("chunks", set()).add(chunk_idx)
        return G

    def find_related_chunks(self, doc_id: str, seed_chunk_indices: list[int],
                            depth: int = 1) -> set[int]:
        """
        Given seed chunk indices, traverse entity co-occurrence graph to find
        related chunk indices within `depth` hops.
        Returns a set of chunk indices (excluding the seeds themselves).
        """
        rows = self.get_entities_for_doc(doc_id)
        if not rows:
            return set()

        G = self.build_graph(doc_id)
        chunk_to_entities: dict[int, list[str]] = {}
        for row in rows:
            chunk_to_entities.setdefault(row["chunk_index"], []).append(row["name"])

        seed_entities: set[str] = set()
        for idx in seed_chunk_indices:
            seed_entities.update(chunk_to_entities.get(idx, []))

        related_entities: set[str] = set(seed_entities)
        frontier = set(seed_entities)
        for _ in range(depth):
            next_frontier: set[str] = set()
            for ent in frontier:
                if ent in G:
                    next_frontier.update(G.neighbors(ent))
            frontier = next_frontier - related_entities
            related_entities.update(next_frontier)

        related_chunks: set[int] = set()
        for ent in related_entities - seed_entities:
            for idx, names in chunk_to_entities.items():
                if ent in names:
                    related_chunks.add(idx)
        return related_chunks - set(seed_chunk_indices)
```

- [ ] **Step 5: Run the tests**

```
cd backend
python -m pytest tests/test_graph_rag.py -v
```
Expected: `2 PASSED`

- [ ] **Step 6: Commit**

```
git add backend/core/rag/__init__.py backend/core/rag/graph_rag.py backend/tests/test_graph_rag.py
git commit -m "feat(rag): add GraphRAG entity extraction and traversal

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Hybrid retriever — vector + graph, deduplicated

**Files:**
- Create: `backend/core/rag/hybrid_retriever.py`
- Test: `backend/tests/test_hybrid_retriever.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_hybrid_retriever.py
from unittest.mock import MagicMock, patch
import pytest
from backend.core.rag.hybrid_retriever import HybridRetriever

def _make_chromadb_result(doc_id: str, chunk_index: int, score: float) -> dict:
    return {
        "id": f"{doc_id}_chunk_{chunk_index}",
        "document": "sample text",
        "metadata": {
            "doc_id": doc_id,
            "page": 1,
            "original_name": "test.pdf",
            "source": f"{doc_id}_chunk_{chunk_index}",
        },
        "distance": 1.0 - score,
    }

def test_hybrid_deduplicates_vector_and_graph():
    """Chunks returned by both vector and graph expansion should not be duplicated."""
    mock_rag = MagicMock()
    mock_rag.search.return_value = [
        _make_chromadb_result("doc1", 0, 0.9),
        _make_chromadb_result("doc1", 1, 0.8),
    ]
    mock_graph = MagicMock()
    mock_graph.find_related_chunks.return_value = {1, 2}  # chunk 1 overlaps

    retriever = HybridRetriever(rag_engine=mock_rag, graph_rag=mock_graph)
    results = retriever.retrieve(query="test", doc_ids=["doc1"], top_k=10)
    ids = [r["id"] for r in results]
    # chunk 1 appears in both vector and graph — must appear only once
    assert ids.count("doc1_chunk_1") == 1
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_hybrid_retriever.py -v
```
Expected: `FAILED`

- [ ] **Step 3: Create `backend/core/rag/hybrid_retriever.py`**

```python
"""
Hybrid retriever: combines ChromaDB vector results with graph-expanded chunks.

Workflow:
1. Vector search via RAGEngine for top_k results.
2. Extract chunk indices from vector results.
3. Use GraphRAG to find related chunks from entity co-occurrence.
4. Fetch graph-expanded chunks from ChromaDB by ID.
5. Merge, deduplicate by chunk ID, sort by score descending.
"""
from __future__ import annotations

from typing import Any

from backend.core.rag.graph_rag import GraphRAG
from backend.core.rag_engine import RAGEngine


class HybridRetriever:
    def __init__(self, rag_engine: RAGEngine, graph_rag: GraphRAG,
                 graph_expansion_depth: int = 1,
                 graph_weight: float = 0.6):
        self._rag = rag_engine
        self._graph = graph_rag
        self._depth = graph_expansion_depth
        self._graph_weight = graph_weight  # score multiplier for graph-expanded chunks

    def retrieve(self, query: str, doc_ids: list[str] | None = None,
                 top_k: int = 8) -> list[dict[str, Any]]:
        """
        Return deduplicated, re-ranked list of chunk result dicts.
        Each result: {id, document, metadata, score}
        """
        # ── 1. Vector search ──────────────────────────────────────────────────
        vec_filter = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        raw_results = self._rag.search(query, top_k=top_k, filter=vec_filter)

        seen_ids: set[str] = set()
        merged: list[dict[str, Any]] = []

        for r in raw_results:
            rid = r.get("id") or r["metadata"].get("source", "")
            score = 1.0 - float(r.get("distance", 0.5))
            merged.append({**r, "id": rid, "score": score})
            seen_ids.add(rid)

        # ── 2. Graph expansion ────────────────────────────────────────────────
        if doc_ids:
            for doc_id in doc_ids:
                seed_indices = [
                    int(r["id"].split("_chunk_")[-1])
                    for r in merged
                    if r["metadata"].get("doc_id") == doc_id
                    and "_chunk_" in r["id"]
                ]
                if not seed_indices:
                    continue
                related_indices = self._graph.find_related_chunks(
                    doc_id, seed_indices, depth=self._depth
                )
                # Fetch these chunks from ChromaDB
                extra_ids = [f"{doc_id}_chunk_{i}" for i in related_indices]
                extra_ids = [eid for eid in extra_ids if eid not in seen_ids]
                if not extra_ids:
                    continue
                try:
                    fetched = self._rag.collection.get(
                        ids=extra_ids, include=["documents", "metadatas"]
                    )
                    for cid, text, meta in zip(
                        fetched["ids"], fetched["documents"], fetched["metadatas"]
                    ):
                        if cid not in seen_ids:
                            merged.append({
                                "id": cid,
                                "document": text,
                                "metadata": meta,
                                "score": self._graph_weight,  # lower than vector results
                            })
                            seen_ids.add(cid)
                except Exception:
                    pass  # ChromaDB error — continue without graph expansion

        # ── 3. Sort by score descending ───────────────────────────────────────
        merged.sort(key=lambda r: r["score"], reverse=True)
        return merged[:top_k]
```

- [ ] **Step 4: Run the tests**

```
cd backend
python -m pytest tests/test_hybrid_retriever.py -v
```
Expected: `PASSED`

- [ ] **Step 5: Wire hybrid retriever into `rag_engine.py` as `hybrid_search`**

In `backend/core/rag_engine.py`, add a method after the existing `search`:

```python
def hybrid_search(self, query: str, doc_ids: list[str] | None = None,
                  top_k: int = 8) -> list[dict]:
    """
    Perform hybrid vector + graph search.
    Falls back to plain vector search when GraphRAG returns no entities.
    """
    from backend.core.rag.hybrid_retriever import HybridRetriever
    from backend.core.rag.graph_rag import GraphRAG
    import pathlib
    graph = GraphRAG(db_path=pathlib.Path(__file__).parent.parent / "chatbot.db")
    retriever = HybridRetriever(rag_engine=self, graph_rag=graph)
    return retriever.retrieve(query=query, doc_ids=doc_ids, top_k=top_k)
```

- [ ] **Step 6: Run all RAG tests**

```
cd backend
python -m pytest tests/test_graph_rag.py tests/test_hybrid_retriever.py -v
```
Expected: `4 PASSED`

- [ ] **Step 7: Commit**

```
git add backend/core/rag/hybrid_retriever.py backend/core/rag_engine.py backend/tests/test_hybrid_retriever.py
git commit -m "feat(rag): hybrid vector+graph retriever

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3 — Report Intelligence Layer (P1 Critical)

### Task 6: `REPORT_INTEL` dictionary

**Files:**
- Create: `backend/core/report_templates/__init__.py` (empty)
- Create: `backend/core/report_templates/report_intel.py`
- Test: `backend/tests/test_report_intel.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_report_intel.py
from backend.core.report_templates.report_intel import REPORT_INTEL

EXPECTED_TYPES = [
    "mis", "audit", "tax_advisory", "legal_memo", "due_diligence",
    "financial_analysis", "compliance", "board_pack", "vat_filing",
    "aml_report", "valuation", "contract_review",
]

def test_all_report_types_present():
    for rt in EXPECTED_TYPES:
        assert rt in REPORT_INTEL, f"Missing report type: {rt}"

def test_each_type_has_required_keys():
    for rt, intel in REPORT_INTEL.items():
        for key in ("audience", "purpose", "key_points", "tone", "structure"):
            assert key in intel, f"{rt} missing key: {key}"

def test_key_points_are_lists():
    for rt, intel in REPORT_INTEL.items():
        assert isinstance(intel["key_points"], list)
        assert len(intel["key_points"]) >= 3, f"{rt} has fewer than 3 key_points"
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_report_intel.py -v
```
Expected: `FAILED`

- [ ] **Step 3: Create `backend/core/report_templates/__init__.py`** (empty)

- [ ] **Step 4: Create `backend/core/report_templates/report_intel.py`**

```python
"""
REPORT_INTEL — authoritative intelligence per report type.

Every entry provides:
  audience   : Who will read this report (persona description).
  purpose    : The primary purpose / job to be done.
  key_points : Ordered list of mandatory sections/considerations the LLM must address.
  tone       : Writing tone instruction.
  structure  : High-level document structure instruction.
"""

REPORT_INTEL: dict[str, dict] = {

    "mis": {
        "audience": (
            "C-suite executives (CEO, CFO, Board of Directors) who need a fast, "
            "data-dense snapshot of business performance. They are time-poor and "
            "want numbers first, narrative second."
        ),
        "purpose": (
            "Provide a concise Management Information System report summarising "
            "KPIs, financial highlights, and operational metrics for the period."
        ),
        "key_points": [
            "Executive summary: 3–5 bullet-point highlights",
            "Revenue vs budget / prior period (variance analysis)",
            "Gross margin, EBITDA, Net Profit with % change",
            "Cash position and working capital movement",
            "Top cost drivers and any abnormal items",
            "Departmental performance vs targets",
            "Key risks and mitigating actions",
            "Outlook / next-period guidance",
        ],
        "tone": "Concise, factual, executive-friendly. Use tables and bullet points.",
        "structure": (
            "1. Executive Summary  2. Financial Highlights (table)  "
            "3. Revenue Analysis  4. Cost Analysis  5. Cash Flow  "
            "6. Operational KPIs  7. Risks & Actions  8. Outlook"
        ),
    },

    "audit": {
        "audience": (
            "Audit committee, board of directors, and external stakeholders. "
            "Readers are financially literate but expect formal, precise language."
        ),
        "purpose": (
            "Present findings, opinions, and recommendations from an audit engagement "
            "in accordance with applicable auditing standards (ISA/IFRS/local GAAP)."
        ),
        "key_points": [
            "Auditor's independent opinion (unqualified/qualified/adverse/disclaimer)",
            "Basis of opinion — standards applied (e.g., ISAs issued by IAASB)",
            "Key audit matters (KAMs) with responses",
            "Going concern assessment",
            "Material misstatements found and management response",
            "Internal control deficiencies and recommendations",
            "Emphasis of matter paragraphs if applicable",
            "Comparative period figures and restatements",
        ],
        "tone": "Formal, precise, independent. Use passive voice where appropriate.",
        "structure": (
            "1. Auditor's Report  2. Basis of Opinion  3. Key Audit Matters  "
            "4. Going Concern  5. Responsibilities (Management / Auditor)  "
            "6. Internal Control Observations  7. Recommendations"
        ),
    },

    "tax_advisory": {
        "audience": (
            "Tax directors, CFOs, and legal counsel. They require technically precise "
            "advice with clear references to statutes, decrees, and precedents."
        ),
        "purpose": (
            "Deliver a professional tax advisory memo outlining exposure, "
            "planning opportunities, and compliance obligations."
        ),
        "key_points": [
            "Executive summary of tax position",
            "Applicable laws, decrees, and ministerial decisions cited by article/number",
            "Taxable vs exempt income/supply breakdown",
            "Tax base calculation with step-by-step workings",
            "Transfer pricing considerations (where relevant)",
            "Penalties and interest exposure for non-compliance",
            "Recommended tax planning strategies with risk ratings",
            "Filing deadlines and next action items",
        ],
        "tone": "Technical, precise, authoritative. Cite all statutory references.",
        "structure": (
            "1. Executive Summary  2. Background & Facts  3. Legal Analysis  "
            "4. Tax Calculation  5. Planning Options  6. Risks & Penalties  "
            "7. Recommendations  8. Next Steps"
        ),
    },

    "legal_memo": {
        "audience": (
            "Partners, senior counsel, or in-house legal teams. They require "
            "structured legal analysis with clear conclusions and risk ratings."
        ),
        "purpose": (
            "Analyse a legal question, contract, or dispute and provide a well-reasoned "
            "legal opinion with actionable recommendations."
        ),
        "key_points": [
            "Issue statement — precise legal question(s) being addressed",
            "Applicable law, jurisdiction, and governing legislation",
            "Facts and assumptions relied upon",
            "Legal analysis — case law, statutory interpretation",
            "Risk assessment (Low / Medium / High) with reasoning",
            "Counter-arguments and how they are addressed",
            "Clear conclusions and legal opinion",
            "Recommended course of action",
        ],
        "tone": "Formal legal prose. Precise, logical, objective.",
        "structure": (
            "1. Issue  2. Brief Answer  3. Facts  4. Analysis  "
            "5. Conclusion  6. Recommendations"
        ),
    },

    "due_diligence": {
        "audience": (
            "Investors, acquirers, and their advisors. Readers are sophisticated but "
            "need a balanced view of opportunities and risks to inform a transaction decision."
        ),
        "purpose": (
            "Provide comprehensive due diligence findings covering financial, legal, "
            "tax, and operational dimensions of a target entity."
        ),
        "key_points": [
            "Transaction overview and scope of review",
            "Financial due diligence — historical performance, quality of earnings",
            "Balance sheet review — asset quality, off-balance-sheet items",
            "Working capital analysis and normalised levels",
            "Legal due diligence — contracts, litigation, IP, regulatory licences",
            "Tax due diligence — exposures, filing history, disputes",
            "Operational and management team assessment",
            "Red flags, deal-breakers, and conditions precedent",
            "Valuation considerations and suggested adjustments",
        ],
        "tone": "Balanced, thorough, investor-oriented. Highlight red flags clearly.",
        "structure": (
            "1. Executive Summary  2. Scope & Limitations  3. Financial Analysis  "
            "4. Legal Review  5. Tax Review  6. Operational Review  "
            "7. Key Findings & Red Flags  8. Conditions & Recommendations"
        ),
    },

    "financial_analysis": {
        "audience": (
            "Finance managers, analysts, and business stakeholders who need a detailed "
            "quantitative and qualitative analysis of financial performance."
        ),
        "purpose": (
            "Analyse financial statements to assess profitability, liquidity, solvency, "
            "and efficiency, benchmarked against industry or prior periods."
        ),
        "key_points": [
            "Profitability ratios (GPM, NPM, EBITDA margin, ROE, ROA)",
            "Liquidity ratios (current, quick, cash ratios)",
            "Solvency / leverage ratios (D/E, interest coverage)",
            "Efficiency ratios (inventory turnover, receivables days, payables days)",
            "Trend analysis over 2–3 periods",
            "Variance analysis — actuals vs budget vs prior year",
            "Peer comparison / industry benchmark (where data available)",
            "Conclusion on financial health and investment attractiveness",
        ],
        "tone": "Analytical, data-driven. Use ratios, tables, and trend commentary.",
        "structure": (
            "1. Overview  2. Income Statement Analysis  3. Balance Sheet Analysis  "
            "4. Cash Flow Analysis  5. Ratio Summary Table  6. Benchmarking  "
            "7. Conclusions"
        ),
    },

    "compliance": {
        "audience": (
            "Compliance officers, regulators, and senior management. They need evidence "
            "of compliance posture and clear identification of gaps."
        ),
        "purpose": (
            "Document the entity's compliance status against applicable regulations, "
            "identify gaps, and recommend corrective actions."
        ),
        "key_points": [
            "Regulatory framework and applicable laws/standards",
            "Compliance assessment methodology",
            "Gap analysis — compliant vs non-compliant areas",
            "Severity rating for each gap (Critical / High / Medium / Low)",
            "Root cause analysis for non-compliances",
            "Corrective action plan with owners and deadlines",
            "Monitoring and testing procedures",
            "Management attestation requirements",
        ],
        "tone": "Systematic, evidence-based. Use gap matrices and RAG status indicators.",
        "structure": (
            "1. Scope  2. Regulatory Summary  3. Assessment Methodology  "
            "4. Gap Analysis Matrix  5. Root Cause Analysis  "
            "6. Corrective Action Plan  7. Monitoring Framework"
        ),
    },

    "board_pack": {
        "audience": (
            "Non-executive directors and board members. They require high-level strategic "
            "information, not operational detail. Time is extremely limited."
        ),
        "purpose": (
            "Provide a concise, decision-ready board pack covering performance, "
            "strategy, risk, and governance matters for the board meeting."
        ),
        "key_points": [
            "Agenda and purpose of the meeting",
            "Financial performance summary (one-page dashboard style)",
            "Strategic initiatives — progress vs plan",
            "Key risks and updated risk register",
            "Governance and compliance matters",
            "Capital allocation / investment decisions requiring approval",
            "CEO / MD operational update",
            "Resolutions to be passed",
        ],
        "tone": "Concise, strategic, decision-oriented. No operational minutiae.",
        "structure": (
            "1. Agenda  2. Financial Dashboard  3. Strategic Update  "
            "4. Risk Report  5. Governance  6. Resolutions"
        ),
    },

    "vat_filing": {
        "audience": (
            "Tax teams, CFOs, and UAE FTA (Federal Tax Authority) as the regulatory recipient. "
            "Must comply with FTA format requirements and be defensible under audit."
        ),
        "purpose": (
            "Prepare or review a UAE VAT return filing with full workings, "
            "reconciliation to accounting records, and supporting schedules."
        ),
        "key_points": [
            "Tax period covered and return reference",
            "Standard-rated supplies — Emirates-wise breakdown",
            "Zero-rated supplies (exports, international services)",
            "Exempt supplies",
            "Input tax credit claimed with eligibility analysis",
            "Input tax blocked/apportioned (partial exemption)",
            "Adjustment for previous period errors (where applicable)",
            "Net VAT payable / refundable with FTA reference",
            "Reconciliation to VAT control account in GL",
        ],
        "tone": "Regulatory-precise. Follow FTA VAT return box numbering.",
        "structure": (
            "1. Filing Summary  2. Output Tax Workings  3. Input Tax Workings  "
            "4. Adjustments  5. Net Position  6. GL Reconciliation  7. Supporting Schedules"
        ),
    },

    "aml_report": {
        "audience": (
            "Compliance officers, Money Laundering Reporting Officers (MLROs), and regulators "
            "(CBUAE, FSRA). Readers expect technical precision and regulatory alignment."
        ),
        "purpose": (
            "Document AML/CFT compliance findings, suspicious activity, and the "
            "entity's risk-based approach in line with FATF recommendations and UAE law."
        ),
        "key_points": [
            "Regulatory basis — UAE AML Law (Fed Decree 20/2018), Cabinet Decision 10/2019",
            "Risk appetite and methodology (FATF risk-based approach)",
            "Customer risk assessment — low/medium/high risk segmentation",
            "Transaction monitoring findings and alert statistics",
            "Suspicious Transaction Reports (STRs) filed in period",
            "Enhanced due diligence (EDD) cases and outcomes",
            "Sanctions screening results",
            "Training and awareness completion rates",
            "Gaps identified and remediation plan",
        ],
        "tone": "Regulatory, precise, risk-focused.",
        "structure": (
            "1. Executive Summary  2. Regulatory Framework  3. Risk Assessment  "
            "4. Transaction Monitoring  5. STR/SAR Summary  6. EDD Cases  "
            "7. Sanctions  8. Training  9. Gaps & Remediation"
        ),
    },

    "valuation": {
        "audience": (
            "Business owners, investors, banks, and courts. They need a defensible, "
            "methodology-driven value conclusion with clear assumptions."
        ),
        "purpose": (
            "Deliver a professional business or asset valuation using recognised methods "
            "(DCF, market multiples, net assets) with a concluded value range."
        ),
        "key_points": [
            "Purpose and scope of the valuation",
            "Standard of value used (fair market value, investment value, etc.)",
            "Valuation date and information relied upon",
            "Business / asset description and industry overview",
            "DCF analysis — projected cash flows, WACC, terminal value",
            "Market multiples approach — comparable transactions / trading multiples",
            "Net asset value approach (where applicable)",
            "Reconciliation and concluded value range",
            "Sensitivity analysis on key assumptions",
            "Limitations and disclaimer",
        ],
        "tone": "Professional, independent, methodology-transparent.",
        "structure": (
            "1. Executive Summary  2. Scope & Methodology  3. Business Overview  "
            "4. DCF Valuation  5. Market Multiples  6. NAV Approach  "
            "7. Reconciliation  8. Sensitivity  9. Conclusion & Disclaimer"
        ),
    },

    "contract_review": {
        "audience": (
            "Legal counsel, business managers, and counterparties. "
            "They need clear identification of risks, obligations, and negotiation points."
        ),
        "purpose": (
            "Review a contract or agreement and provide a structured summary of key "
            "terms, risks, and recommended amendments."
        ),
        "key_points": [
            "Parties, governing law, and jurisdiction",
            "Key commercial terms (price, payment, delivery, duration)",
            "Representations, warranties, and indemnities",
            "Limitation of liability and exclusion clauses",
            "Termination triggers and consequences",
            "Intellectual property rights and confidentiality",
            "Dispute resolution mechanism (arbitration/litigation/ADR)",
            "Unusual or one-sided clauses — flag and recommend amendments",
            "Missing standard protections (force majeure, change in law, etc.)",
        ],
        "tone": "Legal, analytical. Clearly flag risk items with RED / AMBER / GREEN ratings.",
        "structure": (
            "1. Contract Summary Table  2. Key Commercial Terms  3. Legal Risk Analysis  "
            "4. Clause-by-Clause Review  5. Red Flags  6. Recommended Amendments"
        ),
    },
}
```

- [ ] **Step 5: Run the tests**

```
cd backend
python -m pytest tests/test_report_intel.py -v
```
Expected: `3 PASSED`

- [ ] **Step 6: Commit**

```
git add backend/core/report_templates/__init__.py backend/core/report_templates/report_intel.py backend/tests/test_report_intel.py
git commit -m "feat(reports): REPORT_INTEL dict with audience/purpose/key_points for all 12 report types

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Template manager — download and cache public Big4/ISA/FTA templates

**Files:**
- Create: `backend/core/report_templates/template_manager.py`
- Test: `backend/tests/test_template_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_template_manager.py
import pathlib, pytest
from unittest.mock import patch, MagicMock
from backend.core.report_templates.template_manager import TemplateManager

@pytest.fixture
def mgr(tmp_path):
    return TemplateManager(cache_dir=tmp_path)

def test_get_template_returns_str(mgr):
    """get_template must always return a string (even if download fails)."""
    with patch("httpx.get", side_effect=Exception("network error")):
        result = mgr.get_template("audit")
    assert isinstance(result, str)

def test_get_template_cached_after_first_call(mgr):
    """Second call must not make a network request."""
    fake_content = "# ISA 700 Audit Template\nThis is a test template."
    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = fake_content
        mock_get.return_value = mock_response
        r1 = mgr.get_template("audit")
    # second call — no network
    r2 = mgr.get_template("audit")
    assert r1 == r2 == fake_content

def test_refresh_clears_cache(mgr, tmp_path):
    """refresh() must delete cached files so next call re-downloads."""
    cache_file = tmp_path / "audit.md"
    cache_file.write_text("old content")
    mgr.refresh("audit")
    assert not cache_file.exists()
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_template_manager.py -v
```
Expected: `FAILED`

- [ ] **Step 3: Create `backend/core/report_templates/template_manager.py`**

```python
"""
TemplateManager — downloads, caches, and serves public accounting/audit templates.

Template sources (all public domain / open-access):
  - ISA 700 / IAASB model audit opinion
  - UAE FTA VAT guide
  - ACCA financial analysis guidance
  - Big4-style MIS / Board Pack structure (synthesised from published examples)

Templates are stored as Markdown files in a local cache directory.
They are injected into LLM system prompts as structural scaffolding.
"""
from __future__ import annotations

import pathlib
from typing import Optional

import httpx

# Public template sources keyed by report_type
_TEMPLATE_URLS: dict[str, str] = {
    "audit": (
        "https://raw.githubusercontent.com/IAASB/model-auditor-report/"
        "main/isa700-revised-example.md"
    ),
    # FTA VAT filing guide (public PDF → converted text version on GitHub)
    "vat_filing": (
        "https://raw.githubusercontent.com/uae-tax/vat-guides/"
        "main/vat-return-guide.md"
    ),
}

# Fallback templates embedded in code (used when download fails)
_FALLBACK_TEMPLATES: dict[str, str] = {
    "audit": """## Independent Auditor's Report Structure (ISA 700)

### Title
Independent Auditor's Report to the Shareholders of [Entity Name]

### Audit Opinion
We have audited the financial statements of [Entity], which comprise:
- The statement of financial position as at [Date]
- The statement of profit or loss and other comprehensive income
- The statement of changes in equity
- The statement of cash flows
- Notes to the financial statements

In our opinion, the accompanying financial statements present fairly, in all material
respects, the financial position of [Entity] as at [Date], in accordance with
International Financial Reporting Standards (IFRSs).

### Basis for Opinion
We conducted our audit in accordance with International Standards on Auditing (ISAs).
Our responsibilities under those standards are further described in the Auditor's
Responsibilities section. We are independent of the Entity and have fulfilled our
ethical responsibilities in accordance with IESBA Code of Ethics.

### Key Audit Matters
[Describe each KAM: matter, how it was addressed in the audit, reference to note]

### Going Concern
[Assess and state conclusion]

### Responsibilities of Management
[Standard paragraph]

### Auditor's Responsibilities
[Standard ISA 700 paragraph on reasonable assurance, material misstatement, fraud/error]
""",
    "mis": """## MIS Report Structure (Big4 Standard)

### Executive Summary
| KPI | Current Period | Prior Period | Variance | Variance % |
|-----|---------------|-------------|----------|------------|
| Revenue | | | | |
| Gross Profit | | | | |
| EBITDA | | | | |
| Net Profit | | | | |
| Cash Position | | | | |

### Financial Highlights
[3–5 bullet points on key performance drivers]

### Revenue Analysis
[Table: Revenue by segment / product / geography]

### Cost Analysis
[Table: Cost breakdown with actuals vs budget]

### Cash Flow Summary
[Opening balance → Operating → Investing → Financing → Closing]

### Operational KPIs
[Table: non-financial metrics relevant to the business]

### Risks and Actions
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| | | | |

### Outlook
[Forward-looking commentary for next period]
""",
    "board_pack": """## Board Pack Structure (Big4 / ACCA Standard)

### Agenda
1. Financial Performance Review
2. Strategic Initiatives Update
3. Risk Report
4. Governance & Compliance
5. Resolutions

### Financial Dashboard (One-Page Summary)
| Metric | Budget | Actual | Variance |
|--------|--------|--------|---------|
| Revenue | | | |
| EBITDA | | | |
| Cash | | | |

### Strategic Update
[Progress against each strategic priority]

### Risk Register (Top 5)
| Risk | Rating | Owner | Status |
|------|--------|-------|--------|

### Resolutions
[List of resolutions requiring board approval]
""",
    "due_diligence": """## Due Diligence Report Structure (Big4 Standard)

### Executive Summary
[Transaction overview, key findings in 3–5 bullets, overall recommendation]

### Scope and Limitations
[Work performed, information relied upon, limitations]

### Financial Due Diligence
#### Historical Performance (3-year trend)
[Revenue, EBITDA, Net Profit tables]
#### Quality of Earnings Adjustments
[Normalisation items]
#### Working Capital Analysis
[Normalised working capital calculation]
#### Balance Sheet Review
[Asset quality, contingencies, off-balance-sheet items]

### Legal Due Diligence
[Contracts, litigation, licences, IP]

### Tax Due Diligence
[Filing history, exposures, disputes]

### Key Findings and Red Flags
| Finding | Severity | Impact on Valuation |
|---------|----------|---------------------|

### Conditions Precedent
[Required actions before transaction completion]
""",
    "tax_advisory": """## Tax Advisory Memo Structure

### Executive Summary
[Key conclusion in 3 sentences]

### Background and Facts
[Entity description, transaction facts, assumptions relied upon]

### Legal Analysis
#### Applicable Legislation
[Cite: Decree number, Article number, effective date]
#### Technical Analysis
[Step-by-step statutory interpretation]

### Tax Calculation
| Item | Amount (AED) | Notes |
|------|-------------|-------|

### Planning Options
| Option | Tax Saving | Risk Level | Recommendation |
|--------|-----------|------------|---------------|

### Penalties and Exposures
[FTA penalty schedule reference]

### Recommendations and Next Steps
[Numbered action items with deadlines]
""",
    "vat_filing": """## UAE VAT Return Structure (FTA Format)

### Filing Period
Tax Period: [DD/MM/YYYY – DD/MM/YYYY]
TRN: [Tax Registration Number]

### Output Tax
| Box | Description | Amount (AED) | VAT (AED) |
|-----|-------------|-------------|----------|
| 1 | Standard-rated supplies in Abu Dhabi | | |
| 2 | Standard-rated supplies in Dubai | | |
| 3 | Standard-rated supplies in Sharjah | | |
| 4 | Standard-rated supplies in Ajman | | |
| 5 | Standard-rated supplies in UAQ | | |
| 6 | Standard-rated supplies in RAK | | |
| 7 | Standard-rated supplies in Fujairah | | |
| 8 | Standard-rated supplies — Total | | |
| 9 | Zero-rated supplies | | |
| 10 | Exempt supplies | | |
| 11 | Total supplies | | |
| 12 | Imports subject to VAT (deferred) | | |

### Input Tax
| Box | Description | Amount (AED) | Recoverable VAT (AED) |
|-----|-------------|-------------|----------------------|
| 13 | Standard-rated purchases | | |
| 14 | Imports subject to VAT (paid at customs) | | |

### Net VAT
| Box | Description | Amount (AED) |
|-----|-------------|-------------|
| 15 | Total output VAT due | |
| 16 | Total input VAT recoverable | |
| 17 | Net VAT payable / (refundable) | |
""",
}


class TemplateManager:
    """
    Manages download, caching, and retrieval of report structure templates.

    Templates are stored as {report_type}.md files in `cache_dir`.
    If a template cannot be downloaded, a built-in fallback is returned.
    """

    def __init__(self, cache_dir: Optional[pathlib.Path] = None):
        if cache_dir is None:
            cache_dir = pathlib.Path(__file__).parent / "_cache"
        self._cache_dir = pathlib.Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_template(self, report_type: str) -> str:
        """
        Return the template for the given report type.
        1. Check disk cache → return if found.
        2. Try to download from URL.
        3. Fall back to embedded template string.
        """
        cache_file = self._cache_dir / f"{report_type}.md"
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8")

        url = _TEMPLATE_URLS.get(report_type)
        if url:
            try:
                resp = httpx.get(url, timeout=10, follow_redirects=True)
                if resp.status_code == 200 and resp.text.strip():
                    cache_file.write_text(resp.text, encoding="utf-8")
                    return resp.text
            except Exception:
                pass  # network unavailable — use fallback

        fallback = _FALLBACK_TEMPLATES.get(report_type, "")
        if fallback:
            cache_file.write_text(fallback, encoding="utf-8")
        return fallback

    def refresh(self, report_type: Optional[str] = None) -> list[str]:
        """
        Delete cached template(s) so the next get_template() re-downloads.
        Returns list of deleted file names.
        """
        deleted: list[str] = []
        if report_type:
            f = self._cache_dir / f"{report_type}.md"
            if f.exists():
                f.unlink()
                deleted.append(f.name)
        else:
            for f in self._cache_dir.glob("*.md"):
                f.unlink()
                deleted.append(f.name)
        return deleted
```

- [ ] **Step 4: Run the tests**

```
cd backend
python -m pytest tests/test_template_manager.py -v
```
Expected: `3 PASSED`

- [ ] **Step 5: Commit**

```
git add backend/core/report_templates/template_manager.py backend/tests/test_template_manager.py
git commit -m "feat(reports): TemplateManager with cache + public template downloads

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Inject REPORT_INTEL into `generate-stream` system prompt

**Files:**
- Modify: `backend/api/reports.py` (around lines 2370–2437)
- Test: `backend/tests/test_reports_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reports_api.py
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_generate_stream_includes_audience_in_prompt(client):
    """
    The generate-stream endpoint must build a system prompt that includes
    the audience description for the requested report type.
    """
    captured_prompts = []

    async def mock_stream(*args, **kwargs):
        captured_prompts.append(kwargs.get("messages", args[0] if args else []))
        yield {"choices": [{"delta": {"content": "test report"}, "finish_reason": None}]}
        yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}

    with patch("backend.api.reports.client.chat.completions.create",
               new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value.__aiter__ = mock_stream
        payload = {
            "report_type": "audit",
            "entity_name": "Test Co LLC",
            "period_end": "2025-12-31",
            "auditor_format": "big4",
            "selected_doc_ids": [],
        }
        resp = await client.post("/api/reports/generate-stream", json=payload)
        # We only check that the endpoint returns 200 and that audience was injected

    # Check at least one captured system message contains audience info
    sys_messages = [
        m["content"] for call_args in captured_prompts
        for m in (call_args if isinstance(call_args, list) else [])
        if isinstance(m, dict) and m.get("role") == "system"
    ]
    assert any("audit committee" in m.lower() or "board" in m.lower()
               for m in sys_messages), "Audience not found in system prompt"
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_reports_api.py::test_generate_stream_includes_audience_in_prompt -v
```
Expected: `FAILED`

- [ ] **Step 3: Edit `backend/api/reports.py` — add imports at top**

```python
# Add to existing imports near the top of reports.py
from backend.core.report_templates.report_intel import REPORT_INTEL
from backend.core.report_templates.template_manager import TemplateManager

_template_mgr = TemplateManager()
```

- [ ] **Step 4: Replace the `generate-stream` system prompt construction**

Find the block in `generate-stream` that builds the system prompt (search for `REPORT_SYSTEM_PROMPTS.get`). Replace it with:

```python
# ── Build rich system prompt ─────────────────────────────────────────────────
intel = REPORT_INTEL.get(req.report_type, {})
audience    = intel.get("audience", "finance professionals")
purpose     = intel.get("purpose", "produce a professional report")
key_points  = intel.get("key_points", [])
tone        = intel.get("tone", "professional and precise")
structure   = intel.get("structure", "")

# Format string (Big4 / ISA / FTA / internal)
format_instr = _FORMAT_PROMPTS.get(req.auditor_format, _FORMAT_PROMPTS.get("big4", ""))

# Structural template scaffold
template_scaffold = _template_mgr.get_template(req.report_type)

# Period enforcement — LLM must not use data outside the requested period
period_clause = (
    f"\n\nCRITICAL — Period Constraint: This report covers the period ending "
    f"{req.period_end}. You MUST use ONLY data for this period. "
    f"Do NOT include data from any other year or period, even if available in context."
)

key_points_text = "\n".join(f"  {i+1}. {kp}" for i, kp in enumerate(key_points))

system_prompt = (
    f"You are a senior professional preparing a {req.report_type.upper().replace('_', ' ')} "
    f"report for {req.entity_name}.\n\n"
    f"AUDIENCE: {audience}\n\n"
    f"PURPOSE: {purpose}\n\n"
    f"MANDATORY KEY POINTS — every section below must be addressed:\n{key_points_text}\n\n"
    f"TONE: {tone}\n\n"
    f"DOCUMENT STRUCTURE:\n{structure}\n\n"
    f"{format_instr}\n"
    f"{period_clause}\n\n"
    f"STRUCTURAL TEMPLATE (follow this skeleton, populate from the provided documents):\n"
    f"{'=' * 60}\n{template_scaffold}\n{'=' * 60}\n\n"
    f"BASE YOUR REPORT EXCLUSIVELY on the document extracts provided below. "
    f"If a required section cannot be populated from the documents, state: "
    f"'[Insufficient data — not determinable from provided documents]' "
    f"and explain what additional information is needed. "
    f"NEVER invent figures, dates, or entity names."
)
```

- [ ] **Step 5: Ensure the system prompt is used in the messages list**

Find the `messages=[...]` list in the `generate-stream` endpoint. Ensure the system message uses the new `system_prompt` variable:

```python
messages=[
    {"role": "system", "content": system_prompt},   # ← use new variable
    {"role": "user",   "content": rag_context_and_query},
]
```

Where `rag_context_and_query` is the existing user message that includes RAG context + the user's generation request. Verify the variable name matches the existing code before editing.

- [ ] **Step 6: Run the test**

```
cd backend
python -m pytest tests/test_reports_api.py -v
```
Expected: `PASSED`

- [ ] **Step 7: Commit**

```
git add backend/api/reports.py backend/tests/test_reports_api.py
git commit -m "feat(reports): inject REPORT_INTEL + template scaffold + period enforcement into generate-stream

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: `POST /api/reports/refresh-templates` endpoint

**Files:**
- Modify: `backend/api/reports.py`
- Test: extend `backend/tests/test_reports_api.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_reports_api.py

async def test_refresh_templates_returns_200(client):
    """POST /api/reports/refresh-templates must return 200 with deleted list."""
    resp = await client.post("/api/reports/refresh-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "deleted" in data
    assert isinstance(data["deleted"], list)
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_reports_api.py::test_refresh_templates_returns_200 -v
```
Expected: `FAILED`

- [ ] **Step 3: Add the endpoint to `reports.py`**

At the end of the reports router (before the final `return router` or after the last existing endpoint):

```python
@router.post("/refresh-templates")
async def refresh_templates(report_type: str | None = None):
    """
    Clears cached report structure templates so the next generate-stream
    call re-downloads them from public sources.
    """
    deleted = _template_mgr.refresh(report_type=report_type)
    return {"deleted": deleted, "message": f"Cleared {len(deleted)} cached template(s)."}
```

- [ ] **Step 4: Run the tests**

```
cd backend
python -m pytest tests/test_reports_api.py -v
```
Expected: all PASSED

- [ ] **Step 5: Commit**

```
git add backend/api/reports.py backend/tests/test_reports_api.py
git commit -m "feat(reports): add /api/reports/refresh-templates endpoint

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 10: Fix `reportConfigs.ts` — add audience/purpose/keyPoints, remove duplicates

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/reportConfigs.ts`

- [ ] **Step 1: Add new fields to the `ReportConfig` interface**

Find the `ReportConfig` interface (around line 12) and add three optional fields:

```typescript
export interface ReportConfig {
  type: string;
  label: string;
  icon: string;
  fields: ReportField[];
  sections?: string[];
  supportedFormats?: string[];
  detectFields?: Record<string, string[]>;
  chartTypes?: string[];
  category?: string;
  audience?: string;          // ← add
  purpose?: string;           // ← add
  keyPoints?: string[];       // ← add
}
```

- [ ] **Step 2: Remove duplicate property blocks in each config entry**

Every config entry in `REPORT_CONFIGS` has duplicated properties (`category`, `detectFields`, `chartTypes`, `supportedFormats`, `sections` appear twice). For each of the 12 report entries:

1. Keep the **first** occurrence of each property.
2. Delete the second occurrence (the duplicate).

Use your editor to search for the pattern: open a config entry, find the second `category:` within the same object literal, delete from the second `category:` to the next `}` closing the duplicate block.

Verify by running:
```
cd frontend && npx tsc --noEmit
```
Expected: zero type errors.

- [ ] **Step 3: Add `audience`, `purpose`, and `keyPoints` to each config**

For each of the 12 report types, add the three fields matching what is in `REPORT_INTEL` on the backend. Below is the complete set — apply each one:

**mis:**
```typescript
audience: "C-suite executives (CEO, CFO, Board) needing a fast KPI snapshot.",
purpose: "Management Information System report — KPIs and financial highlights.",
keyPoints: [
  "Executive summary bullets",
  "Revenue vs budget variance",
  "EBITDA and Net Profit",
  "Cash position",
  "Key risks and actions",
  "Outlook",
],
```

**audit:**
```typescript
audience: "Audit committee, board of directors, and external stakeholders.",
purpose: "Independent audit opinion and findings per ISA/IFRS.",
keyPoints: [
  "Auditor's opinion (unqualified/qualified/adverse)",
  "Key audit matters (KAMs)",
  "Going concern assessment",
  "Material misstatements",
  "Internal control recommendations",
],
```

**tax_advisory:**
```typescript
audience: "Tax directors, CFOs, and legal counsel.",
purpose: "Technical tax advisory with statutory references and planning options.",
keyPoints: [
  "Applicable laws and article citations",
  "Tax base calculation",
  "Transfer pricing",
  "Penalty exposure",
  "Planning recommendations",
  "Filing deadlines",
],
```

**legal_memo:**
```typescript
audience: "Partners, senior counsel, or in-house legal teams.",
purpose: "Legal analysis and opinion with actionable recommendations.",
keyPoints: [
  "Issue and brief answer",
  "Applicable law and jurisdiction",
  "Facts and assumptions",
  "Risk assessment (Low/Medium/High)",
  "Conclusions and recommendations",
],
```

**due_diligence:**
```typescript
audience: "Investors, acquirers, and their advisors.",
purpose: "Comprehensive due diligence covering financial, legal, tax, and operational dimensions.",
keyPoints: [
  "Transaction overview",
  "Quality of earnings",
  "Working capital analysis",
  "Legal and tax exposures",
  "Red flags and deal-breakers",
  "Valuation adjustments",
],
```

**financial_analysis:**
```typescript
audience: "Finance managers and business stakeholders.",
purpose: "Quantitative and qualitative financial performance analysis.",
keyPoints: [
  "Profitability ratios",
  "Liquidity ratios",
  "Solvency ratios",
  "Trend analysis (2–3 periods)",
  "Peer benchmarking",
],
```

**compliance:**
```typescript
audience: "Compliance officers, regulators, and senior management.",
purpose: "Compliance status assessment with gap analysis and corrective actions.",
keyPoints: [
  "Regulatory framework",
  "Gap analysis matrix",
  "Severity ratings (Critical/High/Medium/Low)",
  "Corrective action plan with owners",
  "Monitoring procedures",
],
```

**board_pack:**
```typescript
audience: "Non-executive directors and board members — time-limited, strategic focus.",
purpose: "Decision-ready board pack for the board meeting.",
keyPoints: [
  "Financial performance dashboard",
  "Strategic initiatives update",
  "Top 5 risks",
  "Governance matters",
  "Resolutions requiring approval",
],
```

**vat_filing:**
```typescript
audience: "Tax teams, CFOs, and UAE FTA as the regulatory recipient.",
purpose: "UAE VAT return preparation with FTA box-by-box workings.",
keyPoints: [
  "Emirates-wise standard-rated supplies",
  "Zero-rated and exempt supplies",
  "Input tax credit eligibility",
  "Blocked/apportioned input tax",
  "GL reconciliation",
],
```

**aml_report:**
```typescript
audience: "Compliance officers, MLROs, and regulators (CBUAE, FSRA).",
purpose: "AML/CFT compliance findings per FATF and UAE AML Law.",
keyPoints: [
  "Regulatory basis (UAE AML Law citations)",
  "Customer risk segmentation",
  "Transaction monitoring and STR stats",
  "EDD cases",
  "Gaps and remediation plan",
],
```

**valuation:**
```typescript
audience: "Business owners, investors, banks, and courts.",
purpose: "Defensible valuation using DCF, multiples, and NAV with sensitivity analysis.",
keyPoints: [
  "Standard of value and valuation date",
  "DCF analysis with WACC",
  "Market multiples approach",
  "NAV approach",
  "Reconciliation and concluded value range",
  "Sensitivity analysis",
],
```

**contract_review:**
```typescript
audience: "Legal counsel, business managers, and counterparties.",
purpose: "Contract risk review with RED/AMBER/GREEN ratings and amendment recommendations.",
keyPoints: [
  "Parties, governing law, jurisdiction",
  "Key commercial terms",
  "Risk-rated clause analysis",
  "Unusual or one-sided clauses",
  "Missing standard protections",
  "Recommended amendments",
],
```

- [ ] **Step 4: Type-check the frontend**

```
cd frontend && npx tsc --noEmit
```
Expected: zero type errors.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/studios/LegalStudio/reportConfigs.ts
git commit -m "feat(reports-ui): add audience/purpose/keyPoints to ReportConfig, fix duplicate properties

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 11: Show audience pill in `ConfirmReportCard`

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ConfirmReportCard.tsx`

- [ ] **Step 1: Locate the `Format` row (around line 51–62)**

Find the JSX block that renders the "Format" label row. It looks approximately like:

```tsx
<div className="confirm-row">
  <span className="confirm-label">Format</span>
  <span className="confirm-value">{config.label}</span>
</div>
```

- [ ] **Step 2: Add the audience pill immediately after the Format row**

```tsx
{config.audience && (
  <div className="confirm-row" style={{ alignItems: 'flex-start' }}>
    <span className="confirm-label">Audience</span>
    <span
      className="confirm-value"
      style={{
        background: 'var(--s-accent-subtle, rgba(37,99,235,0.1))',
        color: 'var(--s-accent, #2563eb)',
        borderRadius: '999px',
        padding: '2px 10px',
        fontSize: '11px',
        fontWeight: 500,
        maxWidth: '240px',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
      title={config.audience}
    >
      👥 {config.audience.split('(')[0].trim()}
    </span>
  </div>
)}
```

This shows only the first part of the audience string (before the parenthetical detail) to keep it compact, with the full text available on hover via `title`.

- [ ] **Step 3: Type-check**

```
cd frontend && npx tsc --noEmit
```
Expected: zero errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/components/studios/LegalStudio/ConfirmReportCard.tsx
git commit -m "feat(reports-ui): show audience pill in ConfirmReportCard before generation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 12: Fix report panel scroll + center pane report request visibility

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` (center pane scroll)

- [ ] **Step 1: Fix `ArtifactPanel` scroll containment**

In `ArtifactPanel.tsx`, find the outer container `div` and add `overflow: 'hidden'` to the outer div, and ensure the body div (`flex: 1, overflowY: 'auto'`) has `minHeight: 0`:

```tsx
{/* Outer container — change to: */}
<div style={{
  display: 'flex', flexDirection: 'column', height: '100%',
  overflow: 'hidden',    // ← add this
  background: 'var(--s-bg-1, #fff)', borderLeft: '1px solid var(--s-border, #e2e8f0)',
}}>
  {/* Header stays as-is */}

  {/* Body — add minHeight: 0 */}
  <div style={{ flex: 1, overflowY: 'auto', padding: '16px', minHeight: 0 }}>
```

- [ ] **Step 2: Render Markdown in ArtifactPanel instead of `<pre>`**

Install `react-markdown` if not already present:
```
cd frontend && npm install react-markdown
```

Replace the `<pre>` block in `ArtifactPanel.tsx` with `ReactMarkdown`:

```tsx
import ReactMarkdown from 'react-markdown';

// Replace the <pre> block with:
<div className="report-markdown">
  <ReactMarkdown>{content}</ReactMarkdown>
</div>
```

- [ ] **Step 3: Fix center pane scroll when report panel is open**

In `ThreePaneLayout.tsx`, add `minWidth: 0` and `overflow: 'hidden'` to the center pane:

```tsx
<div className="three-pane-layout__center" style={{ minWidth: 0, overflow: 'hidden' }}>
  {center}
</div>
```

This prevents the center pane from blocking the right panel when it opens.

- [ ] **Step 4: Verify report discuss area is visible in center**

In `LegalStudio.tsx`, find the `centerContent` variable (the JSX rendered in the center pane). Verify it includes the report request UI (`StudioPanel` / `ReportPanel`) and that it is scrollable. If the discuss area is missing from center when the right panel is open, it may be because `artifactOpen` hides it. The right panel currently replaces the `StudioPanel` — **this is correct by design**. The user can close the right panel to return to the report request UI.

If the report discuss options (the form that triggers generation) are not showing at all in center, search for `centerContent` in `LegalStudio.tsx` and ensure the `StudioPanel` (which renders the report trigger) is part of the center pane, not the right pane. Verify by reading the `centerContent` variable assignment — it should include the chat messages AND the report request section below them.

- [ ] **Step 5: Type-check and verify no import errors**

```
cd frontend && npx tsc --noEmit
```
Expected: zero errors.

- [ ] **Step 6: Commit**

```
git add frontend/src/components/studios/LegalStudio/ArtifactPanel.tsx frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx
git commit -m "fix(reports-ui): ArtifactPanel scroll containment, Markdown rendering, center pane scroll

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 4 — Deep Research Endpoint (P1)

### Task 13: `POST /api/chat/deep-research` SSE endpoint

**Files:**
- Modify: `backend/api/chat.py`
- Test: `backend/tests/test_deep_research.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_deep_research.py
import json, pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_deep_research_endpoint_exists(client):
    """POST /api/chat/deep-research must exist and return 200."""
    payload = {
        "query": "What is the VAT rate in UAE?",
        "conversation_id": None,
        "selected_doc_ids": [],
    }
    resp = await client.post("/api/chat/deep-research", json=payload)
    # Endpoint exists — not 404 or 405
    assert resp.status_code not in (404, 405), f"Endpoint missing: {resp.status_code}"

async def test_deep_research_returns_sse(client):
    """Response must be text/event-stream content-type."""
    payload = {"query": "Test query", "conversation_id": None, "selected_doc_ids": []}
    resp = await client.post("/api/chat/deep-research", json=payload)
    assert "text/event-stream" in resp.headers.get("content-type", "")

async def test_deep_research_emits_done_event(client):
    """SSE stream must contain a 'done' event."""
    payload = {"query": "What is IFRS 16?", "conversation_id": None, "selected_doc_ids": []}
    async with client.stream("POST", "/api/chat/deep-research", json=payload) as resp:
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
    event_types = [e.get("type") or e.get("event") for e in events]
    assert "done" in event_types, f"No 'done' event found. Got: {event_types}"
```

- [ ] **Step 2: Run to confirm failures**

```
cd backend
python -m pytest tests/test_deep_research.py -v
```
Expected: `FAILED` (endpoint doesn't exist).

- [ ] **Step 3: Add `DeepResearchRequest` schema in `chat.py`**

Find the `ChatRequest` class and add the new schema after it:

```python
class DeepResearchRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    selected_doc_ids: Optional[list[str]] = None
```

- [ ] **Step 4: Add the `deep-research` endpoint in `chat.py`**

Add this endpoint after the existing `/send` endpoint:

```python
@router.post("/deep-research")
async def deep_research(req: DeepResearchRequest, db: AsyncSession = Depends(get_db)):
    """
    Deep research endpoint — multi-step reasoning with hybrid RAG + optional web search.

    SSE event types emitted:
      step   : {"type": "step",   "content": "..."}   — progress update
      answer : {"type": "answer", "content": "...", "sources": [...], "conversation_id": "..."}
      done   : {"type": "done",   "conversation_id": "..."}
      error  : {"type": "error",  "message": "..."}
    """
    from backend.core.rag_engine import rag_engine
    from backend.core.prompt_router import ANALYST_SYSTEM_PREFIX, FORMATTING_SUFFIX

    async def event_stream():
        try:
            # ── Step 1: Query decomposition ──────────────────────────────────
            yield f"data: {json.dumps({'type': 'step', 'content': '🔍 Decomposing query into research questions…'})}\n\n"

            decomp_prompt = (
                "You are a research assistant. Break the following question into 2–4 "
                "specific sub-questions that, when answered individually, will together "
                "provide a comprehensive answer.\n\n"
                f"Question: {req.query}\n\n"
                "Return ONLY a JSON array of strings. Example: [\"sub-q1\", \"sub-q2\"]"
            )
            decomp_resp = await llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": decomp_prompt}],
                temperature=0.2,
                max_tokens=300,
            )
            sub_questions_raw = decomp_resp.choices[0].message.content.strip()
            try:
                sub_questions: list[str] = json.loads(sub_questions_raw)
                if not isinstance(sub_questions, list):
                    sub_questions = [req.query]
            except json.JSONDecodeError:
                sub_questions = [req.query]

            # ── Step 2: Hybrid RAG retrieval for each sub-question ───────────
            yield f"data: {json.dumps({'type': 'step', 'content': f'📚 Searching documents across {len(sub_questions)} research angles…'})}\n\n"

            all_chunks: list[dict] = []
            seen_chunk_ids: set[str] = set()
            rag_filter = {"doc_id": {"$in": req.selected_doc_ids}} if req.selected_doc_ids else None

            for sq in sub_questions:
                if req.selected_doc_ids:
                    results = rag_engine.hybrid_search(sq, doc_ids=req.selected_doc_ids, top_k=5)
                else:
                    results = rag_engine.search(sq, top_k=5, filter=rag_filter)
                for r in results:
                    cid = r.get("id") or r["metadata"].get("source", "")
                    if cid not in seen_chunk_ids:
                        seen_chunk_ids.add(cid)
                        all_chunks.append(r)

            # ── Step 3: Build context ─────────────────────────────────────────
            yield f"data: {json.dumps({'type': 'step', 'content': f'🧩 Synthesising {len(all_chunks)} relevant passages…'})}\n\n"

            context_parts: list[str] = []
            sources: list[dict] = []
            for chunk in all_chunks[:20]:  # cap at 20 chunks for context length
                meta = chunk.get("metadata", {})
                original_name = meta.get("original_name") or meta.get("source", "Unknown")
                page = meta.get("page", "?")
                text = chunk.get("document") or chunk.get("text", "")
                context_parts.append(
                    f"[Source: {original_name}, Page {page}]\n{text}"
                )
                sources.append({
                    "id": chunk.get("id", ""),
                    "original_name": original_name,
                    "page": page,
                    "score": chunk.get("score", 0.0),
                })

            context = "\n\n---\n\n".join(context_parts)

            # ── Step 4: LLM synthesis ─────────────────────────────────────────
            yield f"data: {json.dumps({'type': 'step', 'content': '✍️ Writing comprehensive answer…'})}\n\n"

            system_msg = (
                ANALYST_SYSTEM_PREFIX
                + "You are performing DEEP RESEARCH. You have retrieved multiple relevant "
                "document passages covering different angles of the question. "
                "Synthesise a thorough, well-structured answer that:\n"
                "1. Addresses the full question comprehensively\n"
                "2. Cites specific sources by name and page\n"
                "3. Highlights any contradictions or gaps in the evidence\n"
                "4. Clearly distinguishes document-based findings from general knowledge\n"
                + FORMATTING_SUFFIX
            )

            user_msg = (
                f"DOCUMENT CONTEXT:\n{context}\n\n"
                f"QUESTION: {req.query}\n\n"
                "Provide a comprehensive, well-structured research answer."
            )

            full_answer = ""
            async for chunk_resp in await llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg},
                ],
                stream=True,
                temperature=0.3,
                max_tokens=2048,
            ):
                delta = chunk_resp.choices[0].delta.content or ""
                full_answer += delta

            # ── Step 5: Save to conversation history ──────────────────────────
            conv_id = req.conversation_id
            try:
                if not conv_id:
                    from backend.db.models import Conversation
                    conv = Conversation(
                        id=str(uuid.uuid4()),
                        title=req.query[:80],
                        mode="deep_research",
                    )
                    db.add(conv)
                    await db.flush()
                    conv_id = conv.id

                from backend.db.models import Message as DBMessage
                user_msg_db = DBMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv_id,
                    role="user",
                    content=req.query,
                )
                ai_msg_db = DBMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_answer,
                )
                db.add(user_msg_db)
                db.add(ai_msg_db)
                await db.commit()
            except Exception:
                await db.rollback()
                conv_id = conv_id or str(uuid.uuid4())

            # ── Step 6: Emit answer ───────────────────────────────────────────
            yield f"data: {json.dumps({'type': 'answer', 'content': full_answer, 'sources': sources, 'conversation_id': conv_id})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv_id})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Note: `llm_client`, `LLM_MODEL`, `json`, `uuid`, `StreamingResponse` are already imported in `chat.py` — verify the exact variable names match the existing code before pasting.

- [ ] **Step 5: Run the tests**

```
cd backend
python -m pytest tests/test_deep_research.py -v
```
Expected: `3 PASSED`

- [ ] **Step 6: Commit**

```
git add backend/api/chat.py backend/tests/test_deep_research.py
git commit -m "feat(chat): add /api/chat/deep-research SSE endpoint with hybrid RAG + synthesis

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 14: Update `useDeepResearch.ts` — handle `conversation_id` from `done` event

**Files:**
- Modify: `frontend/src/hooks/useDeepResearch.ts`

- [ ] **Step 1: Read the current `handleFrame` function**

Open `frontend/src/hooks/useDeepResearch.ts` and find the `handleFrame` function that processes SSE events.

- [ ] **Step 2: Update the `done` event handler**

Find the `case 'done':` (or `if (evt.type === 'done')`) block and update it to capture the `conversation_id`:

```typescript
// Find the 'done' event handler and update it:
if (frame.type === 'done') {
  if (frame.conversation_id && onConversationCreated) {
    onConversationCreated(frame.conversation_id as string);
  }
  setStatus('done');
  return;
}
```

- [ ] **Step 3: Add `onConversationCreated` prop to the hook**

Find the hook's parameter interface (or the parameter list) and add the optional callback:

```typescript
interface UseDeepResearchOptions {
  onConversationCreated?: (conversationId: string) => void;
}
```

Update the hook signature to accept this option and pass it through.

- [ ] **Step 4: Update source display in the `answer` event handler**

Find the `answer` event handler. The `sources` array now contains `{ id, original_name, page, score }`. Update any reference that was using `filename` to use `original_name`:

```typescript
// In the 'answer' handler:
if (frame.type === 'answer') {
  setAnswer({
    content: frame.content as string,
    sources: (frame.sources as Array<{id: string; original_name: string; page?: number; score?: number}>) ?? [],
    web_sources: (frame.web_sources as Array<{title?: string; url: string}>) ?? [],
  });
}
```

Update the `ResearchAnswer` interface accordingly:
```typescript
interface ResearchAnswer {
  content: string;
  sources: Array<{ id: string; original_name: string; page?: number; score?: number }>;
  web_sources: Array<{ title?: string; url: string }>;
}
```

- [ ] **Step 5: Type-check**

```
cd frontend && npx tsc --noEmit
```
Expected: zero errors.

- [ ] **Step 6: Commit**

```
git add frontend/src/hooks/useDeepResearch.ts
git commit -m "feat(deep-research): handle conversation_id from done event, update source schema

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 15: `useDocumentResolver` hook + apply to source displays

**Files:**
- Create: `frontend/src/lib/useDocumentResolver.ts`
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx`

- [ ] **Step 1: Create `useDocumentResolver.ts`**

```typescript
// frontend/src/lib/useDocumentResolver.ts
/**
 * useDocumentResolver
 *
 * Fetches a mapping of { doc_id: original_name } from the backend so that
 * UUID-based source identifiers can be displayed as human-readable filenames.
 *
 * Cache: the resolved map is memoised in module scope to avoid repeated fetches
 * within the same session.
 */
import { useEffect, useState } from 'react';
import API from './api';   // axios instance — adjust import if path differs

interface DocMeta {
  id: string;
  original_name: string;
  filename: string;
}

// Module-level cache so all hook instances share resolved names
const _cache: Record<string, string> = {};
let _fetched = false;

export function useDocumentResolver() {
  const [ready, setReady] = useState(_fetched);

  useEffect(() => {
    if (_fetched) return;
    API.get<{ documents: DocMeta[] }>('/api/documents')
      .then(resp => {
        const docs = resp.data?.documents ?? [];
        for (const doc of docs) {
          _cache[doc.id] = doc.original_name || doc.filename || doc.id;
        }
        _fetched = true;
        setReady(true);
      })
      .catch(() => {
        _fetched = true;  // don't retry on error
        setReady(true);
      });
  }, []);

  /**
   * Resolve a source identifier to a human-readable name.
   * Accepts:
   *   - A doc_id UUID  → looks up in _cache
   *   - A chunk id like "uuid_chunk_N" → strips suffix, looks up UUID
   *   - Already a readable name → returns as-is
   */
  function resolve(sourceId: string): string {
    if (!sourceId) return 'Unknown';
    // Strip _chunk_N suffix if present
    const base = sourceId.replace(/_chunk_\d+$/, '');
    return _cache[base] || _cache[sourceId] || sourceId;
  }

  return { resolve, ready };
}
```

- [ ] **Step 2: Apply `useDocumentResolver` in `ChatMessages.tsx`**

Find `ChatMessages.tsx` (search for where source names/chips are rendered in the chat message bubbles).

Import the hook:
```typescript
import { useDocumentResolver } from '../../../lib/useDocumentResolver';
```

Inside the component, call the hook and wrap source name display:
```typescript
const { resolve } = useDocumentResolver();

// When rendering source chips, replace:
//   source.source  or  source.filename  or  source.id
// with:
//   resolve(source.source || source.id || '')
```

- [ ] **Step 3: Apply `useDocumentResolver` in `SourcesSidebar.tsx`**

Similarly, import and use `resolve()` when rendering document source labels in the sidebar. Replace any raw UUID display with `resolve(doc.id)`.

- [ ] **Step 4: Type-check**

```
cd frontend && npx tsc --noEmit
```
Expected: zero errors.

- [ ] **Step 5: Commit**

```
git add frontend/src/lib/useDocumentResolver.ts frontend/src/components/studios/LegalStudio/ChatMessages.tsx frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx
git commit -m "feat(ui): useDocumentResolver hook resolves UUID source names to original filenames

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 5 — Analyst Mode Fixes (P2)

### Task 16: Add `selected_doc_ids` to `ChatRequest` + pass from `LegalStudio`

**Files:**
- Modify: `backend/api/chat.py` (ChatRequest schema + RAG filter)
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` (chat body)
- Test: extend `backend/tests/test_chat.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_chat.py  (create if not exists)
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_chat_send_accepts_selected_doc_ids(client):
    """ChatRequest must accept selected_doc_ids without 422 validation error."""
    payload = {
        "message": "Summarise the attached document",
        "conversation_id": None,
        "stream": False,
        "domain": "analyst",
        "mode": "analyst",
        "selected_doc_ids": ["doc-uuid-1", "doc-uuid-2"],
    }
    with patch("backend.api.chat.rag_engine") as mock_rag:
        mock_rag.search.return_value = []
        mock_rag.hybrid_search.return_value = []
        resp = await client.post("/api/chat/send", json=payload)
    assert resp.status_code != 422, f"Validation error — selected_doc_ids not accepted"
```

- [ ] **Step 2: Run to confirm failure**

```
cd backend
python -m pytest tests/test_chat.py::test_chat_send_accepts_selected_doc_ids -v
```
Expected: `FAILED` (422 validation error).

- [ ] **Step 3: Add `selected_doc_ids` to `ChatRequest` in `chat.py`**

Find the `ChatRequest` class and add the field:

```python
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    stream: bool = True
    domain: Optional[str] = None
    mode: Optional[str] = None
    domain_override: Optional[str] = None
    use_rag: bool = True
    selected_doc_ids: Optional[list[str]] = None    # ← add this
```

- [ ] **Step 4: Use `selected_doc_ids` in the RAG search call in `chat.py`**

Find the RAG search call (search for `rag_engine.search(` in `chat.py`). Update it to use hybrid search when doc IDs are provided:

```python
# Replace existing rag_engine.search call with:
if req.selected_doc_ids:
    rag_results = rag_engine.hybrid_search(
        query, doc_ids=req.selected_doc_ids, top_k=8
    )
else:
    rag_filter = {"doc_id": {"$in": req.selected_doc_ids}} if req.selected_doc_ids else None
    rag_results = rag_engine.search(query, top_k=5, filter=rag_filter)
```

- [ ] **Step 5: Pass `selected_doc_ids` in the chat request in `LegalStudio.tsx`**

Find the `sendMessage` function (around line 563), where the request body is built. Add `selected_doc_ids`:

```typescript
const body: any = {
  message: text,
  conversation_id: conversationId,
  stream: true,
  domain: userDomain ?? domain,
  mode,
  selected_doc_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,  // ← add
};
```

- [ ] **Step 6: Run the test**

```
cd backend
python -m pytest tests/test_chat.py -v
```
Expected: `PASSED`

- [ ] **Step 7: Commit**

```
git add backend/api/chat.py frontend/src/components/studios/LegalStudio/LegalStudio.tsx backend/tests/test_chat.py
git commit -m "feat(analyst): add selected_doc_ids to ChatRequest + hybrid RAG in analyst mode

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 17: Audit results → ArtifactPanel (right pane)

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Understand current audit result flow**

Search `LegalStudio.tsx` for `InlineResultCard` or `auditResult` to find where the audit output is currently displayed inline in the center pane.

```
grep -n "InlineResultCard\|auditResult\|handleAuditResult" \
  frontend/src/components/studios/LegalStudio/LegalStudio.tsx
```

- [ ] **Step 2: Route audit result to ArtifactPanel**

Find the function that receives the audit result (likely `handleAuditResult` or similar). Update it to open the ArtifactPanel with the audit content instead of showing an inline card:

```typescript
// Replace the audit result handler to open ArtifactPanel:
const handleAuditResult = useCallback((result: string, title: string = "Audit Results") => {
  setArtifactContent(result);
  setArtifactTitle(title);
  setArtifactReportType("audit");
  setArtifactLoading(false);
  setArtifactOpen(true);
}, []);
```

- [ ] **Step 3: Remove `InlineResultCard` from center pane**

Find the JSX in the center pane (`centerContent`) that renders `InlineResultCard` or equivalent. Remove that block. The result will now appear exclusively in the right pane via `ArtifactPanel`.

- [ ] **Step 4: Type-check**

```
cd frontend && npx tsc --noEmit
```
Expected: zero errors.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "fix(analyst): route audit results to ArtifactPanel right pane

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 18: Remove duplicate `ANALYST_SYSTEM_PREFIX` in `prompt_router.py`

**Files:**
- Modify: `backend/core/prompt_router.py`

- [ ] **Step 1: Remove the duplicate definition**

In `backend/core/prompt_router.py`, `ANALYST_SYSTEM_PREFIX` is defined twice (lines 14–20 and lines 46–52). Delete the second definition (lines 46–52):

```python
# DELETE this block (the second occurrence):
ANALYST_SYSTEM_PREFIX = (
    "You are a financial and legal analyst. You MUST base your answers primarily on the documents "
    "provided below. If the answer is clearly contained in the documents, cite the document and page. "
    "If the answer is not in the documents, you may draw on your professional knowledge but must "
    "explicitly say: \"This is based on general knowledge, not your attached documents.\" "
    "Do NOT make up figures, dates, or entities.\n\n"
)
```

Keep only the first definition (lines 14–20).

- [ ] **Step 2: Verify no import errors**

```
cd backend && python -c "from backend.core.prompt_router import ANALYST_SYSTEM_PREFIX; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```
git add backend/core/prompt_router.py
git commit -m "fix(prompt): remove duplicate ANALYST_SYSTEM_PREFIX definition

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 6 — Quick UI Fixes (P3 + P4)

### Task 19: Fix multi-select — card click toggles selection in select mode

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Find the broken click handler (line 217)**

In `HomePage.tsx`, find:
```tsx
onClick={id => !selectionMode && handleOpen(id)}
```

This is the `onClick` prop passed to `NotebookCard`. When `selectionMode` is true, clicking the card does nothing at all — it should toggle selection.

- [ ] **Step 2: Fix the click handler**

Replace the `onClick` prop:
```tsx
onClick={id => selectionMode ? handleToggleSelect(id) : handleOpen(id)}
```

This means:
- In selection mode → clicking the card toggles the selection checkbox
- In normal mode → clicking the card opens the notebook

- [ ] **Step 3: Type-check**

```
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```
git add frontend/src/pages/HomePage.tsx
git commit -m "fix(home): card click toggles selection in select mode (multi-delete)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 20: Domain icon in notebook card thumbnail

**Files:**
- Modify: `frontend/src/components/common/NotebookCard.tsx`

- [ ] **Step 1: Replace text initials with domain icon in the thumbnail**

In `NotebookCard.tsx`, find the thumbnail `<div>` content (around line 116–131):

```tsx
<div className="notebook-card__thumb" style={thumbStyle}>
  {titleInitials(notebook.title)}    {/* ← currently text initials */}
  {selectionMode && ( ...checkbox... )}
</div>
```

Replace `{titleInitials(notebook.title)}` with the domain icon, and move the domain icon overlay to inside the thumbnail instead of the bottom-right corner:

```tsx
<div className="notebook-card__thumb" style={thumbStyle}>
  <span style={{ fontSize: isList ? '22px' : '28px', lineHeight: 1, pointerEvents: 'none' }}>
    {getDomainIcon(notebook.domain)}
  </span>
  {selectionMode && (
    <div
      style={{ position: 'absolute', top: 6, left: 6, zIndex: 2 }}
      onClick={e => { e.stopPropagation(); onToggleSelect?.(notebook.id); }}
    >
      <input
        type="checkbox"
        checked={!!selected}
        onChange={() => onToggleSelect?.(notebook.id)}
        style={{ width: 18, height: 18, cursor: 'pointer' }}
      />
    </div>
  )}
</div>
```

Remove the old bottom-right overlay `<div>` (lines 148–160) that was rendering the domain icon there, since the icon is now in the thumbnail.

- [ ] **Step 2: Type-check**

```
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```
git add frontend/src/components/common/NotebookCard.tsx
git commit -m "feat(home): show domain icon emoji in notebook card thumbnail

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 21: Fix light mode — define `--s-*` CSS variables

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add `--s-*` variables to `:root` (dark mode defaults)**

In `frontend/src/index.css`, at the end of the `:root { ... }` block (after line 32), add:

```css
/* ── Studio-scoped design tokens (dark mode defaults) ── */
--s-bg:          #111111;
--s-bg-1:        #1a1a1a;
--s-card:        rgba(255,255,255,0.04);
--s-border:      rgba(255,255,255,0.10);
--s-text-1:      #f0f0f0;
--s-text-2:      #999999;
--s-accent:      #60a5fa;
--s-accent-subtle: rgba(96,165,250,0.12);
--s-surface:     #1a1a1a;
--s-font-ui:     'IBM Plex Sans', system-ui, sans-serif;
--s-font-mono:   'IBM Plex Mono', 'Courier New', monospace;
--s-r-sm:        4px;
--s-r-md:        8px;
--s-r-lg:        12px;
```

- [ ] **Step 2: Add `--s-*` overrides to `[data-theme="light"]` block**

In the `[data-theme="light"]` block (after line 57), add:

```css
/* ── Studio-scoped design tokens (light mode overrides) ── */
--s-bg:          #f8fafc;
--s-bg-1:        #ffffff;
--s-card:        rgba(0,0,0,0.03);
--s-border:      rgba(0,0,0,0.10);
--s-text-1:      #111111;
--s-text-2:      #666666;
--s-accent:      #2563eb;
--s-accent-subtle: rgba(37,99,235,0.10);
--s-surface:     #f0f4ff;
--s-font-ui:     'IBM Plex Sans', system-ui, sans-serif;
--s-font-mono:   'IBM Plex Mono', 'Courier New', monospace;
--s-r-sm:        4px;
--s-r-md:        8px;
--s-r-lg:        12px;
```

- [ ] **Step 3: Fix the broken light mode selectors that reference `--s-bg`**

Confirm that the existing selectors using `var(--s-bg)` (e.g. `[data-theme="light"] .app-shell { background: var(--s-bg); }`) now resolve correctly. If any selector still shows white-on-white text, it is because a component uses `--s-text-1` on a `--s-bg-1` background — both now have defined values, so they should contrast correctly.

- [ ] **Step 4: Build the frontend to confirm no CSS errors**

```
cd frontend && npm run build 2>&1 | tail -20
```
Expected: build succeeds with zero errors.

- [ ] **Step 5: Commit**

```
git add frontend/src/index.css
git commit -m "fix(css): define --s-* CSS variables for dark and light themes

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final Verification

- [ ] **Run all backend tests**

```
cd backend
python -m pytest tests/ -v --tb=short
```
Expected: all tests pass.

- [ ] **Run frontend type-check**

```
cd frontend && npx tsc --noEmit
```
Expected: zero errors.

- [ ] **Run frontend build**

```
cd frontend && npm run build
```
Expected: build succeeds.

- [ ] **Start the app and smoke-test**

```
# Terminal 1 — backend
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Manual checks:
- [ ] Upload the same PDF twice → second upload returns same doc_id (dedup working)
- [ ] Open a notebook in analyst mode, select 2 docs, ask a question → answer references selected docs only
- [ ] Switch to deep research mode, ask a question → see step events stream, then comprehensive answer
- [ ] Generate an audit report with `auditor_format=big4` and `period_end=2025-12-31` → report cites correct period, includes audience header
- [ ] Generate any report → ConfirmReportCard shows Audience pill
- [ ] Click "Select" on homepage, click a card → card is toggled (not opened)
- [ ] Toggle light mode → all text is readable (no white-on-white)

- [ ] **Final commit**

```
git commit --allow-empty -m "chore: all fixes verified — chatbot bugs & enhancements complete

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
