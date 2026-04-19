"""Test that ResearchJob model can be created and queried."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import engine, Base
from db.models import ResearchJob


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_create_research_job():
    from db.database import async_session
    async with async_session() as session:
        job = ResearchJob(query="UAE VAT refund overview")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        assert job.id is not None
        assert job.query == "UAE VAT refund overview"
        assert job.status == "running"
        assert job.started_at is not None
