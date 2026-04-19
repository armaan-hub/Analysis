"""Accuracy integration test for the domain classifier — requires a live LLM."""
import json
import os
from pathlib import Path

import pytest
from core.chat.domain_classifier import classify_domain, DomainLabel

FIXTURE = Path(__file__).parent / "fixtures" / "domain_queries.json"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_LLM_TESTS") != "1",
    reason="Set RUN_LLM_TESTS=1 to run live LLM accuracy tests",
)
@pytest.mark.asyncio
async def test_classifier_accuracy_threshold():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hits = 0
    for row in rows:
        result = await classify_domain(row["q"])
        if result.domain.value == row["expected"]:
            hits += 1
        else:
            print(f"  MISS: '{row['q']}' expected={row['expected']} got={result.domain.value}")
    accuracy = hits / len(rows)
    print(f"\nAccuracy: {accuracy:.2%} ({hits}/{len(rows)})")
    assert accuracy >= 0.9, f"Accuracy {accuracy:.2%} below 90% threshold"
