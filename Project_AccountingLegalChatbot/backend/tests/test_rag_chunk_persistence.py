import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, event, text
from db.models import Base, DocumentChunk, Document

@pytest.fixture
async def mem_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

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


async def test_document_chunk_cascade_delete_db_level(mem_db):
    """DB-level ON DELETE CASCADE removes chunks when parent doc is deleted via SQL."""
    from sqlalchemy import text as sa_text
    from db.models import Document as DBDocument, DocumentChunk as DBChunk

    doc = DBDocument(id="doc-db-cascade", filename="x.pdf", original_name="x.pdf", file_type=".pdf")
    mem_db.add(doc)
    await mem_db.flush()
    mem_db.add(DBChunk(id="c-db-1", doc_id="doc-db-cascade", chunk_index=0, text="test text"))
    await mem_db.commit()

    # Delete via raw SQL (bypasses ORM cascade — tests DB FK cascade)
    await mem_db.execute(sa_text("DELETE FROM documents WHERE id = 'doc-db-cascade'"))
    await mem_db.commit()

    result = await mem_db.execute(
        sa_text("SELECT COUNT(*) FROM document_chunks WHERE doc_id = 'doc-db-cascade'")
    )
    count = result.scalar()
    assert count == 0, f"Expected 0 chunks after DB-level cascade delete, got {count}"


# ── Task 2 tests ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Requires local Ollama server",
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
    """NVIDIA provider uses <=350 char chunk size."""
    import os as _os
    _os.environ["EMBEDDING_PROVIDER"] = "nvidia"
    from importlib import reload
    import config as cfg_module
    reload(cfg_module)
    from config import settings as s
    assert s.embedding_chunk_size <= 350, f"Expected <=350, got {s.embedding_chunk_size}"


async def test_provider_aware_chunk_size_ollama():
    """Ollama provider uses >=1000 char chunk size."""
    import os as _os
    _os.environ["EMBEDDING_PROVIDER"] = "ollama"
    from importlib import reload
    import config as cfg_module
    reload(cfg_module)
    from config import settings as s
    assert s.embedding_chunk_size >= 1000, f"Expected >=1000, got {s.embedding_chunk_size}"
    _os.environ["EMBEDDING_PROVIDER"] = "nvidia"  # reset


async def test_embedding_fingerprint_format():
    """embedding_fingerprint is provider:model:dimension string."""
    from importlib import reload
    import config as cfg_module
    reload(cfg_module)
    from config import settings as s
    fp = s.embedding_fingerprint
    parts = fp.split(":")
    assert len(parts) == 3, f"Expected 3 parts, got: {fp}"
    assert parts[2].isdigit(), f"Dimension must be integer, got: {parts[2]}"
