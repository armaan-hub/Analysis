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


GENERIC_PATTERNS = [
    "what aspect", "general or detailed", "prior knowledge",
    "interested in learning", "specific topic", "what type of information",
    "what would you like", "are you looking for", "which area",
    "how detailed should", "what do you want to know",
]


def _is_generic(q: str) -> bool:
    if not q or not q.strip():
        return True
    ql = q.lower()
    return any(p in ql for p in GENERIC_PATTERNS)


async def _plan(query: str) -> list[str]:
    """Generate 3-5 factual, independently-searchable sub-questions from query."""
    system = (
        "You are a research planner specializing in UAE legal and financial topics. "
        "Your job is to decompose a research query into 3-5 SPECIFIC, FACTUAL sub-questions "
        "that can be answered by searching documents and the web.\n\n"
        "RULES:\n"
        "- Sub-questions must be about the TOPIC, not about what the user wants\n"
        "- Never ask clarifying questions like 'what aspect?' or 'general or detailed?'\n"
        "- Each sub-question must be independently searchable\n\n"
        "EXAMPLE INPUT: 'Peppol e-invoicing buyer ID for third party shipment UAE'\n"
        "EXAMPLE OUTPUT: {\"sub_questions\": [\n"
        "  \"Who must register for Peppol participant ID in UAE e-invoicing?\",\n"
        "  \"What is the Peppol BIS billing standard for third-party shipment scenarios?\",\n"
        "  \"UAE FTA e-invoicing requirements for buyer identification in cross-border transactions\"\n"
        "]}\n\n"
        "Respond ONLY with valid JSON: {\"sub_questions\": [\"q1\", \"q2\", ...]}"
    )
    raw = await _llm(system, query)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            cleaned = "\n".join(inner)
        data = json.loads(cleaned.strip())
        sub_questions = list(data.get("sub_questions", [query]))[:5]
        if not sub_questions:
            return [query]
    except Exception as e:
        logger.warning("_plan() failed to parse LLM response: %s — falling back to original query", e)
        return [query]

    # Filter out generic questions instead of rejecting all
    filtered = [q for q in sub_questions if not _is_generic(q)]
    if not filtered:
        logger.warning("_plan() returned all generic questions — falling back to original query")
        return [query]
    return filtered


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

    return "\n".join(parts) if parts else ""


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

        # Phase 2: Gather (concurrent)
        await emit(job_id, {"phase": "gathering", "message": "Searching sources..."})

        async def _gather_with_progress(i: int, sq: str) -> tuple[str, str]:
            await emit(job_id, {
                "phase": "gathering",
                "progress": i + 1,
                "total": len(sub_questions),
                "message": f"Researching: {sq[:60]}...",
            })
            return sq, await _gather_one(sq)

        results = await asyncio.gather(
            *[_gather_with_progress(i, sq) for i, sq in enumerate(sub_questions)],
            return_exceptions=True,
        )
        gathered: dict[str, str] = {}
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Gather task failed: %s", r)
            elif r[1]:  # skip empty results
                gathered[r[0]] = r[1]

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

        # Save report as a virtual document
        try:
            await _save_as_document(job_id, query, report)
        except Exception as e:
            logger.warning("Failed to save research as document: %s", e)

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


async def _save_as_document(job_id: str, query: str, report: str) -> None:
    """Save the research report as a virtual document in the DB."""
    from db.models import Document

    short_title = query[:80].replace(" ", "_")

    async with async_session() as session:
        doc = Document(
            filename=f"research_{job_id[:8]}.md",
            original_name=f"Research: {short_title}",
            file_type="md",
            file_size=len(report.encode()),
            chunk_count=0,
            status="indexed",
            summary=report[:300],
            key_terms=[],
            source="research",
        )
        session.add(doc)
        await session.commit()
