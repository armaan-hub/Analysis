"""
Trial Balance Classifier — detects high-risk accounts using hard-coded rules
and optionally a trained Random Forest model.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Hard-coded risk keywords per category
_HIGH_RISK_KEYWORDS: dict[str, list[str]] = {
    "Cash and Cash Equivalents": ["cash", "petty cash", "bank"],
    "Trade Receivables": ["receivable", "debtor", "ar"],
    "Retained Earnings": ["retained", "accumulated"],
    "Revenue": ["revenue", "sales", "income", "turnover"],
    "Related Party": ["related party", "director loan", "shareholder loan"],
}

_CONCENTRATION_THRESHOLD = 0.40  # >40% of total abs value = concentration risk


def classify_risks(rows: list[dict]) -> list[dict]:
    """
    Classify each TB row for audit risk.

    Args:
        rows: list of {"account": str, "mappedTo": str, "amount": float}

    Returns:
        Same list with an added "risk" key: "high" | "medium" | "low"
    """
    total_abs = sum(abs(r.get("amount", 0)) for r in rows) or 1.0
    result = []
    for row in rows:
        account = (row.get("account") or "").lower()
        category = (row.get("mappedTo") or "").lower()
        amount = row.get("amount", 0)
        risk = "low"

        # Concentration risk
        if abs(amount) / total_abs > _CONCENTRATION_THRESHOLD:
            risk = "high"

        # Keyword-based risk rules
        if risk != "high":
            for _cat, keywords in _HIGH_RISK_KEYWORDS.items():
                if any(kw in account or kw in category for kw in keywords):
                    risk = "medium" if risk == "low" else risk
                    break

        # Related party is always high
        for kw in _HIGH_RISK_KEYWORDS["Related Party"]:
            if kw in account:
                risk = "high"
                break

        result.append({**row, "risk": risk})

    return result


def get_risk_summary(classified_rows: list[dict]) -> dict[str, int]:
    """Return counts of high/medium/low risks."""
    summary: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for row in classified_rows:
        risk = row.get("risk", "low")
        if risk in summary:
            summary[risk] += 1
    return summary


_VARIANCE_THRESHOLD = 0.20  # >20% year-on-year change = elevated risk


def classify_with_prior_year(
    current_rows: list[dict],
    prior_year_rows: list[dict],
) -> list[dict]:
    """
    Classify TB rows using year-on-year variance analysis as an override.

    Accounts with >20% YoY variance are elevated to at least 'medium' risk;
    accounts with >50% variance or sign change are elevated to 'high'.

    Args:
        current_rows: Current year TB rows (same format as classify_risks input)
        prior_year_rows: Prior year TB rows (matched by 'account' key)

    Returns:
        current_rows with 'risk' and 'yoy_variance_pct' keys added.
    """
    # Build a lookup from account name → prior year amount
    prior_lookup: dict[str, float] = {}
    for row in prior_year_rows:
        account = (row.get("account") or row.get("account_name") or "").strip()
        if account:
            prior_lookup[account.lower()] = float(row.get("amount", row.get("net", 0)))

    # Start with the standard rule-based classification
    classified = classify_risks(current_rows)

    result = []
    for row in classified:
        account_lc = (row.get("account") or "").lower()
        current_amount = float(row.get("amount", 0))
        prior_amount = prior_lookup.get(account_lc)

        yoy_variance_pct: float | None = None
        if prior_amount is not None and prior_amount != 0:
            yoy_variance_pct = (current_amount - prior_amount) / abs(prior_amount)
            sign_change = (current_amount >= 0) != (prior_amount >= 0)

            if sign_change or abs(yoy_variance_pct) > 0.50:
                row = {**row, "risk": "high"}
            elif abs(yoy_variance_pct) > _VARIANCE_THRESHOLD and row["risk"] == "low":
                row = {**row, "risk": "medium"}
        elif prior_amount is None:
            # New account with no prior year — flag as medium (new transactions need scrutiny)
            if row["risk"] == "low":
                row = {**row, "risk": "medium"}

        result.append({**row, "yoy_variance_pct": yoy_variance_pct})

    return result


# Optional: Random Forest classifier (trained on labeled data)
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    import numpy as np

    class TBClassifier:
        """Random Forest classifier for TB risk levels."""

        def __init__(self) -> None:
            self._clf = RandomForestClassifier(n_estimators=100, random_state=42)
            self._le = LabelEncoder()
            self._trained = False

        def fit(self, rows: list[dict], labels: list[str]) -> None:
            X = self._featurise(rows)
            y = self._le.fit_transform(labels)
            self._clf.fit(X, y)
            self._trained = True

        def predict(self, rows: list[dict]) -> list[str]:
            if not self._trained:
                # Fall back to rule-based classifier
                return [r.get("risk", "low") for r in classify_risks(rows)]
            X = self._featurise(rows)
            encoded = self._clf.predict(X)
            return list(self._le.inverse_transform(encoded))

        @staticmethod
        def _featurise(rows: list[dict]) -> "np.ndarray":
            total_abs = sum(abs(r.get("amount", 0)) for r in rows) or 1.0
            feats = []
            for row in rows:
                amount = float(row.get("amount", 0))
                feats.append([
                    abs(amount) / total_abs,          # concentration ratio
                    1.0 if amount < 0 else 0.0,       # is credit
                    abs(amount),                      # absolute amount
                ])
            return np.array(feats, dtype=float)

except ImportError:
    logger.warning("scikit-learn not installed — TBClassifier unavailable; using rule-based fallback only.")
    TBClassifier = None  # type: ignore[assignment,misc]


# ── Full trial balance analysis ───────────────────────────────────────────────

_RELATED_PARTY_KEYWORDS = ["shareholder", "director loan", "related party", "owner"]


def analyze_trial_balance(rows: list[dict], company_info: dict | None = None) -> dict:
    """
    Perform a full analysis of a trial balance: grouping, risk flags, financial ratios.

    Args:
        rows: list of dicts with keys "account", "mappedTo" (or "mapped_to"), "amount".
              May also contain "yoy_variance_pct" (added by classify_with_prior_year).
        company_info: optional dict. Supported key:
            - "share_capital": float — used for the going_concern accumulated-losses check.

    Returns:
        {
            "grouping": [{"account": str, "mapped_to": str, "amount": float, "risk": str}],
            "risk_flags": [{"flag": str, "triggered": bool, "detail": str}],
            "financial_ratios": {
                "current_ratio": float | None,
                "debt_to_equity": float | None,
                "gross_margin": float | None,
            }
        }
    """
    if company_info is None:
        company_info = {}

    # Normalise field names: accept both "mappedTo" and "mapped_to"
    normalised: list[dict] = []
    for r in rows:
        mapped = r.get("mappedTo") or r.get("mapped_to") or ""
        normalised.append({
            "account": r.get("account", ""),
            "mappedTo": mapped,
            "amount": float(r.get("amount", 0)),
            "yoy_variance_pct": r.get("yoy_variance_pct"),
        })

    classified = classify_risks(normalised)

    # Build grouping with snake_case output keys
    grouping = [
        {
            "account": r["account"],
            "mapped_to": r["mappedTo"],
            "amount": r["amount"],
            "risk": r["risk"],
        }
        for r in classified
    ]

    # Aggregate amounts by category
    category_totals: dict[str, float] = {}
    for r in classified:
        cat = r["mappedTo"]
        category_totals[cat] = category_totals.get(cat, 0.0) + r["amount"]

    # ── Financial Ratios ──────────────────────────────────────────────────────
    current_assets = (
        category_totals.get("Current Assets", 0.0)
        + category_totals.get("Cash and Cash Equivalents", 0.0)
    )
    current_liabilities = abs(category_totals.get("Current Liabilities", 0.0))
    non_current_liabilities = abs(category_totals.get("Non-Current Liabilities", 0.0))
    total_liabilities = current_liabilities + non_current_liabilities
    equity = (
        category_totals.get("Equity", 0.0)
        + category_totals.get("Retained Earnings", 0.0)
    )
    revenue = category_totals.get("Revenue", 0.0)
    cost_of_sales = abs(category_totals.get("Cost of Sales", 0.0))

    current_ratio: float | None = None
    if current_liabilities != 0:
        current_ratio = round(current_assets / current_liabilities, 4)

    debt_to_equity: float | None = None
    if equity != 0:
        debt_to_equity = round(total_liabilities / equity, 4)

    gross_margin: float | None = None
    if revenue != 0:
        gross_margin = round((revenue - cost_of_sales) / revenue, 4)

    # ── Risk Flags (hard-coded rules only) ────────────────────────────────────
    risk_flags: list[dict] = []

    # 1. Going concern: current ratio < 1.0 OR accumulated losses > 50% of share capital
    going_concern_triggered = False
    going_concern_parts: list[str] = []

    if current_ratio is not None and current_ratio < 1.0:
        going_concern_triggered = True
        going_concern_parts.append(f"Current ratio {current_ratio:.2f} is below 1.0")

    share_capital = float(company_info.get("share_capital", 0.0))
    retained = category_totals.get("Retained Earnings", 0.0)
    if retained < 0 and share_capital > 0 and abs(retained) > 0.5 * share_capital:
        going_concern_triggered = True
        going_concern_parts.append(
            f"Accumulated losses ({abs(retained):,.2f}) exceed 50% of share capital ({share_capital:,.2f})"
        )

    risk_flags.append({
        "flag": "going_concern",
        "triggered": going_concern_triggered,
        "detail": "; ".join(going_concern_parts) if going_concern_parts else "No going concern indicators detected",
    })

    # 2. Related party: any account name contains related-party keywords
    related_accounts = [
        r["account"] for r in classified
        if any(kw in r["account"].lower() for kw in _RELATED_PARTY_KEYWORDS)
    ]
    risk_flags.append({
        "flag": "related_party",
        "triggered": bool(related_accounts),
        "detail": (
            f"Related party accounts detected: {', '.join(related_accounts)}"
            if related_accounts
            else "No related party accounts detected"
        ),
    })

    # 3. Large variance: YoY change > 40% on amounts > AED 100,000
    large_variance_accounts = [
        f"{r['account']} ({r['yoy_variance_pct'] * 100:.1f}%)"
        for r in classified
        if r.get("yoy_variance_pct") is not None
        and abs(r["yoy_variance_pct"]) > 0.40
        and abs(r["amount"]) > 100_000
    ]
    risk_flags.append({
        "flag": "large_variance",
        "triggered": bool(large_variance_accounts),
        "detail": (
            f"Accounts with >40% YoY variance (>AED 100,000): {', '.join(large_variance_accounts)}"
            if large_variance_accounts
            else "No large YoY variances detected"
        ),
    })

    # 4. Negative equity: total equity (capital + retained earnings) < 0
    risk_flags.append({
        "flag": "negative_equity",
        "triggered": equity < 0,
        "detail": (
            f"Total equity is {equity:,.2f} (negative)"
            if equity < 0
            else f"Total equity is {equity:,.2f} (positive)"
        ),
    })

    return {
        "grouping": grouping,
        "risk_flags": risk_flags,
        "financial_ratios": {
            "current_ratio": current_ratio,
            "debt_to_equity": debt_to_equity,
            "gross_margin": gross_margin,
        },
    }


# ── IFRS category → section key mapping ──────────────────────────────────────

_IFRS_SECTION_MAP: dict[str, str] = {
    "Current Assets": "current_assets",
    "current assets": "current_assets",
    "Non-Current Assets": "non_current_assets",
    "non-current assets": "non_current_assets",
    "Fixed Assets": "non_current_assets",
    "Current Liabilities": "current_liabilities",
    "current liabilities": "current_liabilities",
    "Non-Current Liabilities": "non_current_liabilities",
    "non-current liabilities": "non_current_liabilities",
    "Equity": "equity",
    "equity": "equity",
    "Retained Earnings": "equity",
    "Revenue": "revenue",
    "revenue": "revenue",
    "Income": "revenue",
    "Cost of Sales": "cost_of_sales",
    "cost of sales": "cost_of_sales",
    "Operating Expenses": "operating_expenses",
    "operating expenses": "operating_expenses",
    "Finance Costs": "finance_costs",
    "Other Income": "other_income",
    "Input VAT": "current_assets",
    "Output VAT": "current_liabilities",
    "Cash and Cash Equivalents": "current_assets",
}

_SECTION_LABELS: dict[str, str] = {
    "non_current_assets": "Non-Current Assets",
    "current_assets": "Current Assets",
    "current_liabilities": "Current Liabilities",
    "non_current_liabilities": "Non-Current Liabilities",
    "equity": "Equity",
    "revenue": "Revenue",
    "cost_of_sales": "Cost of Sales",
    "operating_expenses": "Operating Expenses",
    "finance_costs": "Finance Costs",
    "other_income": "Other Income / (Expense)",
    "unclassified": "Other",
}

_SOFP_ORDER = [
    "non_current_assets", "current_assets",
    "current_liabilities", "non_current_liabilities",
    "equity",
]

_SOPL_ORDER = [
    "revenue", "cost_of_sales", "operating_expenses",
    "finance_costs", "other_income",
]


def group_tb_for_ifrs(tb_data: list[dict]) -> dict:
    """
    Group trial balance rows into IFRS financial statement sections.
    Input rows: {account, mappedTo, amount}. Returns section_key → {label, rows, total}.
    """
    sections: dict[str, dict] = {}

    for row in tb_data:
        mapped = row.get("mappedTo", "") or ""
        amount = float(row.get("amount", 0) or 0)

        section_key = _IFRS_SECTION_MAP.get(mapped)
        if not section_key:
            for k, v in _IFRS_SECTION_MAP.items():
                if k.lower() == mapped.lower():
                    section_key = v
                    break
        if not section_key:
            section_key = "unclassified"

        if section_key not in sections:
            sections[section_key] = {
                "label": _SECTION_LABELS.get(section_key, mapped),
                "rows": [],
                "total": 0.0,
            }

        sections[section_key]["rows"].append({
            "account": row.get("account", ""),
            "amount": amount,
        })
        sections[section_key]["total"] += amount

    for key, sec in sections.items():
        sec["total"] = abs(sec["total"])

    total_assets = (
        sections.get("non_current_assets", {}).get("total", 0)
        + sections.get("current_assets", {}).get("total", 0)
    )
    total_liabilities = (
        sections.get("current_liabilities", {}).get("total", 0)
        + sections.get("non_current_liabilities", {}).get("total", 0)
    )
    total_equity = sections.get("equity", {}).get("total", 0)
    gross_profit = (
        sections.get("revenue", {}).get("total", 0)
        - sections.get("cost_of_sales", {}).get("total", 0)
    )
    net_profit = (
        gross_profit
        - sections.get("operating_expenses", {}).get("total", 0)
        - sections.get("finance_costs", {}).get("total", 0)
        + sections.get("other_income", {}).get("total", 0)
    )

    sections["_totals"] = {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_and_equity": total_liabilities + total_equity,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
    }

    return sections


def format_ifrs_for_llm(grouped: dict) -> str:
    """Format grouped IFRS data as readable text for the LLM prompt."""
    lines = []

    lines.append("=== STATEMENT OF FINANCIAL POSITION ===")
    for key in _SOFP_ORDER:
        sec = grouped.get(key)
        if not sec:
            continue
        lines.append(f"\n{sec['label'].upper()}")
        for row in sec["rows"]:
            lines.append(f"  {row['account']:<45} AED {abs(row['amount']):>15,.0f}")
        lines.append(f"  {'Total ' + sec['label']:<45} AED {sec['total']:>15,.0f}")

    t = grouped.get("_totals", {})
    lines.append(f"\n  {'TOTAL ASSETS':<45} AED {t.get('total_assets', 0):>15,.0f}")
    lines.append(f"  {'TOTAL LIABILITIES':<45} AED {t.get('total_liabilities', 0):>15,.0f}")
    lines.append(f"  {'TOTAL EQUITY':<45} AED {t.get('total_equity', 0):>15,.0f}")
    lines.append(f"  {'TOTAL LIABILITIES AND EQUITY':<45} AED {t.get('total_liabilities_and_equity', 0):>15,.0f}")

    lines.append("\n=== STATEMENT OF PROFIT OR LOSS ===")
    for key in _SOPL_ORDER:
        sec = grouped.get(key)
        if not sec:
            continue
        lines.append(f"\n{sec['label'].upper()}")
        for row in sec["rows"]:
            lines.append(f"  {row['account']:<45} AED {abs(row['amount']):>15,.0f}")
        lines.append(f"  {'Total ' + sec['label']:<45} AED {sec['total']:>15,.0f}")

    lines.append(f"\n  {'GROSS PROFIT':<45} AED {t.get('gross_profit', 0):>15,.0f}")
    lines.append(f"  {'NET PROFIT / (LOSS)':<45} AED {t.get('net_profit', 0):>15,.0f}")

    return "\n".join(lines)
