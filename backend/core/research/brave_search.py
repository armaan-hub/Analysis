import os
import httpx

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


async def brave_search(query: str, max_results: int = 5) -> list[dict]:
    """Return a list of {title, url, content} dicts from Brave Search."""
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            BRAVE_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": max_results, "text_decorations": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("description", "")}
            for r in data.get("web", {}).get("results", [])
        ]
