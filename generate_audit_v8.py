"""
End-to-end test: generates Castle_Plaza_Audit_2025_v8.pdf
Fixes vs v7:
  - Correct 2024 prior year figures (Revenue 5,186,636 etc.)
  - Fab Mortgage Loan → Non-Current Liabilities (proper IFRS grouping)
  - Retained Earnings absorbs net profit (no separate equity line)
  - Authorized Signatory block on SOFP page
  - G&A prior year derived from section total
"""

import asyncio
import sys
import os
import json
from pathlib import Path

BASE    = Path(r"C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026")
BACKEND = BASE / "Project_AccountingLegalChatbot" / "backend"
TB_PATH   = BASE / "Testing data" / "Trail Balance.xlsx"
OUT_PDF   = BASE / "Testing data" / "Castle_Plaza_Audit_2025_v8.pdf"
OUT_JSON  = BASE / "Testing data" / "Castle_Plaza_Audit_2025_v8.json"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("OPENAI_API_KEY", "")

from core.trial_balance_mapper import map_trial_balance
from core.structured_report_generator import generate_audit_report
from core.format_applier import apply_format

COMPANY_INFO = {
    "company_name": "Castles Plaza Real Estate LLC",
    "period_end": "2025-12-31",
    "auditor_name": "NBN Auditing of Accounts",
    "auditor_firm": "NBN Auditing of Accounts",
    "auditor_registration": "509",
    "currency": "AED",
}

FORMAT_TEMPLATE = {
    "page_size": "LETTER",
    "currency_symbol": "AED",
    "font_family": "Times New Roman",
    "font_size": 10,
    "margins": {"top": 120, "bottom": 40, "left": 109, "right": 25},
}

PROFILE = {
    "client_name": "Castles Plaza Real Estate LLC",
    "period_end": "2025-12-31",
    # Move Fab Mortgage Loan to Non-Current Liabilities for correct IFRS grouping
    "account_mapping": {
        "Fab Mortgage Loan": "Non-Current Liabilities",
    },
    "format_template": FORMAT_TEMPLATE,
    "custom_requirements": {
        "currency": "AED",
        "audit_standard": "ISA",
        "opinion_type": "unqualified",
    },
}


async def main():
    print("=" * 65)
    print("  Castle Plaza Audit Report v8 — Generator")
    print("=" * 65)

    print("\n[1/5] Loading Trial Balance...")
    tb_rows = map_trial_balance(str(TB_PATH))
    print(f"  {len(tb_rows)} accounts loaded")

    print("\n[2/5] Loading prior year data...")
    py_out = BASE / "Testing data" / "prior_year_extraction.json"
    prior_result = json.loads(py_out.read_text())
    prior_rows = prior_result.get("rows", [])
    print(f"  Using cached extraction: {len(prior_rows)} rows")

    print("\n[3/5] Generating audit report JSON...")
    report_json = generate_audit_report(
        trial_balance=tb_rows,
        profile=PROFILE,
        company_info=COMPANY_INFO,
        prior_year_data=prior_rows or None,
        tb_categories={row["account_name"]: row.get("category", "other") for row in tb_rows},
    )
    is_comp = report_json.get("metadata", {}).get("is_comparative", False)
    print(f"  is_comparative={is_comp}")
    OUT_JSON.write_text(json.dumps(report_json, indent=2, default=str))
    print(f"  JSON saved → {OUT_JSON.name}")

    print("\n[4/5] Generating PDF...")
    pdf_bytes = apply_format(report_json, FORMAT_TEMPLATE, "pdf")
    OUT_PDF.write_bytes(pdf_bytes)
    print(f"  PDF saved: {len(pdf_bytes):,} bytes → {OUT_PDF.name}")

    print("\n[5/5] Verification:")
    sopl = report_json.get("financial_statements", {}).get("statement_of_profit_or_loss", {})
    for sec in sopl.get("sections", []):
        if sec.get("title") == "Revenue":
            st = sec.get("subtotal", {})
            print(f"  Revenue 2025: AED {st.get('current_year', 0):>12,.2f}")
            print(f"  Revenue 2024: AED {st.get('prior_year', 0):>12,.2f}  (expect 5,186,636)")
    net = sopl.get("total", {})
    print(f"  Net P/(L) 2025: AED {net.get('current_year', 0):>12,.2f}")
    print(f"  Net P/(L) 2024: AED {net.get('prior_year', 0):>12,.2f}  (expect -4,279,114)")

    sofp = report_json.get("financial_statements", {}).get("statement_of_financial_position", {})
    print(f"  Total Assets 2025: AED {sofp.get('total', {}).get('current_year', 0):>12,.2f}")
    print(f"  Total Assets 2024: AED {sofp.get('total', {}).get('prior_year', 0):>12,.2f}  (expect 5,929,549)")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
