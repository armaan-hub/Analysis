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
