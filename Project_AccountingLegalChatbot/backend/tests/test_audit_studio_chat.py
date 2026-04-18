import uuid
import pytest
from db.database import AsyncSessionLocal
from db.models import AuditProfile, AuditChatMessage
from sqlalchemy import select


@pytest.mark.asyncio
async def test_audit_chat_message_persists():
    profile_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=profile_id, engagement_name="Test Co"))
        await s.flush()
        m = AuditChatMessage(
            profile_id=profile_id,
            role="user",
            content="Flag anomalies",
            citations='[{"doc_id":"d1","page":3}]',
        )
        s.add(m)
        await s.commit()
        row = (await s.execute(select(AuditChatMessage).where(AuditChatMessage.profile_id == profile_id))).scalar_one()
        assert row.role == "user"
        assert "d1" in row.citations


# ── Task 9 ────────────────────────────────────────────────────────

from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from main import app


@pytest.mark.asyncio
async def test_chat_send_persists_user_and_assistant():
    pid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=pid, engagement_name="X"))
        await s.commit()

    fake_reply = {"content": "No anomalies found.", "citations": []}
    with patch("core.audit_studio.chat_service.run_chat", new=AsyncMock(return_value=fake_reply)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/audit-profiles/{pid}/chat", json={"message": "Flag anomalies"})
            assert r.status_code == 200
            body = r.json()
            assert body["content"] == "No anomalies found."

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(AuditChatMessage).where(AuditChatMessage.profile_id == pid).order_by(AuditChatMessage.created_at)
        )).scalars().all()
        assert [r.role for r in rows] == ["user", "assistant"]


# ── Task 10 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_history_and_clear():
    pid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=pid, engagement_name="X"))
        await s.flush()
        s.add(AuditChatMessage(profile_id=pid, role="user", content="hi"))
        s.add(AuditChatMessage(profile_id=pid, role="assistant", content="hello"))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/audit-profiles/{pid}/chat/history")
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]

        d = await c.delete(f"/api/audit-profiles/{pid}/chat/history")
        assert d.status_code == 200

        r2 = await c.get(f"/api/audit-profiles/{pid}/chat/history")
        assert r2.json()["messages"] == []
