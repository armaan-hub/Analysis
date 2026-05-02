"""Test that ResearchJob model can be created and queried."""
import pytest
from db.models import ResearchJob


@pytest.mark.asyncio
async def test_create_research_job(db_session):
    job = ResearchJob(query="UAE VAT refund overview")
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    assert job.id is not None
    assert job.query == "UAE VAT refund overview"
    assert job.status == "running"
    assert job.started_at is not None
