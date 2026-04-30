"""
Web search fallback — used when RAG has no relevant results.
Uses DuckDuckGo HTML endpoint via native async httpx (no primp, fully cancellable).
"""
import asyncio
import logging
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DDG_HTML_URL = "https://html.duckduckgo.com/html/"
_DDG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

_SUSPICIOUS_URL_PATTERNS = [
    r"bit\.ly|tinyurl|goo\.gl|short\.link",  # URL shorteners
    r"pinterest|instagram|facebook|twitter\.com(?!/)",  # Social media
    r"youtube|reddit|medium",  # Content platforms
    r"wikipedia(?!\.org)",  # Wikipedia forks
    r"\.tk|\.ml|\.ga|\.cf$",  # Free domains
    r"404|error|not.*found",  # Error pages
]


async def _is_valid_url(url: str, timeout: float = 3.0) -> bool:
    """
    Check if URL is reachable and not a redirect/error page.
    Returns False for suspicious patterns, 404s, redirects to error pages.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False

    # Check for suspicious patterns
    for pattern in _SUSPICIOUS_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return False

    # Verify URL is reachable
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=3.0, read=timeout)) as client:
            resp = await client.head(url, follow_redirects=False)
            # Accept 2xx, 3xx (redirects are normal), but reject 4xx, 5xx
            return 200 <= resp.status_code < 400
    except (httpx.HTTPError, asyncio.TimeoutError):
        return False
    except Exception as e:
        logger.debug(f"URL validation error for {url}: {e}")
        return False


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web for query using DuckDuckGo HTML endpoint.
    Validates URLs — rejects suspicious patterns and unreachable links.
    Returns list of dicts with keys: title, href, body.
    Returns [] on any error — caller must handle gracefully.
    Fully async — no thread executor, no primp, cancellable.
    """
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=8.0, read=12.0, write=8.0, pool=5.0),
            follow_redirects=True,
        ) as client:
            resp = await client.post(_DDG_HTML_URL, data={"q": query}, headers=_DDG_HEADERS)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            candidates: list[dict] = []
            for div in soup.find_all("div", class_="result"):
                link_tag = div.find("a", class_="result__a")
                snippet_div = div.find("div", class_="result__snippet")
                if not link_tag:
                    continue
                raw_href = link_tag.get("href", "")
                # DDG wraps URLs in redirect links: /l/?uddg=<encoded_url>&rut=...
                if "uddg=" in raw_href:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                    href = qs.get("uddg", [raw_href])[0]
                else:
                    href = raw_href
                title = link_tag.get_text(strip=True)
                body = snippet_div.get_text(strip=True) if snippet_div else ""
                if href and title:
                    candidates.append({"title": title, "href": href, "body": body})

        # Validate URLs in parallel; keep only valid ones
        validation_tasks = [_is_valid_url(c["href"]) for c in candidates]
        validities = await asyncio.gather(*validation_tasks, return_exceptions=True)

        results: list[dict] = []
        for candidate, is_valid in zip(candidates, validities):
            if is_valid is True:
                results.append(candidate)
                if len(results) >= max_results:
                    break

        if len(results) < len(candidates):
            logger.debug(
                f"Web search: {len(candidates)} results found, "
                f"{len(results)} passed URL validation for query '{query[:60]}'"
            )
        return results
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
        # Use fast model — query generation needs speed, not depth
        llm = get_llm_provider(mode="fast")
        resp = await asyncio.wait_for(
            llm.chat(
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
            ),
            timeout=30.0,
        )
        import json as _json, re as _re
        raw = resp.content.strip()
        raw = _re.sub(r"^```(?:json)?\s*", "", raw, flags=_re.MULTILINE)
        raw = _re.sub(r"\s*```\s*$", "", raw, flags=_re.MULTILINE)
        match = _re.search(r"\[.*\]", raw, _re.DOTALL)
        if match:
            queries = _json.loads(match.group(0))
            return [str(q) for q in queries[:max_queries] if q]
    except asyncio.TimeoutError:
        logger.warning("Sub-query generation timed out — using fallback queries")
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
