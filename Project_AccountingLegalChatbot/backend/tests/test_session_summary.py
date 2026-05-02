"""Tests for session summary memory in fast mode."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from db.models import Conversation
from db.database import AsyncSessionLocal
from sqlalchemy import select
from core.llm_manager import LLMResponse
from core.chat.domain_classifier import DomainLabel, ClassifierResult


def _mock_llm(answer: str = "Summary text."):
    mock = MagicMock()
    mock.chat = AsyncMock(
        return_value=LLMResponse(content=answer, tokens_used=10, provider="mock", model="mock-v1")
    )
    async def _stream(*a, **kw):
        yield answer
    mock.chat_stream = _stream
    return mock


@pytest.mark.asyncio
async def test_summary_columns_exist():
    """Conversation model must have summary and summary_msg_count columns."""
    assert hasattr(Conversation, "summary"), "Conversation.summary column missing"
    assert hasattr(Conversation, "summary_msg_count"), "Conversation.summary_msg_count column missing"


@pytest.mark.asyncio
async def test_summary_written_after_many_messages(client, db_session):
    """After 21+ messages in fast mode, summary must be written to the conversation."""
    stub_classifier = ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.9, alternatives=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=stub_classifier)),
        patch("api.chat.get_llm_provider", return_value=_mock_llm("Older turns covered VAT basics.")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        r = await client.post("/api/chat/send", json={"message": "msg0", "mode": "fast", "stream": False})
        assert r.status_code == 200
        cid = r.json()["conversation_id"]

        for i in range(1, 22):
            await client.post("/api/chat/send", json={
                "message": f"msg{i}", "conversation_id": cid, "mode": "fast", "stream": False
            })

        await asyncio.sleep(1.0)

    db_session.expire_all()
    conv = (await db_session.execute(select(Conversation).where(Conversation.id == cid))).scalar_one()
    assert conv.summary is not None, "Summary was never written"
    assert conv.summary_msg_count > 0
