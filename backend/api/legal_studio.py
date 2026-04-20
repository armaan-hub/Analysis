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
from db.models import Conversation, Message, ResearchJob, Document
from core.chat.auditor_agent import run_audit
from core.research.orchestrator import run_deep_research
from core.research.event_bus import create_channel, get_channel, remove_channel
from core.llm_manager import get_llm_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/legal-studio", tags=["Legal Studio"])


class AuditRequest(BaseModel):
    document_ids: list[str]
    entity_name: str = ""
    period: str = ""
    format: str = "standard"   # standard | big4 | legal_brief | compliance
    scope: str = "Full financial audit"


class AuditResponse(BaseModel):
    risk_flags: list[dict]
    anomalies: list[dict]
    compliance_gaps: list[dict]
    summary: str


@router.post("/auditor", response_model=AuditResponse)
async def auditor(req: AuditRequest):
    """Run audit analysis on selected documents."""
    result = await run_audit(
        req.document_ids,
        entity_name=req.entity_name,
        period=req.period,
        format=req.format,
        scope=req.scope,
    )
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


# ── Notebook Source Persist + Delete ──────────────────────────────

from sqlalchemy import select, update
from sqlalchemy import delete as sa_delete


async def extract_entity_name(source_ids: list[str], db: AsyncSession) -> str | None:
    """Run a quick LLM extraction on the first available source doc.

    Returns the extracted entity name, or None if extraction fails or
    the result is ambiguous. Only uses the first source document to avoid
    multi-entity confusion.
    """
    if not source_ids:
        return None

    # Use only the first document to avoid multi-entity confusion
    result = await db.execute(
        select(Document).where(Document.id == source_ids[0])
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    # Use summary if available (cheaper than re-reading full doc)
    snippet = doc.summary or ""
    if not snippet and doc.metadata_json:
        meta = doc.metadata_json if isinstance(doc.metadata_json, dict) else {}
        snippet = meta.get("structured_text", "")[:1000]

    if not snippet:
        return None

    try:
        llm = get_llm_provider()
        resp = await llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract the primary company or entity name from this document text. "
                        "Respond with ONLY the entity name — nothing else. "
                        "If you cannot determine a single clear entity name, respond with: UNKNOWN"
                    ),
                },
                {"role": "user", "content": snippet[:2000]},
            ],
            temperature=0.0,
            max_tokens=50,
        )
        name = resp.content.strip()
        if name.upper() == "UNKNOWN" or not name:
            return None
        return name
    except Exception as e:
        logger.warning("Entity extraction failed for source %s: %s", source_ids[0] if source_ids else 'unknown', e)
        return None


class SaveSourcesRequest(BaseModel):
    conversation_id: str
    source_ids: list[str]


@router.post("/save-sources")
async def save_checked_sources(req: SaveSourcesRequest, db: AsyncSession = Depends(get_db)):
    """Persist which source document IDs are checked for a notebook."""
    await db.execute(
        update(Conversation)
        .where(Conversation.id == req.conversation_id)
        .values(checked_source_ids=req.source_ids)
    )
    await db.commit()
    return {"status": "ok"}


@router.get("/notebook/{conversation_id}/sources")
async def get_notebook_sources(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Get persisted checked source IDs for a notebook."""
    result = await db.execute(
        select(Conversation.checked_source_ids).where(Conversation.id == conversation_id)
    )
    row = result.scalar_one_or_none()
    return {"source_ids": row or []}


@router.delete("/notebook/{conversation_id}")
async def delete_notebook(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a notebook (conversation) and all its messages."""
    conv = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv_obj = conv.scalar_one_or_none()
    if not conv_obj:
        raise HTTPException(status_code=404, detail="Notebook not found")

    await db.execute(sa_delete(Message).where(Message.conversation_id == conversation_id))
    await db.delete(conv_obj)
    await db.commit()
    return {"status": "deleted"}


@router.get("/notebook/{conversation_id}/entity-name")
async def get_entity_name(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Extract entity name from the conversation's saved source documents."""
    result = await db.execute(
        select(Conversation.checked_source_ids).where(Conversation.id == conversation_id)
    )
    source_ids = result.scalar_one_or_none() or []
    name = await extract_entity_name(source_ids, db)
    return {"entity_name": name}
