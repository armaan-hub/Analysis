"""
Comparative Mainland Audit Report Format — Target Template Specification & Schema.

Adheres strictly to:
- UAE Federal Decree-Law No. 32 of 2021 on Commercial Companies
- International Financial Reporting Standards (IFRS) / IFRS for SMEs
- International Standards on Auditing (ISA 700 / 705)
- UAE Mainland Statutory Audit Reporting Conventions (AED Currency, 2025 first, 2024 second)
"""

from typing import Any

TEMPLATE_ID = "comparative-mainland"
TEMPLATE_NAME = "Comparative Mainland Audit Report Format"
TEMPLATE_CURRENCY = "AED"
YEAR_CURRENT = "2025"
YEAR_COMPARATIVE = "2024"
COLUMN_ORDER = ["2025", "2024"]

# ── Statement of Financial Position (Balance Sheet) Structure ─────────────────
SOFP_STRUCTURE = {
    "title": "STATEMENT OF FINANCIAL POSITION",
    "as_at": f"As at 31 December {YEAR_CURRENT}",
    "currency": "AED",
    "column_headers": ["Particulars", "Note", f"{YEAR_CURRENT} (AED)", f"{YEAR_COMPARATIVE} (AED)"],
    "sections": [
        {
            "category": "ASSETS",
            "groups": [
                {
                    "name": "Non-Current Assets",
                    "items": [
                        {"field": "property_plant_equipment", "label": "Property, plant and equipment", "note_ref": "3"},
                        {"field": "right_of_use_assets", "label": "Right-of-use assets", "note_ref": "4"},
                        {"field": "intangible_assets", "label": "Intangible assets", "note_ref": "5"},
                        {"field": "non_current_deposits", "label": "Long-term deposits and advances", "note_ref": "6"},
                        {"field": "non_current_investments", "label": "Non-current investments", "note_ref": "7"},
                    ],
                    "subtotal_field": "total_non_current_assets",
                    "subtotal_label": "Total Non-Current Assets",
                },
                {
                    "name": "Current Assets",
                    "items": [
                        {"field": "inventories", "label": "Inventories", "note_ref": "8"},
                        {"field": "trade_receivables", "label": "Trade receivables", "note_ref": "9"},
                        {"field": "advances_deposits_prepayments", "label": "Advances, prepayments and other receivables", "note_ref": "10"},
                        {"field": "due_from_related_parties", "label": "Due from related parties", "note_ref": "11"},
                        {"field": "cash_and_bank_balances", "label": "Cash and bank balances", "note_ref": "12"},
                    ],
                    "subtotal_field": "total_current_assets",
                    "subtotal_label": "Total Current Assets",
                },
            ],
            "total_field": "total_assets",
            "total_label": "TOTAL ASSETS",
        },
        {
            "category": "EQUITY AND LIABILITIES",
            "groups": [
                {
                    "name": "Equity",
                    "items": [
                        {"field": "share_capital", "label": "Share capital", "note_ref": "13"},
                        {"field": "statutory_reserve", "label": "Statutory reserve", "note_ref": "14"},
                        {"field": "retained_earnings", "label": "Retained earnings / (Accumulated losses)", "note_ref": "15"},
                        {"field": "shareholder_current_accounts", "label": "Shareholders' current / loan accounts", "note_ref": "16"},
                    ],
                    "subtotal_field": "total_equity",
                    "subtotal_label": "Total Equity",
                },
                {
                    "name": "Non-Current Liabilities",
                    "items": [
                        {"field": "employees_end_of_service_benefits", "label": "Provision for employees' end of service benefits", "note_ref": "17"},
                        {"field": "non_current_lease_liabilities", "label": "Lease liabilities - non-current portion", "note_ref": "4"},
                        {"field": "long_term_borrowings", "label": "Bank borrowings - non-current portion", "note_ref": "18"},
                    ],
                    "subtotal_field": "total_non_current_liabilities",
                    "subtotal_label": "Total Non-Current Liabilities",
                },
                {
                    "name": "Current Liabilities",
                    "items": [
                        {"field": "bank_overdrafts_short_term_loans", "label": "Bank overdrafts and short-term borrowings", "note_ref": "18"},
                        {"field": "current_portion_lease_liabilities", "label": "Lease liabilities - current portion", "note_ref": "4"},
                        {"field": "trade_payables", "label": "Trade payables", "note_ref": "19"},
                        {"field": "accruals_and_other_payables", "label": "Accruals and other payables", "note_ref": "20"},
                        {"field": "due_to_related_parties", "label": "Due to related parties", "note_ref": "11"},
                        {"field": "vat_and_tax_payable", "label": "VAT and corporate tax payable", "note_ref": "21"},
                    ],
                    "subtotal_field": "total_current_liabilities",
                    "subtotal_label": "Total Current Liabilities",
                },
            ],
            "subtotal_field": "total_liabilities",
            "subtotal_label": "Total Liabilities",
            "total_field": "total_equity_and_liabilities",
            "total_label": "TOTAL EQUITY AND LIABILITIES",
        },
    ],
}

