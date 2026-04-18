import uuid
import pytest
from db.database import AsyncSessionLocal
from db.models import AuditProfile, ProfileVersion
from sqlalchemy import select


@pytest.mark.asyncio
async def test_profile_version_persists():
    profile_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        profile = AuditProfile(id=profile_id, engagement_name="Test Co")
        s.add(profile)
        await s.flush()
        v = ProfileVersion(
            profile_id=profile_id,
            branch_name="main",
            profile_json='{"account_mappings": []}',
            is_current=True,
        )
        s.add(v)
        await s.commit()
        row = (await s.execute(select(ProfileVersion).where(ProfileVersion.profile_id == profile_id))).scalar_one()
        assert row.branch_name == "main"
        assert row.is_current is True
