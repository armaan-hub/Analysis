import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.llm_manager import get_llm_provider
from core.council.council_service import run_council

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Council"])


class CouncilRequest(BaseModel):
    question: str
    base_answer: str
    provider: str | None = None


@router.post("/council")
async def council_stream(req: CouncilRequest):
    llm = get_llm_provider(req.provider)

    async def gen():
        async for evt in run_council(question=req.question, base_answer=req.base_answer, llm=llm):
            yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
