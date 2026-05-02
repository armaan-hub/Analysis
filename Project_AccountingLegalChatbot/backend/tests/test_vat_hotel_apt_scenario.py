"""
Comprehensive test suite for the Hotel Apartment VAT scenario.

Tests every mode the user expects:
  1. Fast Mode — 3 conversation turns (initial + follow-ups)
  2. Deep Research endpoint
  3. Deep Research + Council pipeline
  4. Analyst mode
  5. Analyst + Council pipeline

Also validates:
  - Sources use original_name, not UUID filenames
  - SSE events are correctly ordered (meta before chunks)
  - Council fires all 4 experts then synthesis
  - No empty responses at any stage
  - Domain is correctly classified as 'vat'
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse

# ── The exact user query ──────────────────────────────────────────────────────

QUERY = (
    "I have a client who sold Hotel Apartment and now got notice from FTA to pay VAT, "
    "need a on pager on this as well documents required to make payment on portal"
)

FOLLOW_UP_DOCS = (
    "What are the specific documents I need to upload to the FTA portal for this payment?"
)

FOLLOW_UP_PENALTIES = (
    "How do I calculate the late payment penalties if the notice was received "
    "3 months after the sale?"
)

# ── Shared helpers ────────────────────────────────────────────────────────────

def _vat_classifier():
    return ClassifierResult(domain=DomainLabel.VAT, confidence=0.95, alternatives=[])


def _mock_llm(response_text: str = "VAT answer"):
    m = MagicMock()
    m.compute_safe_max_tokens = MagicMock(return_value=2000)
    m.chat = AsyncMock(
        return_value=LLMResponse(
            content=response_text, tokens_used=50, provider="mock", model="mock-v1"
        )
    )

    async def _stream(*a, **kw):
        for word in response_text.split():
            yield word + " "

    m.chat_stream = _stream
    return m


RAG_RESULT = [
    {
        "id": "chunk-vatgre1",
        "text": (
            "Hotel Apartments are classified as commercial property under UAE VAT Law. "
            "The sale is subject to 5% standard-rate VAT. "
            "The seller must account for output VAT and file Form VAT201."
        ),
        "metadata": {
            "source": "a1b2c3d4_vatgre1_real_estate_guide.pdf",
            "original_name": "FTA VAT Guide – Real Estate (VATGRE1).pdf",
            "page": 14,
            "doc_id": "doc-vatgre1",
            "category": "law",
        },
        "score": 0.91,
    },
    {
        "id": "chunk-vat-payment",
        "text": (
            "Documents required for VAT payment on property sale: "
            "Sale/Purchase Agreement, Title Deed, Emirates ID, VAT Return Form VAT201."
        ),
        "metadata": {
            "source": "b3c4d5e6_vat_payment_guide.pdf",
            "original_name": "FTA VAT Payment Procedures Guide.pdf",
            "page": 7,
            "doc_id": "doc-vat-payment",
            "category": "law",
        },
        "score": 0.88,
    },
]


def _parse_sse(raw: bytes) -> list[dict]:
    events = []
    for frame in raw.decode().split("\n\n"):
        frame = frame.strip()
        if frame.startswith("data: "):
            try:
                events.append(json.loads(frame[6:]))
            except json.JSONDecodeError:
                pass
    return events


# ── Fast Mode Tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fast_mode_turn1_initial_query_non_streaming(client):
    """Turn 1 (fast/non-stream): must return a non-empty VAT answer with sources."""
    ONE_PAGER = (
        "## One-Pager: VAT on Hotel Apartment Sale\n"
        "Hotel Apartment classified as commercial property. 5% VAT standard rate. "
        "File Form VAT201 via FTA e-Services portal."
    )
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(ONE_PAGER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": False},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Response content
    content = body["message"]["content"]
    assert content, "Response content must not be empty"
    assert len(content) > 50, "Response too short for a one-pager"

    # Sources returned and use original_name not UUID
    sources = body["message"]["sources"]
    assert sources, "Sources must be present for a RAG-backed answer"
    source_names = [s["source"] for s in sources]
    assert any("FTA" in name or "VAT" in name or ".pdf" in name for name in source_names), (
        f"Expected recognisable source names, got: {source_names}"
    )
    for name in source_names:
        assert not (name.startswith("a1b2") or "a1b2c3d4" in name), (
            f"Source should be original_name, not UUID prefix: {name}"
        )

    # Provider info
    assert body["provider"] == "mock"
    assert body["conversation_id"]


@pytest.mark.asyncio
async def test_fast_mode_turn1_streaming(client):
    """Turn 1 (fast/stream): first SSE event must be 'meta' with domain='vat'."""
    ONE_PAGER = (
        "Hotel Apartment sold. 5% VAT applies. File via FTA portal at tax.gov.ae."
    )
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(ONE_PAGER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "one_pager", "topic": "VAT Hotel Apartment"})()
        )),
        patch("api.chat._get_query_variations", new=AsyncMock(return_value=[QUERY])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": True},
        )

    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.content)
    assert events, "No SSE events returned"

    # meta must be first
    assert events[0]["type"] == "meta", f"First event must be 'meta', got: {events[0]}"
    assert events[0]["detected_domain"] == "vat", (
        f"Domain must be 'vat', got: {events[0].get('detected_domain')}"
    )
    assert events[0]["mode"] == "fast"
    assert "conversation_id" in events[0]

    # at least one chunk event
    chunks = [e for e in events if e["type"] == "chunk"]
    assert chunks, "No chunk events in stream"
    full_text = "".join(c["content"] for c in chunks)
    assert len(full_text) > 10

    # sources event
    src_events = [e for e in events if e["type"] == "sources"]
    assert src_events, "No sources SSE event when RAG returned results"

    # done event must be last
    assert events[-1]["type"] == "done", f"Last event must be 'done', got: {events[-1]}"


@pytest.mark.asyncio
async def test_fast_mode_turn2_follow_up_documents(client):
    """Turn 2: follow-up about portal documents must return non-empty content."""
    DOCS_ANSWER = (
        "## Documents for FTA Portal\n"
        "1. SPA – Sale/Purchase Agreement\n"
        "2. Title Deed\n"
        "3. Emirates ID\n"
        "4. Form VAT201\n"
        "Upload at tax.gov.ae → VAT → Submit VAT Return."
    )
    # Turn 1 — create conversation
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm("Initial VAT answer")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        r1 = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": False},
        )
    assert r1.status_code == 200
    conv_id = r1.json()["conversation_id"]

    # Turn 2 — follow-up
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(DOCS_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        r2 = await client.post(
            "/api/chat/send",
            json={
                "message": FOLLOW_UP_DOCS,
                "conversation_id": conv_id,
                "mode": "fast",
                "stream": False,
            },
        )

    assert r2.status_code == 200, r2.text
    content = r2.json()["message"]["content"]
    assert content, "Turn 2 response must not be empty"
    assert r2.json()["conversation_id"] == conv_id, "Must stay in same conversation"
    # Response must be substantive (not a generic fallback)
    assert len(content) > 30, f"Turn 2 response suspiciously short: {content!r}"


@pytest.mark.asyncio
async def test_fast_mode_turn3_follow_up_penalties(client):
    """Turn 3: follow-up about late payment penalties must return non-empty content."""
    PENALTY_ANSWER = (
        "## Late Payment Penalties\n"
        "2% immediately + 4% after 7 days (Cabinet Decision 49/2021). "
        "1% per month thereafter."
    )
    # Turn 1
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm("Initial answer")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        r1 = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": False},
        )
    conv_id = r1.json()["conversation_id"]

    # Turn 2
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm("Docs answer")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        await client.post(
            "/api/chat/send",
            json={"message": FOLLOW_UP_DOCS, "conversation_id": conv_id,
                  "mode": "fast", "stream": False},
        )

    # Turn 3
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(PENALTY_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        r3 = await client.post(
            "/api/chat/send",
            json={
                "message": FOLLOW_UP_PENALTIES,
                "conversation_id": conv_id,
                "mode": "fast",
                "stream": False,
            },
        )

    assert r3.status_code == 200, r3.text
    content = r3.json()["message"]["content"]
    assert content, "Turn 3 response must not be empty"
    assert len(content) > 30


@pytest.mark.asyncio
async def test_fast_mode_sources_use_original_name(client):
    """Sources in fast mode must use original_name, not UUID-prefixed filenames."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm("VAT answer")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": False},
        )

    sources = resp.json()["message"]["sources"]
    assert sources, "Sources must be returned when RAG finds results"

    for s in sources:
        name = s["source"]
        assert "a1b2c3d4" not in name, f"UUID prefix leaked into source name: {name}"
        assert "b3c4d5e6" not in name, f"UUID prefix leaked into source name: {name}"


