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


@pytest.mark.asyncio
async def test_title_scheduled_on_new_conversation(client):
    """Posting a new message must trigger _generate_title via asyncio.create_task."""
    from api.chat import _generate_title

    title_calls = []

    async def _fake_generate_title(conv_id, message, provider=None):
        title_calls.append(conv_id)

    from unittest.mock import patch as _patch
    from core.chat.domain_classifier import DomainLabel, ClassifierResult
    from core.llm_manager import LLMResponse

    def _stub_cls():
        return ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value=LLMResponse(content="ok", tokens_used=5, provider="mock", model="m")
    )

    async def _stream(*a, **kw):
        yield "ok"

    mock_llm.chat_stream = _stream

    with (
        _patch("api.chat._generate_title", side_effect=_fake_generate_title),
        _patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        _patch("api.chat.get_llm_provider", return_value=mock_llm),
        _patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        _patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
    ):
        resp = await client.post("/api/chat/send", json={
            "message": "I have a client who sold a hotel apartment",
            "mode": "fast",
            "stream": False,
        })

    import asyncio as _asyncio
    await _asyncio.sleep(0)  # yield to let create_task'd coroutine run

    assert resp.status_code == 200
    assert len(title_calls) == 1, (
        f"Expected _generate_title to be called once on new conversation, got: {title_calls}"
    )
    conv_id = resp.json().get("conversation_id")
    assert title_calls[0] == conv_id, (
        f"_generate_title called with wrong conv_id: {title_calls[0]} != {conv_id}"
    )


@pytest.mark.asyncio
async def test_title_uses_background_tasks_not_create_task(client):
    """_generate_title must be registered via background_tasks.add_task, not asyncio.create_task.

    BackgroundTasks runs after get_db's session.commit() cleanup, so the
    Conversation row is always visible when _generate_title opens a new session.
    Using asyncio.create_task risks running the coroutine before that commit.
    """
    from fastapi import BackgroundTasks
    from unittest.mock import patch, AsyncMock
    from core.chat.domain_classifier import DomainLabel, ClassifierResult
    from core.llm_manager import LLMResponse

    registered_funcs: list = []
    _orig_add_task = BackgroundTasks.add_task

    def _capture_add_task(self, func, *args, **kwargs):
        registered_funcs.append(func)
        return _orig_add_task(self, func, *args, **kwargs)

    mock_gt = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value=LLMResponse(content="Answer", tokens_used=5, provider="mock", model="m")
    )

    with (
        patch.object(BackgroundTasks, 'add_task', new=_capture_add_task),
        patch("api.chat._generate_title", new=mock_gt),
        patch("api.chat.classify_domain", new=AsyncMock(
            return_value=ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])
        )),
        patch("api.chat.get_llm_provider", return_value=mock_llm),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
    ):
        resp = await client.post("/api/chat/send", json={
            "message": "I have a client who sold a hotel apartment",
            "mode": "fast",
            "stream": False,
        })

    assert resp.status_code == 200
    assert mock_gt in registered_funcs, (
        "_generate_title was not registered via background_tasks.add_task. "
        "Title generation must use background_tasks, not asyncio.create_task. "
        f"Registered funcs: {[getattr(f, '__name__', repr(f)) for f in registered_funcs]}"
    )


@pytest.mark.asyncio
async def test_title_uses_background_tasks_not_create_task_streaming(client):
    """Streaming path must also register _generate_title via background_tasks.add_task."""
    from fastapi import BackgroundTasks
    from unittest.mock import patch, AsyncMock
    from core.chat.domain_classifier import DomainLabel, ClassifierResult
    from core.llm_manager import LLMResponse

    registered_funcs: list = []
    _orig_add_task = BackgroundTasks.add_task

    def _capture_add_task(self, func, *args, **kwargs):
        registered_funcs.append(func)
        return _orig_add_task(self, func, *args, **kwargs)

    mock_gt = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value=LLMResponse(content="Answer", tokens_used=5, provider="mock", model="m")
    )

    async def _fake_stream(*a, **kw):
        yield "Answer"

    mock_llm.chat_stream = _fake_stream

    with (
        patch.object(BackgroundTasks, 'add_task', new=_capture_add_task),
        patch("api.chat._generate_title", new=mock_gt),
        patch("api.chat.classify_domain", new=AsyncMock(
            return_value=ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])
        )),
        patch("api.chat.get_llm_provider", return_value=mock_llm),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
    ):
        resp = await client.post("/api/chat/send", json={
            "message": "I have a client who sold a hotel apartment",
            "mode": "fast",
            "stream": True,
        })

    assert resp.status_code == 200
    assert mock_gt in registered_funcs, (
        "Streaming path: _generate_title was not registered via background_tasks.add_task. "
        f"Registered funcs: {[getattr(f, '__name__', repr(f)) for f in registered_funcs]}"
    )


@pytest.mark.asyncio
async def test_generate_title_has_defensive_delay():
    """_generate_title must await asyncio.sleep at startup for DB-commit safety."""
    import asyncio
    from unittest.mock import patch, AsyncMock, MagicMock

    sleep_calls: list = []
    _orig_sleep = asyncio.sleep

    async def _capture_sleep(delay, *a, **kw):
        sleep_calls.append(delay)
        return await _orig_sleep(0)  # don't actually wait in tests

    with patch("api.chat.asyncio.sleep", side_effect=_capture_sleep):
        # Import the function so we can call it directly
        from api.chat import _generate_title, _TITLE_GENERATION_DELAY_S
        from core.llm_manager import LLMResponse
        
        # Patch its DB session factory so it doesn't hit real DB
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # conv not found → function exits early
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Mock LLM provider
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(
            return_value=LLMResponse(content="Test Title", tokens_used=5, provider="mock", model="m")
        )

        with patch("api.chat.AsyncSessionLocal", return_value=mock_session), \
             patch("api.chat.get_llm_provider", return_value=mock_llm):
            await _generate_title(conversation_id="00000000-0000-0000-0000-000000000001", message="test", provider="openai")

    assert sleep_calls and sleep_calls[0] == _TITLE_GENERATION_DELAY_S, (
        f"_generate_title must call `await asyncio.sleep({_TITLE_GENERATION_DELAY_S})` as its FIRST statement. "
        f"Actual sleep calls (in order): {sleep_calls}"
    )
