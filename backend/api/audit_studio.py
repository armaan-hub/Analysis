"""
Audit Studio API — versioning, chat, generation.
Routes nest under each profile: /api/audit-profiles/{id}/...
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import AuditProfile, ProfileVersion
from core.audit_studio.versioning import (
    branch_version,
    activate_version,
    compare_versions,
)

router = APIRouter(prefix="/api/audit-profiles", tags=["audit-studio"])


async def _require_profile(profile_id: str) -> AuditProfile:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(AuditProfile).where(AuditProfile.id == profile_id)
        )).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return row


# ── Task 5: list versions ─────────────────────────────────────────

@router.get("/{profile_id}/versions")
async def list_versions(profile_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(ProfileVersion)
            .where(ProfileVersion.profile_id == profile_id)
            .order_by(ProfileVersion.created_at)
        )).scalars().all()
    return {"versions": [
        {
            "id": r.id,
            "branch_name": r.branch_name,
            "is_current": r.is_current,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]}


# ── Task 6: branch ────────────────────────────────────────────────

class BranchRequest(BaseModel):
    branch_name: str


@router.post("/{profile_id}/branch")
async def branch(profile_id: str, req: BranchRequest):
    await _require_profile(profile_id)
    try:
        new_id = await branch_version(profile_id, req.branch_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"version_id": new_id}


# ── Task 7: activate ──────────────────────────────────────────────

@router.patch("/{profile_id}/versions/{version_id}/activate")
async def activate(profile_id: str, version_id: str):
    await _require_profile(profile_id)
    try:
        await activate_version(profile_id, version_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok"}


# ── Task 8: compare ───────────────────────────────────────────────

@router.get("/{profile_id}/versions/{v1_id}/compare/{v2_id}")
async def compare(profile_id: str, v1_id: str, v2_id: str):
    await _require_profile(profile_id)
    try:
        return await compare_versions(profile_id, v1_id, v2_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
