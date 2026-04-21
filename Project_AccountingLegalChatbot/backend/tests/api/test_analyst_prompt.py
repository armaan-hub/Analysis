import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_analyst_prefix_constant_exists():
    from core.prompt_router import ANALYST_SYSTEM_PREFIX
    assert ANALYST_SYSTEM_PREFIX, "ANALYST_SYSTEM_PREFIX must be a non-empty string"
    assert "MUST base your answers primarily on the documents" in ANALYST_SYSTEM_PREFIX


def test_analyst_prefix_is_prepended_in_domain_prompts():
    from core.prompt_router import ANALYST_SYSTEM_PREFIX, DOMAIN_PROMPTS
    assert ANALYST_SYSTEM_PREFIX in DOMAIN_PROMPTS.get("analyst", "")
