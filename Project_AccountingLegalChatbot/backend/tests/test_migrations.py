import pytest
from sqlalchemy import text
from db.database import engine
from db.models import Base

@pytest.mark.asyncio
async def test_content_hash_column_exists():
    """Verify that create_all creates the expected columns."""
    from sqlalchemy.ext.asyncio import create_async_engine
    # Use a fresh in-memory DB for this test to be certain of state
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with test_engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(documents)"))
        cols = {row[1] for row in result.fetchall()}
        assert 'content_hash' in cols, f"content_hash not found. Columns: {cols}"
        assert 'summary' in cols
        assert 'key_terms' in cols
        assert 'source' in cols


@pytest.mark.asyncio
async def test_entities_tables_exist():
    """Verify that create_all creates GraphRAG tables."""
    from sqlalchemy.ext.asyncio import create_async_engine
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with test_engine.connect() as conn:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {row[0] for row in result.fetchall()}
        assert 'entities' in tables, f"entities table not found. Tables: {tables}"
        assert 'entity_relations' in tables


@pytest.mark.asyncio
async def test_conversation_columns_exist():
    """Verify that create_all creates new conversation columns."""
    from sqlalchemy.ext.asyncio import create_async_engine
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with test_engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(conversations)"))
        cols = {row[1] for row in result.fetchall()}
        assert 'domain' in cols
        assert 'is_pinned' in cols
        assert 'mode' in cols
        assert 'summary' in cols
        assert 'summary_msg_count' in cols
