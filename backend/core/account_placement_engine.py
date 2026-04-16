"""
Account Placement Engine — classifies trial balance accounts into the correct
audit report sections using the prior year template as reference.

New accounts (not in the prior year template) are classified by LLM with
confidence scoring.  Falls back to keyword-based classification when LLM
is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from core.llm_manager import get_llm_provider

logger = logging.getLogger(__name__)

# ── Name normalisation ────────────────────────────────────────────────────────

_STRIP_TOKENS = {"a/c", "ac", "account", "acct"}


def _normalise_name(raw: str) -> str:
    """Lower-case, strip, remove 'a/c' and special chars, collapse spaces."""
    s = raw.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)          # remove special chars
    tokens = s.split()
    tokens = [t for t in tokens if t not in _STRIP_TOKENS]
    return " ".join(tokens).strip()


# ── Template lookup builder ───────────────────────────────────────────────────

def _build_template_lookup(
    account_grouping: dict[str, list[dict]],
) -> dict[str, dict]:
    """
    Build a normalised-name → {section, indent_level} lookup from the
    template's account_grouping.
    """
    lookup: dict[str, dict] = {}
    for section_title, account_list in account_grouping.items():
        for entry in account_list:
            name = entry.get("account_name", "")
            if not name:
                continue
            norm = _normalise_name(name)
            if norm:
                lookup[norm] = {
                    "section": section_title,
                    "indent_level": entry.get("indent_level", 1),
                }
    return lookup


# ── Fuzzy matching ────────────────────────────────────────────────────────────

def _token_overlap_ratio(a: str, b: str) -> float:
    """Jaccard-like token overlap between two normalised strings."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _fuzzy_find(
    norm_name: str,
    lookup: dict[str, dict],
    threshold: float = 0.50,
) -> Optional[dict]:
    """
    Return the best fuzzy match from the lookup if token overlap ≥ threshold.
    Returns dict with section, indent_level keys or None.
    """
    best_score = 0.0
    best_match: Optional[dict] = None

    for template_name, info in lookup.items():
        # substring containment check
        if norm_name in template_name or template_name in norm_name:
            return info

        score = _token_overlap_ratio(norm_name, template_name)
        if score > best_score:
            best_score = score
            best_match = info

    if best_score >= threshold:
        return best_match
    return None


# ── LLM classification ───────────────────────────────────────────────────────

def _build_llm_prompt(
    account_name: str,
    category: str,
    account_grouping: dict[str, list[dict]],
) -> str:
    """Build the LLM classification prompt."""
    sections_block = ""
    for section, accounts in account_grouping.items():
        names = [a.get("account_name", "") for a in accounts if a.get("account_name")]
        sections_block += f"\n{section}:\n"
        for n in names:
            sections_block += f"  - {n}\n"

    return (
        "You are a senior chartered accountant. Given the following section "
        "structure from a prior year audit:\n"
        f"{sections_block}\n"
        "Classify this NEW account into the correct section:\n"
        f'Account Name: "{account_name}"\n'
        f'Account Category: "{category}"\n\n'
        'Respond ONLY with JSON: {"section": "section_title", '
        '"indent_level": 0, "confidence": 0.0, "reasoning": "brief explanation"}'
    )


async def _llm_classify(
    account_name: str,
    category: str,
    account_grouping: dict[str, list[dict]],
) -> Optional[dict]:
    """
    Ask the LLM to classify a single account.  Returns parsed dict or None
    on any failure.
    """
    prompt = _build_llm_prompt(account_name, category, account_grouping)
    try:
        llm = get_llm_provider()
        resp = await llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )
        raw = resp.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        # Validate required keys
        if "section" not in result:
            return None
        return {
            "section": result["section"],
            "indent_level": int(result.get("indent_level", 1)),
            "confidence": float(result.get("confidence", 0.70)),
            "reasoning": result.get("reasoning", ""),
        }
    except Exception as exc:
        logger.warning("LLM classification failed for '%s': %s", account_name, exc)
        return None


# ── Keyword fallback (from trial_balance_mapper categories) ───────────────────

_CATEGORY_TO_SECTION: dict[str, str] = {
    "assets": "Assets",
    "liabilities": "Liabilities",
    "equity": "Equity",
    "revenue": "Revenue",
    "expenses": "Expenses",
    "other": "Other",
}


def _keyword_fallback(category: str) -> dict:
    """Last-resort classification based on the account's category field."""
    section = _CATEGORY_TO_SECTION.get(category, "Other")
    return {
        "section": section,
        "indent_level": 1,
        "confidence": 0.50,
        "placement_method": "keyword_fallback",
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def place_accounts_with_template(
    accounts: list[dict],
    template: dict,
) -> list[dict]:
    """
    Classify each trial balance account into the correct audit section
    using the prior year template as reference.

    Args:
        accounts: list of trial balance rows, each with at minimum:
            {"account_name": str, "account_code": str|None,
             "debit": float, "credit": float, "net": float, "category": str}
        template: the template dict from DocumentFormatAnalyzer, containing
            "account_grouping" key mapping section titles → account lists

    Returns:
        list of accounts, each augmented with:
            {"section": str, "indent_level": int, "confidence": float,
             "placement_method": str, "needs_review": bool}
    """
    if not accounts:
        return []

    account_grouping: dict[str, list[dict]] = template.get("account_grouping", {})
    lookup = _build_template_lookup(account_grouping)

    results: list[dict] = []

    for acct in accounts:
        acct_name = acct.get("account_name", "")
        category = acct.get("category", "other")
        norm = _normalise_name(acct_name)

        enriched = dict(acct)  # shallow copy

        # 1. Exact match
        if norm and norm in lookup:
            info = lookup[norm]
            enriched.update({
                "section": info["section"],
                "indent_level": info["indent_level"],
                "confidence": 0.95,
                "placement_method": "template_match",
            })
        else:
            # 2. Fuzzy match
            fuzzy = _fuzzy_find(norm, lookup) if norm else None
            if fuzzy is not None:
                enriched.update({
                    "section": fuzzy["section"],
                    "indent_level": fuzzy["indent_level"],
                    "confidence": 0.85,
                    "placement_method": "fuzzy_match",
                })
            else:
                # 3. LLM classification
                llm_result = await _llm_classify(
                    acct_name, category, account_grouping,
                )
                if llm_result is not None:
                    enriched.update({
                        "section": llm_result["section"],
                        "indent_level": llm_result["indent_level"],
                        "confidence": llm_result["confidence"],
                        "placement_method": "llm_classification",
                    })
                else:
                    # 4. Keyword fallback
                    fb = _keyword_fallback(category)
                    enriched.update(fb)

        # Flag for review if confidence < 0.80
        enriched["needs_review"] = enriched.get("confidence", 0) < 0.80

        results.append(enriched)

    return results
