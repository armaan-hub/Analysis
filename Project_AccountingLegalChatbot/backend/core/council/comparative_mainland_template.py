"""
Comparative Mainland Audit Report Format — Target Template Specification & Schema.

Adheres strictly to:
- UAE Federal Decree-Law No. 32 of 2021 on Commercial Companies
- International Financial Reporting Standards (IFRS) / IFRS for SMEs
- International Standards on Auditing (ISA 700 / 705)
- UAE Mainland Statutory Audit Reporting Conventions (AED Currency, 2025 first, 2024 second)
- Standard Spreadsheet / Excel Formula Calculation Modeling (SUM, SUMIF, SUMIFS, GROUPBY, IF, MIN)
"""

from typing import Any

TEMPLATE_ID = "comparative-mainland"
TEMPLATE_NAME = "Comparative Mainland Audit Report Format"
TEMPLATE_CURRENCY = "AED"
YEAR_CURRENT = "2025"
YEAR_COMPARATIVE = "2024"
COLUMN_ORDER = ["2025", "2024"]

# ── Standard Excel Formula Mapping Specification ──────────────────────────────
EXCEL_AUDIT_FORMULAS = {
    "debit_credit_balance": "=SUM(Debit_Range) - SUM(Credit_Range) == 0.00",
    "total_non_current_assets": "=SUM(Note3_PPE:Note7_Investments)",
    "total_current_assets": "=SUM(Note8_Inventories:Note12_Cash)",
    "total_assets": "=Total_Non_Current_Assets + Total_Current_Assets",
    "total_equity": "=Share_Capital + Statutory_Reserve + Retained_Earnings + Shareholders_Current_Accounts",
    "total_non_current_liabilities": "=SUM(Note17_EOSB:Note18_LT_Borrowings)",
    "total_current_liabilities": "=SUM(Note18_Overdrafts:Note21_Tax_Payable)",
    "total_liabilities": "=Total_Non_Current_Liabilities + Total_Current_Liabilities",
    "balance_sheet_parity": "=Total_Assets - (Total_Equity + Total_Liabilities) == 0.00",
    "gross_profit": "=Revenue - Cost_of_Sales",
    "total_ga_expenses": "=SUM(Note24_GA_Items)",
    "operating_profit": "=Gross_Profit - Total_GA_Expenses - Selling_Expenses + Other_Income",
    "profit_before_tax": "=Operating_Profit - Finance_Costs",
    "corporate_tax_expense": "=IF(Profit_Before_Tax > 375000, (Profit_Before_Tax - 375000) * 0.09, 0)",
    "net_profit": "=Profit_Before_Tax - Corporate_Tax_Expense",
    "statutory_reserve_transfer": "=IF(Net_Profit > 0, MIN(Net_Profit * 0.10, MAX(0, Share_Capital * 0.50 - Existing_Reserve)), 0)",
    "retained_earnings_closing": "=Opening_RE + Net_Profit - Statutory_Reserve_Transfer - Dividends",
    "shareholding_capital_total": "=SUM(Shareholder_Capital_Range) == Total_Share_Capital",
    "shareholding_percentage_total": "=SUM(Shareholder_Percentage_Range) == 100.00%",
}

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
                        {"field": "property_plant_equipment", "label": "Property, plant and equipment", "note_ref": "3", "formula": "=SUM(PPE_Subledger)"},
                        {"field": "right_of_use_assets", "label": "Right-of-use assets", "note_ref": "4", "formula": "=Cost_ROU - Acc_Deprec_ROU"},
                        {"field": "intangible_assets", "label": "Intangible assets", "note_ref": "5", "formula": "=Cost_Intangibles - Acc_Amort"},
                        {"field": "non_current_deposits", "label": "Long-term deposits and advances", "note_ref": "6", "formula": "=SUM(LT_Deposits_Range)"},
                        {"field": "non_current_investments", "label": "Non-current investments", "note_ref": "7", "formula": "=SUM(Investments_Range)"},
                    ],
                    "subtotal_field": "total_non_current_assets",
                    "subtotal_label": "Total Non-Current Assets",
                    "formula": "=SUM(property_plant_equipment:non_current_investments)",
                },
                {
                    "name": "Current Assets",
                    "items": [
                        {"field": "inventories", "label": "Inventories", "note_ref": "8", "formula": "=SUM(Raw_Mat, WIP, Fin_Goods) - Slow_Moving_Prov"},
                        {"field": "trade_receivables", "label": "Trade receivables", "note_ref": "9", "formula": "=Gross_Receivables - ECL_Allowance"},
                        {"field": "advances_deposits_prepayments", "label": "Advances, prepayments and other receivables", "note_ref": "10", "formula": "=SUM(Advances, Prepayments, Other_Debtors)"},
                        {"field": "due_from_related_parties", "label": "Due from related parties", "note_ref": "11", "formula": "=SUMIFS(TB_Amount, Related_Party_Range, \"Due From\")"},
                        {"field": "cash_and_bank_balances", "label": "Cash and bank balances", "note_ref": "12", "formula": "=SUM(Cash_In_Hand, Bank_Current, Bank_Deposit)"},
                    ],
                    "subtotal_field": "total_current_assets",
                    "subtotal_label": "Total Current Assets",
                    "formula": "=SUM(inventories:cash_and_bank_balances)",
                },
            ],
            "total_field": "total_assets",
            "total_label": "TOTAL ASSETS",
            "formula": "=total_non_current_assets + total_current_assets",
        },
        {
            "category": "EQUITY AND LIABILITIES",
            "groups": [
                {
                    "name": "Equity",
                    "items": [
                        {"field": "share_capital", "label": "Share capital", "note_ref": "13", "formula": "=Total_Shares * Par_Value"},
                        {"field": "statutory_reserve", "label": "Statutory reserve", "note_ref": "14", "formula": "=Opening_Reserve + Transfer_Current_Year"},
                        {"field": "retained_earnings", "label": "Retained earnings / (Accumulated losses)", "note_ref": "15", "formula": "=Opening_RE + Net_Profit - Reserve_Transfer - Dividends"},
                        {"field": "shareholder_current_accounts", "label": "Shareholders' current / loan accounts", "note_ref": "16", "formula": "=SUM(Shareholder_Current_Balances)"},
                    ],
                    "subtotal_field": "total_equity",
                    "subtotal_label": "Total Equity",
                    "formula": "=SUM(share_capital:shareholder_current_accounts)",
                },
                {
                    "name": "Non-Current Liabilities",
                    "items": [
                        {"field": "employees_end_of_service_benefits", "label": "Provision for employees' end of service benefits", "note_ref": "17", "formula": "=Opening_EOSB + Charge - Paid"},
                        {"field": "non_current_lease_liabilities", "label": "Lease liabilities - non-current portion", "note_ref": "4", "formula": "=Total_Lease_Liabilities - Current_Lease_Portion"},
                        {"field": "long_term_borrowings", "label": "Bank borrowings - non-current portion", "note_ref": "18", "formula": "=Total_Bank_Loans - Current_Portion_Loans"},
                    ],
                    "subtotal_field": "total_non_current_liabilities",
                    "subtotal_label": "Total Non-Current Liabilities",
                    "formula": "=SUM(employees_end_of_service_benefits:long_term_borrowings)",
                },
                {
                    "name": "Current Liabilities",
                    "items": [
                        {"field": "bank_overdrafts_short_term_loans", "label": "Bank overdrafts and short-term borrowings", "note_ref": "18", "formula": "=Bank_Overdrafts + Short_Term_Loans"},
                        {"field": "current_portion_lease_liabilities", "label": "Lease liabilities - current portion", "note_ref": "4", "formula": "=Lease_Liability_Due_Within_12M"},
                        {"field": "trade_payables", "label": "Trade payables", "note_ref": "19", "formula": "=SUM(Trade_Creditors_Range)"},
                        {"field": "accruals_and_other_payables", "label": "Accruals and other payables", "note_ref": "20", "formula": "=SUM(Accruals_Range, Other_Payables_Range)"},
                        {"field": "due_to_related_parties", "label": "Due to related parties", "note_ref": "11", "formula": "=SUMIFS(TB_Amount, Related_Party_Range, \"Due To\")"},
                        {"field": "vat_and_tax_payable", "label": "VAT and corporate tax payable", "note_ref": "21", "formula": "=VAT_Payable + Corporate_Tax_Payable"},
                    ],
                    "subtotal_field": "total_current_liabilities",
                    "subtotal_label": "Total Current Liabilities",
                    "formula": "=SUM(bank_overdrafts_short_term_loans:vat_and_tax_payable)",
                },
            ],
            "subtotal_field": "total_liabilities",
            "subtotal_label": "Total Liabilities",
            "formula": "=total_non_current_liabilities + total_current_liabilities",
            "total_field": "total_equity_and_liabilities",
            "total_label": "TOTAL EQUITY AND LIABILITIES",
            "formula": "=total_equity + total_liabilities",
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
        {"field": "revenue", "label": "Revenue / Turnover", "note_ref": "22", "is_subtotal": False, "formula": "=SUM(Revenue_Streams)"},
        {"field": "cost_of_sales", "label": "Cost of sales", "note_ref": "23", "is_subtotal": False, "is_negative": True, "formula": "=SUM(Direct_Materials, Direct_Labor, Overhead)"},
        {"field": "gross_profit", "label": "GROSS PROFIT", "note_ref": "", "is_subtotal": True, "is_bold": True, "formula": "=revenue - cost_of_sales"},
        {"field": "general_and_admin_expenses", "label": "General and administrative expenses", "note_ref": "24", "is_subtotal": False, "is_negative": True, "formula": "=SUM(Note24_GA_Expense_Items)"},
        {"field": "selling_and_distribution_expenses", "label": "Selling and distribution expenses", "note_ref": "25", "is_subtotal": False, "is_negative": True, "formula": "=SUM(Note25_Selling_Items)"},
        {"field": "other_operating_income", "label": "Other operating income / (expense)", "note_ref": "26", "is_subtotal": False, "formula": "=SUM(Note26_Other_Income_Items)"},
        {"field": "operating_profit", "label": "OPERATING PROFIT / (LOSS)", "note_ref": "", "is_subtotal": True, "is_bold": True, "formula": "=gross_profit - general_and_admin_expenses - selling_and_distribution_expenses + other_operating_income"},
        {"field": "finance_costs", "label": "Finance costs and bank charges", "note_ref": "27", "is_subtotal": False, "is_negative": True, "formula": "=SUM(Interest_Expense, Bank_Charges)"},
        {"field": "profit_before_tax", "label": "PROFIT / (LOSS) FOR THE YEAR BEFORE TAX", "note_ref": "", "is_subtotal": True, "is_bold": True, "formula": "=operating_profit - finance_costs"},
        {"field": "corporate_tax_expense", "label": "UAE Corporate tax expense", "note_ref": "28", "is_subtotal": False, "is_negative": True, "formula": "=IF(profit_before_tax > 375000, (profit_before_tax - 375000) * 0.09, 0)"},
        {"field": "net_profit_for_the_year", "label": "PROFIT / (LOSS) FOR THE YEAR", "note_ref": "", "is_subtotal": True, "is_bold": True, "formula": "=profit_before_tax - corporate_tax_expense"},
        {"field": "other_comprehensive_income", "label": "Other comprehensive income", "note_ref": "", "is_subtotal": False, "formula": "=SUM(OCI_Items)"},
        {"field": "total_comprehensive_income", "label": "TOTAL COMPREHENSIVE INCOME FOR THE YEAR", "note_ref": "", "is_subtotal": True, "is_bold": True, "formula": "=net_profit_for_the_year + other_comprehensive_income"},
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
        {"label": f"Balance as at 1 January {YEAR_COMPARATIVE}", "type": "opening", "formula": "=SUM(Opening_Equity_Columns)"},
        {"label": f"Profit for the year {YEAR_COMPARATIVE}", "type": "profit_comparative", "formula": "=SOPL_2024_Net_Profit"},
        {"label": f"Transfer to statutory reserve ({YEAR_COMPARATIVE})", "type": "transfer_reserve", "formula": "=IF(Profit_2024>0, MIN(Profit_2024*0.10, MAX(0, Capital*0.50 - Reserve)), 0)"},
        {"label": "Other movements / Dividends / Capital changes", "type": "movements", "formula": "=Dividends_Paid_2024"},
        {"label": f"Balance as at 31 December {YEAR_COMPARATIVE}", "type": "subtotal", "is_bold": True, "formula": "=SUM(Column_Movements_2024)"},
        {"label": f"Profit for the year {YEAR_CURRENT}", "type": "profit_current", "formula": "=SOPL_2025_Net_Profit"},
        {"label": f"Transfer to statutory reserve ({YEAR_CURRENT})", "type": "transfer_reserve", "formula": "=IF(Profit_2025>0, MIN(Profit_2025*0.10, MAX(0, Capital*0.50 - Reserve)), 0)"},
        {"label": "Other movements / Shareholder transactions", "type": "movements", "formula": "=Shareholder_Drawings_2025"},
        {"label": f"Balance as at 31 December {YEAR_CURRENT}", "type": "closing", "is_bold": True, "formula": "=SUM(Column_Movements_2025)"},
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
        "formula": "=Cost - Accumulated_Depreciation",
    },
    {
        "note_number": 4,
        "title": "RIGHT-OF-USE ASSETS AND LEASE LIABILITIES",
        "description": "IFRS 16 lease assets and split between current and non-current lease obligations.",
        "formula": "=Total_Lease_Liability - Current_Portion",
    },
    {
        "note_number": 5,
        "title": "INTANGIBLE ASSETS",
        "description": "Software, licenses, goodwill or other intangible assets.",
        "formula": "=Cost - Accumulated_Amortization",
    },
    {
        "note_number": 6,
        "title": "LONG-TERM DEPOSITS AND ADVANCES",
        "description": "Premises security deposits, utility deposits, and non-current financial assets.",
        "formula": "=SUM(Security_Deposits, Long_Term_Advances)",
    },
    {
        "note_number": 7,
        "title": "NON-CURRENT INVESTMENTS",
        "description": "Investments in subsidiaries, associates, or unquoted securities.",
        "formula": "=SUM(Unquoted_Investments, Subsidiary_Holdings)",
    },
    {
        "note_number": 8,
        "title": "INVENTORIES",
        "description": "Breakdown of Raw Materials, Work in Progress, Finished Goods, Goods in Transit, less provision for slow-moving items.",
        "formula": "=SUM(Raw_Materials, WIP, Finished_Goods) - Slow_Moving_Provision",
    },
    {
        "note_number": 9,
        "title": "TRADE RECEIVABLES",
        "description": "Gross trade receivables, Less: Allowance for Expected Credit Losses (ECL), aging schedule, and net recoverable balance.",
        "formula": "=Gross_Trade_Receivables - ECL_Allowance",
    },
    {
        "note_number": 10,
        "title": "ADVANCES, PREPAYMENTS AND OTHER RECEIVABLES",
        "description": "Prepaid rent, insurance, supplier advances, employee advances, refundable deposits, VAT input tax credit.",
        "formula": "=SUM(Prepaid_Expenses, Supplier_Advances, VAT_Input, Deposits)",
    },
    {
        "note_number": 11,
        "title": "RELATED PARTY TRANSACTIONS AND BALANCES",
        "description": "Balances Due from / Due to related parties, nature of relationship, volume of key management compensation, sales/purchases.",
        "formula": "=SUMIFS(Ledger_Amount, Related_Party_Flag, TRUE)",
    },
    {
        "note_number": 12,
        "title": "CASH AND BANK BALANCES",
        "description": "Cash in hand, cash at bank in current accounts, call accounts, fixed term deposits.",
        "formula": "=SUM(Cash_In_Hand, Bank_Current_Accounts, Fixed_Deposits)",
    },
    {
        "note_number": 13,
        "title": "SHARE CAPITAL",
        "description": "Authorized, issued and paid-up capital, par value per share, total number of shares, and detailed shareholding breakdown.",
        "formula": "=Total_Shares * Par_Value_Per_Share",
    },
    {
        "note_number": 14,
        "title": "STATUTORY RESERVE",
        "description": "Statutory reserve transfer (10% of net annual profit pursuant to UAE Commercial Companies Law until 50% of paid-up capital).",
        "formula": "=IF(Net_Profit > 0, MIN(Net_Profit * 0.10, MAX(0, Share_Capital * 0.50 - Opening_Reserve)), 0)",
    },
    {
        "note_number": 15,
        "title": "RETAINED EARNINGS",
        "description": "Opening balance, profit for the year, dividend declarations, transfer to statutory reserve, closing balance.",
        "formula": "=Opening_RE + Net_Profit_Current_Year - Statutory_Reserve_Transfer - Dividends",
    },
    {
        "note_number": 16,
        "title": "SHAREHOLDERS' CURRENT / LOAN ACCOUNTS",
        "description": "Funds advanced by or withdrawn by shareholders, interest terms, repayment expectations.",
        "formula": "=Opening_Balance + Funds_Introduced - Drawings",
    },
    {
        "note_number": 17,
        "title": "PROVISION FOR EMPLOYEES' END OF SERVICE BENEFITS",
        "description": "Opening provision, charge for the year, payments during the year, closing liability.",
        "formula": "=Opening_EOSB + Current_Year_Charge - Paid_During_Year",
    },
    {
        "note_number": 18,
        "title": "BANK BORROWINGS AND OVERDRAFTS",
        "description": "Short-term facilities, trust receipts, term loans, non-current portion, security and interest rates.",
        "formula": "=SUM(Term_Loans, Overdrafts, Trust_Receipts)",
    },
    {
        "note_number": 19,
        "title": "TRADE PAYABLES",
        "description": "Trade creditors, suppliers, bills payable, aging profile.",
        "formula": "=SUM(Trade_Creditors_Subledger)",
    },
    {
        "note_number": 20,
        "title": "ACCRUALS AND OTHER PAYABLES",
        "description": "Accrued expenses, staff salaries payable, advance from customers, rent payable, audit fee accrual.",
        "formula": "=SUM(Accrued_Salaries, Accrued_Rent, Audit_Fee_Accrual, Customer_Advances)",
    },
    {
        "note_number": 21,
        "title": "VAT AND CORPORATE TAX LIABILITIES",
        "description": "VAT output less input payable to FTA, UAE Corporate Tax liability for the financial year.",
        "formula": "=VAT_Payable + Corporate_Tax_Liability",
    },
    {
        "note_number": 22,
        "title": "REVENUE / TURNOVER",
        "description": "Disaggregation of revenue by stream/activity/geography, timing of recognition.",
        "formula": "=SUM(Operating_Revenue_Streams)",
    },
    {
        "note_number": 23,
        "title": "COST OF SALES",
        "description": "Direct material consumption, direct labor, sub-contractor charges, freight & customs, other direct operational overheads.",
        "formula": "=Opening_Stock + Purchases + Direct_Expenses - Closing_Stock",
    },
    {
        "note_number": 24,
        "title": "GENERAL AND ADMINISTRATIVE EXPENSES",
        "description": "Staff salaries & benefits, rent, utilities, legal & professional fees, audit fees, depreciation, visa & license expenses, repairs & maintenance, communication, office expenses.",
        "formula": "=SUM(Salaries, Rent, Utilities, Depreciation, Legal_Fees, Other_Admin)",
    },
    {
        "note_number": 25,
        "title": "SELLING AND DISTRIBUTION EXPENSES",
        "description": "Marketing, advertising, sales commission, delivery & logistics, promotion.",
        "formula": "=SUM(Advertising, Sales_Commissions, Delivery_Charges)",
    },
    {
        "note_number": 26,
        "title": "OTHER OPERATING INCOME / (EXPENSE)",
        "description": "Scrap sales, foreign exchange gain/loss, interest income, sundry income.",
        "formula": "=SUM(Scrap_Sales, FX_Gain_Loss, Sundry_Income)",
    },
    {
        "note_number": 27,
        "title": "FINANCE COSTS",
        "description": "Bank interest, loan interest, bank charges and processing fees.",
        "formula": "=SUM(Loan_Interest, Bank_Charges)",
    },
    {
        "note_number": 28,
        "title": "UAE CORPORATE TAX",
        "description": "Computation of taxable income, 9% standard corporate tax rate above AED 375,000 threshold or Small Business Relief application.",
        "formula": "=IF(Taxable_Net_Profit > 375000, (Taxable_Net_Profit - 375000) * 0.09, 0)",
    },
    {
        "note_number": 29,
        "title": "CONTINGENCIES, COMMITMENTS AND SUBSEQUENT EVENTS",
        "description": "Letters of guarantee, capital commitments, material non-adjusting events after reporting date.",
        "formula": "=SUM(Bank_Guarantees, Capital_Commitments)",
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
