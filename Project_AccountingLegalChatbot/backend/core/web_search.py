"""
Web search fallback — used when RAG has no relevant results.
Uses DuckDuckGo (no API key required).
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web for query. Returns list of dicts with keys:
    title, href, body (snippet text).
    Returns [] on any error — caller must handle gracefully.
    """
    try:
        from duckduckgo_search import DDGS

        def _sync_search() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, _sync_search)
        return results or []
    except Exception as exc:
        logger.warning(f"Web search failed for query '{query[:60]}': {exc}")
        return []


def build_web_context(results: list[dict]) -> str:
    """
    Format web search results into a context block for the LLM system prompt.
    """
    if not results:
        return ""
    lines = ["The following information was found on the web:\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("href", "")
        body = r.get("body", "")
        lines.append(f"[Source {i}] {title}\nURL: {url}\n{body}\n")
    return "\n".join(lines)


async def generate_sub_queries(query: str, max_queries: int = 6) -> list[str]:
    """Use LLM to generate diverse sub-queries from the original question."""
    try:
        from core.llm_manager import get_llm_provider
        llm = get_llm_provider()
        resp = await llm.chat(
            [
                {
                    "role": "user",
                    "content": (
                        f"Generate {max_queries} distinct search queries to comprehensively research this topic: "
                        f'"{query}"\n\n'
                        "Return ONLY a JSON array of strings. No explanation. "
                        "Each query should cover a different angle: regulations, examples, exceptions, "
                        "recent updates, official guidance, penalties/compliance."
                    ),
                }
            ],
            temperature=0.3,
            max_tokens=300,
        )
        import json as _json, re as _re
        raw = resp.content.strip()
        raw = _re.sub(r"^```(?:json)?\s*", "", raw, flags=_re.MULTILINE)
        raw = _re.sub(r"\s*```\s*$", "", raw, flags=_re.MULTILINE)
        match = _re.search(r"\[.*\]", raw, _re.DOTALL)
        if match:
            queries = _json.loads(match.group(0))
            return [str(q) for q in queries[:max_queries] if q]
    except Exception as exc:
        logger.warning(f"Sub-query generation failed: {exc}")
    return [query, f"{query} UAE regulations", f"{query} FTA guidance"]


async def deep_search(query: str, max_queries: int = 6) -> list[dict]:
    """Extended multi-query web search. Generates sub-queries, runs in parallel, deduplicates."""
    sub_queries = await generate_sub_queries(query, max_queries)
    import asyncio as _asyncio
    tasks = [search_web(q, max_results=5) for q in sub_queries]
    all_results_nested = await _asyncio.gather(*tasks, return_exceptions=True)

    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for batch in all_results_nested:
        if isinstance(batch, Exception):
            continue
        for result in batch:
            url = result.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

    logger.info(f"Deep search: {len(sub_queries)} queries → {len(unique_results)} unique results")
    return unique_results[:15]
