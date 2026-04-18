"""
End-to-end flow per spec §10:
  create → upload → build → chat → apply format → generate → download
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_finance_studio_end_to_end(tmp_path):
    fake_pdf = tmp_path / "audit.pdf"

    async def fake_generate(profile_id, output_type, template_id, job_id):
        fake_pdf.write_bytes(b"%PDF-1.4 fake")
        return str(fake_pdf)

    with patch("core.audit_studio.generation_service._generate_by_type",
               new=AsyncMock(side_effect=fake_generate)), \
         patch("core.audit_studio.chat_service.run_chat",
               new=AsyncMock(return_value={"content": "No risks flagged.", "citations": []})):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            # 1. create profile
            r = await c.post("/api/audit-profiles", json={"engagement_name": "Integration Co"})
            assert r.status_code in (200, 201)
            pid = r.json()["id"]

            # 2. upload source doc (trial balance)
            files = {"file": ("tb.csv", b"acct,amount\n4001,10000\n", "text/csv")}
            r = await c.post(f"/api/audit-profiles/{pid}/upload-source",
                             data={"document_type": "trial_balance"}, files=files)
            assert r.status_code == 200

            # 3. build profile
            r = await c.post(f"/api/audit-profiles/{pid}/build-profile")
            assert r.status_code == 200

            # 4. chat
            r = await c.post(f"/api/audit-profiles/{pid}/chat", json={"message": "Flag anomalies"})
            assert r.status_code == 200
            assert "No risks" in r.json()["content"]

            # 5. generate (template_id is frontend-only; pass directly)
            template_id = "ifrs-standard-a4"
            r = await c.post(
                f"/api/audit-profiles/{pid}/generate/audit_report",
                json={"template_id": template_id, "options": {}},
            )
            assert r.status_code == 200
            job_id = r.json()["job_id"]

            # Wait for background task (immediate because _generate_by_type is mocked)
            await asyncio.sleep(0.1)

            # 6. download
            r = await c.get(f"/api/audit-profiles/{pid}/outputs/{job_id}/download")
            assert r.status_code == 200
            assert r.content.startswith(b"%PDF")
