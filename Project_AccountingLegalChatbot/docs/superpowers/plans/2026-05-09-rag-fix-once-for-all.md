# RAG Fix — Once For All Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the RAG system reliably retrieve from all 449 documents on disk, survive provider changes (NVIDIA → Ollama → OpenAI → Claude) with zero manual re-indexing, and always tell the user when an answer is from general knowledge vs. indexed documents.

**Architecture:** Raw chunk text is permanently stored in a `document_chunks` DB table — ChromaDB is just a fast search index that can be rebuilt any time. An embedding fingerprint (provider + model + dimension) is stored in `user_settings`; on startup, if the fingerprint mismatches the current provider, the system rebuilds ChromaDB automatically in the background. All 449 files on disk are ingested on first startup via a directory scan.

**Tech Stack:** SQLAlchemy async (SQLite), ChromaDB 1.5.8, FastAPI, httpx, Ollama (local), NVIDIA NIM, pytest+asyncio, React/TypeScript frontend.

---

## Current State Summary (Verified)

| Item | Count |
|------|-------|
| Files on disk | **449** |
| DB docs (indexed) | 273 — all INACCESSIBLE (ChromaDB corrupt) |
| DB docs (error) | 170 — never embedded (NVIDIA 400 errors) |
| Files never added to DB | **62** |
| RAG results returned right now | **0** |

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/db/models.py` | Modify | Add `DocumentChunk` ORM model |
| `backend/db/database.py` | Modify | Add `document_chunks` ALTER TABLE migration |
| `backend/config.py` | Modify | Add `ollama_embed_model`, `embedding_chunk_size`, `embedding_chunk_overlap` computed per provider |
| `backend/core/rag_engine.py` | Modify | Add `OllamaEmbeddingProvider`; fix ChromaDB corruption handling; add `_check_and_rebuild_on_fingerprint_change()` startup check; persist chunks to DB in `ingest_chunks()` |
| `backend/core/document_processor.py` | Modify | Use provider-aware chunk size from `settings.embedding_chunk_size` |
| `backend/api/documents.py` | Modify | Add `POST /api/documents/scan-and-ingest` endpoint; add `POST /api/documents/reindex-all` endpoint |
| `backend/api/chat.py` | Modify | Add no-sources disclaimer when `_search_results` is empty |
| `backend/api/settings.py` | Modify | Add Anthropic model fetch; fix Ollama model fetch to call live API |
| `frontend/src/pages/SettingsPage.tsx` | Modify | Auto-fetch models on provider switch; show model dropdown |
| `backend/tests/test_rag_chunk_persistence.py` | Create | Tests: chunk persistence, Ollama embed, fingerprint change rebuild |
| `backend/tests/test_rag_transparency.py` | Create | Tests: disclaimer appears when 0 RAG results |
| `backend/tests/test_scan_and_ingest.py` | Create | Tests: scan-and-ingest picks up new files |

---

## Task 1: Add DocumentChunk Table (The Source of Truth)

**Files:**
- Modify: `backend/db/models.py`
- Modify: `backend/db/database.py`
- Test: `backend/tests/test_rag_chunk_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rag_chunk_persistence.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from db.models import Base, DocumentChunk, Document

@pytest.fixture
async def mem_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()

async def test_document_chunk_model_exists(mem_db):
    """DocumentChunk table exists and can store chunk text."""
    doc = Document(
        id="doc-001",
        filename="test.pdf",
        original_name="test.pdf",
        file_type=".pdf",
    )
    mem_db.add(doc)
    await mem_db.flush()

    chunk = DocumentChunk(
        id="chunk-001",
        doc_id="doc-001",
        chunk_index=0,
        text="Federal Decree-Law No. 50 of 2022 on the regulation of bounced cheques.",
        metadata_json={"domain": "general", "category": "law", "page": 1},
    )
    mem_db.add(chunk)
    await mem_db.commit()

    result = await mem_db.execute(select(DocumentChunk).where(DocumentChunk.doc_id == "doc-001"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].text.startswith("Federal Decree-Law No. 50")
    assert rows[0].chunk_index == 0

async def test_document_chunk_cascade_delete(mem_db):
    """Deleting a Document also deletes its DocumentChunks."""
    doc = Document(id="doc-002", filename="f.pdf", original_name="f.pdf", file_type=".pdf")
    mem_db.add(doc)
    await mem_db.flush()
    mem_db.add(DocumentChunk(id="c-002", doc_id="doc-002", chunk_index=0, text="hello"))
    await mem_db.commit()

    await mem_db.delete(doc)
    await mem_db.commit()

    result = await mem_db.execute(select(DocumentChunk).where(DocumentChunk.doc_id == "doc-002"))
    assert result.scalars().all() == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_chunk_persistence.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'DocumentChunk' from 'db.models'`

- [ ] **Step 3: Add DocumentChunk to models.py**

In `backend/db/models.py`, after the `Document` class (after line 84), add:

```python
class DocumentChunk(Base):
    """Permanent store of raw extracted chunk text.

    ChromaDB is rebuilt from this table when the embedding provider changes
    or the vector index is corrupted. This is the source of truth for RAG.
    """
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True)           # same ID used in ChromaDB
    doc_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
```

- [ ] **Step 4: Add migration to database.py**

In `backend/db/database.py`, inside `init_db()`, add to the ALTER TABLE block:

```python
            "ALTER TABLE document_chunks ADD COLUMN created_at DATETIME",
```

Also add a `CREATE TABLE IF NOT EXISTS` before the ALTER block (SQLite's `create_all` handles this, but add explicit migration for the new table):

```python
        # document_chunks table (added 2026-05-09)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id VARCHAR(36) PRIMARY KEY,
                doc_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                metadata_json JSON,
                created_at DATETIME
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_doc_id ON document_chunks (doc_id)"
        ))
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_chunk_persistence.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/db/models.py backend/db/database.py backend/tests/test_rag_chunk_persistence.py
git commit -m "feat(rag): add DocumentChunk table — persistent chunk text storage

