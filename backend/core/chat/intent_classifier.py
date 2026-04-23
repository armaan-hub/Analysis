from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

OutputType = Literal["answer", "explanation", "list", "table", "report", "comparison", "calculation"]
VALID_OUTPUT_TYPES = frozenset({"answer", "explanation", "list", "table", "report", "comparison", "calculation"})

@dataclass
class Intent:
    output_type: OutputType
    topic: str

_CLASSIFY_PROMPT_PREFIX = (
    "Classify the user's question. Return ONLY JSON of the form "
    '{"output_type":"answer|explanation|list|table|report|comparison|calculation",'
    '"topic":"<short topic>"}. No explanation.\n\nQuestion: '
)

async def classify_intent(question: str, llm) -> Intent:
    try:
        resp = await llm.chat(
            messages=[{"role": "user", "content": _CLASSIFY_PROMPT_PREFIX + question}],
            max_tokens=120,
            temperature=0.0,
        )
        match = re.search(r"\{.*\}", resp.content, re.DOTALL)
        if not match:
            return Intent(output_type="answer", topic=question[:80])
        data = json.loads(match.group())
        raw_type = data.get("output_type", "answer")
        output_type: OutputType = raw_type if raw_type in VALID_OUTPUT_TYPES else "answer"
        return Intent(
            output_type=output_type,
            topic=data.get("topic", question[:80])[:80],
        )
    except Exception as exc:
        logger.debug("Intent classification failed (non-fatal): %s", exc)
        return Intent(output_type="answer", topic=question[:80])
