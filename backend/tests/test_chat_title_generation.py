"""Tests for AI-generated conversation title background task."""
import pytest
from unittest.mock import AsyncMock, patch
from core.llm_manager import LLMResponse


@pytest.mark.asyncio
async def test_generate_title_updates_conversation():
    """After calling _generate_title, the conversation title must be updated
    from the truncated raw text to the LLM-generated short title."""
    from api.chat import _generate_title
    from db.database import AsyncSessionLocal
    from db.models import Conversation
    from sqlalchemy import select

    with patch("api.chat.get_llm_provider", return_value=AsyncMock(
        chat=AsyncMock(return_value=LLMResponse(
            content="UAE VAT Hotel Apartment Sale",
            tokens_used=8, provider="mock", model="mock-v1"
        ))
    )):
        async with AsyncSessionLocal() as db:
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

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
            updated = result.scalar_one_or_none()
            assert updated is not None
            assert updated.title == "UAE VAT Hotel Apartment Sale"


@pytest.mark.asyncio
async def test_generate_title_is_non_fatal_on_llm_error():
    """If the LLM call fails, _generate_title must not raise — title stays unchanged."""
    from api.chat import _generate_title
    from db.database import AsyncSessionLocal
    from db.models import Conversation
    from sqlalchemy import select

    with patch("api.chat.get_llm_provider", side_effect=RuntimeError("LLM unavailable")):
        async with AsyncSessionLocal() as db:
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

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
            unchanged = result.scalar_one_or_none()
            assert unchanged is not None
            assert unchanged.title == "Original title"
