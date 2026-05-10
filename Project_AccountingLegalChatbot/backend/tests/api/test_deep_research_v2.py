"""Tests for the hybrid deep research pipeline."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_deep_research_endpoint_exists(client):
    """POST /api/deep-research returns 200 with valid query."""
    with patch("api.deep_research.rag_engine") as mock_rag, \
         patch("api.deep_research.search_web", new_callable=AsyncMock, return_value=[]), \
         patch("api.deep_research.get_llm_provider") as mock_llm:
        mock_rag.search = AsyncMock(return_value=[])
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat_stream = AsyncMock(return_value=iter([]))
        mock_llm.return_value = mock_llm_instance
        r = await client.post("/api/deep-research", json={"query": "What is VAT in UAE?"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_is_complex_query_simple():
    from api.deep_research import _is_complex_query
    assert _is_complex_query("What is VAT?") is False


@pytest.mark.asyncio
async def test_is_complex_query_triggers_on_keywords():
    from api.deep_research import _is_complex_query
    assert _is_complex_query("Compare and analyze VAT compliance across UAE and KSA") is True
    assert _is_complex_query("comprehensive full report on corporate tax") is True
    assert _is_complex_query("evaluate the differences between IFRS and GAAP for accounting") is True


@pytest.mark.asyncio
async def test_is_complex_query_triggers_on_long_legal_query():
    from api.deep_research import _is_complex_query
    long_query = "What are the specific requirements under Federal Decree-Law No. 47 of 2022 regarding corporate tax obligations for free zone entities operating in multiple jurisdictions?" * 2
    assert _is_complex_query(long_query) is True


@pytest.mark.asyncio
async def test_decompose_query_returns_list():
    from api.deep_research import _decompose_query
    with patch("api.deep_research.get_llm_provider") as mock_llm:
        mock_instance = MagicMock()
        mock_instance.chat = AsyncMock(return_value=MagicMock(
            text='["What is X?", "How does Y work?", "What are the rules for Z?"]'
        ))
        mock_llm.return_value = mock_instance
        result = await _decompose_query("Complex multi-part question about law and tax")
    assert isinstance(result, list)
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_decompose_query_falls_back_on_parse_error():
    from api.deep_research import _decompose_query
    with patch("api.deep_research.get_llm_provider") as mock_llm:
        mock_instance = MagicMock()
        mock_instance.chat = AsyncMock(return_value=MagicMock(text="Not valid JSON"))
        mock_llm.return_value = mock_instance
        result = await _decompose_query("My question")
    assert result == ["My question"]
