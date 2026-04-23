import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from core.llm_manager import get_llm_provider
from core.council.council_service import run_council

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Council"])


class CouncilRequest(BaseModel):
    question:    str        = Field(..., min_length=1, description="The user's question")
    base_answer: str        = Field(..., min_length=1, description="Initial answer to critique")
    provider:    str | None = None


@router.post("/council")
async def council_stream(req: CouncilRequest):
    """Stream a multi-expert council review via SSE."""
    try:
        llm = get_llm_provider(req.provider)
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
