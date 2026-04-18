import uuid
import pytest
from db.database import AsyncSessionLocal
from db.models import AuditProfile, GeneratedOutput
from sqlalchemy import select


@pytest.mark.asyncio
async def test_generated_output_persists():
    profile_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=profile_id, engagement_name="Test Co"))
        await s.flush()
        o = GeneratedOutput(
            profile_id=profile_id,
            output_type="audit_report",
            status="pending",
        )
        s.add(o)
        await s.commit()
        row = (await s.execute(select(GeneratedOutput).where(GeneratedOutput.profile_id == profile_id))).scalar_one()
        assert row.output_type == "audit_report"
        assert row.status == "pending"
