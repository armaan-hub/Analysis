"""
Audit Profile Builder — merges document extractions into a unified audit profile.

Takes multiple extraction results (from document_analyzer.py) and builds
a comprehensive audit_profile JSON that captures:
  - Financial data (revenue, assets, liabilities, equity, etc.)
  - Format template (column structure, page layout, statement groupings)
  - Account mappings (account name → IFRS group)
  - Custom requirements (opinion type, disclosures, comparative periods)
"""
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# IFRS groups for account classification
IFRS_GROUPS = [
    "Current Assets", "Non-Current Assets",
    "Current Liabilities", "Non-Current Liabilities",
    "Equity", "Revenue", "Cost of Sales",
    "Operating Expenses", "Other Income",
    "Finance Costs", "Tax Expense",
    "Cash and Cash Equivalents", "Retained Earnings",
]

# Keywords to infer account group from account name
_GROUP_KEYWORDS: dict[str, list[str]] = {
    "Revenue": ["revenue", "sales", "income from operations", "service income", "turnover",
                "commission received", "direct income", "indirect income"],
    "Cost of Sales": ["cost of sales", "cost of goods", "cogs", "direct cost", "purchases"],
    "Operating Expenses": [
        "salary", "salaries", "wages", "rent", "depreciation", "amortization",
        "utilities", "insurance", "travel", "office", "professional fees",
        "marketing", "advertising", "communication", "repairs", "maintenance",
        "staff cost", "employee", "admin", "general expense", "operating expense",
    ],
    "Current Assets": [
        "cash", "bank", "receivable", "inventory", "prepaid", "advance",
        "deposit", "short-term", "trade receivable", "accounts receivable",
    ],
    "Non-Current Assets": [
        "property", "plant", "equipment", "ppe", "intangible", "goodwill",
        "investment property", "right-of-use", "long-term investment",
        "fixed asset", "capital work",
    ],
    "Current Liabilities": [
        "payable", "accrued", "provision", "short-term loan", "overdraft",
        "trade payable", "accounts payable", "current portion",
        "unearned revenue", "deferred revenue",
    ],
    "Non-Current Liabilities": [
        "long-term loan", "lease liability", "bond", "debenture",
        "end of service", "employee benefit", "long-term provision",
    ],
    "Equity": [
        "capital", "share capital", "retained earnings", "reserves",
        "accumulated", "shareholder", "owner equity", "paid-up",
    ],
    "Other Income": ["other income", "interest income", "gain on", "dividend income"],
    "Finance Costs": ["interest expense", "finance cost", "bank charge", "finance charge"],
}


def build_profile_from_documents(
    documents: list[dict],
    client_name: str = "",
    period_end: str = "",
) -> dict:
    """
    Build a unified audit profile from multiple document extractions.

    Args:
        documents: List of extraction dicts from document_analyzer.analyze_document()
        client_name: Client/company name
        period_end: Period end date string

    Returns:
        Complete audit_profile JSON dict.
    """
    profile: dict[str, Any] = {
        "client_name": client_name,
        "period_end": period_end,
        "financial_data": {},
        "format_template": _default_format_template(),
        "account_mapping": {},
        "statement_groupings": _default_statement_groupings(),
        "custom_requirements": _default_requirements(),
        "source_summary": [],
    }

    for doc in documents:
        doc_type = doc.get("doc_type", "unknown")
        file_name = doc.get("file_name", "")

        profile["source_summary"].append({
            "file_name": file_name,
            "doc_type": doc_type,
            "pages": doc.get("pages"),
            "table_count": len(doc.get("tables", [])),
        })

        # Extract financial data from tables (trial balance, prior audit)
        financial = extract_financial_data(doc)
        if financial:
            _merge_financial_data(profile["financial_data"], financial)

        # Extract format template from PDF structure
        if doc_type == "pdf":
            fmt = extract_format_template(doc)
            if fmt.get("columns") or fmt.get("page_structure"):
                _merge_format_template(profile["format_template"], fmt)

        # Infer account mappings from tables
        mappings = infer_account_mapping(doc)
        if mappings:
            profile["account_mapping"].update(mappings)

    return profile


def extract_financial_data(doc: dict) -> dict:
    """
    Extract financial figures from document tables.
    Looks for amounts next to account names.
    """
    financial: dict[str, float] = {}
    currency_pattern = re.compile(r"[\d,]+(?:\.\d+)?")

    for table in doc.get("tables", []):
        for row in table:
            if len(row) < 2:
                continue

            label = str(row[0]).strip().lower()
            # Try to find a numeric value in subsequent columns
            for cell in row[1:]:
                cell_str = str(cell).strip().replace(",", "").replace("(", "-").replace(")", "")
                match = currency_pattern.search(cell_str)
                if match:
                    try:
                        value = float(cell_str.replace(",", ""))
                        _classify_financial_item(financial, label, value)
                        break
                    except (ValueError, TypeError):
                        continue

    return financial


