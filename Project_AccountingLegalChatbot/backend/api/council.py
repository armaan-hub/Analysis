import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from core.llm_manager import get_llm_provider
from core.council.council_service import run_council
from core.council.financial_audit_council import (
    run_financial_audit_council,
    run_financial_audit_council_stream,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Council"])


class CouncilRequest(BaseModel):
    question:    str        = Field(..., min_length=1, description="The user's question")
    base_answer: str        = Field(..., min_length=1, description="Initial answer to critique")
    provider:    str | None = None


class FinancialAuditCouncilRequest(BaseModel):
    doc1_balance_sheet:   str        = Field(default="", description="Document 1: Balance Sheet and/or Trial Balance text")
    doc2_profit_loss:     str        = Field(default="", description="Document 2: Profit & Loss Statement text")
    doc3_corporate_legal: str        = Field(default="", description="Document 3: Trade License & MOA text")
    doc4_template_notes:  str        = Field(default="", description="Document 4 / Additional template context")
    provider:             str | None = Field(default=None, description="LLM Provider override")


@router.post("/council")
async def council_stream(req: CouncilRequest):
    """Stream a multi-expert council review via SSE."""
    try:
        llm = get_llm_provider(req.provider, mode="fast")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def gen():
        try:
            async for evt in run_council(question=req.question, base_answer=req.base_answer, llm=llm):
                yield f"data: {json.dumps(evt)}\n\n"
        except Exception as exc:
            logger.exception("Unhandled error in council stream")
            yield f"data: {json.dumps({'type': 'council_error', 'error': str(exc)})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/financial-council")
@router.post("/council/financial-audit")
async def financial_audit_council_stream(req: FinancialAuditCouncilRequest):
    """
    Stream 6-subagent Financial Audit Council review via SSE:
    1. Corporate Legal Extractor (Trade License & MOA)
    2. Trial Balance Auditor (Balance Sheet 2025/2024)
    3. Profit & Loss Analyst (Performance & Margins 2025/2024)
    4. Comparative Mainland Mapper (Target Template Mapping 2025-first)
    5. Audit Report Synthesis Chair (Pristine Markdown Audit Report)
    6. Audit Math Verification Critic (Line-by-line QC & Tie-out check)
    """
    try:
        llm = get_llm_provider(req.provider, mode="analyst")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def gen():
        try:
            async for evt in run_financial_audit_council_stream(
                doc1_balance_sheet=req.doc1_balance_sheet,
                doc2_profit_loss=req.doc2_profit_loss,
                doc3_corporate_legal=req.doc3_corporate_legal,
                doc4_template_notes=req.doc4_template_notes,
                llm=llm,
            ):
                yield f"data: {json.dumps(evt)}\n\n"
        except Exception as exc:
            logger.exception("Unhandled error in financial audit council stream")
            yield f"data: {json.dumps({'type': 'audit_council_error', 'error': str(exc)})}\n\n"
            yield f"data: {json.dumps({'type': 'audit_council_done', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/financial-council/sync")
async def financial_audit_council_sync(req: FinancialAuditCouncilRequest):
    """Synchronous execution of the 6-subagent Financial Audit Council."""
    try:
        llm = get_llm_provider(req.provider, mode="analyst")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await run_financial_audit_council(
        doc1_balance_sheet=req.doc1_balance_sheet,
        doc2_profit_loss=req.doc2_profit_loss,
        doc3_corporate_legal=req.doc3_corporate_legal,
        doc4_template_notes=req.doc4_template_notes,
        llm=llm,
    )
    return result