# ── Statement of Profit or Loss and Other Comprehensive Income Structure ──────
SOPL_STRUCTURE = {
    "title": "STATEMENT OF PROFIT OR LOSS AND OTHER COMPREHENSIVE INCOME",
    "period": f"For the year ended 31 December {YEAR_CURRENT}",
    "currency": "AED",
    "column_headers": ["Particulars", "Note", f"{YEAR_CURRENT} (AED)", f"{YEAR_COMPARATIVE} (AED)"],
    "items": [
        {"field": "revenue", "label": "Revenue / Turnover", "note_ref": "22", "is_subtotal": False},
        {"field": "cost_of_sales", "label": "Cost of sales", "note_ref": "23", "is_subtotal": False, "is_negative": True},
        {"field": "gross_profit", "label": "GROSS PROFIT", "note_ref": "", "is_subtotal": True, "is_bold": True},
        {"field": "general_and_admin_expenses", "label": "General and administrative expenses", "note_ref": "24", "is_subtotal": False, "is_negative": True},
        {"field": "selling_and_distribution_expenses", "label": "Selling and distribution expenses", "note_ref": "25", "is_subtotal": False, "is_negative": True},
        {"field": "other_operating_income", "label": "Other operating income / (expense)", "note_ref": "26", "is_subtotal": False},
        {"field": "operating_profit", "label": "OPERATING PROFIT / (LOSS)", "note_ref": "", "is_subtotal": True, "is_bold": True},
        {"field": "finance_costs", "label": "Finance costs and bank charges", "note_ref": "27", "is_subtotal": False, "is_negative": True},
        {"field": "profit_before_tax", "label": "PROFIT / (LOSS) FOR THE YEAR BEFORE TAX", "note_ref": "", "is_subtotal": True, "is_bold": True},
        {"field": "corporate_tax_expense", "label": "UAE Corporate tax expense", "note_ref": "28", "is_subtotal": False, "is_negative": True},
        {"field": "net_profit_for_the_year", "label": "PROFIT / (LOSS) FOR THE YEAR", "note_ref": "", "is_subtotal": True, "is_bold": True},
        {"field": "other_comprehensive_income", "label": "Other comprehensive income", "note_ref": "", "is_subtotal": False},
        {"field": "total_comprehensive_income", "label": "TOTAL COMPREHENSIVE INCOME FOR THE YEAR", "note_ref": "", "is_subtotal": True, "is_bold": True},
    ],
}

# ── Statement of Changes in Equity Structure ──────────────────────────────────
SOCE_STRUCTURE = {
    "title": "STATEMENT OF CHANGES IN EQUITY",
    "period": f"For the years ended 31 December {YEAR_CURRENT} and {YEAR_COMPARATIVE}",
    "currency": "AED",
    "column_headers": [
        "Particulars",
        "Share Capital (AED)",
        "Statutory Reserve (AED)",
        "Retained Earnings (AED)",
        "Shareholders' Current A/c (AED)",
        "Total Equity (AED)",
    ],
    "rows": [
        {"label": f"Balance as at 1 January {YEAR_COMPARATIVE}", "type": "opening"},
        {"label": f"Profit for the year {YEAR_COMPARATIVE}", "type": "profit_comparative"},
        {"label": f"Transfer to statutory reserve ({YEAR_COMPARATIVE})", "type": "transfer_reserve"},
        {"label": "Other movements / Dividends / Capital changes", "type": "movements"},
        {"label": f"Balance as at 31 December {YEAR_COMPARATIVE}", "type": "subtotal", "is_bold": True},
        {"label": f"Profit for the year {YEAR_CURRENT}", "type": "profit_current"},
        {"label": f"Transfer to statutory reserve ({YEAR_CURRENT})", "type": "transfer_reserve"},
        {"label": "Other movements / Shareholder transactions", "type": "movements"},
        {"label": f"Balance as at 31 December {YEAR_CURRENT}", "type": "closing", "is_bold": True},
    ],
}

