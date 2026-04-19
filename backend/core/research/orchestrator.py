"""Deep research orchestrator — plan → gather → synthesize → done."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from db.database import async_session
from db.models import ResearchJob
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine
from core.web_search import search_web, build_web_context
from core.research.event_bus import emit

logger = logging.getLogger(__name__)


async def _llm(system: str, user: str, temperature: float = 0.3, max_tokens: int = 1500) -> str:
    llm = get_llm_provider()
    resp = await llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.content


async def _plan(query: str) -> list[str]:
    """Generate 3-5 sub-questions from the user query."""
    system = (
        "Break down the user's research query into 3-5 focused sub-questions. "
        'Respond ONLY with JSON: {"sub_questions": ["q1", "q2", ...]}'
    )
    raw = await _llm(system, query)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        data = json.loads(cleaned.strip())
        return list(data.get("sub_questions", [query]))[:5]
    except Exception:
        return [query]


async def _gather_one(sub_q: str) -> str:
    """Gather from RAG + web for a single sub-question."""
    parts = []
    try:
        rag_results = await rag_engine.search(sub_q, top_k=3)
        for r in rag_results:
            parts.append(r.get("text", "")[:500])
    except Exception as e:
        logger.warning("RAG search failed for '%s': %s", sub_q, e)

    try:
        web_results = await search_web(sub_q)
        web_ctx = build_web_context(web_results)
        if web_ctx:
            parts.append(web_ctx[:1000])
    except Exception as e:
        logger.warning("Web search failed for '%s': %s", sub_q, e)

    return "\n".join(parts) if parts else f"No results found for: {sub_q}"


async def _synthesize(query: str, gathered: dict[str, str]) -> str:
    """Synthesize all gathered info into a final report."""
    context = "\n\n".join(
        f"## {q}\n{text}" for q, text in gathered.items()
    )
    system = (
        "You are a UAE legal and financial research analyst. "
        "Synthesize the following research findings into a comprehensive, well-structured report. "
        "Use headings and bullet points. Be thorough and cite specific details."
    )
    user = f"Original query: {query}\n\nResearch findings:\n{context}"
    return await _llm(system, user, temperature=0.3, max_tokens=3000)


async def run_deep_research(job_id: str, query: str) -> None:
    """Run the full deep research pipeline. Updates DB and emits events."""
    try:
        # Phase 1: Plan
        await emit(job_id, {"phase": "planning", "message": "Breaking down your query..."})
        sub_questions = await _plan(query)

        async with async_session() as session:
            job = await session.get(ResearchJob, job_id)
            if job:
                job.plan_json = {"sub_questions": sub_questions}
                await session.commit()

        await emit(job_id, {
            "phase": "planned",
            "sub_questions": sub_questions,
            "message": f"Research plan: {len(sub_questions)} sub-questions",
        })

        # Phase 2: Gather
        await emit(job_id, {"phase": "gathering", "message": "Searching sources..."})
        gathered: dict[str, str] = {}
        for i, sq in enumerate(sub_questions):
            await emit(job_id, {
                "phase": "gathering",
                "progress": i + 1,
                "total": len(sub_questions),
                "message": f"Researching: {sq[:60]}...",
            })
            gathered[sq] = await _gather_one(sq)

        # Phase 3: Synthesize
        await emit(job_id, {"phase": "synthesizing", "message": "Writing report..."})
        report = await _synthesize(query, gathered)

        # Phase 4: Done
        async with async_session() as session:
            job = await session.get(ResearchJob, job_id)
            if job:
                job.status = "completed"
                job.result_json = {"report": report, "sources": list(gathered.keys())}
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()

        await emit(job_id, {
            "phase": "completed",
            "message": "Research complete!",
            "report": report,
        })

    except Exception as e:
        logger.exception("Deep research failed for job %s", job_id)
        async with async_session() as session:
            job = await session.get(ResearchJob, job_id)
            if job:
                job.status = "failed"
                job.result_json = {"error": str(e)}
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
        await emit(job_id, {"phase": "failed", "message": f"Research failed: {e}"})