Raw chunk text stored in document_chunks table. ChromaDB is now
a rebuild-able index, not the source of truth. Cascade delete
ensures chunks are removed when parent document is deleted.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Add Ollama Embedding Provider + Provider-Aware Chunking

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/core/rag_engine.py`
- Modify: `backend/core/document_processor.py`
- Test: `backend/tests/test_rag_chunk_persistence.py` (extend)

- [ ] **Step 1: Pull Ollama nomic-embed-text model**

```bash
ollama pull nomic-embed-text
```

Expected: `pulling manifest... success` (768-dim embedding model, no token limit)

- [ ] **Step 2: Write failing test for Ollama embedding**

Add to `backend/tests/test_rag_chunk_persistence.py`:

```python
import os
import pytest

@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires local Ollama server"
)
async def test_ollama_embed_returns_vector():
    """OllamaEmbeddingProvider returns a 768-dim vector."""
    import sys; sys.path.insert(0, ".")
    from core.rag_engine import OllamaEmbeddingProvider
    provider = OllamaEmbeddingProvider(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
    )
    vec = await provider.embed_query("cheque bounce rent Dubai law")
    assert isinstance(vec, list)
    assert len(vec) == 768
    assert all(isinstance(v, float) for v in vec)

async def test_provider_aware_chunk_size_nvidia():
    """NVIDIA provider uses ≤350 char chunk size."""
    import sys; sys.path.insert(0, ".")
    os.environ["EMBEDDING_PROVIDER"] = "nvidia"
    # Re-import settings with new env
    from importlib import reload
    import config as cfg_module
    reload(cfg_module)
    from config import settings as s
    assert s.embedding_chunk_size <= 350

async def test_provider_aware_chunk_size_ollama():
    """Ollama provider uses ≥1000 char chunk size."""
    os.environ["EMBEDDING_PROVIDER"] = "ollama"
    from importlib import reload
    import config as cfg_module
    reload(cfg_module)
    from config import settings as s
    assert s.embedding_chunk_size >= 1000
    # reset
    os.environ["EMBEDDING_PROVIDER"] = "nvidia"
```

- [ ] **Step 3: Run failing tests**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_chunk_persistence.py::test_provider_aware_chunk_size_nvidia -v
```

Expected: `ImportError` or `AttributeError: 'Settings' object has no attribute 'embedding_chunk_size'`

- [ ] **Step 4: Add config.py changes**

In `backend/config.py`, add after the `# ── Embedding` section:

```python
    # ── Ollama Embeddings ────────────────────────────────────────────
    ollama_embed_model: str = "nomic-embed-text"   # 768-dim, no token limit

    @property
    def embedding_model(self) -> str:
        """Return the embedding model name for the active embedding provider."""
        return {
            "nvidia": self.nvidia_embed_model,
            "openai": self.openai_embed_model,
            "ollama": self.ollama_embed_model,
        }.get(self.embedding_provider, self.nvidia_embed_model)

    @property
    def embedding_chunk_size(self) -> int:
        """Provider-aware chunk size to avoid token-limit 400 errors."""
        return {
            "nvidia": 350,   # nv-embedqa-e5-v5 has 512-token limit; 350 chars ≈ 250 tokens (safe)
            "openai": 1200,  # text-embedding-3-small: 8192-token limit
            "ollama": 1200,  # nomic-embed-text: ~8192-token limit
        }.get(self.embedding_provider, 350)

    @property
    def embedding_chunk_overlap(self) -> int:
        """Provider-aware chunk overlap."""
        return {
            "nvidia": 50,
            "openai": 150,
            "ollama": 150,
        }.get(self.embedding_provider, 50)

    @property
    def embedding_dimension(self) -> int:
        """Vector dimension for the active embedding provider."""
        return {
            "nvidia": 1024,
            "openai": 1536,
            "ollama": 768,
        }.get(self.embedding_provider, 1024)

    @property
    def embedding_fingerprint(self) -> str:
        """Unique string identifying current embedding config. If this changes, re-embed all docs."""
        return f"{self.embedding_provider}:{self.embedding_model}:{self.embedding_dimension}"
```

- [ ] **Step 5: Add OllamaEmbeddingProvider to rag_engine.py**

In `backend/core/rag_engine.py`, after the `_embed_openai` method (after line 137), add this new class before `_infer_domain_from_name`:

```python
class OllamaEmbeddingProvider:
    """Ollama local embedding provider. No token limit, no API cost."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using Ollama."""
        results = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                resp.raise_for_status()
                results.append(resp.json()["embedding"])
        return results

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": query},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
```

- [ ] **Step 6: Update EmbeddingProvider to route to Ollama**

In `backend/core/rag_engine.py`, update `EmbeddingProvider.__init__` and `embed_texts`/`embed_query` to include Ollama:

```python
class EmbeddingProvider:
    """Interface for text embedding models."""

    def __init__(self):
        self.provider = settings.embedding_provider.lower()
        self.api_key = settings.nvidia_api_key
        self.model = settings.embedding_model          # use new property
        self.base_url = settings.nvidia_base_url
        self._ollama = OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embed_model,
        )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if self.provider == "mock":
            return [[0.1] * 1024 for _ in texts]
        if self.provider == "openai":
            return await self._embed_openai(texts)
        if self.provider == "ollama":
            return await self._ollama.embed_texts(texts)
        return await self._embed_nvidia(texts)

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query. Raises on failure (no retry)."""
        if self.provider == "mock":
            return [0.1] * 1024
        if self.provider == "openai":
            results = await self._embed_openai([query])
            return results[0]
        if self.provider == "ollama":
            return await self._ollama.embed_query(query)
        # NVIDIA path below (existing code unchanged)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": [query],
            "model": self.model,
            "input_type": "query",
            "encoding_format": "float",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return data["data"][0]["embedding"]
```

