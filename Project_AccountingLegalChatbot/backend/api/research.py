import json
from collections.abc import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.research.deep_research_service import run_deep_research
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine
from core.document_processor import ingest_text

router = APIRouter(prefix="/api/chat", tags=["research"])


class _LLMAdapter:
    """Adapts BaseLLMProvider to the interface expected by deep_research_service."""

    def __init__(self, provider):
        self._provider = provider

    async def complete(self, prompt: str, max_tokens: int = 150, temperature: float = 0.1) -> str:
        resp = await self._provider.chat(
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.content

    async def stream(self, prompt: str, max_tokens: int = 1200, temperature: float = 0.2):
        async for chunk in self._provider.chat_stream(
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk


class _RAGAdapter:
    """Adapts RAGEngine to the interface expected by deep_research_service."""

    def __init__(self, engine):
        self._engine = engine

    async def search(self, query: str, doc_ids: list[str] | None = None) -> list[dict]:
        if not doc_ids:
            return await self._engine.search(query, top_k=5)
        # RAGEngine only supports single doc_id; search each and merge
        results: list[dict] = []
        seen: set[str] = set()
        for doc_id in doc_ids[:5]:
            for r in await self._engine.search(query, top_k=3, doc_id=doc_id):
                key = r.get("text", "")[:80]
                if key not in seen:
                    seen.add(key)
                    results.append(r)
        return results[:10]



class DeepResearchRequest(BaseModel):
    conversation_id: str
    query: str
    selected_doc_ids: list[str] = []


async def _sse_stream(req: DeepResearchRequest) -> AsyncGenerator[str, None]:
    llm = _LLMAdapter(get_llm_provider())
    rag = _RAGAdapter(rag_engine)
    async for event in run_deep_research(
        query=req.query,
        selected_doc_ids=req.selected_doc_ids,
        llm=llm,
        rag=rag,
        ingest=ingest_text,
    ):
        yield f"data: {json.dumps(event)}\n\n"


@router.post("/deep-research")
async def deep_research(req: DeepResearchRequest) -> StreamingResponse:
    return StreamingResponse(_sse_stream(req), media_type="text/event-stream")
