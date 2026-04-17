"""
Structured Report Generator — produces audit_report.json from trial balance + profile.

Takes:
  - trial_balance: list of account dicts [{account_name, debit, credit}, ...]
  - profile: audit_profile JSON from AuditProfile model
  - company_info: dict with company_name, period_end, auditor_name, etc.

Returns:
  - Complete audit_report.json dict (matches AuditReportJSON schema)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def generate_audit_report(
    trial_balance: list[dict],
    profile: dict,
    company_info: dict | None = None,
    prior_year_data: list[dict] | None = None,
    tb_categories: dict[str, str] | None = None,
) -> dict:
    """
    Main entry point. Generate a structured audit report JSON.

    Args:
        trial_balance: List of TB rows, each with 'account_name', 'debit', 'credit' (or 'balance')
        profile: The audit_profile JSON from AuditProfile.profile_json
        company_info: Optional overrides for company_name, period_end, auditor_name, currency
        prior_year_data: Optional list of prior-year rows [{account_name, prior_year_value}]
        tb_categories: Optional dict {account_name: category} from trial_balance_mapper for fallback grouping

    Returns:
        dict matching AuditReportJSON schema
    """
    company_info = company_info or {}
    account_mapping = profile.get("account_mapping", {})
    format_template = profile.get("format_template", {})
    requirements = profile.get("custom_requirements", {})

    # Normalize trial balance
    normalized_tb = _normalize_trial_balance(trial_balance)

    # Build prior year lookup {account_name_lower: value}
    prior_lookup = _build_prior_year_lookup(prior_year_data or [])

    # Group accounts using profile mapping + TB category fallback
    grouped = _group_accounts(normalized_tb, account_mapping, tb_categories)

    # Build financial statements (with prior year data)
    financial_statements = _build_financial_statements(grouped, format_template, prior_lookup)

    # Build metadata
    metadata = {
        "report_id": str(uuid.uuid4()),
        "profile_id": company_info.get("profile_id", ""),
        "company_name": company_info.get("company_name", profile.get("client_name", "")),
        "period_end": company_info.get("period_end", profile.get("period_end", "")),
        "currency": company_info.get("currency", requirements.get("currency", "AED")),
        "auditor_name": company_info.get("auditor_name", ""),
        "audit_standard": requirements.get("audit_standard", "ISA"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "is_comparative": bool(prior_lookup),
    }

    # Build auditor opinion
    auditor_opinion = _build_auditor_opinion(requirements)

    # Build notes
    notes = _build_notes(requirements, grouped, metadata, prior_lookup)

    return {
        "metadata": metadata,
        "auditor_opinion": auditor_opinion,
        "financial_statements": financial_statements,
        "notes": notes,
    }


def _normalize_trial_balance(tb: list[dict]) -> list[dict]:
    """Normalize TB rows to consistent format: {account_name, balance}."""
    normalized = []
    for row in tb:
        name = str(row.get("account_name", row.get("Account", row.get("name", "")))).strip()
        if not name:
            continue

        # Calculate balance from debit/credit or use directly
        if "balance" in row:
            balance = _to_float(row["balance"])
        else:
            debit = _to_float(row.get("debit", row.get("Debit", 0)))
            credit = _to_float(row.get("credit", row.get("Credit", 0)))
            balance = debit - credit

        normalized.append({
            "account_name": name,
            "balance": balance,
            "notes_ref": row.get("notes_ref"),
        })

    return normalized


def _to_float(val: Any) -> float:
    """Safely convert value to float."""
    if val is None or val == "" or val == "-":
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("(", "-").replace(")", ""))
    except (ValueError, TypeError):
        return 0.0


def _build_prior_year_lookup(prior_year_data: list[dict]) -> dict[str, float]:
    """Build a case-insensitive lookup dict from prior year extraction rows."""
    lookup: dict[str, float] = {}
    for row in prior_year_data:
        name = str(row.get("account_name", "")).strip()
        val = row.get("prior_year_value", 0)
        if name:
            try:
                lookup[name.lower()] = float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                continue
    return lookup


def _find_prior_year(account_name: str, prior_lookup: dict[str, float]) -> float:
    """Find prior year value using fuzzy name matching."""
    name_lower = account_name.lower().strip()
    # Exact match
    if name_lower in prior_lookup:
        return prior_lookup[name_lower]
    # Skip fuzzy matching for balance-sheet-specific terms that would
    # falsely match P&L entries (e.g. "accumulated depreciation" → "depreciation")
    BS_SKIP_KEYWORDS = {"accumulated", "prepaid", "provision for", "allowance for"}
    if any(kw in name_lower for kw in BS_SKIP_KEYWORDS):
        return 0.0
    # Partial match (prior year data may have slightly different names)
    # Sort by key length descending to prefer longer/more specific matches first
    for key, val in sorted(prior_lookup.items(), key=lambda x: len(x[0]), reverse=True):
        if key in name_lower or name_lower in key:
            return val
    return 0.0


def _group_accounts(
    tb: list[dict], account_mapping: dict, tb_categories: dict[str, str] | None = None,
) -> dict[str, list[dict]]:
    """Group TB accounts into IFRS categories using the profile mapping.

    Falls back to tb_categories from trial_balance_mapper when an account
    isn't covered by the profile mapping.
    """
    # Map TB mapper categories → default IFRS groups
    CATEGORY_TO_IFRS = {
        "revenue": "Revenue",
        "other_income": "Other Income",
        "cost_of_sales": "Cost of Sales",
        "expenses": "Operating Expenses",
        "assets": "Current Assets",
        "assets_current": "Current Assets",
        "assets_non_current": "Non-Current Assets",
        "liabilities": "Current Liabilities",
        "liabilities_current": "Current Liabilities",
        "liabilities_non_current": "Non-Current Liabilities",
        "equity": "Equity",
        "other": "Operating Expenses",
    }

    tb_categories = tb_categories or {}
    groups: dict[str, list[dict]] = {}
    unmapped: list[dict] = []

    def _get_group(mapping_val) -> str | None:
        if isinstance(mapping_val, dict):
            return mapping_val.get("mapped_to")
        if isinstance(mapping_val, str):
            return mapping_val
        return None

    for row in tb:
        name = row["account_name"]
        mapping = account_mapping.get(name)
        group = _get_group(mapping) if mapping is not None else None

        if not group:
            for key, val in account_mapping.items():
                if key.lower() == name.lower():
                    group = _get_group(val)
                    break

        # Fallback to TB mapper category
        if not group and name in tb_categories:
            group = CATEGORY_TO_IFRS.get(tb_categories[name].lower())

        if group:
            groups.setdefault(group, []).append(row)
        else:
            unmapped.append(row)

    if unmapped:
        groups["Unmapped Accounts"] = unmapped

    return groups


def _build_financial_statements(
    grouped: dict, format_template: dict, prior_lookup: dict[str, float] | None = None,
) -> dict:
    """Build SOFP and SOPL from grouped accounts."""
    prior_lookup = prior_lookup or {}

    # Statement of Financial Position (Balance Sheet)
    sofp_sections = []

    # Assets (debit-normal → keep signs)
    asset_groups = ["Current Assets", "Non-Current Assets", "Cash and Cash Equivalents"]
    asset_section_items = []
    for group_name in asset_groups:
        items = grouped.get(group_name, [])
        if items:
            asset_section_items.append(
                _build_statement_section(group_name, items, prior_lookup, credit_normal=False)
            )

    total_assets = sum(
        item["current_year"]
        for section in asset_section_items
        for item in section.get("line_items", [])
    )
    total_assets_prior = sum(
        section["subtotal"]["prior_year"]
        for section in asset_section_items
    )

    # Liabilities (credit-normal → flip signs to positive)
    liability_groups = ["Current Liabilities", "Non-Current Liabilities"]
    liability_section_items = []
    for group_name in liability_groups:
        items = grouped.get(group_name, [])
        if items:
            liability_section_items.append(
                _build_statement_section(group_name, items, prior_lookup, credit_normal=True)
            )

    total_liabilities = sum(
        item["current_year"]
        for section in liability_section_items
        for item in section.get("line_items", [])
    )
    total_liabilities_prior = sum(
        section["subtotal"]["prior_year"]
        for section in liability_section_items
    )

    # Equity (credit-normal → flip signs to positive)
    equity_items = grouped.get("Equity", []) + grouped.get("Retained Earnings", [])
    equity_section = (
        _build_statement_section("Equity", equity_items, prior_lookup, credit_normal=True)
        if equity_items else None
    )

    total_equity = sum(
        item["current_year"]
        for item in (equity_section or {}).get("line_items", [])
    )
    total_equity_prior = (equity_section or {}).get("subtotal", {}).get("prior_year", 0.0)

    sofp = {
        "title": "Statement of Financial Position",
        "sections": asset_section_items + liability_section_items + ([equity_section] if equity_section else []),
        "total": {
            "account_name": "Total Assets",
            "current_year": round(total_assets, 2),
            "prior_year": round(total_assets_prior, 2),
        },
    }

    # Statement of Profit or Loss
    # Revenue and Other Income are credit-normal; expenses are debit-normal
    _CREDIT_NORMAL_PL = {"Revenue", "Other Income"}
    sopl_groups = ["Revenue", "Cost of Sales", "Operating Expenses", "Other Income", "Finance Costs"]
    sopl_sections = []
    for group_name in sopl_groups:
        items = grouped.get(group_name, [])
        if items:
            sopl_sections.append(
                _build_statement_section(
                    group_name, items, prior_lookup,
                    credit_normal=(group_name in _CREDIT_NORMAL_PL),
                )
            )

    # Net Profit = Revenue + Other Income - Cost of Sales - Expenses
    # Credit-normal sections (Revenue, Other Income) contribute positively
    # Debit-normal sections (Cost of Sales, Expenses) contribute negatively
    total_income = 0.0
    total_expense = 0.0
    total_income_prior = 0.0
    total_expense_prior = 0.0
    for section in sopl_sections:
        title = section["title"]
        section_total = section["subtotal"]["current_year"]
        section_prior = section["subtotal"]["prior_year"]
        if title in _CREDIT_NORMAL_PL:
            total_income += section_total
            total_income_prior += section_prior
        else:
            total_expense += section_total
            total_expense_prior += section_prior

    sopl = {
        "title": "Statement of Profit or Loss",
        "sections": sopl_sections,
        "total": {
            "account_name": "Net Profit / (Loss)",
            "current_year": round(total_income - total_expense, 2),
            "prior_year": round(total_income_prior - total_expense_prior, 2),
        },
    }

    # Handle unmapped
    unmapped = grouped.get("Unmapped Accounts", [])

    return {
        "statement_of_financial_position": sofp,
        "statement_of_profit_or_loss": sopl,
        "statement_of_changes_in_equity": None,
        "statement_of_cash_flows": None,
    }


def _build_statement_section(
    title: str, accounts: list[dict], prior_lookup: dict[str, float] | None = None,
    credit_normal: bool = False,
) -> dict:
    """Build a section with line items from account list, including prior year.

    Args:
        credit_normal: If True, negate amounts (balance = debit-credit is negative
            for credit-normal accounts like Revenue/Liabilities/Equity, so flip
            them to positive for display).

    Prior year matching strategy:
    1. Try matching individual account names to prior_lookup.
    2. If no individual matches found, look for a group-level match
       (e.g., "Revenue" section title matches a "Revenue" entry in prior_lookup).
    3. Show group-level total at the subtotal level.
    """
    prior_lookup = prior_lookup or {}
    sign = -1 if credit_normal else 1
    line_items = []
    individual_prior_total = 0.0

    for acc in accounts:
        prior = _find_prior_year(acc["account_name"], prior_lookup)
        individual_prior_total += prior
        line_items.append({
            "account_name": acc["account_name"],
            "notes_ref": acc.get("notes_ref"),
            "current_year": round(acc["balance"] * sign, 2),
            "prior_year": round(prior, 2),
        })

    # Always try group-level match for subtotal (preferred over individual sum
    # for accuracy when authoritative group totals are in prior_lookup).
    group_prior = 0.0
    if prior_lookup:
        group_prior = _find_prior_year(title, prior_lookup)
        if group_prior == 0.0:
            aliases = {
                "Current Assets": ["total current assets", "current assets"],
                "Non-Current Assets": ["total non-current assets", "fixed assets", "property plant equipment"],
                "Current Liabilities": ["total current liabilities", "current liabilities"],
                "Non-Current Liabilities": ["total non-current liabilities", "long term liabilities"],
                "Equity": ["total equity", "shareholders equity", "share capital", "total shareholders equity"],
                "Revenue": ["total revenue", "revenue", "income", "total income"],
                "Cost of Sales": ["cost of sales", "cost of revenue", "cost of goods sold"],
                "Operating Expenses": ["total expenses", "operating expenses", "total operating expenses"],
                "Other Income": ["other income"],
                "Finance Costs": ["finance costs", "interest expense"],
            }
            for alias in aliases.get(title, []):
                group_prior = _find_prior_year(alias, prior_lookup)
                if group_prior != 0.0:
                    break
    # Group total takes precedence when available (more authoritative); fall
    # back to individual sum when no group entry exists.
    subtotal_prior = group_prior if group_prior != 0.0 else individual_prior_total

    subtotal = {
        "account_name": f"Total {title}",
        "current_year": round(sum(a["balance"] for a in accounts) * sign, 2),
        "prior_year": round(subtotal_prior, 2),
    }

    return {
        "title": title,
        "line_items": line_items,
        "subtotal": subtotal,
    }


def _build_auditor_opinion(requirements: dict) -> dict:
    """Build auditor opinion section."""
    opinion_type = requirements.get("opinion_type", "unqualified")

    opinion_texts = {
        "unqualified": (
            "In our opinion, the accompanying financial statements present fairly, "
            "in all material respects, the financial position of the Company as at the "
            "reporting date, and its financial performance and its cash flows for the "
            "year then ended in accordance with International Financial Reporting Standards (IFRS)."
        ),
        "qualified": (
            "In our opinion, except for the effects of the matter described in the "
            "Basis for Qualified Opinion section of our report, the accompanying financial "
            "statements present fairly, in all material respects, the financial position of "
            "the Company in accordance with IFRS."
        ),
    }

    return {
        "opinion_type": opinion_type,
        "opinion_text": opinion_texts.get(opinion_type, opinion_texts["unqualified"]),
        "basis_text": "",
        "key_audit_matters": [],
        "going_concern": requirements.get("going_concern", False),
        "going_concern_note": "",
    }


def _build_notes(
    requirements: dict, grouped: dict, metadata: dict,
    prior_lookup: dict[str, float] | None = None,
) -> dict:
    """Build notes to financial statements."""
    company = metadata.get("company_name", "the Company")
    currency = metadata.get("currency", "AED")

    accounting_policies = (
        f"1. General Information\n"
        f"{company} is incorporated and domiciled in the United Arab Emirates. "
        f"The financial statements are presented in {currency}.\n\n"
        f"2. Basis of Preparation\n"
        f"These financial statements have been prepared in accordance with "
        f"International Financial Reporting Standards (IFRS) as issued by the "
        f"International Accounting Standards Board (IASB).\n\n"
        f"3. Summary of Material Accounting Policies\n"
        f"Revenue is recognised when control of goods or services is transferred "
        f"to the customer. Property, plant and equipment are stated at cost less "
        f"accumulated depreciation."
    )

    critical_estimates = (
        f"The preparation of financial statements requires management to make "
        f"judgements, estimates and assumptions that affect the application of "
        f"accounting policies and the reported amounts of assets, liabilities, "
        f"income and expenses. Actual results may differ from these estimates."
    )

    # Generate note sections for each group
    prior_lookup = prior_lookup or {}
    note_sections = []
    note_num = 4
    for group_name, accounts in grouped.items():
        if group_name == "Unmapped Accounts":
            continue
        total = sum(a["balance"] for a in accounts)
        total_prior = sum(
            _find_prior_year(a["account_name"], prior_lookup) for a in accounts
        )
        detail_lines = []
        for a in accounts:
            prior = _find_prior_year(a["account_name"], prior_lookup)
            line = f"  - {a['account_name']}: {currency} {abs(a['balance']):,.2f}"
            if prior != 0.0:
                line += f" (Prior: {currency} {abs(prior):,.2f})"
            detail_lines.append(line)
        content = f"Total {group_name}: {currency} {abs(total):,.2f}"
        if total_prior != 0.0:
            content += f" (Prior: {currency} {abs(total_prior):,.2f})"
        content += "\n\n" + "\n".join(detail_lines)
        note_sections.append({
            "note_number": note_num,
            "title": group_name,
            "content": content,
        })
        note_num += 1

    return {
        "accounting_policies": accounting_policies,
        "critical_estimates": critical_estimates,
        "sections": note_sections,
    }