def _classify_financial_item(financial: dict, label: str, value: float):
    """Classify a financial line item into standard categories."""
    label_lower = label.lower()

    mappings = {
        "total revenue": "revenue",
        "revenue": "revenue",
        "sales": "revenue",
        "total assets": "total_assets",
        "total liabilities": "total_liabilities",
        "total equity": "total_equity",
        "net profit": "net_profit",
        "net income": "net_profit",
        "net loss": "net_profit",
        "gross profit": "gross_profit",
        "cost of sales": "cost_of_sales",
        "cost of goods": "cost_of_sales",
        "operating expenses": "operating_expenses",
        "total operating expenses": "operating_expenses",
        "cash and cash equivalents": "cash",
        "retained earnings": "retained_earnings",
    }

    for keyword, category in mappings.items():
        if keyword in label_lower:
            if category not in financial or abs(value) > abs(financial.get(category, 0)):
                financial[category] = abs(value)
            return


def extract_format_template(doc: dict) -> dict:
    """
    Extract format template from a PDF document's structure.
    Detects column layout, page structure, statement sections.
    """
    template: dict[str, Any] = {}

    # Detect columns from table headers
    for table in doc.get("tables", []):
        if not table:
            continue
        header_row = table[0]
        # Look for financial statement column patterns
        header_text = " | ".join(str(c) for c in header_row).lower()
        if any(kw in header_text for kw in ["aed", "usd", "notes", "current year", "prior year"]):
            template["columns"] = [str(c).strip() for c in header_row if str(c).strip()]
            break

    # Page structure from headings
    headings = doc.get("structure", {}).get("headings", [])
    page_structure: dict[str, Any] = {}

    for heading in headings:
        text = heading.get("text", "").lower()
        page = heading.get("page", 0)

        if "independent auditor" in text:
            page_structure["auditor_report_start"] = page
        elif "financial position" in text or "balance sheet" in text:
            page_structure["balance_sheet_page"] = page
        elif "profit" in text and "loss" in text:
            page_structure["income_statement_page"] = page
        elif "cash flow" in text:
            page_structure["cash_flow_page"] = page
        elif "notes to" in text:
            page_structure["notes_start_page"] = page

    if page_structure:
        template["page_structure"] = page_structure

    template["total_pages"] = doc.get("pages") or doc.get("metadata", {}).get("page_count")

    return template


def infer_account_mapping(doc: dict) -> dict:
    """
    Infer account name → IFRS group mappings from document tables.
    Uses keyword matching against known account group patterns.
    """
    mappings: dict[str, dict] = {}

    for table in doc.get("tables", []):
        for row in table:
            if not row or len(row) < 1:
                continue

            account_name = str(row[0]).strip()
            if not account_name or len(account_name) < 3:
                continue

            # Skip header-like rows
            if account_name.lower() in ("account", "description", "particulars", "notes", ""):
                continue

            group = _infer_group_from_name(account_name)
            if group:
                mappings[account_name] = {
                    "name": account_name,
                    "mapped_to": group,
                    "confidence": 0.7,
                    "source": "keyword_inference",
                }

    return mappings


def _infer_group_from_name(account_name: str) -> Optional[str]:
    """Match account name to IFRS group using keyword patterns."""
    name_lower = account_name.lower()

    # Skip totals and subtotals
    if name_lower.startswith("total") or name_lower.startswith("sub-total"):
        return None

    best_match: Optional[str] = None
    best_score = 0

    for group, keywords in _GROUP_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name_lower:
                score = len(keyword)  # Longer match = more specific
                if score > best_score:
                    best_score = score
                    best_match = group

    return best_match


def _merge_financial_data(target: dict, source: dict):
    """Merge financial data, preferring larger absolute values."""
    for key, value in source.items():
        if key not in target or abs(value) > abs(target.get(key, 0)):
            target[key] = value


def _merge_format_template(target: dict, source: dict):
    """Merge format template, preferring non-empty values."""
    for key, value in source.items():
        if value and (key not in target or not target[key]):
            target[key] = value


def _default_format_template() -> dict:
    return {
        "columns": ["Notes", "Current Year (AED)", "Prior Year (AED)"],
        "page_structure": {},
        "total_pages": None,
    }


def _default_statement_groupings() -> dict:
    return {
        "balance_sheet": {
            "assets": ["Current Assets", "Non-Current Assets"],
            "liabilities": ["Current Liabilities", "Non-Current Liabilities"],
            "equity": ["Equity"],
        },
        "income_statement": {
            "sections": ["Revenue", "Cost of Sales", "Operating Expenses",
                         "Other Income", "Finance Costs"],
        },
    }


def _default_requirements() -> dict:
    return {
        "audit_standard": "ISA",
        "opinion_type": "unqualified",
        "comparative_required": True,
        "currency": "AED",
        "notes_required": [
            "Accounting Policies",
            "Critical Accounting Estimates",
            "Related Party Transactions",
        ],
    }
