"""Tests for prompt_router: ANALYST_SYSTEM_PREFIX behaviour and FORMATTING_REMINDER."""
import pytest
from core.prompt_router import ANALYST_SYSTEM_PREFIX, DOMAIN_PROMPTS, FORMATTING_REMINDER, get_system_prompt


def test_formatting_reminder_is_exported():
    """FORMATTING_REMINDER must exist and mention blank lines."""
    assert isinstance(FORMATTING_REMINDER, str)
    assert len(FORMATTING_REMINDER) > 20
    assert "blank" in FORMATTING_REMINDER.lower() or "line" in FORMATTING_REMINDER.lower()


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