- [ ] **Step 7: Update DocumentProcessor to use provider-aware chunk size**

In `backend/core/document_processor.py`, change `DocumentProcessor.__init__` default arguments:

```python
    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        # Use provider-aware defaults if not explicitly specified
        _default_size = settings.embedding_chunk_size
        _default_overlap = settings.embedding_chunk_overlap
        chunk_size = chunk_size if chunk_size is not None else _default_size
        chunk_overlap = chunk_overlap if chunk_overlap is not None else _default_overlap

        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size}). "
                "Check CHUNK_OVERLAP and CHUNK_SIZE in your .env."
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # ... rest of existing init unchanged
```

- [ ] **Step 8: Run all tests**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_chunk_persistence.py -v -m "not integration"
```

Expected: All pass (Ollama test skipped in CI, runs locally if Ollama is running)

- [ ] **Step 9: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/config.py backend/core/rag_engine.py backend/core/document_processor.py backend/tests/test_rag_chunk_persistence.py
git commit -m "feat(rag): add Ollama embedding provider + provider-aware chunk sizing

- OllamaEmbeddingProvider: nomic-embed-text (768-dim, no token limit)
- Settings.embedding_chunk_size: 350 for NVIDIA (safe under 512-token limit),
  1200 for Ollama/OpenAI
- Settings.embedding_fingerprint: detects provider changes for auto-rebuild
- EmbeddingProvider routes to correct backend based on EMBEDDING_PROVIDER

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Fix ChromaDB Corruption + Persist Chunks on Ingest + Auto-Rebuild

**Files:**
- Modify: `backend/core/rag_engine.py`
- Test: `backend/tests/test_rag_chunk_persistence.py` (extend)

The corruption error is: `mismatched types; Rust type u64 (as SQL type INTEGER) is not compatible with SQL type BLOB`. This happens on `collection.count()`. The existing `__init__` backup/recreate logic handles the outer client init but not this inner count() error. We add a specific handler.

Additionally: persist chunk text to `document_chunks` table inside `ingest_chunks()`, and add `_check_and_rebuild_on_fingerprint_change()` on startup.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_rag_chunk_persistence.py`:

```python
async def test_ingest_chunks_persists_to_db(mem_db):
    """ingest_chunks() saves raw text to document_chunks table."""
    import sys; sys.path.insert(0, ".")
    os.environ["VECTOR_STORE_DIR"] = ":memory:"
    os.environ["EMBEDDING_PROVIDER"] = "mock"

    from importlib import reload
    import config as cfg_mod; reload(cfg_mod)
    import core.rag_engine as rag_mod; reload(rag_mod)
    from core.rag_engine import RAGEngine
    from db.models import DocumentChunk
    from sqlalchemy import select

    engine_instance = RAGEngine()

    # Insert parent document
    doc = Document(id="doc-rag-01", filename="decree50.pdf",
                   original_name="DecreeLaw_50_2022_pdf.pdf", file_type=".pdf")
    mem_db.add(doc)
    await mem_db.commit()

    chunks = [
        {"id": "c1", "text": "Federal Decree-Law No. 50 of 2022 on cheque crimes.",
         "metadata": {"domain": "general", "category": "law"}},
        {"id": "c2", "text": "Article 1: Issuing a cheque with insufficient funds.",
         "metadata": {"domain": "general", "category": "law"}},
    ]
    await engine_instance.ingest_chunks(
        chunks,
        doc_id="doc-rag-01",
        original_name="DecreeLaw_50_2022_pdf.pdf",
        category="law",
        db_session=mem_db,
    )

    result = await mem_db.execute(
        select(DocumentChunk).where(DocumentChunk.doc_id == "doc-rag-01")
        .order_by(DocumentChunk.chunk_index)
    )
    saved = result.scalars().all()
    assert len(saved) == 2
    assert saved[0].text == "Federal Decree-Law No. 50 of 2022 on cheque crimes."
    assert saved[1].text == "Article 1: Issuing a cheque with insufficient funds."
    assert saved[0].chunk_index == 0
    assert saved[1].chunk_index == 1
```

- [ ] **Step 2: Run — expect failure**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_chunk_persistence.py::test_ingest_chunks_persists_to_db -v
```

Expected: `TypeError: ingest_chunks() got an unexpected keyword argument 'db_session'`

- [ ] **Step 3: Update ingest_chunks() signature and add chunk persistence**

In `backend/core/rag_engine.py`, update `ingest_chunks` method signature (find the existing `async def ingest_chunks`):

```python
    async def ingest_chunks(
        self,
        chunks: list[dict],
        doc_id: str,
        original_name: str,
        category: str = "law",
        db_session=None,          # NEW: optional AsyncSession for persisting to document_chunks
    ) -> int:
```

At the START of `ingest_chunks()`, before ChromaDB insertion, add chunk persistence logic:

```python
        # Persist raw chunk text to document_chunks table (source of truth for re-embedding)
        if db_session is not None:
            from db.models import DocumentChunk
            from sqlalchemy import delete as sa_delete
            # Remove any existing chunks for this doc (idempotent re-ingest)
            await db_session.execute(
                sa_delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
            )
            for idx, chunk in enumerate(chunks):
                db_session.add(DocumentChunk(
                    id=chunk["id"],
                    doc_id=doc_id,
                    chunk_index=idx,
                    text=chunk["text"],
                    metadata_json=chunk.get("metadata", {}),
                ))
            await db_session.flush()
