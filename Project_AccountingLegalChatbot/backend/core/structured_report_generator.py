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
) -> dict:
    """
    Main entry point. Generate a structured audit report JSON.

    Args:
        trial_balance: List of TB rows, each with 'account_name', 'debit', 'credit' (or 'balance')
        profile: The audit_profile JSON from AuditProfile.profile_json
        company_info: Optional overrides for company_name, period_end, auditor_name, currency

    Returns:
        dict matching AuditReportJSON schema
    """
    company_info = company_info or {}
    account_mapping = profile.get("account_mapping", {})
    format_template = profile.get("format_template", {})
    requirements = profile.get("custom_requirements", {})

    # Normalize trial balance
    normalized_tb = _normalize_trial_balance(trial_balance)

    # Group accounts using profile mapping
    grouped = _group_accounts(normalized_tb, account_mapping)

    # Build financial statements
    financial_statements = _build_financial_statements(grouped, format_template)

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
    }

    # Build auditor opinion
    auditor_opinion = _build_auditor_opinion(requirements)

    # Build notes
    notes = _build_notes(requirements, grouped, metadata)

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


def _group_accounts(tb: list[dict], account_mapping: dict) -> dict[str, list[dict]]:
    """Group TB accounts into IFRS categories using the profile mapping."""
    groups: dict[str, list[dict]] = {}
    unmapped: list[dict] = []

    for row in tb:
        name = row["account_name"]
        mapping = account_mapping.get(name, {})
        group = mapping.get("mapped_to")

        if not group:
            # Try case-insensitive lookup
            for key, val in account_mapping.items():
                if key.lower() == name.lower():
                    group = val.get("mapped_to")
                    break

        if group:
            groups.setdefault(group, []).append(row)
        else:
            unmapped.append(row)

    if unmapped:
        groups["Unmapped Accounts"] = unmapped

    return groups


def _build_financial_statements(grouped: dict, format_template: dict) -> dict:
    """Build SOFP and SOPL from grouped accounts."""

    # Statement of Financial Position (Balance Sheet)
    sofp_sections = []

    # Assets
    asset_groups = ["Current Assets", "Non-Current Assets", "Cash and Cash Equivalents"]
    asset_section_items = []
    for group_name in asset_groups:
        items = grouped.get(group_name, [])
        if items:
            asset_section_items.append(_build_statement_section(group_name, items))

    total_assets = sum(
        item["current_year"]
        for section in asset_section_items
        for item in section.get("line_items", [])
    )

    # Liabilities
    liability_groups = ["Current Liabilities", "Non-Current Liabilities"]
    liability_section_items = []
    for group_name in liability_groups:
        items = grouped.get(group_name, [])
        if items:
            liability_section_items.append(_build_statement_section(group_name, items))

    total_liabilities = sum(
        abs(item["current_year"])
        for section in liability_section_items
        for item in section.get("line_items", [])
    )

    # Equity
    equity_items = grouped.get("Equity", []) + grouped.get("Retained Earnings", [])
    equity_section = _build_statement_section("Equity", equity_items) if equity_items else None

    total_equity = sum(
        abs(item["current_year"])
        for item in (equity_section or {}).get("line_items", [])
    )

    sofp = {
        "title": "Statement of Financial Position",
        "sections": asset_section_items + liability_section_items + ([equity_section] if equity_section else []),
        "total": {
            "account_name": "Total Assets",
            "current_year": round(total_assets, 2),
            "prior_year": 0.0,
        },
    }

    # Statement of Profit or Loss
    sopl_groups = ["Revenue", "Cost of Sales", "Operating Expenses", "Other Income", "Finance Costs"]
    sopl_sections = []
    for group_name in sopl_groups:
        items = grouped.get(group_name, [])
        if items:
            sopl_sections.append(_build_statement_section(group_name, items))

    total_revenue = sum(
        abs(item["current_year"])
        for item in (sopl_sections[0] if sopl_sections else {}).get("line_items", [])
    )
    total_expenses = sum(
        abs(item["current_year"])
        for section in sopl_sections[1:]
        for item in section.get("line_items", [])
    )

    sopl = {
        "title": "Statement of Profit or Loss",
        "sections": sopl_sections,
        "total": {
            "account_name": "Net Profit / (Loss)",
            "current_year": round(total_revenue - total_expenses, 2),
            "prior_year": 0.0,
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


def _build_statement_section(title: str, accounts: list[dict]) -> dict:
    """Build a section with line items from account list."""
    line_items = []
    for acc in accounts:
        line_items.append({
            "account_name": acc["account_name"],
            "notes_ref": acc.get("notes_ref"),
            "current_year": round(acc["balance"], 2),
            "prior_year": 0.0,
        })

    subtotal = {
        "account_name": f"Total {title}",
        "current_year": round(sum(a["balance"] for a in accounts), 2),
        "prior_year": 0.0,
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


def _build_notes(requirements: dict, grouped: dict, metadata: dict) -> dict:
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
    note_sections = []
    note_num = 4
    for group_name, accounts in grouped.items():
        if group_name == "Unmapped Accounts":
            continue
        total = sum(a["balance"] for a in accounts)
        detail_lines = "\n".join(
            f"  - {a['account_name']}: {currency} {abs(a['balance']):,.2f}"
            for a in accounts
        )
        note_sections.append({
            "note_number": note_num,
            "title": group_name,
            "content": f"Total {group_name}: {currency} {abs(total):,.2f}\n\n{detail_lines}",
        })
        note_num += 1

    return {
        "accounting_policies": accounting_policies,
        "critical_estimates": critical_estimates,
        "sections": note_sections,
    }
