import pytest
from unittest.mock import AsyncMock, patch
from core.research.deep_research_service import run_deep_research


@pytest.mark.asyncio
async def test_run_deep_research_emits_expected_events(monkeypatch):
    events = []

    async def fake_decompose(q, llm):
        return ["q1", "q2"]

    async def fake_search(query, max_results=5):
        return [{"title": f"T-{query}", "url": f"https://x/{query}", "content": "C"}]

    fake_rag = AsyncMock()
    fake_rag.search = AsyncMock(return_value=[
        {"text": "doc chunk", "source": "Policy.pdf", "page": 4}
    ])

    fake_llm = AsyncMock()
    async def stream_answer(messages, **_):
        for piece in ["Hello ", "world."]:
            yield piece
    fake_llm.chat_stream = stream_answer

    fake_ingest = AsyncMock()

    with patch("core.research.deep_research_service.decompose_query", fake_decompose), \
         patch("core.research.deep_research_service.brave_search", fake_search), \
         patch("core.research.deep_research_service._is_valid_url", AsyncMock(return_value=True)):
        async for ev in run_deep_research(
            query="orig", selected_doc_ids=["d1"],
            llm=fake_llm, rag=fake_rag, ingest=fake_ingest,
        ):
            events.append(ev)

    types = [e["type"] for e in events]
    assert types[0] == "step"
    assert types[-1] == "done"
    assert any(e["type"] == "answer" for e in events)

    # ingest must be called per web result (2 queries × 1 result = 2)
    assert fake_ingest.await_count == 2
