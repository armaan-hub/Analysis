from backend.core.report_templates.report_intel import REPORT_INTEL

EXPECTED_TYPES = [
    "mis", "audit", "tax_advisory", "legal_memo", "due_diligence",
    "financial_analysis", "compliance", "board_pack", "vat_filing",
    "aml_report", "valuation", "contract_review",
]


def test_all_report_types_present():
    for rt in EXPECTED_TYPES:
        assert rt in REPORT_INTEL, f"Missing report type: {rt}"


def test_each_type_has_required_keys():
    for rt, intel in REPORT_INTEL.items():
        for key in ("audience", "purpose", "key_points", "tone", "structure"):
            assert key in intel, f"{rt} missing key: {key}"


def test_key_points_are_lists_with_min_3():
    for rt, intel in REPORT_INTEL.items():
        assert isinstance(intel["key_points"], list), f"{rt} key_points not a list"
        assert len(intel["key_points"]) >= 3, f"{rt} has fewer than 3 key_points"
