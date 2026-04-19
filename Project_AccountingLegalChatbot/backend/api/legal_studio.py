"""Legal Studio API — auditor, sessions, and research endpoints."""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Conversation, Message, ResearchJob
from core.chat.auditor_agent import run_audit
from core.research.orchestrator import run_deep_research
from core.research.event_bus import create_channel, get_channel, remove_channel

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


# ── Deep Research ─────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None


class ResearchJobResponse(BaseModel):
    job_id: str
    status: str


@router.post("/research", response_model=ResearchJobResponse)
async def start_research(
    req: ResearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a deep research job."""
    job = ResearchJob(query=req.query, thread_id=req.thread_id)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    create_channel(job.id)
    background_tasks.add_task(run_deep_research, job.id, req.query)

    return ResearchJobResponse(job_id=job.id, status="running")


@router.get("/research/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get research job status and result."""
    job = await db.get(ResearchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "query": job.query,
        "plan": job.plan_json,
        "result": job.result_json,
        "started_at": str(job.started_at) if job.started_at else None,
        "completed_at": str(job.completed_at) if job.completed_at else None,
    }


@router.get("/research/{job_id}/stream")
async def stream_research(job_id: str):
    """SSE stream of research progress events."""
    channel = get_channel(job_id)
    if not channel:
        raise HTTPException(status_code=404, detail="No active channel for this job")

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(channel.get(), timeout=60.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("phase") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            remove_channel(job_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
