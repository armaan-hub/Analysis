"""
End-to-end test: generates Castle_Plaza_Audit_2025_v7.pdf
- Trail Balance: Trail Balance.xlsx
- Prior year:    Signed Audit Report 2024.pdf (OCR/vision extraction)
- Format:        US Letter, matching Draft FS - Castle Plaza 2025.pdf
- Query answer:  Revenue 2024 and 2025
"""

import asyncio
import sys
import os
import json
from pathlib import Path

BASE    = Path(r"C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026")
BACKEND = BASE / "Project_AccountingLegalChatbot" / "backend"
TB_PATH   = BASE / "Testing data" / "Trail Balance.xlsx"
PRIOR_PDF = BASE / "Testing data" / "Signed Audit Report 2024.pdf"
OUT_PDF   = BASE / "Testing data" / "Castle_Plaza_Audit_2025_v7.pdf"
OUT_JSON  = BASE / "Testing data" / "Castle_Plaza_Audit_2025_v7.json"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("OPENAI_API_KEY", "")

from core.trial_balance_mapper import map_trial_balance
from core.prior_year_extractor import extract_prior_year_from_pdf
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
    "account_mapping": {},   # will use keyword-based mapping from trial_balance_mapper
    "format_template": FORMAT_TEMPLATE,
    "custom_requirements": {
        "currency": "AED",
        "audit_standard": "ISA",
        "opinion_type": "unqualified",
    },
}


async def main():
    print("=" * 65)
    print("  Castle Plaza Audit Report v7 — Generator")
    print("=" * 65)

    # ── Step 1: Load Trial Balance ────────────────────────────────────────
    print("\n[1/5] Loading Trial Balance...")
    tb_rows = map_trial_balance(str(TB_PATH))
    total_dr = sum(r["debit"]  for r in tb_rows)
    total_cr = sum(r["credit"] for r in tb_rows)
    print(f"  ✓ {len(tb_rows)} accounts | DR: {total_dr:,.2f} | CR: {total_cr:,.2f} AED")

    # ── Step 2: Extract Prior Year Data from 2024 Signed Audit ───────────
    print("\n[2/5] Extracting prior year data from Signed Audit 2024...")
    try:
        prior_result = await extract_prior_year_from_pdf(str(PRIOR_PDF))
        prior_rows   = prior_result.get("rows", [])
        method       = prior_result.get("extraction_method", "unknown")
        confidence   = prior_result.get("confidence", 0)
        print(f"  ✓ {len(prior_rows)} rows extracted | method={method} | confidence={confidence:.0%}")

        # Show key prior year figures
        for name_hint in ("revenue", "net profit", "total asset"):
            match = next((r for r in prior_rows
                          if name_hint in r.get("account_name","").lower()), None)
            if match:
                print(f"     {match['account_name']}: AED {match.get('prior_year_value',0):,.0f}")

        # Save extraction result
        py_out = BASE / "Testing data" / "prior_year_extraction.json"
        py_out.write_text(json.dumps(prior_result, indent=2, default=str))
        print(f"  Saved extraction → {py_out.name}")

    except Exception as ex:
        print(f"  ⚠ Prior year extraction failed: {ex}")
        print("    Continuing without prior year data (all 2024 figures will be zero)")
        prior_rows = []

    # ── Step 3: Generate Audit Report JSON ───────────────────────────────
    print("\n[3/5] Generating structured audit report JSON...")
    report_json = generate_audit_report(
        trial_balance=tb_rows,
        profile=PROFILE,
        company_info=COMPANY_INFO,
        prior_year_data=prior_rows or None,
        tb_categories={row["account_name"]: row.get("category", "other") for row in tb_rows},
    )

    is_comp = report_json.get("metadata", {}).get("is_comparative", False)
    print(f"  ✓ Report generated | is_comparative={is_comp}")

    stmts     = report_json.get("financial_statements", {})
    sofp_data = stmts.get("statement_of_financial_position", {})
    sopl_data = stmts.get("statement_of_profit_or_loss", {})

    # Print key figures
    sofp_total = sofp_data.get("total", {})
    if sofp_total:
        print(f"  Total Assets  2025: AED {sofp_total.get('current_year', 0):>15,.0f}")
        print(f"  Total Assets  2024: AED {sofp_total.get('prior_year',  0):>15,.0f}")

    for sec in sopl_data.get("sections", []):
        if sec.get("title") == "Revenue":
            st = sec.get("subtotal", {})
            print(f"  Revenue       2025: AED {st.get('current_year', 0):>15,.0f}")
            print(f"  Revenue       2024: AED {st.get('prior_year',  0):>15,.0f}")
            break

    sopl_tot = sopl_data.get("total") or sopl_data.get("net_profit") or {}
    if sopl_tot:
        print(f"  Net Profit    2025: AED {sopl_tot.get('current_year', 0):>15,.0f}")
        print(f"  Net Profit    2024: AED {sopl_tot.get('prior_year',  0):>15,.0f}")

    OUT_JSON.write_text(json.dumps(report_json, indent=2, default=str))
    print(f"  Saved JSON → {OUT_JSON.name}")

    # ── Step 4: Generate PDF ──────────────────────────────────────────────
    print("\n[4/5] Generating PDF (US Letter, 21 notes)...")
    pdf_bytes = apply_format(report_json, FORMAT_TEMPLATE, "pdf")
    OUT_PDF.write_bytes(pdf_bytes)
    print(f"  ✓ PDF saved → {OUT_PDF.name} ({len(pdf_bytes):,} bytes)")

    # ── Step 5: Query — Revenue 2024 vs 2025 ─────────────────────────────
    print("\n[5/5] QUERY: Revenue for 2024 and 2025")
    print("-" * 65)

    rev_2025 = rev_2024 = None
    for sec in sopl_data.get("sections", []):
        if sec.get("title") == "Revenue":
            st = sec.get("subtotal", {})
            rev_2025 = st.get("current_year")
            rev_2024 = st.get("prior_year")
            break

    if rev_2025 is not None:
        print(f"  Revenue 2025 (current year):  AED {rev_2025:>12,.2f}")
    if rev_2024 is not None and rev_2024 != 0:
        print(f"  Revenue 2024 (prior year):    AED {rev_2024:>12,.2f}")
    elif prior_rows:
        py_rev = next((r for r in prior_rows
                       if "revenue" in r.get("account_name","").lower()), None)
        if py_rev:
            v = py_rev.get("prior_year_value", 0)
            print(f"  Revenue 2024 (from signed audit): AED {v:>8,.2f}")
        else:
            print("  Revenue 2024: not matched in prior year extraction")
    else:
        print("  Revenue 2024: not available (prior year extraction failed)")

    print("\n✅ Done!")
    print(f"   PDF: {OUT_PDF}")


if __name__ == "__main__":
    asyncio.run(main())

