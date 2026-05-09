"""
TDD test for web-search fallback suppression in law domains.
Verifies that web fallback is skipped for UAE law domain queries.
"""
import pytest

CHAT_FILE = '/Users/armaan/chatbot_local/Project_AccountingLegalChatbot/backend/api/chat.py'

@pytest.fixture(scope="module")
def chat_content():
    with open(CHAT_FILE) as f:
        return f.read()


def test_LAW_DOMAINS_constant_exists(chat_content):
    """_LAW_DOMAINS set must exist in chat.py."""
    assert '_LAW_DOMAINS' in chat_content


def test_LAW_DOMAINS_covers_uae_law_categories(chat_content):
    """All UAE-specific law domains must be in _LAW_DOMAINS."""
    required = ["general_law", "commercial", "labour", "e_invoicing", "peppol"]
    for domain in required:
        assert domain in chat_content, f"Missing UAE law domain '{domain}' in chat.py"


def test_is_law_domain_guard_present(chat_content):
    """Guard variable _is_law_domain must be set and used in the fallback check."""
    assert '_is_law_domain = _cls.domain.value in _LAW_DOMAINS' in chat_content
    assert 'not _is_law_domain' in chat_content


def test_web_fallback_condition_includes_law_domain_guard(chat_content):
    """The if-condition for web search must include not _is_law_domain."""
    # Find the web fallback block
    idx = chat_content.find("Web search fallback (if no RAG results)")
    assert idx != -1, "Could not find web search fallback comment"
    block = chat_content[idx:idx+500]
    assert "not _is_law_domain" in block, (
        "Web search fallback must include 'not _is_law_domain' guard. "
        f"Found block:\n{block}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
