"""
Deep Research API — Hybrid pipeline for comprehensive research queries.

Simple path:  RAG + web → single synthesized response (streaming)
Complex path: decompose → parallel retrieval → synthesis → report (streaming)
"""

import asyncio
import inspect
import json
import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings, compute_llm_params
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine, _normalize_chunk
from core.web_search import search_web

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deep-research", tags=["Deep Research"])

_COMPLEX_KEYWORDS = {
    "compare", "analyze", "analyse", "evaluate", "comprehensive",
    "full report", "thesis", "detailed analysis", "in-depth",
}
_COMPLEX_LAW_REFS = {"federal", "decree", "article", "law no", "regulation"}


class DeepResearchRequest(BaseModel):
    query: str
    selected_doc_ids: Optional[list[str]] = None
    provider: Optional[str] = None


def _is_complex_query(query: str) -> bool:
    """Return True if query requires multi-step decomposition."""
    lower = query.lower()
    if any(kw in lower for kw in _COMPLEX_KEYWORDS):
        return True
    if len(query) > 200 and any(ref in lower for ref in _COMPLEX_LAW_REFS):
        return True
    return False


async def _decompose_query(query: str, provider: Optional[str] = None) -> list[str]:
    """Ask LLM to break query into 3-6 sub-questions. Falls back to [query] on error."""
    llm = get_llm_provider(provider, mode="fast")
    prompt = (
        "Break this research question into 3-6 specific sub-questions that together would "
        "comprehensively answer it. Return ONLY a JSON array of strings, no other text.\n\n"
        f"Question: {query}"
    )
    try:
        resp = await llm.chat([{"role": "user", "content": prompt}], max_tokens=400, temperature=0.2)
        raw_text = getattr(resp, "text", None) or getattr(resp, "content", "")
        raw_text = str(raw_text).strip()
        sub_questions = json.loads(raw_text)
        if isinstance(sub_questions, list) and sub_questions:
            return [str(sq) for sq in sub_questions[:6] if str(sq).strip()]
    except Exception as e:
        logger.warning("Query decomposition failed (%s) — using original query", e)
    return [query]


async def _retrieve_for_subquestion(
    sub_q: str,
    top_k: int = 10,
    doc_filter: Optional[dict] = None,
) -> tuple[list[dict], list[dict]]:
    """Parallel RAG + web retrieval for a single sub-question."""
    rag_task = asyncio.create_task(
        rag_engine.search(sub_q, top_k=top_k, filter=doc_filter, min_score=settings.rag_min_score)
    )
    web_task = asyncio.create_task(
        asyncio.wait_for(search_web(sub_q, max_results=5), timeout=30.0)
    )
    rag_raw, web_results = await asyncio.gather(rag_task, web_task, return_exceptions=True)
    if isinstance(rag_raw, Exception):
        logger.warning("RAG retrieval failed for sub-question %r: %s", sub_q[:80], rag_raw)
    if isinstance(web_results, Exception):
        logger.warning("Web retrieval failed for sub-question %r: %s", sub_q[:80], web_results)
    rag_chunks = [_normalize_chunk(r) for r in (rag_raw or [])] if not isinstance(rag_raw, Exception) else []
    web_items = web_results if not isinstance(web_results, Exception) else []
    return rag_chunks, web_items or []


def _build_research_context(rag_chunks: list[dict], web_items: list[dict]) -> str:
    """Format RAG + web results into a context block for the LLM."""
    parts = []
    if rag_chunks:
        parts.append("## Document Context")
        for c in rag_chunks:
            src = c.get("source_file", "unknown")
            pg = c.get("page", "?")
            parts.append(f"[{src}, p.{pg}]\n{c.get('text', '')[:500]}")
    if web_items:
        parts.append("## Web Research")
        for w in web_items:
            url = w.get("href") or w.get("url", "")
            title = w.get("title", url)
            body = w.get("body", "")[:400]
            parts.append(f"[{title}]({url})\n{body}")
    return "\n\n".join(parts)


async def _iter_stream_chunks(llm, messages: list[dict], temperature: float, max_tokens: int):
    stream = llm.chat_stream(messages, temperature=temperature, max_tokens=max_tokens)
    if inspect.isawaitable(stream):
        stream = await stream

    if hasattr(stream, "__aiter__"):
        async for chunk in stream:
            yield chunk
    else:
        for chunk in stream:
            yield chunk


_SYNTHESIS_SYSTEM = (
    "You are a thorough research analyst specializing in UAE law and accounting regulations. "
    "Synthesise the provided document excerpts and web search results into a comprehensive, "
    "well-structured answer. Use Markdown with ## headings and bullet points.\n"
    "When citing documents use: 📄 [filename] (page N)\n"
    "When citing web sources use markdown hyperlinks: [Title](url)\n"
    "NEVER invent URLs. Only use URLs explicitly provided in the web results."
)


