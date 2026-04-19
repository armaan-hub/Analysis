"""Legal Studio API — auditor, sessions, and research endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Conversation
from core.chat.auditor_agent import run_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/legal-studio", tags=["Legal Studio"])


class AuditRequest(BaseModel):
    document_ids: list[str]


class AuditResponse(BaseModel):
    risk_flags: list[dict]
    anomalies: list[dict]
    compliance_gaps: list[dict]
    summary: str


@router.post("/auditor", response_model=AuditResponse)
async def auditor(req: AuditRequest):
    """Run audit analysis on selected documents."""
    result = await run_audit(req.document_ids)
    return AuditResponse(**result)


# ── Cross-domain session ──────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    domain: str = "finance"
    context_summary: Optional[str] = None


class CreateSessionResponse(BaseModel):
    conversation_id: str
    title: str
    domain: str


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_cross_domain_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation pre-configured for a specific domain (e.g., finance handoff from legal)."""
    title = req.title or f"Legal \u2192 {req.domain.title()} handoff"
    conv = Conversation(
        title=title,
        domain=req.domain,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    # If context_summary provided, add it as a system message for continuity
    if req.context_summary:
        from db.models import Message

        msg = Message(
            conversation_id=conv.id,
            role="system",
            content=f"Context from legal session: {req.context_summary}",
        )
        db.add(msg)
        await db.commit()

    return CreateSessionResponse(
        conversation_id=conv.id,
        title=conv.title,
        domain=req.domain,
    )
