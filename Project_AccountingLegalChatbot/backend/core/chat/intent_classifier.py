from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Literal

OutputType = Literal["answer", "explanation", "list", "table", "report", "comparison", "calculation"]

@dataclass
class Intent:
    output_type: OutputType
    topic: str

CLASSIFY_PROMPT = (
    "Classify the user's question. Return ONLY JSON of the form "
    '{{"output_type":"answer|explanation|list|table|report|comparison|calculation",'
    '"topic":"<short topic>"}}. No explanation.\n\nQuestion: {q}'
)

async def classify_intent(question: str, llm) -> Intent:
    try:
        resp = await llm.chat(
            messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(q=question)}],
            max_tokens=120,
            temperature=0.0,
        )
        match = re.search(r"\{.*\}", resp.content, re.DOTALL)
        if not match:
            return Intent(output_type="answer", topic=question[:80])
        data = json.loads(match.group())
        return Intent(
            output_type=data.get("output_type", "answer"),
            topic=data.get("topic", question[:80]),
        )
    except Exception:
        return Intent(output_type="answer", topic=question[:80])
