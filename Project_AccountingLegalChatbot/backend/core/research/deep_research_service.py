import asyncio
from collections.abc import AsyncGenerator
from core.research.brave_search import brave_search
from core.research.query_decomposer import decompose_query


def _build_synthesis_prompt(question: str, web: list[dict], doc_chunks: list[dict]) -> str:
    web_block = "\n".join(
        f"- [{r.get('title')}]({r.get('url')}): {r.get('content','')[:400]}"
        for r in web
    ) or "(no web results)"
    doc_block = "\n".join(
        f"- {c.get('source')} p.{c.get('page','?')}: {c.get('text','')[:400]}"
        for c in doc_chunks
    ) or "(no document chunks)"
    return (
        "You are a research assistant. Answer the user's question using ONLY the "
        "provided web results and document chunks. Cite sources inline. If the "
        "information is insufficient, say so explicitly.\n\n"
        f"Question: {question}\n\nWeb results:\n{web_block}\n\nDocument chunks:\n{doc_block}\n\nAnswer:"
    )


async def run_deep_research(
    *,
    query: str,
    selected_doc_ids: list[str] | None,
    llm,
    rag,
    ingest,
) -> AsyncGenerator[dict, None]:
    """Yield SSE-ready event dicts for a deep research run."""
    error: str | None = None
    answer_emitted = False
    try:
        yield {"type": "step", "text": "Analyzing query..."}

        sub_queries = await decompose_query(query, llm)
        yield {"type": "step", "text": f"Generated {len(sub_queries)} search queries"}

        for q in sub_queries:
            yield {"type": "step", "text": f"Searching: {q}"}

        search_results = await asyncio.gather(
            *[brave_search(q, max_results=5) for q in sub_queries],
            return_exceptions=True,
        )
        web: list[dict] = []
        for r in search_results:
            if isinstance(r, Exception):
                continue
            web.extend(r)

        yield {"type": "step", "text": f"Found {len(web)} web results across {len(sub_queries)} searches"}

        yield {"type": "step", "text": "Searching your documents..."}
        doc_chunks = await rag.search(query, doc_ids=selected_doc_ids) if rag else []
        yield {"type": "step", "text": f"Found {len(doc_chunks)} relevant document chunks"}

        # Persist web content to RAG for future reuse
        for r in web:
            try:
                await ingest(
                    text=f"{r.get('title','')}\n\n{r.get('content','')}",
                    source=r.get("url"),
                    source_type="research",
                )
            except Exception:
                pass

        yield {"type": "step", "text": "Synthesizing answer..."}
        prompt = _build_synthesis_prompt(query, web, doc_chunks)

        answer_parts: list[str] = []
        async for piece in llm.stream(prompt, max_tokens=1200, temperature=0.2):
            answer_parts.append(piece)
        answer = "".join(answer_parts)

        yield {
            "type": "answer",
            "content": answer,
            "sources": [
                {"filename": c.get("source"), "page": c.get("page")} for c in doc_chunks
            ],
            "web_sources": [
                {"title": r.get("title"), "url": r.get("url")} for r in web
            ],
        }
        answer_emitted = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        yield {"type": "step", "text": f"Error: {error}"}
    finally:
        done_payload: dict = {"type": "done"}
        if error:
            done_payload["error"] = error
        if not answer_emitted:
            done_payload["partial"] = True
        yield done_payload
