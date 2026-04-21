import pytest
import respx
import httpx
from core.research.brave_search import brave_search, BRAVE_URL


@pytest.mark.asyncio
@respx.mock
async def test_brave_search_returns_mapped_results(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "TEST_KEY")
    respx.get(BRAVE_URL).mock(
        return_value=httpx.Response(
            200,
            json={"web": {"results": [
                {"title": "UAE VAT Guide", "url": "https://example.com/vat",
                 "description": "VAT is 5%"},
                {"title": "FTA Site",      "url": "https://fta.gov.ae",
                 "description": "Official site"},
            ]}},
        )
    )

    out = await brave_search("UAE VAT rate", max_results=5)

    assert out == [
        {"title": "UAE VAT Guide", "url": "https://example.com/vat", "content": "VAT is 5%"},
        {"title": "FTA Site",      "url": "https://fta.gov.ae",      "content": "Official site"},
    ]
    sent = respx.calls.last.request
    assert sent.headers["X-Subscription-Token"] == "TEST_KEY"
    assert "q=UAE+VAT+rate" in str(sent.url) or "q=UAE%20VAT%20rate" in str(sent.url)


@pytest.mark.asyncio
@respx.mock
async def test_brave_search_returns_empty_list_on_missing_web(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "x")
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json={}))
    assert await brave_search("q") == []
