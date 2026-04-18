import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from db.database import AsyncSessionLocal
from db.models import AuditProfile, GeneratedOutput
from sqlalchemy import select
from main import app


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


@pytest.mark.asyncio
async def test_generate_creates_pending_output_and_returns_job_id():
    pid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=pid, engagement_name="X"))
        await s.commit()

    with patch("core.audit_studio.generation_service._schedule", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/audit-profiles/{pid}/generate/audit_report",
                json={"template_id": None, "options": {}},
            )
            assert r.status_code == 200
            body = r.json()
            assert "job_id" in body

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(GeneratedOutput).where(GeneratedOutput.profile_id == pid)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].output_type == "audit_report"
        assert rows[0].status == "pending"


@pytest.mark.asyncio
async def test_list_outputs_returns_all_for_profile():
    pid = str(uuid.uuid4())
    o1 = str(uuid.uuid4())
    o2 = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=pid, engagement_name="X"))
        await s.flush()
        s.add(GeneratedOutput(id=o1, profile_id=pid, output_type="audit_report", status="ready",
                              output_path="storage/generated/o1.pdf"))
        s.add(GeneratedOutput(id=o2, profile_id=pid, output_type="profit_loss", status="pending"))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/audit-profiles/{pid}/outputs")
        assert r.status_code == 200
        types = {o["output_type"] for o in r.json()["outputs"]}
        assert types == {"audit_report", "profit_loss"}


@pytest.mark.asyncio
async def test_download_returns_file_bytes(tmp_path):
    pid = str(uuid.uuid4())
    dl1 = str(uuid.uuid4())
    fpath = tmp_path / "sample.pdf"
    fpath.write_bytes(b"%PDF-1.4 test")
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=pid, engagement_name="X"))
        await s.flush()
        s.add(GeneratedOutput(id=dl1, profile_id=pid, output_type="audit_report",
                              status="ready", output_path=str(fpath)))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/audit-profiles/{pid}/outputs/{dl1}/download")
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_dispatch_routes_each_output_type():
    from core.audit_studio.generation_service import _dispatch, SUPPORTED_TYPES

    pid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id=pid, engagement_name="X"))
        await s.flush()
        for t in SUPPORTED_TYPES:
            s.add(GeneratedOutput(id=f"d-{t}-{pid[:8]}", profile_id=pid, output_type=t, status="processing"))
        await s.commit()

    with patch("core.audit_studio.generation_service._generate_by_type",
               new=AsyncMock(return_value="storage/generated/fake.pdf")) as m:
        for t in SUPPORTED_TYPES:
            path = await _dispatch(f"d-{t}-{pid[:8]}")
            assert path.endswith(".pdf")
        assert m.await_count == len(SUPPORTED_TYPES)
