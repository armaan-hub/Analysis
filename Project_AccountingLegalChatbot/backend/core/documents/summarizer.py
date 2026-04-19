"""Document summarization using LLM."""
import json
import logging
from pydantic import BaseModel
from core.llm_manager import get_llm_provider

logger = logging.getLogger(__name__)


class DocSummary(BaseModel):
    summary: str
    key_terms: list[str]


async def _llm_complete(text: str) -> str:
    """Call LLM to generate a summary and key terms."""
    system = (
        "Summarize the following document text in 3-5 lines (max 60 words). "
        "Then list exactly 5 key terms. "
        'Respond ONLY with JSON: {"summary": "...", "key_terms": ["...", ...]}'
    )
    llm = get_llm_provider()
    resp = await llm.chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": text[:8000]},
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return resp.content


async def summarize_document_text(text: str) -> DocSummary:
    """Summarize document text and extract key terms."""
    raw = await _llm_complete(text)
    try:
        # Strip markdown fencing if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        return DocSummary(
            summary=data["summary"],
            key_terms=list(data["key_terms"])[:5],
        )
    except Exception as e:
        logger.warning("summarize failed: %s", e)
        return DocSummary(summary="Summary unavailable.", key_terms=[])