# ── Statement of Cash Flows (IAS 7 Indirect Method) Structure ─────────────────
CFS_STRUCTURE = {
    "title": "STATEMENT OF CASH FLOWS",
    "period": f"For the year ended 31 December {YEAR_CURRENT}",
    "currency": "AED",
    "column_headers": ["Particulars", f"{YEAR_CURRENT} (AED)", f"{YEAR_COMPARATIVE} (AED)"],
    "sections": [
        {
            "heading": "Cash flows from operating activities",
            "items": [
                "Profit for the year before tax",
                "Adjustments for non-cash and financial items:",
                "  Depreciation of property, plant and equipment",
                "  Amortization of right-of-use / intangible assets",
                "  Provision for employees' end of service benefits",
                "  Finance costs",
                "Operating cash flows before changes in working capital",
                "Working capital adjustments:",
                "  (Increase) / decrease in inventories",
                "  (Increase) / decrease in trade and other receivables",
                "  (Increase) / decrease in due from related parties",
                "  Increase / (decrease) in trade and other payables",
                "  Increase / (decrease) in due to related parties",
                "Cash generated from / (used in) operations",
                "  Employees' end of service benefits paid",
                "  Corporate tax paid",
                "Net cash generated from / (used in) operating activities",
            ],
        },
        {
            "heading": "Cash flows from investing activities",
            "items": [
                "Payment for purchase of property, plant and equipment",
                "Proceeds from disposal of property, plant and equipment",
                "Movement in long-term deposits",
                "Net cash generated from / (used in) investing activities",
            ],
        },
        {
            "heading": "Cash flows from financing activities",
            "items": [
                "Net proceeds from / (repayment of) bank borrowings",
                "Principal lease liability payments",
                "Finance costs paid",
                "Movement in shareholders' current accounts / dividends",
                "Net cash generated from / (used in) financing activities",
            ],
        },
        {
            "heading": "Summary",
            "items": [
                "Net increase / (decrease) in cash and cash equivalents",
                "Cash and cash equivalents at 1 January",
                "Cash and cash equivalents at 31 December",
            ],
        },
    ],
}