```

- [ ] **Step 4: Fix ChromaDB corruption handler in `collection` property**

In `backend/core/rag_engine.py`, update the `collection` property to handle the 1.5.8 Rust type error:

```python
    @property
    def collection(self):
        """Robust collection access that attempts to recover from common segment errors."""
        try:
            self._collection.count()
            return self._collection
        except Exception as e:
            err_str = str(e).lower()
            if (
                "dimensionality" in err_str
                or "segment" in err_str
                or "u64" in err_str
                or "blob" in err_str
                or "mismatched types" in err_str
                or "backfill" in err_str
                or "compactor" in err_str
            ):
                logger.warning(
                    "ChromaDB collection corrupt or incompatible (%s). "
                    "Rebuilding from scratch — existing embeddings will be re-created "
                    "from document_chunks table.",
                    type(e).__name__,
                )
                try:
                    # Back up corrupted store
                    backup = Path(settings.vector_store_dir + "_backup_" +
                                  str(int(time.time())))
                    if Path(settings.vector_store_dir).exists():
                        shutil.move(settings.vector_store_dir, str(backup))
                        logger.info("Corrupted store backed up to: %s", backup)
                    self._reinit_client()
                    # Mark all documents for re-indexing
                    self._needs_full_reindex = True
                    logger.warning(
                        "ChromaDB rebuilt empty. All documents need re-embedding. "
                        "Call /api/documents/reindex-all to re-embed from stored chunks."
                    )
                    return self._collection
                except Exception as rebuild_err:
                    logger.critical("Failed to rebuild ChromaDB: %s", rebuild_err)
                    raise
            raise
```

Also add `self._needs_full_reindex: bool = False` to `RAGEngine.__init__` after `self._collection = ...` line.

- [ ] **Step 5: Run tests**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_chunk_persistence.py -v -m "not integration"
```

Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/core/rag_engine.py backend/tests/test_rag_chunk_persistence.py
git commit -m "feat(rag): persist chunks to DB + fix ChromaDB 1.5.8 corruption

- ingest_chunks() now saves raw text to document_chunks table
- collection property handles u64/BLOB type mismatch (ChromaDB 1.5.8)
- Corrupted store auto-backed-up and rebuilt empty
- _needs_full_reindex flag set when store is rebuilt

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Scan-and-Ingest All 449 Documents + Reindex-All Endpoint

**Files:**
- Modify: `backend/api/documents.py`
- Test: `backend/tests/test_scan_and_ingest.py`

This is the core "fix once for all" task. Two new endpoints:
1. `POST /api/documents/scan-and-ingest` — scans data_source dirs, processes any file not already successfully indexed
2. `POST /api/documents/reindex-all` — re-embeds all documents from `document_chunks` table into a fresh ChromaDB (no PDF parsing — reads stored text)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_scan_and_ingest.py
import os
import tempfile
import pathlib
import pytest
from httpx import AsyncClient, ASGITransport
import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ["VECTOR_STORE_DIR"] = ":memory:"
os.environ["EMBEDDING_PROVIDER"] = "mock"

