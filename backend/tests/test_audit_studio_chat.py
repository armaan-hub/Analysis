import uuid
import pytest
from db.models import AuditProfile, AuditChatMessage
from sqlalchemy import select


@pytest.mark.asyncio
async def test_audit_chat_message_persists(db_session):
    profile_id = str(uuid.uuid4())
    db_session.add(AuditProfile(id=profile_id, engagement_name="Test Co"))
    await db_session.flush()
    m = AuditChatMessage(
        profile_id=profile_id,
        role="user",
        content="Flag anomalies",
        citations='[{"doc_id":"d1","page":3}]',
    )
    db_session.add(m)
    await db_session.commit()
    row = (await db_session.execute(select(AuditChatMessage).where(AuditChatMessage.profile_id == profile_id))).scalar_one()
    assert row.role == "user"
    assert "d1" in row.citations


# ── Task 9 ────────────────────────────────────────────────────────

from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_chat_send_persists_user_and_assistant(db_session, client):
    pid = str(uuid.uuid4())
    db_session.add(AuditProfile(id=pid, engagement_name="X"))
    await db_session.commit()

    fake_reply = {"content": "No anomalies found.", "citations": []}
    with patch("core.audit_studio.chat_service.run_chat", new=AsyncMock(return_value=fake_reply)):
        r = await client.post(f"/api/audit-profiles/{pid}/chat", json={"message": "Flag anomalies"})
        assert r.status_code == 200
        body = r.json()
        assert body["content"] == "No anomalies found."

    rows = (await db_session.execute(
        select(AuditChatMessage).where(AuditChatMessage.profile_id == pid).order_by(AuditChatMessage.created_at)
    )).scalars().all()
    assert [r.role for r in rows] == ["user", "assistant"]


# ── Task 10 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_history_and_clear(db_session, client):
    pid = str(uuid.uuid4())
    db_session.add(AuditProfile(id=pid, engagement_name="X"))
    await db_session.flush()
    db_session.add(AuditChatMessage(profile_id=pid, role="user", content="hi"))
    db_session.add(AuditChatMessage(profile_id=pid, role="assistant", content="hello"))
    await db_session.commit()

    r = await client.get(f"/api/audit-profiles/{pid}/chat/history")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]

    d = await client.delete(f"/api/audit-profiles/{pid}/chat/history")
    assert d.status_code == 200

    r2 = await client.get(f"/api/audit-profiles/{pid}/chat/history")
    assert r2.json()["messages"] == []
