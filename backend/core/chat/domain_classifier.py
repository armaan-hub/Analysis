import json
import logging
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from core.llm_manager import get_llm_provider

logger = logging.getLogger(__name__)
_PROMPT_PATH = Path(__file__).parent / "prompts" / "domain_classifier.md"


class DomainLabel(str, Enum):
    VAT = "vat"
    CORPORATE_TAX = "corporate_tax"
    PEPPOL = "peppol"
    E_INVOICING = "e_invoicing"
    LABOUR = "labour"
    COMMERCIAL = "commercial"
    IFRS = "ifrs"
    GENERAL_LAW = "general_law"


class ClassifierResult(BaseModel):
    domain: DomainLabel
    confidence: float
    alternatives: list[tuple[DomainLabel, float]]


async def _llm_complete(user_query: str) -> str:
    """Call LLM with the classifier prompt. Return raw text."""
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    llm = get_llm_provider(mode="fast")  # simple classification — fast model is sufficient
    resp = await llm.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    return resp.content


async def classify_domain(query: str) -> ClassifierResult:
    """Classify a user query into a UAE domain. Falls back to GENERAL_LAW on error."""
    try:
        raw = await _llm_complete(query)
        # Strip any markdown fencing the LLM may have added
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        parsed = json.loads(raw)
        domain = DomainLabel(parsed["domain"])
        confidence = float(parsed.get("confidence", 0.0))
        alts = [
            (DomainLabel(label), float(score))
            for label, score in parsed.get("alternatives", [])
        ]
        return ClassifierResult(domain=domain, confidence=confidence, alternatives=alts)
    except Exception as e:
        logger.warning("Domain classifier failed, falling back to general_law: %s", e)
        return ClassifierResult(
            domain=DomainLabel.GENERAL_LAW, confidence=0.3, alternatives=[]
        )
