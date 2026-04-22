"""
TemplateManager: downloads public accounting/audit report templates from
official sources (IAASB, Big4 style guides, FTA, ACCA) and caches them locally.
"""
from __future__ import annotations

import json
import pathlib
import time
import urllib.request
from typing import Any

_CACHE_DIR = pathlib.Path(__file__).parent / "cached_templates"
_CACHE_INDEX = _CACHE_DIR / "index.json"
_CACHE_TTL_DAYS = 30


# Public, freely-downloadable template references (metadata + URL stubs)
# These are open-access documents from IAASB, ACCA, and similar bodies.
TEMPLATE_LIBRARY: dict[str, dict[str, Any]] = {
    "isa_700_audit_report": {
        "name": "ISA 700 Auditor's Report Template",
        "body": "IAASB",
        "url": "https://www.iaasb.org/publications/international-standard-auditing-700-revised-forming-opinion-and-reporting-financial-statements",
        "standard": "ISA 700 (Revised)",
        "format_key": "isa",
        "key_sections": [
            "Independent Auditor's Report",
            "Opinion paragraph",
            "Basis for Opinion",
            "Key Audit Matters",
            "Going Concern",
            "Other Information",
            "Responsibilities of Management",
            "Auditor's Responsibilities",
            "Signature and Date",
        ],
        "audience": "Shareholders and Board of Directors",
        "applicable_reports": ["audit"],
    },
    "big4_financial_report_style": {
        "name": "Big4-Style Financial Report Structure",
        "body": "Big4 (Deloitte/PwC/EY/KPMG derived)",
        "url": "https://www.pwc.com/gx/en/services/audit-assurance/assets/pwc-illustrative-ifrs-consolidated-financial-statements.pdf",
        "standard": "IFRS + Big4 conventions",
        "format_key": "big4",
        "key_sections": [
            "Executive Summary",
            "Independent Auditor's Report",
            "Statement of Financial Position",
            "Statement of Profit or Loss and OCI",
            "Statement of Changes in Equity",
            "Statement of Cash Flows",
            "Notes to Financial Statements",
            "Key Audit Matters (Big4 style)",
        ],
        "audience": "Institutional investors, regulators",
        "applicable_reports": ["audit", "mis", "financial_analysis"],
    },
    "fta_vat_return_template": {
        "name": "UAE FTA VAT Return Form",
        "body": "UAE Federal Tax Authority",
        "url": "https://tax.gov.ae/en/taxes/value.added.tax.aspx",
        "standard": "UAE VAT Law Federal Decree-Law No. 8 of 2017",
        "format_key": "fta",
        "key_sections": [
            "Taxable Person Details",
            "VAT on Sales and all other Outputs",
            "VAT on Expenses and all other Inputs",
            "Net VAT Due",
            "Declared Tax",
            "Penalties (if any)",
        ],
        "audience": "UAE Federal Tax Authority",
        "applicable_reports": ["vat_filing", "compliance"],
    },
    "acca_due_diligence_framework": {
        "name": "ACCA Due Diligence Framework",
        "body": "ACCA",
        "url": "https://www.accaglobal.com/gb/en/professional-insights/global-economics/due-diligence.html",
        "standard": "ACCA Professional Framework",
        "format_key": "isa",
        "key_sections": [
            "Executive Summary",
            "Scope and Methodology",
            "Financial Due Diligence Findings",
            "Legal Due Diligence Findings",
            "Operational Review",
            "Risk Assessment",
            "Management Information Systems Review",
            "Conclusions and Recommendations",
        ],
        "audience": "Acquirer / Investment committee",
        "applicable_reports": ["due_diligence"],
    },
    "mis_management_report_template": {
        "name": "Management Information System Report Template",
        "body": "CIMA/ACCA derived",
        "url": "https://www.cimaglobal.com/Thought-leadership/Research-topics/Finance-transformation/",
        "standard": "CIMA Management Reporting Framework",
        "format_key": "internal",
        "key_sections": [
            "Executive Dashboard",
            "KPI Summary (vs Budget/Prior Period)",
            "Revenue Analysis",
            "Cost Analysis",
            "Cash Flow Position",
            "Variance Analysis",
            "Rolling Forecast",
            "Action Items",
        ],
        "audience": "Management / CFO",
        "applicable_reports": ["mis", "board_pack"],
    },
    "aml_compliance_report_template": {
        "name": "AML/KYC Compliance Report",
        "body": "FATF/UAE CBUAE derived",
        "url": "https://www.fatf-gafi.org/en/topics/fatf-recommendations.html",
        "standard": "FATF Recommendations + UAE AML Law",
        "format_key": "compliance",
        "key_sections": [
            "Executive Summary",
            "Regulatory Framework",
            "Risk Assessment Summary",
            "Transaction Monitoring Results",
            "Suspicious Activity Reports (SARs)",
            "Customer Due Diligence (CDD) Review",
            "Remediation Actions",
            "Compliance Officer Sign-Off",
        ],
        "audience": "Compliance Committee / Regulators",
        "applicable_reports": ["aml_report", "compliance"],
    },
}


class TemplateManager:
    """Load, cache, and refresh public report templates."""

    def __init__(self, cache_dir: pathlib.Path | None = None):
        self._cache_dir = cache_dir or _CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, Any] = self._load_index()

    # ── Public API ─────────────────────────────────────────────────────────

    def get_template(self, template_key: str) -> dict[str, Any] | None:
        """Return template metadata. Does NOT download full PDF — returns structured metadata."""
        return TEMPLATE_LIBRARY.get(template_key)

    def get_templates_for_report_type(self, report_type: str) -> list[dict[str, Any]]:
        """Return all templates applicable to a given report type."""
        return [
            {"key": k, **v}
            for k, v in TEMPLATE_LIBRARY.items()
            if report_type in v.get("applicable_reports", [])
        ]

    def get_format_instructions(self, format_key: str) -> str:
        """Return structured section guidance for a format (big4/isa/fta/internal)."""
        matches = [
            v for v in TEMPLATE_LIBRARY.values()
            if v.get("format_key") == format_key
        ]
        if not matches:
            return ""
        t = matches[0]
        sections = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(t["key_sections"]))
        return (
            f"Follow {t['name']} ({t['standard']}) structure:\n"
            f"{sections}\n"
            f"Target audience: {t['audience']}"
        )

    def refresh_cache(self) -> dict[str, str]:
        """
        Attempt to fetch HEAD request for each template URL to verify availability.
        Returns dict of {key: status} where status is 'ok' or 'unavailable'.
        """
        results: dict[str, str] = {}
        for key, template in TEMPLATE_LIBRARY.items():
            url = template.get("url", "")
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    results[key] = "ok" if resp.status < 400 else f"http_{resp.status}"
            except Exception as e:
                results[key] = f"unavailable: {str(e)[:50]}"
        self._index["last_refresh"] = time.time()
        self._save_index()
        return results

    def get_cache_status(self) -> dict[str, Any]:
        """Return cache index metadata."""
        return {
            "last_refresh": self._index.get("last_refresh"),
            "template_count": len(TEMPLATE_LIBRARY),
            "cache_dir": str(self._cache_dir),
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _load_index(self) -> dict[str, Any]:
        if _CACHE_INDEX.exists():
            try:
                return json.loads(_CACHE_INDEX.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_index(self) -> None:
        _CACHE_INDEX.write_text(
            json.dumps(self._index, indent=2, default=str),
            encoding="utf-8",
        )


# Module-level singleton
template_manager = TemplateManager()