# ── Standard Notes to the Financial Statements (Notes 1 to 29) ─────────────────
STANDARD_NOTES_SPEC = [
    {
        "note_number": 1,
        "title": "LEGAL STATUS AND PRINCIPAL ACTIVITIES",
        "required_fields": [
            "company_name_en",
            "company_name_ar",
            "license_number",
            "legal_structure",
            "issuing_authority",
            "registered_address",
            "license_issue_date",
            "license_expiry_date",
            "share_capital_amount",
            "shareholders",
            "manager_name",
            "commercial_activities",
        ],
        "description": "Incorporates corporate details extracted from Trade License and MOA (Document 3).",
    },
    {
        "note_number": 2,
        "title": "BASIS OF PREPARATION AND SIGNIFICANT ACCOUNTING POLICIES",
        "topics": [
            "Statement of compliance with IFRS / IFRS for SMEs and UAE Federal Decree-Law No. 32 of 2021",
            "Functional and presentation currency (UAE Dirhams - AED)",
            "Historical cost convention and going concern assessment",
            "Revenue recognition policy (IFRS 15 five-step model)",
            "Property, plant and equipment and depreciation methods (IAS 16)",
            "Leases accounting policy (IFRS 16)",
            "Financial instruments and expected credit loss (IFRS 9)",
            "Inventories valuation policy (IAS 2 - lower of cost and net realizable value)",
            "Employees' end of service benefits policy (UAE Federal Decree-Law No. 33 of 2021)",
            "Provisions and contingent liabilities (IAS 37)",
            "UAE Corporate Tax policy (Federal Decree-Law No. 47 of 2022)",
        ],
    },
    {
        "note_number": 3,
        "title": "PROPERTY, PLANT AND EQUIPMENT",
        "description": "Movement schedule showing Cost, Additions, Disposals, Accumulated Depreciation, and Net Book Value for 2025 and 2024.",
    },
    {
        "note_number": 4,
        "title": "RIGHT-OF-USE ASSETS AND LEASE LIABILITIES",
        "description": "IFRS 16 lease assets and split between current and non-current lease obligations.",
    },
    {
        "note_number": 5,
        "title": "INTANGIBLE ASSETS",
        "description": "Software, licenses, goodwill or other intangible assets.",
    },
    {
        "note_number": 6,
        "title": "LONG-TERM DEPOSITS AND ADVANCES",
        "description": "Premises security deposits, utility deposits, and non-current financial assets.",
    },
    {
        "note_number": 7,
        "title": "NON-CURRENT INVESTMENTS",
        "description": "Investments in subsidiaries, associates, or unquoted securities.",
    },
    {
        "note_number": 8,
        "title": "INVENTORIES",
        "description": "Breakdown of Raw Materials, Work in Progress, Finished Goods, Goods in Transit, less provision for slow-moving items.",
    },
    {
        "note_number": 9,
        "title": "TRADE RECEIVABLES",
        "description": "Gross trade receivables, Less: Allowance for Expected Credit Losses (ECL), aging schedule, and net recoverable balance.",
    },
    {
        "note_number": 10,
        "title": "ADVANCES, PREPAYMENTS AND OTHER RECEIVABLES",
        "description": "Prepaid rent, insurance, supplier advances, employee advances, refundable deposits, VAT input tax credit.",
    },
    {
        "note_number": 11,
        "title": "RELATED PARTY TRANSACTIONS AND BALANCES",
        "description": "Balances Due from / Due to related parties, nature of relationship, volume of key management compensation, sales/purchases.",
    },
    {
        "note_number": 12,
        "title": "CASH AND BANK BALANCES",
        "description": "Cash in hand, cash at bank in current accounts, call accounts, fixed term deposits.",
    },
    {
        "note_number": 13,
        "title": "SHARE CAPITAL",
        "description": "Authorized, issued and paid-up capital, par value per share, total number of shares, and detailed shareholding breakdown.",
    },
    {
        "note_number": 14,
        "title": "STATUTORY RESERVE",
        "description": "Statutory reserve transfer (10% of net annual profit pursuant to UAE Commercial Companies Law until 50% of paid-up capital).",
    },
    {
        "note_number": 15,
        "title": "RETAINED EARNINGS",
        "description": "Opening balance, profit for the year, dividend declarations, transfer to statutory reserve, closing balance.",
    },
    {
        "note_number": 16,
        "title": "SHAREHOLDERS' CURRENT / LOAN ACCOUNTS",
        "description": "Funds advanced by or withdrawn by shareholders, interest terms, repayment expectations.",
    },
    {
        "note_number": 17,
        "title": "PROVISION FOR EMPLOYEES' END OF SERVICE BENEFITS",
        "description": "Opening provision, charge for the year, payments during the year, closing liability.",
    },
    {
        "note_number": 18,
        "title": "BANK BORROWINGS AND OVERDRAFTS",
        "description": "Short-term facilities, trust receipts, term loans, non-current portion, security and interest rates.",
    },
    {
        "note_number": 19,
        "title": "TRADE PAYABLES",
        "description": "Trade creditors, suppliers, bills payable, aging profile.",
    },
    {
        "note_number": 20,
        "title": "ACCRUALS AND OTHER PAYABLES",
        "description": "Accrued expenses, staff salaries payable, advance from customers, rent payable, audit fee accrual.",
    },
    {
        "note_number": 21,
        "title": "VAT AND CORPORATE TAX LIABILITIES",
        "description": "VAT output less input payable to FTA, UAE Corporate Tax liability for the financial year.",
    },
    {
        "note_number": 22,
        "title": "REVENUE / TURNOVER",
        "description": "Disaggregation of revenue by stream/activity/geography, timing of recognition.",
    },
    {
        "note_number": 23,
        "title": "COST OF SALES",
        "description": "Direct material consumption, direct labor, sub-contractor charges, freight & customs, other direct operational overheads.",
    },
    {
        "note_number": 24,
        "title": "GENERAL AND ADMINISTRATIVE EXPENSES",
        "description": "Staff salaries & benefits, rent, utilities, legal & professional fees, audit fees, depreciation, visa & license expenses, repairs & maintenance, communication, office expenses.",
    },
    {
        "note_number": 25,
        "title": "SELLING AND DISTRIBUTION EXPENSES",
        "description": "Marketing, advertising, sales commission, delivery & logistics, promotion.",
    },
    {
        "note_number": 26,
        "title": "OTHER OPERATING INCOME / (EXPENSE)",
        "description": "Scrap sales, foreign exchange gain/loss, interest income, sundry income.",
    },
    {
        "note_number": 27,
        "title": "FINANCE COSTS",
        "description": "Bank interest, loan interest, bank charges and processing fees.",
    },
    {
        "note_number": 28,
        "title": "UAE CORPORATE TAX",
        "description": "Computation of taxable income, 9% standard corporate tax rate above AED 375,000 threshold or Small Business Relief application.",
    },
    {
        "note_number": 29,
        "title": "CONTINGENCIES, COMMITMENTS AND SUBSEQUENT EVENTS",
        "description": "Letters of guarantee, capital commitments, material non-adjusting events after reporting date.",
    },
]


def format_audit_currency(val: Any) -> str:
    """Format numeric values with standard audit notation: '-' for zero."""
    if val is None or val == "":
        return "-"
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "").replace("AED", "").replace("$", "")
        if cleaned in ("-", "0", "0.0", "0.00", "nil", "none"):
            return "-"
        try:
            num = float(cleaned)
        except ValueError:
            return val
    elif isinstance(val, (int, float)):
        num = float(val)
    else:
        return "-"

    if abs(num) < 0.0001:
        return "-"
    if num < 0:
        return f"({abs(num):,.2f})"
    return f"{num:,.2f}"
