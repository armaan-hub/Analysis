"""Tests for prompt_router: ANALYST_SYSTEM_PREFIX behaviour."""
import pytest
from core.prompt_router import ANALYST_SYSTEM_PREFIX, DOMAIN_PROMPTS, get_system_prompt


def test_analyst_prefix_in_analyst_mode():
    """Analyst domain prompt must start with ANALYST_SYSTEM_PREFIX."""
    analyst_prompt = DOMAIN_PROMPTS.get("analyst", "")
    assert analyst_prompt.startswith(ANALYST_SYSTEM_PREFIX), (
        "DOMAIN_PROMPTS['analyst'] must start with ANALYST_SYSTEM_PREFIX"
    )


def test_analyst_prefix_not_in_standard_mode():
    """fast/deep_research modes must not start with ANALYST_SYSTEM_PREFIX."""
    for mode in ("fast", "deep_research"):
        prompt = get_system_prompt(mode)
        assert not prompt.startswith(ANALYST_SYSTEM_PREFIX), (
            f"prompt for mode '{mode}' must not start with ANALYST_SYSTEM_PREFIX"
        )
