import pytest
from core.council.council_service import run_council


class _ScriptedLLM:
    def __init__(self, scripts): self.scripts = list(scripts); self.calls = []
    async def stream(self, prompt, **kw):
        self.calls.append(prompt)
        for piece in self.scripts.pop(0):
            yield piece


@pytest.mark.asyncio
async def test_council_runs_four_experts_then_synthesis():
    llm = _ScriptedLLM([
        ["CA says ", "audit issue"],
        ["CPA says ", "tax issue"],
        ["CMA says ", "cost issue"],
        ["Analyst says ", "valuation issue"],
        ["Synthesis: ", "all combined"],
    ])
    events = []
    async for evt in run_council(question="Q?", base_answer="initial answer", llm=llm):
        events.append(evt)

    expert_evts = [e for e in events if e["type"] == "council_expert"]
    expert_names = [e["expert"] for e in expert_evts if e.get("final")]
    assert expert_names == ["Senior CA", "CPA", "CMA", "Financial Analyst"]

    synth = next(e for e in events if e["type"] == "council_synthesis" and e.get("final"))
    assert "Synthesis" in synth["content"]

    done = next(e for e in events if e["type"] == "done")
    assert done

    # Each expert prompt must include prior experts' final critiques (sequential chain)
    assert "CA says audit issue" in llm.calls[1]  # CPA sees CA
    assert "CPA says tax issue" in llm.calls[2]   # CMA sees CPA


@pytest.mark.asyncio
async def test_council_emits_done_on_llm_error():
    class _BrokenLLM:
        async def stream(self, prompt, **kw):
            if False:
                yield  # makes this an async generator
            raise RuntimeError("LLM unavailable")

    events = []
    async for evt in run_council(question="Q?", base_answer="answer", llm=_BrokenLLM()):
        events.append(evt)

    done = next((e for e in events if e["type"] == "done"), None)
    assert done is not None
    error_evt = next((e for e in events if e["type"] == "council_error"), None)
    assert error_evt is not None


@pytest.mark.asyncio
async def test_council_emits_done_when_synthesis_fails():
    """If all 4 experts succeed but synthesis raises, done event has error field."""
    llm = _ScriptedLLM([
        ["CA critique"],
        ["CPA critique"],
        ["CMA critique"],
        ["Analyst critique"],
    ])  # ScriptedLLM will IndexError on call #5 (synthesis)
    events = []
    async for evt in run_council(question="Q?", base_answer="A", llm=llm):
        events.append(evt)
    types = [e["type"] for e in events]
    assert "done" in types
    done = next(e for e in events if e["type"] == "done")
    assert done.get("error") is not None


@pytest.mark.asyncio
async def test_done_event_has_error_on_llm_failure():
    """done event must carry error field when LLM is broken."""
    class _BrokenLLM:
        async def stream(self, prompt, **kw):
            if False:
                yield  # makes this an async generator
            raise RuntimeError("LLM unavailable")

    events = []
    async for evt in run_council(question="Q?", base_answer="A", llm=_BrokenLLM()):
        events.append(evt)
    done = next(e for e in events if e["type"] == "done")
    assert done.get("error") is not None
