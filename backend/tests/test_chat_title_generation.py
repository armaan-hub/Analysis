"""Tests for AI-generated conversation title background task."""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from core.llm_manager import LLMResponse
from db.database import Base
from db.models import Conversation
from sqlalchemy import select


@pytest_asyncio.fixture
async def title_db():
    """Per-test in-memory SQLite engine — tables created in the same event loop as the test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def _session():
        async with factory() as s:
            yield s

    yield _session

    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_title_updates_conversation(title_db):
    """After calling _generate_title, the conversation title must be updated
    from the truncated raw text to the LLM-generated short title."""
    from api.chat import _generate_title

    with patch("api.chat.AsyncSessionLocal", title_db), \
         patch("api.chat.get_llm_provider", return_value=AsyncMock(
             chat=AsyncMock(return_value=LLMResponse(
                 content="UAE VAT Hotel Apartment Sale",
                 tokens_used=8, provider="mock", model="mock-v1"
             ))
         )):
        async with title_db() as db:
            conv = Conversation(
                title="I have a client who sold Hotel Apartment and now...",
                llm_provider="mock",
                llm_model="mock-v1",
                mode="fast",
            )
            db.add(conv)
            await db.flush()
            conv_id = conv.id
            await db.commit()

        await _generate_title(conv_id, "I have a client who sold Hotel Apartment and now got notice from FTA")

        async with title_db() as db:
            result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
            updated = result.scalar_one_or_none()
            assert updated is not None
            assert updated.title == "UAE VAT Hotel Apartment Sale"


@pytest.mark.asyncio
async def test_generate_title_is_non_fatal_on_llm_error(title_db):
    """If the LLM call fails, _generate_title must not raise — title stays unchanged."""
    from api.chat import _generate_title

    with patch("api.chat.AsyncSessionLocal", title_db), \
         patch("api.chat.get_llm_provider", side_effect=RuntimeError("LLM unavailable")):
        async with title_db() as db:
            conv = Conversation(
                title="Original title",
                llm_provider="mock",
                llm_model="mock-v1",
                mode="fast",
            )
            db.add(conv)
            await db.flush()
            conv_id = conv.id
            await db.commit()

        # Must NOT raise
        await _generate_title(conv_id, "some message")

        async with title_db() as db:
            result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
            unchanged = result.scalar_one_or_none()
            assert unchanged is not None
            assert unchanged.title == "Original title"
