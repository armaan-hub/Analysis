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
@pytest.mark.asyncio
async def test_ollama_embed_returns_vector():
    """OllamaEmbeddingProvider returns a 768-dim vector (mocked Ollama)."""
    import sys; sys.path.insert(0, ".")
    import respx
    import httpx
    from core.rag_engine import OllamaEmbeddingProvider

    fake_vector = [0.01] * 768
    with respx.mock:
        respx.post("http://localhost:11434/api/embeddings").mock(
            return_value=httpx.Response(200, json={"embedding": fake_vector})
        )
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


async def test_document_processor_default_chunk_size():
    """DocumentProcessor() with no args uses provider-aware chunk size (not None)."""
    import sys; sys.path.insert(0, ".")
    from core.document_processor import DocumentProcessor
    dp = DocumentProcessor()
    assert dp.chunk_size is not None, "chunk_size must not be None"
    assert isinstance(dp.chunk_size, int), f"Expected int, got {type(dp.chunk_size)}"
    assert dp.chunk_size > 0
    assert dp.chunk_overlap is not None, "chunk_overlap must not be None"
    assert dp.chunk_overlap < dp.chunk_size


# ── Task 3 tests ─────────────────────────────────────────────────────────────

async def test_ingest_chunks_persists_to_db(mem_db):
    """ingest_chunks() with db_session saves raw text to document_chunks table."""
    import sys; sys.path.insert(0, ".")
    import os as _os
    _os.environ["EMBEDDING_PROVIDER"] = "mock"

    from importlib import reload
    import config as cfg_mod; reload(cfg_mod)
    import core.rag_engine as rag_mod; reload(rag_mod)
    from core.rag_engine import RAGEngine
    from db.models import DocumentChunk as DBDocumentChunk

    engine_instance = RAGEngine()

    # Insert parent document first
    from db.models import Document as DBDocument
    doc = DBDocument(
        id="doc-rag-01",
        filename="decree50.pdf",
        original_name="DecreeLaw_50_2022_pdf.pdf",
        file_type=".pdf",
    )
    mem_db.add(doc)
    await mem_db.commit()

    chunks = [
        {"id": "c-rag-1", "text": "Federal Decree-Law No. 50 of 2022 on cheque crimes.",
         "metadata": {"domain": "general", "category": "law"}},
        {"id": "c-rag-2", "text": "Article 1: Issuing a cheque with insufficient funds.",
         "metadata": {"domain": "general", "category": "law"}},
    ]
    await engine_instance.ingest_chunks(
        chunks=chunks,
        doc_id="doc-rag-01",
        original_name="DecreeLaw_50_2022_pdf.pdf",
        category="law",
        db_session=mem_db,
    )

    result = await mem_db.execute(
        select(DBDocumentChunk)
        .where(DBDocumentChunk.doc_id == "doc-rag-01")
        .order_by(DBDocumentChunk.chunk_index)
    )
    saved = result.scalars().all()
    assert len(saved) == 2, f"Expected 2 chunks, got {len(saved)}"
    assert saved[0].text == "Federal Decree-Law No. 50 of 2022 on cheque crimes."
    assert saved[1].text == "Article 1: Issuing a cheque with insufficient funds."
    assert saved[0].chunk_index == 0
    assert saved[1].chunk_index == 1


async def test_ingest_chunks_idempotent(mem_db):
    """Re-calling ingest_chunks() for same doc replaces old chunks (no duplicates)."""
    import sys; sys.path.insert(0, ".")
    import os as _os
    _os.environ["EMBEDDING_PROVIDER"] = "mock"

    from importlib import reload
    import config as cfg_mod; reload(cfg_mod)
    import core.rag_engine as rag_mod; reload(rag_mod)
    from core.rag_engine import RAGEngine
    from db.models import DocumentChunk as DBDocumentChunk, Document as DBDocument

    engine_instance = RAGEngine()

    doc = DBDocument(id="doc-idem-01", filename="f.pdf", original_name="f.pdf", file_type=".pdf")
    mem_db.add(doc)
    await mem_db.commit()

    for i in range(2):  # ingest twice
        await engine_instance.ingest_chunks(
            chunks=[{"id": f"chunk-idem-{i}", "text": f"Run {i}", "metadata": {}}],
            doc_id="doc-idem-01",
            original_name="f.pdf",
            category="law",
            db_session=mem_db,
        )

    result = await mem_db.execute(
        select(DBDocumentChunk).where(DBDocumentChunk.doc_id == "doc-idem-01")
    )
    saved = result.scalars().all()
    assert len(saved) == 1, f"Expected 1 chunk after idempotent re-ingest, got {len(saved)}"
    assert saved[0].text == "Run 1"