# ── Deep Research Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deep_research_vat_step_events(client):
    """Deep research must yield step → chunk → answer → done SSE events."""
    DR_ANSWER = (
        "## Hotel Apartment VAT – Deep Research\n"
        "The sale triggers 5% UAE VAT. Pay via FTA portal. "
        "Documents: SPA, Title Deed, Emirates ID, Form VAT201."
    )
    with (
        patch("api.chat.get_llm_provider", return_value=_mock_llm(DR_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("core.web_search.deep_search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/deep-research",
            json={"query": QUERY, "selected_doc_ids": []},
        )

    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.content)
    types = [e["type"] for e in events]

    assert "step" in types, f"No 'step' events. Got: {types}"
    assert "chunk" in types, f"No 'chunk' events. Got: {types}"
    assert "answer" in types, f"No 'answer' event. Got: {types}"
    assert "done" in types, f"No 'done' event. Got: {types}"

    # done must be last
    assert events[-1]["type"] == "done", "Last event must be 'done'"


@pytest.mark.asyncio
async def test_deep_research_answer_contains_content(client):
    """Deep research answer event must carry non-empty content."""
    DR_ANSWER = (
        "Hotel Apartment sold in UAE. 5% VAT applies on sale value. "
        "FTA notice requires payment via e-Services portal."
    )
    with (
        patch("api.chat.get_llm_provider", return_value=_mock_llm(DR_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("core.web_search.deep_search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/deep-research",
            json={"query": QUERY},
        )

    events = _parse_sse(resp.content)
    answer_evt = next((e for e in events if e["type"] == "answer"), None)
    assert answer_evt is not None, "No 'answer' event found"
    assert answer_evt["content"], "answer event 'content' must not be empty"
    assert len(answer_evt["content"]) > 20


@pytest.mark.asyncio
async def test_deep_research_sources_list(client):
    """Deep research answer event must include sources from RAG."""
    DR_ANSWER = "VAT on Hotel Apartment sale answer."
    with (
        patch("api.chat.get_llm_provider", return_value=_mock_llm(DR_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("core.web_search.deep_search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/deep-research",
            json={"query": QUERY},
        )

    events = _parse_sse(resp.content)
    answer_evt = next((e for e in events if e["type"] == "answer"), None)
    assert answer_evt is not None
    sources = answer_evt.get("sources", [])
    assert isinstance(sources, list)
    # RAG results should propagate as sources
    assert len(sources) > 0, "Deep research must return sources from RAG results"
    filenames = [s.get("filename", "") for s in sources]
    # original_name should be used (not UUID hash)
    for fname in filenames:
        assert "a1b2c3d4" not in fname, f"UUID hash leaked into deep-research source: {fname}"


# ── Council Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_council_fires_all_four_experts(client):
    """Council must fire all 4 experts (CA, CPA, CMA, Financial Analyst)."""
    BASE_ANSWER = (
        "Hotel Apartment sale is subject to 5% UAE VAT. "
        "File Form VAT201 via FTA e-Services portal."
    )
    EXPERT_CRITIQUE = "[Expert] Looks correct. Verify the VAT period and registration status."
    SYNTHESIS = (
        "## Final Recommendation\n5% VAT applies. Pay via FTA portal. "
        "Check registration and penalty exposure."
    )

    def _council_llm():
        m = MagicMock()
        m.compute_safe_max_tokens = MagicMock(return_value=800)

        call_count = [0]

        async def _stream(*a, **kw):
            call_count[0] += 1
            # First 4 calls = expert critiques, 5th = synthesis
            if call_count[0] <= 4:
                for word in EXPERT_CRITIQUE.split():
                    yield word + " "
            else:
                for word in SYNTHESIS.split():
                    yield word + " "

        m.chat_stream = _stream
        return m

    with patch("api.council.get_llm_provider", return_value=_council_llm()):
        resp = await client.post(
            "/api/chat/council",
            json={"question": QUERY, "base_answer": BASE_ANSWER},
        )

    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.content)
    types = [e["type"] for e in events]

    # All 4 expert events (with status=thinking) expected
    expert_thinking = [
        e for e in events
        if e.get("type") == "council_expert" and e.get("status") == "thinking"
    ]
    assert len(expert_thinking) == 4, (
        f"Expected 4 expert 'thinking' events, got {len(expert_thinking)}: "
        f"{[e.get('expert') for e in expert_thinking]}"
    )

    expected_experts = {"Senior CA", "CPA", "CMA", "Financial Analyst"}
    fired_experts = {e.get("expert") for e in expert_thinking}
    assert fired_experts == expected_experts, (
        f"Expected experts {expected_experts}, got {fired_experts}"
    )


@pytest.mark.asyncio
async def test_council_synthesis_event_produced(client):
    """Council must produce a council_synthesis event with final=True."""
    BASE_ANSWER = "Hotel Apartment: 5% VAT applies under UAE law."
    SYNTHESIS = "Final: 5% VAT on hotel apartment sale. Pay via FTA portal."

    def _council_llm():
        m = MagicMock()
        m.compute_safe_max_tokens = MagicMock(return_value=800)

        async def _stream(*a, **kw):
            for word in SYNTHESIS.split():
                yield word + " "

        m.chat_stream = _stream
        return m

    with patch("api.council.get_llm_provider", return_value=_council_llm()):
        resp = await client.post(
            "/api/chat/council",
            json={"question": QUERY, "base_answer": BASE_ANSWER},
        )

    events = _parse_sse(resp.content)
    synthesis_final = [
        e for e in events
        if e.get("type") == "council_synthesis" and e.get("final") is True
    ]
    assert synthesis_final, "No council_synthesis final event found"
    assert synthesis_final[0]["content"], "Synthesis content must not be empty"


@pytest.mark.asyncio
async def test_council_synthesis_differs_from_base_answer(client):
    """Council synthesis must be different from (and ideally richer than) the base answer."""
    BASE_ANSWER = "Hotel Apartment: 5% VAT applies."
    SYNTHESIS = (
        "## Final Recommendation\n"
        "5% VAT on hotel apartment sale confirmed. Key risks: late payment penalty 2%+4%. "
        "Legal references: UAE VAT Law Art.29, VATGRE1 Guide."
    )

    def _council_llm():
        m = MagicMock()
        m.compute_safe_max_tokens = MagicMock(return_value=800)
        call_count = [0]

        async def _stream(*a, **kw):
            call_count[0] += 1
            if call_count[0] <= 4:
                yield "Expert critique here."
            else:
                for word in SYNTHESIS.split():
                    yield word + " "

        m.chat_stream = _stream
        return m

    with patch("api.council.get_llm_provider", return_value=_council_llm()):
        resp = await client.post(
            "/api/chat/council",
            json={"question": QUERY, "base_answer": BASE_ANSWER},
        )

    events = _parse_sse(resp.content)
    synthesis_final = next(
        (e for e in events if e.get("type") == "council_synthesis" and e.get("final")), None
    )
    assert synthesis_final, "No synthesis final event"
    synth_text = synthesis_final["content"]
    assert synth_text != BASE_ANSWER, "Synthesis must not be identical to the base answer"
    assert len(synth_text) >= len(BASE_ANSWER), "Synthesis should be at least as detailed as base answer"


@pytest.mark.asyncio
async def test_council_done_event_last(client):
    """The last SSE event from council must be type='done' with no error."""
    with patch("api.council.get_llm_provider", return_value=_council_llm_simple()):
        resp = await client.post(
            "/api/chat/council",
            json={"question": QUERY, "base_answer": "5% VAT applies."},
        )

    events = _parse_sse(resp.content)
    assert events[-1]["type"] == "done", f"Last event must be 'done', got: {events[-1]}"
    assert "error" not in events[-1], f"Done event must not carry an error: {events[-1]}"


def _council_llm_simple():
    m = MagicMock()
    m.compute_safe_max_tokens = MagicMock(return_value=800)

    async def _stream(*a, **kw):
        yield "Council response."

    m.chat_stream = _stream
    return m


# ── Analyst Mode Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyst_mode_returns_non_empty(client):
    """Analyst mode must return a non-empty response for the VAT query."""
    ANALYST_ANSWER = (
        "## VAT Analysis: Hotel Apartment Sale\n"
        "**Tax Exposure**: AED 50,000 (5% of AED 1M sale price)\n"
        "**Risk**: Late payment penalty accruing at 2%+4%+1%/month\n"
        "**Action**: File Form VAT201 immediately."
    )
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(ANALYST_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "analyst", "stream": False},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    content = body["message"]["content"]
    assert content, "Analyst response must not be empty"
    assert len(content) > 30


@pytest.mark.asyncio
async def test_analyst_mode_sources_returned(client):
    """Analyst mode must return RAG sources when they exist."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm("Analyst VAT answer.")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "analyst", "stream": False},
        )

    body = resp.json()
    sources = body["message"]["sources"]
    assert sources, "Analyst mode must return sources when RAG finds results"
    for s in sources:
        assert s.get("source"), "Each source must have a name"
        assert "a1b2c3d4" not in s["source"], "UUID prefix must not appear in source name"


# ── Analyst + Council Pipeline ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyst_plus_council_full_pipeline(client):
    """End-to-end: Analyst answer → Council review → synthesis event."""
    ANALYST_ANSWER = (
        "Hotel Apartment sale triggers 5% UAE VAT. "
        "Exposure: AED 50k on a AED 1M sale. File VAT201 now."
    )
    SYNTHESIS = (
        "## Council Final\n"
        "5% VAT confirmed. Penalty risk: 2%+4% immediately if overdue. "
        "Action: file VAT201 and pay via FTA portal by [due date]."
    )

    # Step 1: Analyst mode
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(ANALYST_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        analyst_resp = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "analyst", "stream": False},
        )
    assert analyst_resp.status_code == 200
    base_answer = analyst_resp.json()["message"]["content"]
    assert base_answer, "Analyst base answer must not be empty before council"

    # Step 2: Council
    def _council_llm():
        m = MagicMock()
        m.compute_safe_max_tokens = MagicMock(return_value=800)
        call_count = [0]

        async def _stream(*a, **kw):
            call_count[0] += 1
            if call_count[0] <= 4:
                yield "Expert critique."
            else:
                for word in SYNTHESIS.split():
                    yield word + " "

        m.chat_stream = _stream
        return m

    with patch("api.council.get_llm_provider", return_value=_council_llm()):
        council_resp = await client.post(
            "/api/chat/council",
            json={"question": QUERY, "base_answer": base_answer},
        )

    assert council_resp.status_code == 200
    events = _parse_sse(council_resp.content)

    # All 4 experts
    experts_thinking = [
        e for e in events
        if e.get("type") == "council_expert" and e.get("status") == "thinking"
    ]
    assert len(experts_thinking) == 4, f"Expected 4 expert starts, got {len(experts_thinking)}"

    # Synthesis final
    synthesis = next(
        (e for e in events if e.get("type") == "council_synthesis" and e.get("final")), None
    )
    assert synthesis, "No synthesis final event from council"
    assert synthesis["content"] != base_answer, "Synthesis must refine the base answer"

    # Done last
    assert events[-1]["type"] == "done"
    assert "error" not in events[-1]


# ── Deep Research + Council Pipeline ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_deep_research_plus_council_pipeline(client):
    """End-to-end: deep_research → council → synthesis."""
    DR_ANSWER = (
        "UAE Hotel Apartment sale. 5% VAT under Federal Decree-Law No. 8/2017. "
        "Pay via FTA e-Services."
    )
    SYNTHESIS = "## Council Synthesis\nFive percent VAT. File VAT201. Penalty risk noted."

    # Step 1: Deep Research
    with (
        patch("api.chat.get_llm_provider", return_value=_mock_llm(DR_ANSWER)),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
        patch("core.web_search.deep_search", new=AsyncMock(return_value=[])),
    ):
        dr_resp = await client.post(
            "/api/chat/deep-research",
            json={"query": QUERY},
        )
    assert dr_resp.status_code == 200
    dr_events = _parse_sse(dr_resp.content)
    answer_evt = next((e for e in dr_events if e["type"] == "answer"), None)
    assert answer_evt, "Deep research must produce an answer event"
    base_answer = answer_evt["content"]
    assert base_answer, "Deep research answer content must not be empty"

    # Step 2: Council
    def _council_llm():
        m = MagicMock()
        m.compute_safe_max_tokens = MagicMock(return_value=800)
        call_count = [0]

        async def _stream(*a, **kw):
            call_count[0] += 1
            if call_count[0] <= 4:
                yield "Expert input."
            else:
                for word in SYNTHESIS.split():
                    yield word + " "

        m.chat_stream = _stream
        return m

    with patch("api.council.get_llm_provider", return_value=_council_llm()):
        council_resp = await client.post(
            "/api/chat/council",
            json={"question": QUERY, "base_answer": base_answer},
        )

    assert council_resp.status_code == 200
    c_events = _parse_sse(council_resp.content)

    experts = [
        e for e in c_events
        if e.get("type") == "council_expert" and e.get("status") == "thinking"
    ]
    assert len(experts) == 4

    synthesis = next(
        (e for e in c_events if e.get("type") == "council_synthesis" and e.get("final")), None
    )
    assert synthesis
    assert c_events[-1]["type"] == "done"


# ── MockProvider Integration Tests (verify the mock fix itself) ───────────────

class TestMockProviderContextAwareness:
    """
    Tests that exercise core.llm_manager.MockProvider directly to verify
    the _all_text() context-aware fix.  These do NOT patch get_llm_provider
    so the real MockProvider code path is exercised.
    """

    def _make_mp(self):
        from core.llm_manager import MockProvider
        return MockProvider()

    @pytest.mark.asyncio
    async def test_initial_query_detected(self):
        """MockProvider must return VAT one-pager for the initial hotel-apartment query."""
        mp = self._make_mp()
        resp = await mp.chat([{"role": "user", "content": QUERY}])
        assert "5%" in resp.content or "VAT" in resp.content, (
            f"Expected VAT content, got: {resp.content[:120]}"
        )
        assert len(resp.content) > 100, "One-pager response too short"

    @pytest.mark.asyncio
    async def test_documents_followup_context_aware(self):
        """MockProvider must give documents-specific answer when hotel-apt context is present."""
        mp = self._make_mp()
        messages = [
            {"role": "user", "content": QUERY},
            {"role": "assistant", "content": "Hotel Apartment: 5% VAT."},
            {"role": "user", "content": FOLLOW_UP_DOCS},
        ]
        resp = await mp.chat(messages)
        assert resp.content != "This is a mock response from the LLM manager for: " + FOLLOW_UP_DOCS[:50], (
            "MockProvider returned generic fallback for a contextual follow-up"
        )
        # Should reference documents
        assert any(kw in resp.content for kw in ("Document", "SPA", "Title Deed", "VAT201", "Emirates")), (
            f"Expected document-related answer, got: {resp.content[:200]}"
        )

    @pytest.mark.asyncio
    async def test_penalties_followup_context_aware(self):
        """MockProvider must give penalty-specific answer when hotel-apt context is present."""
        mp = self._make_mp()
        messages = [
            {"role": "user", "content": QUERY},
            {"role": "assistant", "content": "Hotel Apartment: 5% VAT. File VAT201."},
            {"role": "user", "content": FOLLOW_UP_PENALTIES},
        ]
        resp = await mp.chat(messages)
        assert resp.content != "This is a mock response from the LLM manager for: " + FOLLOW_UP_PENALTIES[:50], (
            "MockProvider returned generic fallback for a penalty follow-up"
        )
        assert any(kw in resp.content for kw in ("penalt", "Penalt", "2%", "4%", "Cabinet")), (
            f"Expected penalty content, got: {resp.content[:200]}"
        )

    @pytest.mark.asyncio
    async def test_council_synthesis_differs_from_vat_base(self):
        """MockProvider must return synthesis-specific content when council chair prompt detected."""
        mp = self._make_mp()
        from core.council.council_service import _build_synthesis_prompt
        synth_prompt = _build_synthesis_prompt(
            question=QUERY,
            base_answer="Hotel Apartment: 5% VAT applies.",
            all_critiques=[
                ("Senior CA", "Chartered Accountant", "CA critique here."),
                ("CPA", "CPA", "CPA critique here."),
                ("CMA", "CMA", "CMA critique here."),
                ("Financial Analyst", "Analyst", "Analyst critique here."),
            ],
        )
        messages = [{"role": "user", "content": synth_prompt}]
        resp = await mp.chat(messages)
        # Must contain synthesis markers, not just the base one-pager
        assert any(kw in resp.content for kw in ("Final Recommendation", "Key Risks", "Standards Cited")), (
            f"Expected council synthesis format, got: {resp.content[:200]}"
        )
        assert "Hotel Apartment: 5% VAT applies." != resp.content, (
            "Council synthesis must not be identical to base answer"
        )


# ── Domain Filter Parity: Streaming vs Non-Streaming ────────────────────────
# Regression test for the bug where non-streaming path skipped
# _build_rag_domain_filter, allowing off-domain docs to leak through.

@pytest.mark.asyncio
async def test_non_streaming_applies_domain_filter_for_vat(client):
    """Non-streaming send must apply the VAT domain filter to the RAG search call.

    Bug: streaming path calls _build_rag_domain_filter; non-streaming path did not.
    Symptom: VATP035 (Electronic Devices) document leaked into Hotel Apartment VAT
    responses at low score because no domain filter narrowed the search to vat docs.

    The expected filter for VAT domain is:
      {"$and": [{"category": {"$in": ["law", "finance"]}}, {"domain": {"$in": ["vat"]}}]}
    """
    from api.chat import _DOMAIN_TO_DOC_DOMAINS

    search_mock = AsyncMock(return_value=RAG_RESULT)

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=search_mock),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": False},
        )

    assert resp.status_code == 200, resp.text

    # Collect every unique filter dict passed to rag_engine.search
    called_filters = [call.kwargs.get("filter") for call in search_mock.call_args_list]
    assert called_filters, "rag_engine.search must have been called"

    vat_domains = _DOMAIN_TO_DOC_DOMAINS["vat"]  # ["vat"]
    domain_clause = {"domain": {"$in": vat_domains}}

    for flt in called_filters:
        assert flt is not None, "RAG search must use a filter (not unfiltered)"
        # The filter must include the domain clause (either inline or inside $and)
        has_domain_filter = (
            flt == domain_clause
            or (
                "$and" in flt
                and any(clause == domain_clause for clause in flt["$and"])
            )
        )
        assert has_domain_filter, (
            f"Non-streaming path did not apply VAT domain filter.\n"
            f"  Expected domain clause: {domain_clause}\n"
            f"  Actual filter used: {flt}\n"
            "  This allows off-domain docs (e.g. VATP035 Electronic Devices) to leak in."
        )


@pytest.mark.asyncio
async def test_streaming_and_non_streaming_use_same_rag_filter_shape(client):
    """Streaming and non-streaming paths must produce equivalent RAG filter shapes.

    Both paths must apply _build_rag_domain_filter so the domain clause appears
    in the filter sent to ChromaDB. Before the fix, only streaming did this.
    """
    from api.chat import _DOMAIN_TO_DOC_DOMAINS

    stream_filters: list = []
    nonstream_filters: list = []

    async def capture_stream(*args, **kwargs):
        stream_filters.append(kwargs.get("filter"))
        return RAG_RESULT

    async def capture_nonstream(*args, **kwargs):
        nonstream_filters.append(kwargs.get("filter"))
        return RAG_RESULT

    # Streaming call
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=capture_stream),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "one_pager", "topic": "VAT"})()
        )),
        patch("api.chat._get_query_variations", new=AsyncMock(return_value=[QUERY])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": True},
        )

    # Non-streaming call
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_vat_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=capture_nonstream),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        await client.post(
            "/api/chat/send",
            json={"message": QUERY, "mode": "fast", "stream": False},
        )

    assert stream_filters, "Streaming path must call rag_engine.search"
    assert nonstream_filters, "Non-streaming path must call rag_engine.search"

    vat_domains = _DOMAIN_TO_DOC_DOMAINS["vat"]
    domain_clause = {"domain": {"$in": vat_domains}}

    def _has_domain_clause(flt: dict) -> bool:
        return (
            flt == domain_clause
            or "$and" in flt
            and any(c == domain_clause for c in flt["$and"])
        )

    assert all(_has_domain_clause(f) for f in stream_filters), (
        f"Streaming path missing domain clause. Filters: {stream_filters}"
    )
    assert all(_has_domain_clause(f) for f in nonstream_filters), (
        f"Non-streaming path missing domain clause. Filters: {nonstream_filters}"
    )
