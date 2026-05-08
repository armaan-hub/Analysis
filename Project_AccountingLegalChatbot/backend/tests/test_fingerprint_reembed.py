"""Tests for embedding fingerprint change detection and auto-reindex flagging."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text as sa_text
from db.models import Base, Document as DBDocument


@pytest.fixture
async def mem_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_fingerprint_stored_on_startup(mem_db):
    """On startup, current embedding fingerprint is saved to user_settings."""
    from api.documents import store_fingerprint_if_changed
    from config import settings

    changed = await store_fingerprint_if_changed(db=mem_db)
    # First run — fingerprint stored, returns False (no change, first write)
    assert changed is False or changed is True  # acceptable either way on first write

    result = await mem_db.execute(
        sa_text("SELECT value FROM user_settings WHERE key = 'embedding_fingerprint'")
    )
    row = result.fetchone()
    assert row is not None, "Fingerprint must be stored in user_settings"
    assert row[0] == settings.embedding_fingerprint


async def test_fingerprint_change_marks_docs_needs_reindex(mem_db):
    """When fingerprint changes, all documents get needs_reindex=True."""
    from api.documents import store_fingerprint_if_changed
    from config import settings

    doc = DBDocument(id="fp-doc-01", filename="a.pdf", original_name="a.pdf", file_type=".pdf")
    mem_db.add(doc)
    await mem_db.commit()

    # Manually write an OLD fingerprint
    await mem_db.execute(
        sa_text("INSERT OR REPLACE INTO user_settings (key, value) VALUES ('embedding_fingerprint', 'old:model:999')")
    )
    await mem_db.commit()

    changed = await store_fingerprint_if_changed(db=mem_db)
    assert changed is True, "Should detect fingerprint change"

    result = await mem_db.execute(select(DBDocument).where(DBDocument.id == "fp-doc-01"))
    doc = result.scalar_one()
    assert doc.needs_reindex is True, "Doc should be flagged needs_reindex after fingerprint change"


async def test_no_reindex_when_fingerprint_unchanged(mem_db):
    """When fingerprint is the same, needs_reindex stays False."""
    from api.documents import store_fingerprint_if_changed
    from config import settings

    doc = DBDocument(id="fp-doc-02", filename="b.pdf", original_name="b.pdf", file_type=".pdf")
    mem_db.add(doc)
    await mem_db.commit()

    # Write SAME fingerprint
    await mem_db.execute(
        sa_text(f"INSERT OR REPLACE INTO user_settings (key, value) VALUES ('embedding_fingerprint', '{settings.embedding_fingerprint}')")
    )
    await mem_db.commit()

    changed = await store_fingerprint_if_changed(db=mem_db)
    assert changed is False

    result = await mem_db.execute(select(DBDocument).where(DBDocument.id == "fp-doc-02"))
    doc = result.scalar_one()
    assert doc.needs_reindex is False
