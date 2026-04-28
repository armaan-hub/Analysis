import difflib
import json
import logging
import os
import re
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


try:
    _FUZZY_CUTOFF: float = float(os.environ.get("FUZZY_CUTOFF", "0.78"))
except (ValueError, TypeError):
    _FUZZY_CUTOFF = 0.78

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "vat": [
        "vat", "value added tax", "tax invoice", "input tax", "output tax",
        "zero rating", "hotel apartment", "commercial property", "trn",
        "reverse charge", "excise", "zero rated", "exempt supply",
    ],
    "corporate_tax": [
        "corporate tax", "corporate", "ct", "qualifying income", "free zone",
        "transfer pricing", "permanent establishment", "withholding tax",
        "corporate income", "taxable income", "small business relief",
    ],
    "peppol": [
        "peppol", "peppol bis", "peppol network", "access point", "peppol id",
    ],
    "e_invoicing": [
        "e-invoice", "einvoice", "electronic invoice", "e invoicing",
        "e invoice", "digital invoice",
    ],
    "labour": [
        "labour", "labor", "employment", "visa", "gratuity", "termination",
        "end of service", "worker", "employee", "wages", "mohre", "wps",
    ],
    "commercial": [
        "commercial", "company law", "llc", "partnership", "trading licence",
        "commercial register", "agency", "licensing", "business setup",
    ],
    "ifrs": [
        "ifrs", "ias", "financial statement", "accounting standard",
        "consolidation", "revenue recognition", "lease", "impairment",
        "fair value", "disclosure",
    ],
    "general_law": [
        "wills", "will and testament", "inheritance", "inherit",
        "probate", "testator", "beneficiary", "estate planning",
        "succession", "guardian appointment",
    ],
}

# Flat list of (keyword, domain) pairs for difflib matching
_FLAT_KEYWORDS: list[tuple[str, str]] = [
    (kw, domain)
    for domain, kws in _DOMAIN_KEYWORDS.items()
    for kw in kws
]

_FLAT_KEYWORDS_SORTED: list[tuple[str, str]] = sorted(
    _FLAT_KEYWORDS, key=lambda x: -len(x[0])
)
_FLAT_KW_LIST: list[str] = [kw for kw, _ in _FLAT_KEYWORDS]
_KW_TO_DOMAIN: dict[str, str] = {kw: domain for kw, domain in _FLAT_KEYWORDS}

_FUZZY_STOPWORDS: frozenset[str] = frozenset({"will", "may", "can", "has", "had"})


def _word_boundary_match(kw: str, text: str) -> bool:
    """Return True if kw appears as a whole-word match in text."""
    pattern = r'(?<!\w)' + re.escape(kw) + r'(?!\w)'
    return bool(re.search(pattern, text))


def _fuzzy_classify_query(query: str) -> "ClassifierResult | None":
    """Classify query using exact keyword match, then difflib fuzzy matching.

    Returns ClassifierResult on match, None if no domain can be inferred.
    Exact multi-word matches return confidence 0.8.
    Fuzzy single-word matches return confidence 0.7.
    """
    lower = query.lower()

    # Pass 1: word-boundary-aware match (longest keywords first)
    for kw, domain in _FLAT_KEYWORDS_SORTED:
        if _word_boundary_match(kw, lower):
            return ClassifierResult(
                domain=DomainLabel(domain), confidence=0.8, alternatives=[]
            )

    # Pass 2: difflib fuzzy match on individual query words
    for word in lower.split():
        if len(word) < 3 or word in _FUZZY_STOPWORDS:
            continue
        matches = difflib.get_close_matches(word, _FLAT_KW_LIST, n=1, cutoff=_FUZZY_CUTOFF)
        if matches:
            matched_kw = matches[0]
            # Reject if length ratio is too low — prevents substring false-positives
            # e.g. "release" should not fuzzy-match the keyword "lease"
            min_len = min(len(word), len(matched_kw))
            max_len = max(len(word), len(matched_kw))
            if min_len / max_len < 0.75:
                continue
            matched_domain = _KW_TO_DOMAIN[matched_kw]
            return ClassifierResult(
                domain=DomainLabel(matched_domain), confidence=0.7, alternatives=[]
            )

    return None


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
        
        # Keyword + fuzzy fallback
        fuzzy_result = _fuzzy_classify_query(query)
        if fuzzy_result:
            return fuzzy_result

        return ClassifierResult(
            domain=DomainLabel.GENERAL_LAW, confidence=0.3, alternatives=[]
        )
