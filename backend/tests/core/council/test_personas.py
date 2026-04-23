from core.council.personas import EXPERTS, SYNTHESIS_PROMPT

def test_four_experts_present():
    names = [e.name for e in EXPERTS]
    assert names == ["Senior CA", "CPA", "CMA", "Financial Analyst"]

def test_each_expert_has_persona_prompt():
    for e in EXPERTS:
        assert len(e.system_prompt) > 100
        assert e.name.lower().split()[0] in e.system_prompt.lower() or "you are" in e.system_prompt.lower()

def test_synthesis_prompt_mentions_reconciliation():
    assert "reconcile" in SYNTHESIS_PROMPT.lower() or "synthesi" in SYNTHESIS_PROMPT.lower()