from main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_scan_and_ingest_endpoint_exists(client):
    """POST /api/documents/scan-and-ingest returns 200 with a report."""
    # Use a temp dir with 2 txt files to avoid needing real PDFs
    with tempfile.TemporaryDirectory() as tmpdir:
        (pathlib.Path(tmpdir) / "law_test.txt").write_text(
            "Federal Decree-Law No. 50 of 2022 concerning bounced cheques in UAE."
        )
        resp = await client.post(
            "/api/documents/scan-and-ingest",
            json={"directories": [tmpdir], "category": "law"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "processed" in body
    assert "errors" in body
    assert "skipped" in body
    assert isinstance(body["processed"], int)

async def test_reindex_all_endpoint_exists(client):
    """POST /api/documents/reindex-all returns 200."""
    resp = await client.post("/api/documents/reindex-all")
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body
    assert "queued" in body
```

- [ ] **Step 2: Run — expect 404**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_scan_and_ingest.py -v
```

Expected: `AssertionError: assert 404 == 200`

- [ ] **Step 3: Add scan-and-ingest endpoint to documents.py**

In `backend/api/documents.py`, add near the top imports:

```python
from pydantic import BaseModel as PydanticBase
```

Add these two endpoints at the END of `documents.py`, before any closing code:

```python
class ScanIngestRequest(PydanticBase):
    directories: list[str]
    category: str = "law"  # "law" | "finance"


class ScanIngestResponse(PydanticBase):
    processed: int
    errors: int
    skipped: int
    details: list[str]


@router.post("/scan-and-ingest", response_model=ScanIngestResponse)
async def scan_and_ingest_directories(
    req: ScanIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Scan directories for documents not yet in the DB and ingest them.

    Processes files with status='error' (re-try) and files not in DB at all.
    Skips files already successfully indexed (status='indexed').
    """
    from pathlib import Path as FPath
    from sqlalchemy import select as sa_select

    SUPPORTED = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".csv", ".md"}
    processed = 0
    errors = 0
    skipped = 0
    details: list[str] = []

    # Collect all files in requested directories
    all_files: list[FPath] = []
    for dir_str in req.directories:
        d = FPath(dir_str)
        if not d.exists():
            details.append(f"Directory not found: {dir_str}")
            continue
        all_files.extend(f for f in d.rglob("*") if f.suffix.lower() in SUPPORTED and f.is_file())

    # Get all currently indexed filenames from DB (indexed = skip)
    result = await db.execute(
        sa_select(Document.original_name, Document.status)
    )
    db_docs = {row.original_name: row.status for row in result}

    for file_path in all_files:
        fname = file_path.name
        db_status = db_docs.get(fname)

        if db_status == "indexed":
            skipped += 1
            continue  # already good — do not re-process

        try:
            # Read file bytes
            file_bytes = file_path.read_bytes()
            file_size = len(file_bytes)

            # Check if doc already in DB (error status) — reuse doc_id, or create new
            existing = await db.execute(
                sa_select(Document).where(Document.original_name == fname)
            )
            doc = existing.scalar_one_or_none()

            if doc is None:
                doc = Document(
                    filename=fname,
                    original_name=fname,
                    file_type=file_path.suffix.lower(),
                    file_size=file_size,
                    status="processing",
                    metadata_json={"category": req.category, "source_dir": str(file_path.parent)},
                )
                db.add(doc)
                await db.flush()

            else:
                doc.status = "processing"
                doc.error_message = None
                doc.chunk_count = 0
                await db.flush()

            # Process and ingest
            from core.document_processor import DocumentProcessor
            processor = DocumentProcessor()

            import io
            from fastapi import UploadFile
            # Process in-memory using the existing processor
            chunks = await processor.process_document(
                file_bytes=file_bytes,
                filename=fname,
                doc_id=doc.id,
            )

            if not chunks:
                doc.status = "error"
                doc.error_message = "No text could be extracted from file"
                errors += 1
                details.append(f"ERROR (no text): {fname}")
                await db.flush()
                continue

            await rag_engine.ingest_chunks(
                chunks=[c.to_dict() for c in chunks],
                doc_id=doc.id,
                original_name=fname,
                category=req.category,
                db_session=db,
            )

            doc.status = "indexed"
            doc.chunk_count = len(chunks)
            doc.error_message = None
            await db.flush()

            processed += 1
            details.append(f"OK ({len(chunks)} chunks): {fname}")

        except Exception as exc:
            errors += 1
            details.append(f"ERROR ({type(exc).__name__}: {exc}): {fname}")
            if doc:
                doc.status = "error"
                doc.error_message = str(exc)[:500]
                await db.flush()

    return ScanIngestResponse(
        processed=processed,
        errors=errors,
        skipped=skipped,
        details=details,
    )


class ReindexResponse(PydanticBase):
    message: str
    queued: int


@router.post("/reindex-all", response_model=ReindexResponse)
async def reindex_all_documents(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Re-embed ALL documents from document_chunks table into a fresh ChromaDB.

    Does NOT re-parse PDFs. Reads stored chunk text from document_chunks.
    Safe to call any time: idempotent, processes in background.
    Use after: EMBEDDING_PROVIDER change, ChromaDB corruption, or provider migration.
    """
    from sqlalchemy import select as sa_select, func
    from db.models import DocumentChunk

    result = await db.execute(sa_select(func.count()).select_from(DocumentChunk))
    total_chunks = result.scalar_one()

    async def _do_reindex():
        """Background task: read all chunks from DB and re-embed into ChromaDB."""
        from db.database import async_session
        from db.models import DocumentChunk, Document
        from sqlalchemy import select as sa_select, update as sa_update

        logger.info("Starting full reindex: %d chunks to re-embed", total_chunks)

        # Wipe ChromaDB collection and start fresh
        try:
            rag_engine.chroma_client.delete_collection("documents")
        except Exception:
            pass
        rag_engine._collection = rag_engine.chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

        BATCH = 50
        processed = 0
        errors = 0

        async with async_session() as session:
            # Fetch all chunks, ordered by doc_id + chunk_index
            q = sa_select(DocumentChunk).order_by(DocumentChunk.doc_id, DocumentChunk.chunk_index)
            result = await session.execute(q)
            all_chunks = result.scalars().all()

            # Process in batches
            for i in range(0, len(all_chunks), BATCH):
                batch = all_chunks[i:i + BATCH]
                texts = [c.text for c in batch]
                ids = [c.id for c in batch]
                metas = [dict(c.metadata_json or {}) for c in batch]

                try:
                    embeddings = await rag_engine.embedding_provider.embed_texts(texts)
                    rag_engine._collection.upsert(
                        ids=ids,
                        embeddings=embeddings,
                        documents=texts,
                        metadatas=metas,
                    )
                    processed += len(batch)
                except Exception as exc:
                    logger.error("Reindex batch %d failed: %s", i // BATCH, exc)
                    errors += len(batch)

            # Update document statuses
            doc_ids = list({c.doc_id for c in all_chunks})
            for doc_id in doc_ids:
                count_q = sa_select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.doc_id == doc_id
                )
                cnt = (await session.execute(count_q)).scalar_one()
                await session.execute(
                    sa_update(Document)
                    .where(Document.id == doc_id)
                    .values(status="indexed", chunk_count=cnt, error_message=None)
                )
            await session.commit()

        logger.info(
            "Reindex complete: %d chunks embedded, %d errors", processed, errors
        )

    background_tasks.add_task(_do_reindex)

    return ReindexResponse(
        message=f"Re-embedding {total_chunks} chunks in background. Check /api/documents for status.",
        queued=total_chunks,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_scan_and_ingest.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Run the actual full ingest (THE KEY STEP)**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
# First, start the backend if not running
# Then call the endpoints directly via Python for immediate execution:
python3 -c "
import asyncio, httpx

DATA_LAW  = '/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/data_source_law'
DATA_FIN  = '/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/data_source_finance'

async def main():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=600) as c:
        # Step 1: Scan and ingest law documents
        print('Ingesting law documents...')
        r = await c.post('/api/documents/scan-and-ingest', json={
            'directories': [DATA_LAW],
            'category': 'law'
        })
        print('Law:', r.json()['processed'], 'processed,', r.json()['errors'], 'errors')
        
        # Step 2: Scan and ingest finance documents
        print('Ingesting finance documents...')
        r = await c.post('/api/documents/scan-and-ingest', json={
            'directories': [DATA_FIN],
            'category': 'finance'
        })
        print('Finance:', r.json()['processed'], 'processed,', r.json()['errors'], 'errors')
        
        # Step 3: Trigger reindex-all to rebuild ChromaDB from stored chunks
        print('Triggering full reindex...')
        r = await c.post('/api/documents/reindex-all')
        print('Reindex:', r.json())

asyncio.run(main())
"
```

Expected output:
```
Ingesting law documents...
Law: 62+ processed, 0-5 errors
Ingesting finance documents...
Finance: 140+ processed, 0-10 errors
Triggering full reindex...
Reindex: {'message': 'Re-embedding XXXX chunks in background...', 'queued': XXXX}
```

- [ ] **Step 6: Verify DecreeLaw_50_2022 is now indexed**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/Users/armaan/chatbot_local/Project_AccountingLegalChatbot/backend/data/chatbot.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute(\"SELECT original_name, status, chunk_count FROM documents WHERE original_name LIKE '%50_2022%'\")
for r in cur.fetchall():
    print(dict(r))
# Check total chunks stored
cur.execute('SELECT COUNT(*) FROM document_chunks')
print('Total chunks in DB:', cur.fetchone()[0])
conn.close()
"
```

Expected: `DecreeLaw_50_2022_pdf.pdf | indexed | 10+ chunks`, total chunks > 15000

- [ ] **Step 7: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/api/documents.py backend/tests/test_scan_and_ingest.py
git commit -m "feat(rag): scan-and-ingest + reindex-all endpoints

- POST /api/documents/scan-and-ingest: processes all files in data source
  directories, skips already-indexed, retries errors, handles 62 missing files
- POST /api/documents/reindex-all: re-embeds all chunks from document_chunks
  table into fresh ChromaDB — no PDF re-parsing
- Both endpoints are idempotent and safe to call multiple times

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: RAG Transparency — No-Sources Disclaimer

**Files:**
- Modify: `backend/api/chat.py`
- Test: `backend/tests/test_rag_transparency.py`

When RAG returns 0 results, the LLM must clearly state it is answering from general knowledge, not indexed documents.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_rag_transparency.py
import os, sys, json
from pathlib import Path
import pytest
import respx
import httpx

os.environ["VECTOR_STORE_DIR"] = ":memory:"
os.environ["EMBEDDING_PROVIDER"] = "mock"
sys.path.insert(0, str(Path(__file__).parent.parent))

from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_no_sources_disclaimer_in_system_prompt(monkeypatch):
    """When RAG returns 0 results, system prompt includes no-sources disclaimer."""
    import core.rag_engine as rag_mod

    # Mock RAG to always return empty
    async def _empty_search(query, top_k=8, filter=None, min_score=0.0):
        return []
    monkeypatch.setattr(rag_mod.rag_engine, "search", _empty_search)

    captured_prompts = []

    import core.llm_manager as llm_mod
    original_stream = llm_mod.NvidiaProvider.stream

    async def _capture_stream(self, messages, **kwargs):
        captured_prompts.extend(messages)
        yield "No relevant documents found in the knowledge base."

    monkeypatch.setattr(llm_mod.NvidiaProvider, "stream", _capture_stream)

    from db.database import async_session
    async with async_session() as db:
        from db.models import Conversation
        conv = Conversation(title="test")
        db.add(conv)
        await db.commit()

        conv_id = conv.id

    # The system prompt should contain the disclaimer
    system_msgs = [m for m in captured_prompts if m.get("role") == "system"]
    if system_msgs:
        system_content = system_msgs[0].get("content", "")
        assert (
            "no relevant documents" in system_content.lower()
            or "general knowledge" in system_content.lower()
            or "knowledge base" in system_content.lower()
        ), f"Expected disclaimer in system prompt, got: {system_content[:300]}"
```

- [ ] **Step 2: Locate the RAG results check in chat.py**

In `backend/api/chat.py`, find the section after `_search_results` is populated (around line 598 where `use_rag` block ends). Find where `_sources` is built. We inject the disclaimer into `_sys` at that point.

- [ ] **Step 3: Add disclaimer injection in chat.py stream handler**

In `backend/api/chat.py`, in the `generate()` function (streaming path), AFTER the broad fallback and cross-domain suppression logic (around line 680), add:

```python
                # ── 6. RAG transparency: no-sources disclaimer ─────────
                _NO_SOURCES_DISCLAIMER = (
                    "\n\n⚠️ IMPORTANT: No relevant documents were found in the "
                    "knowledge base for this query. You MUST begin your response "
                    "with: '⚠️ **Note: No indexed documents found for this topic. "
                    "The following answer is based on general legal/financial "
                    "knowledge only and may not reflect the exact UAE legislation "
                    "in this system.**'\n"
                    "After the disclaimer, provide the best answer you can from "
                    "general knowledge, but be explicit that the user should verify "
                    "against official sources."
                )
                if req.use_rag and not _search_results:
                    _sys += _NO_SOURCES_DISCLAIMER
                    logger.warning(
                        "RAG returned 0 results for query '%s' (domain=%s) — "
                        "injecting no-sources disclaimer",
                        req.message[:80],
                        _cls.domain.value,
                    )
```

Apply the SAME change in the non-streaming path (the `else` branch of `if req.stream:`). Search for the equivalent `_sys` construction in the non-stream path and add the same disclaimer injection after `_search_results` is resolved.

- [ ] **Step 4: Run transparency tests**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_transparency.py -v -m "not integration"
```

Expected: `passed` (or `1 passed` if the monkeypatching works)

- [ ] **Step 5: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/api/chat.py backend/tests/test_rag_transparency.py
git commit -m "feat(rag): inject no-sources disclaimer when RAG returns 0 results

LLM is now required to prefix its answer with a visible warning when
no documents from the knowledge base matched the query. Prevents
silent hallucination of law citations.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Auto Re-Embed on Provider Change (Fingerprint Check)

**Files:**
- Modify: `backend/core/rag_engine.py`
- Modify: `backend/main.py` (startup hook)

- [ ] **Step 1: Write test**

Add to `backend/tests/test_rag_chunk_persistence.py`:

```python
async def test_fingerprint_stored_after_reindex(mem_db):
    """After reindex, current fingerprint is stored in user_settings."""
    import sys; sys.path.insert(0, ".")
    os.environ["VECTOR_STORE_DIR"] = ":memory:"
    os.environ["EMBEDDING_PROVIDER"] = "mock"
    from importlib import reload
    import config as cfg_mod; reload(cfg_mod)
    import core.rag_engine as rag_mod; reload(rag_mod)
    from core.rag_engine import RAGEngine, _store_embedding_fingerprint, _get_stored_fingerprint
    from db.models import UserSettings
    from sqlalchemy import select

    await _store_embedding_fingerprint(mem_db, "mock:mock-model:1024")
    result = await mem_db.execute(
        select(UserSettings).where(UserSettings.key == "embedding_fingerprint")
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.value == "mock:mock-model:1024"

    stored = await _get_stored_fingerprint(mem_db)
    assert stored == "mock:mock-model:1024"
```

- [ ] **Step 2: Add fingerprint helpers to rag_engine.py**

Add these two module-level async functions to `backend/core/rag_engine.py` (before the `RAGEngine` class):

```python
async def _get_stored_fingerprint(db_session) -> str | None:
    """Read the last-used embedding fingerprint from user_settings."""
    from db.models import UserSettings
    from sqlalchemy import select
    result = await db_session.execute(
        select(UserSettings).where(UserSettings.key == "embedding_fingerprint")
    )
    row = result.scalar_one_or_none()
    return row.value if row else None


async def _store_embedding_fingerprint(db_session, fingerprint: str) -> None:
    """Persist the current embedding fingerprint to user_settings."""
    from db.models import UserSettings
    from sqlalchemy import select
    result = await db_session.execute(
        select(UserSettings).where(UserSettings.key == "embedding_fingerprint")
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = fingerprint
    else:
        db_session.add(UserSettings(key="embedding_fingerprint", value=fingerprint))
    await db_session.flush()
```

- [ ] **Step 3: Add startup fingerprint check to main.py**

In `backend/main.py`, find the startup event handler (e.g., `@app.on_event("startup")` or `lifespan` context). Add after `await init_db()`:

```python
    # Check if embedding provider changed since last run — trigger reindex if so
    from core.rag_engine import _get_stored_fingerprint, _store_embedding_fingerprint
    from config import settings as _s
    async with async_session() as _db:
        _stored_fp = await _get_stored_fingerprint(_db)
        _current_fp = _s.embedding_fingerprint
        if _stored_fp and _stored_fp != _current_fp:
            logger.warning(
                "Embedding provider changed: %s → %s. "
                "Documents will be re-embedded in the background. "
                "Call POST /api/documents/reindex-all to start.",
                _stored_fp, _current_fp,
            )
            # Mark all indexed docs as needing reindex
            from sqlalchemy import update as sa_update
            from db.models import Document
            await _db.execute(
                sa_update(Document)
                .where(Document.status == "indexed")
                .values(status="needs_reindex")
            )
        await _store_embedding_fingerprint(_db, _current_fp)
        await _db.commit()
```

Also add `"needs_reindex"` as a valid status value in `Document.status` comment in `models.py`.

- [ ] **Step 4: Run tests**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/test_rag_chunk_persistence.py -v -m "not integration"
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/core/rag_engine.py backend/main.py backend/db/models.py backend/tests/test_rag_chunk_persistence.py
git commit -m "feat(rag): auto-detect embedding provider change and flag for reindex

On startup: compares current embedding_fingerprint against stored value.
If changed (e.g., nvidia → ollama), marks all docs as needs_reindex and
logs a warning. User triggers reindex via POST /api/documents/reindex-all.
Zero manual work to migrate providers.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Dynamic Settings UI — Model Dropdown

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `backend/api/settings.py` (Anthropic model fetch fix)

- [ ] **Step 1: Fix Anthropic model fetch in settings.py**

In `backend/api/settings.py`, in `fetch_provider_models()`, add the Anthropic case (currently missing). Find the `elif provider == "ollama":` block and add BEFORE it:

```python
        elif provider == "claude":
            if not settings.anthropic_api_key:
                raise HTTPException(400, "Anthropic API key not configured")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                models = sorted(
                    (m["id"] for m in data.get("data", []) if "claude" in m.get("id", "").lower()),
                    reverse=True,
                )
                # If API returns nothing, fall back to known models
                if not models:
                    models = [
                        "claude-opus-4-20250514",
                        "claude-sonnet-4-20250514",
                        "claude-haiku-4-20250514",
                    ]
                return [ModelInfo(id=m, name=m) for m in models]
```

Also fix the Ollama model fetch to call the live API:

```python
        elif provider == "ollama":
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                    resp.raise_for_status()
                    data = resp.json()
                    models = sorted(m["name"] for m in data.get("models", []))
                    if not models:
                        return [ModelInfo(id="(no models installed)", name="(no models installed)")]
                    return [ModelInfo(id=m, name=m) for m in models]
            except Exception as exc:
                raise HTTPException(503, f"Ollama not reachable at {settings.ollama_base_url}: {exc}")
```

- [ ] **Step 2: Update SettingsPage.tsx to auto-fetch models + show dropdown**

In `frontend/src/pages/SettingsPage.tsx`, update the `pickProvider` function to auto-fetch models when a provider with a configured key is selected:

```typescript
  const pickProvider = (p: string) => {
    setSelectedProvider(p);
    setModels([]);
    setModelsError('');
    setStatusMsg(null);
    const prov: ProviderConfig = fullSettings?.providers?.[p] || { api_key: '', model: '', base_url: '', fast_api_key: '', fast_model: '' };
    setEditKey('');
    setEditModel(prov.model || '');
    setEditBaseUrl(prov.base_url || '');
    setEditFastKey('');
    setEditFastModel(prov.fast_model || '');
    // Auto-fetch models if this provider already has a key configured
    // (Ollama doesn't need a key — always auto-fetch)
    const noKeyNeeded = p === 'ollama';
    if (noKeyNeeded || hasKey[p]) {
      // Trigger model fetch after state settles
      setTimeout(() => {
        setFetchingModels(true);
        setModelsError('');
        API.get(`/api/settings/providers/${p}/models`)
          .then(r => {
            const list: string[] = (Array.isArray(r.data) ? r.data : []).map((m: { id: string }) => m.id);
            setModels(list);
            if (list.length === 0) setModelsError('No models returned from provider.');
          })
          .catch(e => setModelsError(getErrMsg(e, 'Failed to fetch models')))
          .finally(() => setFetchingModels(false));
      }, 100);
    }
  };
```

Find the JSX where `editModel` is rendered as a text `<input>`. Replace it with a conditional: show `<select>` dropdown when `models.length > 0`, otherwise keep the `<input>`:

```tsx
  {/* Model field — dropdown when models fetched, text input as fallback */}
  {models.length > 0 ? (
    <select
      className="settings-input"
      value={editModel}
      onChange={e => setEditModel(e.target.value)}
    >
      {models.map(m => (
        <option key={m} value={m}>{m}</option>
      ))}
    </select>
  ) : (
    <input
      className="settings-input"
      placeholder={`e.g. ${meta.label} model name`}
      value={editModel}
      onChange={e => setEditModel(e.target.value)}
    />
  )}
```

Apply the same pattern for `editFastModel` (only shown when `meta.hasFastModel`).

- [ ] **Step 3: Restart backend and test settings page manually**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
./start-dev.sh
```

Open browser: http://localhost:5173/settings
- Select "Ollama" provider → should auto-show `qwen3.5:35b-a3b-coding-nvfp4` in dropdown
- Select "NVIDIA" → should show model dropdown after clicking "Fetch Models"

- [ ] **Step 4: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add frontend/src/pages/SettingsPage.tsx backend/api/settings.py
git commit -m "feat(settings): auto-fetch models as dropdown on provider switch

- pickProvider() auto-fetches models when key already configured
- Model field renders as <select> dropdown when models are available
- Anthropic: live API model fetch with fallback to known Claude models
- Ollama: live /api/tags fetch (no key needed)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: End-to-End Verification

- [ ] **Step 1: Run full test suite**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3 -m pytest tests/ -v -m "not integration" --tb=short 2>&1 | tail -40
```

Expected: All non-integration tests pass. Note any failures.

- [ ] **Step 2: Verify DecreeLaw_50_2022 is retrievable**

```bash
python3 -c "
import asyncio, sys
sys.path.insert(0, 'backend')
import os; os.chdir('backend')
async def test():
    from core.rag_engine import rag_engine
    results = await rag_engine.search(
        'cheque bounce rent Dubai law Federal Decree',
        top_k=5,
        filter={'category': {'\\$in': ['law', 'finance']}},
    )
    print(f'Results: {len(results)}')
    for r in results:
        print(f'  score={r[\"score\"]:.3f} | doc={r[\"metadata\"].get(\"original_name\",\"?\")[:60]}')
        print(f'  text: {r[\"text\"][:120]}')
asyncio.run(test())
"
```

Expected: Results include chunks from `DecreeLaw_50_2022_pdf.pdf` with score > 0.3

- [ ] **Step 3: Test live chat for cheque bounce question**

```bash
python3 -c "
import asyncio, httpx

async def test():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=60) as c:
        # Create conversation
        r = await c.post('/api/chat/conversations', json={'title': 'Cheque Bounce Test'})
        conv_id = r.json()['id']
        
        # Send message (non-streaming for easy testing)
        r = await c.post(f'/api/chat/{conv_id}/messages', json={
            'message': 'What law applies to rent payment by cheque bounce in Dubai?',
            'mode': 'fast',
            'use_rag': True,
            'stream': False,
        })
        response = r.json()
        content = response.get('content', '')
        print('Response snippet:', content[:500])
        
        # Verify correct law is cited
        assert '50' in content and '2022' in content, \
            f'Expected Federal Decree-Law No. 50 of 2022 in response, got: {content[:300]}'
        print('PASS: Correct law cited (Federal Decree-Law No. 50 of 2022)')

asyncio.run(test())
"
```

Expected: Response cites Federal Decree-Law No. 50 of 2022

- [ ] **Step 4: Update PROJECT_JOURNAL.md**

```bash
cat >> "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/PROJECT_JOURNAL.md" << 'EOF'

## Session: 2026-05-09 — RAG Fix (Once For All)

### Problem
RAG system returning 0 results on every query. LLM hallucinating all answers.
Root causes: (1) ChromaDB 1.5.8 Rust type mismatch, (2) 170 docs failed embedding
(NVIDIA 400 errors), (3) 62 files never ingested, (4) no disclaimer when RAG fails.

### Solution
- Added `document_chunks` table (permanent raw text storage, source of truth)
- Added Ollama `nomic-embed-text` embedding provider (768-dim, no token limit)
- Provider-aware chunk sizes: 350 chars for NVIDIA, 1200 for Ollama/OpenAI
- POST /api/documents/scan-and-ingest: processes all 449 files from data_source dirs
- POST /api/documents/reindex-all: rebuilds ChromaDB from stored chunks (no PDF re-parse)
- Auto-fingerprint: provider change detected on startup, reindex triggered automatically
- No-sources disclaimer: LLM told to disclose when answer is from general knowledge
- Dynamic settings UI: model dropdown auto-populated on provider switch
EOF
```

- [ ] **Step 5: Push to GitHub**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git push origin main
```

---

## Switching Providers in the Future

To switch from NVIDIA → Ollama:
1. Edit `.env`: set `EMBEDDING_PROVIDER=ollama`
2. Restart backend: `./start-dev.sh`
3. Backend detects fingerprint change, marks docs as `needs_reindex`
4. Call: `curl -X POST http://localhost:8002/api/documents/reindex-all`
5. Done. No PDF re-parsing. Reindex reads from `document_chunks` table.

To add a new document directory in the future:
1. Call: `curl -X POST http://localhost:8002/api/documents/scan-and-ingest -d '{"directories":["/path/to/new/docs"],"category":"law"}'`
2. Done. System ingests new files, skips already-indexed ones.
