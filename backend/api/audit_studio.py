"""
Audit Studio API — versioning, chat, generation.
Routes nest under each profile: /api/audit-profiles/{id}/...
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete

from db.database import AsyncSessionLocal
from db.models import AuditProfile, ProfileVersion, AuditChatMessage
from core.audit_studio.versioning import (
    branch_version,
    activate_version,
    compare_versions,
)
from core.audit_studio import chat_service

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


# ── Task 9: chat ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


@router.post("/{profile_id}/chat")
async def chat(profile_id: str, req: ChatRequest):
    await _require_profile(profile_id)
    reply = await chat_service.run_chat(profile_id, req.message)
    await chat_service.persist_exchange(profile_id, req.message, reply)
    return reply


# ── Task 10: chat history ─────────────────────────────────────────

@router.get("/{profile_id}/chat/history")
async def chat_history(profile_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(AuditChatMessage)
            .where(AuditChatMessage.profile_id == profile_id)
            .order_by(AuditChatMessage.created_at)
        )).scalars().all()
    return {"messages": [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "citations": r.citations,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]}


@router.delete("/{profile_id}/chat/history")
async def chat_clear(profile_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        await s.execute(
            delete(AuditChatMessage).where(AuditChatMessage.profile_id == profile_id)
        )
        await s.commit()
    return {"status": "cleared"}
