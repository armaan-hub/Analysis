"""Legal Studio API — auditor, sessions, and research endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
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
