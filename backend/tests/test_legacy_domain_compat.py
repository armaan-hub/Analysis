"""Test backward compatibility with legacy domain string values.

Legacy frontend domain values like 'law', 'finance', 'audit', 'aml',
'general', and 'legal' are NOT members of DomainLabel but must not crash
the /api/chat/send endpoint — the backend should fall back to the LLM
classifier.
"""
import pytest
from unittest.mock import patch, AsyncMock
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_classifier(domain: DomainLabel = DomainLabel.GENERAL_LAW) -> ClassifierResult:
    return ClassifierResult(domain=domain, confidence=0.8, alternatives=[])


def _mock_llm():
    mock = AsyncMock()
    mock.chat = AsyncMock(
        return_value=LLMResponse(
            content="test response", tokens_used=5, provider="mock", model="mock-v1"
        )
    )
    return mock


LEGACY_DOMAINS = ["law", "finance", "audit", "aml", "general", "legal"]


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_domain", LEGACY_DOMAINS)
async def test_legacy_domain_does_not_crash(client, legacy_domain):
    """Legacy domain values not in DomainLabel should not cause 500 errors."""
    with (
        patch(
            "api.chat.classify_domain",
            new=AsyncMock(return_value=_stub_classifier()),
        ),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "test query", "domain": legacy_domain, "stream": False},
        )
    assert resp.status_code == 200, (
        f"Legacy domain '{legacy_domain}' caused error: {resp.text}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_domain", LEGACY_DOMAINS)
async def test_legacy_domain_triggers_classifier(client, legacy_domain):
    """Legacy domain values should fall back to the LLM classifier."""
    mock_cls = AsyncMock(return_value=_stub_classifier())
    with (
        patch("api.chat.classify_domain", new=mock_cls),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "test query", "domain": legacy_domain, "stream": False},
        )
    assert resp.status_code == 200
    mock_cls.assert_called_once()
