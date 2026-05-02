import pytest
from unittest.mock import AsyncMock
from core.research.query_decomposer import decompose_query


@pytest.mark.asyncio
async def test_decompose_query_returns_parsed_list():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value='["UAE VAT 2025", "FTA compliance", "VAT-201 filing"]')
    result = await decompose_query("What are the current UAE VAT rules?", fake)
    assert result == ["UAE VAT 2025", "FTA compliance", "VAT-201 filing"]


@pytest.mark.asyncio
async def test_decompose_query_truncates_to_three():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value='["a","b","c","d","e"]')
    assert await decompose_query("q", fake) == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_decompose_query_falls_back_to_original_on_bad_json():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value="not json at all")
    assert await decompose_query("original question", fake) == ["original question"]


@pytest.mark.asyncio
async def test_decompose_query_falls_back_on_non_list_json():
    fake = AsyncMock()
    fake.complete = AsyncMock(return_value='{"queries": ["a"]}')
    assert await decompose_query("q", fake) == ["q"]
