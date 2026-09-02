import pytest
from core.council.audit_council_personas import AUDIT_COUNCIL_AGENTS
from core.council.comparative_mainland_template import COLUMN_ORDER, YEAR_CURRENT, YEAR_COMPARATIVE
from core.council.financial_audit_council import (
    run_financial_audit_council,
    run_financial_audit_council_stream,
)


def test_six_subagents_present():
    assert len(AUDIT_COUNCIL_AGENTS) == 6
    expected_stages = [
        "legal_extraction",
        "tb_audit",
        "pl_analysis",
        "mainland_mapping",
        "report_synthesis",
        "math_qc",
    ]
    actual_stages = [agent.stage for agent in AUDIT_COUNCIL_AGENTS]
    assert actual_stages == expected_stages


def test_chronological_order_constants():
    assert list(COLUMN_ORDER) == ["2025", "2024"]
    assert YEAR_CURRENT == "2025"
    assert YEAR_COMPARATIVE == "2024"


class _StubLLM:
    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or ["Agent finding chunk 1", " chunk 2"]
        self.call_count = 0

    async def chat_stream(self, messages, **kw):
        self.call_count += 1
        for chunk in self._responses:
            yield chunk


class _FailingLLM:
    async def chat_stream(self, messages, **kw):
        if False:
            yield
        raise RuntimeError("LLM failure in test")


@pytest.mark.asyncio
async def test_financial_audit_council_stream_success():
    llm = _StubLLM(["Report section data"])
    events = []
    async for evt in run_financial_audit_council_stream(
        doc1_balance_sheet="Sample BS",
        doc2_profit_loss="Sample PL",
        doc3_corporate_legal="Sample Legal",
        doc4_template_notes="",
        llm=llm,
    ):
        events.append(evt)

    # 6 agents * (start + delta + complete) + done = 19 events
    start_events = [e for e in events if e.get("type") == "audit_council_agent_start"]
    complete_events = [e for e in events if e.get("type") == "audit_council_agent_complete"]
    done_events = [e for e in events if e.get("type") == "audit_council_done"]

    assert len(start_events) == 6
    assert len(complete_events) == 6
    assert len(done_events) == 1
    assert done_events[0]["stages_completed"] == 6
    assert "error" not in done_events[0]


@pytest.mark.asyncio
async def test_financial_audit_council_stream_handles_llm_error():
    llm = _FailingLLM()
    events = []
    async for evt in run_financial_audit_council_stream(
        doc1_balance_sheet="Sample BS",
        doc2_profit_loss="Sample PL",
        doc3_corporate_legal="Sample Legal",
        doc4_template_notes="",
        llm=llm,
    ):
        events.append(evt)

    error_events = [e for e in events if e.get("type") == "audit_council_error"]
    done_events = [e for e in events if e.get("type") == "audit_council_done"]

    assert len(error_events) >= 1
    assert len(done_events) == 1
    assert done_events[0]["stages_completed"] == 0
    assert "error" in done_events[0]


@pytest.mark.asyncio
async def test_financial_audit_council_sync_success():
    llm = _StubLLM(["# Comparative Mainland Report"])
    result = await run_financial_audit_council(
        doc1_balance_sheet="Sample BS",
        doc2_profit_loss="Sample PL",
        doc3_corporate_legal="Sample Legal",
        doc4_template_notes="",
        llm=llm,
    )

    assert result["success"] is True
    assert "report_markdown" in result
    assert "qc_critique" in result
    assert len(result["stage_outputs"]) == 6