@router.post("")
async def deep_research_stream(req: DeepResearchRequest):
    """Hybrid deep research SSE endpoint."""
    model_name = getattr(settings, "nvidia_model", "")
    llm_params = compute_llm_params(
        model_name=model_name,
        mode="deep_research",
        provider=req.provider or settings.llm_provider,
    )
    doc_filter = None
    if req.selected_doc_ids:
        doc_filter = {
            "$and": [
                {"doc_id": {"$in": req.selected_doc_ids}},
                {"category": {"$in": ["law", "finance"]}},
            ]
        }

    async def generate():
        try:
            is_complex = _is_complex_query(req.query)

            if not is_complex:
                yield f"data: {json.dumps({'type': 'step', 'text': 'Searching knowledge base…'})}\n\n"
                rag_raw = await rag_engine.search(
                    req.query,
                    top_k=llm_params["top_k"],
                    filter=doc_filter or {"category": {"$in": ["law", "finance"]}},
                    min_score=settings.rag_min_score,
                )
                rag_chunks = [_normalize_chunk(r) for r in rag_raw]

                yield f"data: {json.dumps({'type': 'step', 'text': 'Running web research…'})}\n\n"
                try:
                    web_items = await asyncio.wait_for(search_web(req.query, max_results=10), timeout=60.0)
                except asyncio.TimeoutError:
                    logger.warning("Web search timed out for query: %r", req.query[:80])
                    web_items = []

                yield f"data: {json.dumps({'type': 'step', 'text': 'Synthesising answer…'})}\n\n"
                context = _build_research_context(rag_chunks, web_items)
                llm = get_llm_provider(req.provider, mode="deep_research")
                messages = [
                    {"role": "system", "content": _SYNTHESIS_SYSTEM},
                    {"role": "user", "content": context + f"\n\n## Question\n{req.query}"},
                ]
                answer_parts = []
                async for chunk in _iter_stream_chunks(
                    llm,
                    messages,
                    temperature=llm_params["temperature"],
                    max_tokens=llm_params["max_tokens"],
                ):
                    answer_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                full = "".join(answer_parts)
                doc_sources = [{"filename": c.get("source_file"), "page": c.get("page")} for c in rag_chunks]
                web_sources = [{"title": w.get("title", ""), "url": w.get("href") or w.get("url", "")} for w in (web_items or [])]
                yield f"data: {json.dumps({'type': 'answer', 'content': full, 'sources': doc_sources, 'web_sources': web_sources})}\n\n"

            else:
                yield f"data: {json.dumps({'type': 'step', 'text': 'Decomposing research question…'})}\n\n"
                sub_questions = await _decompose_query(req.query, req.provider)
                yield f"data: {json.dumps({'type': 'step', 'text': f'Running {len(sub_questions)} parallel retrievals…'})}\n\n"

                retrieval_tasks = [_retrieve_for_subquestion(sq, top_k=10, doc_filter=doc_filter) for sq in sub_questions]
                all_results = await asyncio.gather(*retrieval_tasks)

                all_rag, all_web = [], []
                for rag_c, web_i in all_results:
                    all_rag.extend(rag_c)
                    all_web.extend(web_i)

                seen_ids: set = set()
                deduped_rag = []
                for c in all_rag:
                    cid = c.get("chunk_id")
                    dedup_key = cid if cid is not None else f"{c.get('source_file')}:{c.get('page')}:{c.get('text', '')[:50]}"
                    if dedup_key not in seen_ids:
                        seen_ids.add(dedup_key)
                        deduped_rag.append(c)

                yield f"data: {json.dumps({'type': 'step', 'text': 'Synthesising findings…'})}\n\n"
                context = _build_research_context(deduped_rag, all_web)
                llm = get_llm_provider(req.provider, mode="deep_research")
                synthesis_prompt = (
                    "Based on the research context below, write a comprehensive report answering:\n"
                    f"{req.query}\n\n"
                    "Structure: Executive Summary → Key Findings → Detailed Analysis → Sources → Conclusion\n\n"
                    f"{context}"
                )
                messages = [
                    {"role": "system", "content": _SYNTHESIS_SYSTEM},
                    {"role": "user", "content": synthesis_prompt},
                ]
                answer_parts = []
                async for chunk in _iter_stream_chunks(
                    llm,
                    messages,
                    temperature=llm_params["temperature"],
                    max_tokens=llm_params["max_tokens"],
                ):
                    answer_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                full = "".join(answer_parts)
                doc_sources = [{"filename": c.get("source_file"), "page": c.get("page")} for c in deduped_rag[:20]]
                web_sources = [{"title": w.get("title", ""), "url": w.get("href") or w.get("url", "")} for w in all_web[:10]]
                yield f"data: {json.dumps({'type': 'answer', 'content': full, 'sources': doc_sources, 'web_sources': web_sources})}\n\n"

        except Exception as e:
            logger.error("Deep research error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
