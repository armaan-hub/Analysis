import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.chat.domain_classifier import ClassifierResult, DomainLabel
from core.llm_manager import LLMResponse


RAG_RESULT = [
    {
        "id": "chunk-vat-001",
        "text": "VAT rate is 5% on most goods.",
        "metadata": {
            "source": "vat_guide.pdf",
            "original_name": "UAE VAT Guide 2024.pdf",
            "page": 3,
            "doc_id": "doc-001",
        },
        "score": 0.92,
    }
]


def _stub_classifier() -> ClassifierResult:
    return ClassifierResult(domain=DomainLabel.VAT, confidence=0.95, alternatives=[])


def _mock_llm(captured: dict):
    mock = AsyncMock()
    mock.compute_safe_max_tokens = MagicMock(return_value=1200)

    async def _chat(messages, **kwargs):
        captured["messages"] = messages
        return LLMResponse(
            content="VAT is 5%.",
            tokens_used=10,
            provider="mock",
            model="mock-v1",
        )

    mock.chat = AsyncMock(side_effect=_chat)
    return mock


@pytest.mark.asyncio
async def test_graph_context_appended_when_available(client):
    captured = {}
    graph_results = [
        {"label": "VAT"},
        {"label": "Input Tax"},
        {"label": "Tax Invoice"},
    ]
    graph_files = ["vat_guide.pdf", "fta_vat_public_clarification.pdf"]

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(captured)),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
        patch("api.chat.graphify_retriever.is_available", return_value=True),
        patch("api.chat.graphify_retriever.search", return_value=graph_results),
        patch("api.chat.graphify_retriever.get_related_source_files", return_value=graph_files),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT rate?", "use_rag": True, "stream": False},
        )

    assert resp.status_code == 200
    system_prompt = captured["messages"][0]["content"]
    assert "--- Knowledge Graph Context ---" in system_prompt
    assert "[Knowledge Graph] Related concepts: VAT → Input Tax → Tax Invoice" in system_prompt
    assert "Query matched concepts: [VAT], [Input Tax], [Tax Invoice]" in system_prompt
    assert "Related source files: [vat_guide.pdf], [fta_vat_public_clarification.pdf]" in system_prompt


@pytest.mark.asyncio
async def test_graph_skipped_when_not_available(client):
    captured = {}
    graph_search = MagicMock(return_value=[{"label": "VAT"}])
    graph_sources = MagicMock(return_value=["vat_guide.pdf"])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(captured)),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
        patch("api.chat.graphify_retriever.is_available", return_value=False),
        patch("api.chat.graphify_retriever.search", graph_search),
        patch("api.chat.graphify_retriever.get_related_source_files", graph_sources),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT rate?", "use_rag": True, "stream": False},
        )

    assert resp.status_code == 200
    graph_search.assert_not_called()
    graph_sources.assert_not_called()
    assert "--- Knowledge Graph Context ---" not in captured["messages"][0]["content"]


@pytest.mark.asyncio
async def test_graph_search_exception_does_not_abort_chat(client):
    captured = {}
    graph_sources = MagicMock(return_value=["vat_guide.pdf"])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm(captured)),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=RAG_RESULT)),
        patch("api.chat._generate_title", new=AsyncMock()),
        patch("api.chat.graphify_retriever.is_available", return_value=True),
        patch("api.chat.graphify_retriever.search", side_effect=Exception("graph unavailable")),
        patch("api.chat.graphify_retriever.get_related_source_files", graph_sources),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT rate?", "use_rag": True, "stream": False},
        )

    assert resp.status_code == 200
    graph_sources.assert_not_called()
    assert "--- Knowledge Graph Context ---" not in captured["messages"][0]["content"]
