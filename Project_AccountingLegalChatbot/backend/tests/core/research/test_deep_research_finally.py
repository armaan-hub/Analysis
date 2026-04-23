import pytest
from core.research.deep_research_service import run_deep_research


class _FailingLLM:
    async def stream(self, prompt, **kw):
        raise RuntimeError("LLM exploded")
        yield  # pragma: no cover


class _StubRAG:
    async def search(self, query, doc_ids=None):
        return []


async def _ingest(**kwargs):
    return None


@pytest.mark.asyncio
async def test_done_event_emitted_even_on_llm_failure(monkeypatch):
    async def _fake_decompose(q, llm):
        return [q]
    async def _fake_brave(q, max_results=5):
        return []
    monkeypatch.setattr("core.research.deep_research_service.decompose_query", _fake_decompose)
    monkeypatch.setattr("core.research.deep_research_service.brave_search", _fake_brave)

    events = []
    async for evt in run_deep_research(
        query="test",
        selected_doc_ids=None,
        llm=_FailingLLM(),
        rag=_StubRAG(),
        ingest=_ingest,
    ):
        events.append(evt)

    types = [e["type"] for e in events]
    assert "done" in types, f"Expected 'done' in {types}"
    done_evt = next(e for e in events if e["type"] == "done")
    assert "error" in done_evt
    assert "LLM exploded" in done_evt["error"]
    assert done_evt.get("partial") is True, "done event should mark partial=True when no answer was emitted"
