"""
Integration + unit tests for the NotebookLM-style audit profile system.

Covers:
  - Profile CRUD  (create / list / get / delete)
  - Source document upload & extraction
  - Profile building (merge extractions → profile_json)
  - Account mapping get / update
  - Format template get / update
  - Report generation from trial balance + profile
  - Report export (PDF, DOCX, XLSX)
  - Unit tests for core modules (document_analyzer, structured_report_generator, format_applier)
"""

import io
import os
import tempfile

import openpyxl
import pytest


# ── Test-data helpers ────────────────────────────────────────────────────────


def _make_tb_xlsx() -> bytes:
    """Create a minimal trial-balance Excel file with realistic accounts."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trial Balance"
    ws.append(["Account Name", "Debit", "Credit"])
    ws.append(["Cash at Bank", "50000", "0"])
    ws.append(["Trade Receivables", "120000", "0"])
    ws.append(["Inventory", "80000", "0"])
    ws.append(["Trade Payables", "0", "60000"])
    ws.append(["Share Capital", "0", "200000"])
    ws.append(["Revenue", "0", "500000"])
    ws.append(["Cost of Sales", "300000", "0"])
    ws.append(["Salaries Expense", "150000", "0"])
    ws.append(["Rent Expense", "30000", "0"])
    ws.append(["Depreciation Expense", "20000", "0"])
    ws.append(["Interest Expense", "10000", "0"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_source_xlsx() -> bytes:
    """Prior-audit style Excel with account data for extraction."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Prior Audit"
    ws.append(["Account", "Notes", "Current Year (AED)", "Prior Year (AED)"])
    ws.append(["Cash at Bank", "4", "45000", "40000"])
    ws.append(["Trade Receivables", "5", "100000", "90000"])
    ws.append(["Revenue", "10", "400000", "350000"])
    ws.append(["Cost of Sales", "11", "250000", "220000"])
    ws.append(["Salaries Expense", "12", "120000", "110000"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SAMPLE_PROFILE_JSON = {
    "account_mapping": {
        "Cash at Bank": {"name": "Cash at Bank", "mapped_to": "Current Assets", "confidence": 0.7, "source": "keyword_inference"},
        "Trade Receivables": {"name": "Trade Receivables", "mapped_to": "Current Assets", "confidence": 0.7, "source": "keyword_inference"},
        "Inventory": {"name": "Inventory", "mapped_to": "Current Assets", "confidence": 0.7, "source": "keyword_inference"},
        "Trade Payables": {"name": "Trade Payables", "mapped_to": "Current Liabilities", "confidence": 0.7, "source": "keyword_inference"},
        "Share Capital": {"name": "Share Capital", "mapped_to": "Equity", "confidence": 0.7, "source": "keyword_inference"},
        "Revenue": {"name": "Revenue", "mapped_to": "Revenue", "confidence": 0.7, "source": "keyword_inference"},
        "Cost of Sales": {"name": "Cost of Sales", "mapped_to": "Cost of Sales", "confidence": 0.7, "source": "keyword_inference"},
        "Salaries Expense": {"name": "Salaries Expense", "mapped_to": "Operating Expenses", "confidence": 0.7, "source": "keyword_inference"},
        "Rent Expense": {"name": "Rent Expense", "mapped_to": "Operating Expenses", "confidence": 0.7, "source": "keyword_inference"},
        "Depreciation Expense": {"name": "Depreciation Expense", "mapped_to": "Operating Expenses", "confidence": 0.7, "source": "keyword_inference"},
        "Interest Expense": {"name": "Interest Expense", "mapped_to": "Finance Costs", "confidence": 0.7, "source": "keyword_inference"},
    },
    "format_template": {
        "columns": ["Account", "Notes", "Current Year", "Prior Year"],
        "currency_symbol": "AED",
        "page_structure": {},
        "total_pages": None,
    },
    "custom_requirements": {
        "audit_standard": "ISA",
        "opinion_type": "unqualified",
        "currency": "AED",
    },
    "financial_data": {},
    "statement_groupings": {},
    "source_summary": [],
}

SAMPLE_REPORT_JSON = {
    "metadata": {
        "report_id": "test-001",
        "company_name": "Test Co",
        "period_end": "31 December 2024",
        "currency": "AED",
        "auditor_name": "Auditor LLC",
    },
    "auditor_opinion": {
        "opinion_type": "unqualified",
        "opinion_text": "In our opinion the financial statements present fairly…",
        "basis_text": "",
        "key_audit_matters": [],
        "going_concern": False,
        "going_concern_note": "",
    },
    "financial_statements": {
        "statement_of_financial_position": {
            "title": "Statement of Financial Position",
            "sections": [
                {
                    "title": "Current Assets",
                    "line_items": [
                        {"account_name": "Cash at Bank", "current_year": 50000, "prior_year": 0},
                        {"account_name": "Trade Receivables", "current_year": 120000, "prior_year": 0},
                    ],
                    "subtotal": {"account_name": "Total Current Assets", "current_year": 170000, "prior_year": 0},
                },
            ],
            "total": {"account_name": "Total Assets", "current_year": 170000, "prior_year": 0},
        },
        "statement_of_profit_or_loss": {
            "title": "Statement of Profit or Loss",
            "sections": [
                {
                    "title": "Revenue",
                    "line_items": [
                        {"account_name": "Revenue", "current_year": 500000, "prior_year": 0},
                    ],
                    "subtotal": {"account_name": "Total Revenue", "current_year": 500000, "prior_year": 0},
                },
            ],
            "total": {"account_name": "Net Profit / (Loss)", "current_year": 500000, "prior_year": 0},
        },
        "statement_of_changes_in_equity": None,
        "statement_of_cash_flows": None,
    },
    "notes": {
        "accounting_policies": "1. General Information\nTest Co.",
        "critical_estimates": "Management makes estimates.",
        "sections": [
            {"note_number": 4, "title": "Current Assets", "content": "Total Current Assets: AED 170,000.00"},
        ],
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  1. Profile CRUD
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_profile(client):
    resp = await client.post("/api/audit-profiles", json={
        "engagement_name": "Test Engagement",
        "client_name": "ACME Corp",
        "period_end": "2024-12-31",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["engagement_name"] == "Test Engagement"
    assert data["client_name"] == "ACME Corp"
    assert data["status"] == "draft"
    assert data["id"]


@pytest.mark.asyncio
async def test_list_profiles(client):
    await client.post("/api/audit-profiles", json={"engagement_name": "List Test 1"})
    await client.post("/api/audit-profiles", json={"engagement_name": "List Test 2"})
    resp = await client.get("/api/audit-profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert isinstance(profiles, list)
    assert len(profiles) >= 2


@pytest.mark.asyncio
async def test_get_profile(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Get Test"})
    pid = create.json()["id"]
    resp = await client.get(f"/api/audit-profiles/{pid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


@pytest.mark.asyncio
async def test_get_profile_not_found(client):
    resp = await client.get("/api/audit-profiles/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_profile(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Delete Test"})
    pid = create.json()["id"]
    resp = await client.delete(f"/api/audit-profiles/{pid}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/audit-profiles/{pid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_profile_not_found(client):
    resp = await client.delete("/api/audit-profiles/nonexistent-id")
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
#  2. Document Upload & Extraction
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_upload_source_document_excel(client, monkeypatch):
    """Upload an Excel source doc and verify extraction metadata."""
    # Patch PROFILE_UPLOAD_DIR to use a temp directory
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        create = await client.post("/api/audit-profiles", json={"engagement_name": "Upload Test"})
        pid = create.json()["id"]

        resp = await client.post(
            f"/api/audit-profiles/{pid}/upload-source",
            files={"file": ("prior_audit.xlsx", io.BytesIO(_make_source_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"document_type": "prior_audit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "extracted"
        assert data["document_type"] == "prior_audit"
        assert data["original_filename"] == "prior_audit.xlsx"
        assert data["confidence"] > 0
        assert data["extracted_data"] is not None
        assert len(data["extracted_data"].get("tables", [])) > 0


@pytest.mark.asyncio
async def test_upload_source_invalid_type(client):
    """Invalid document_type returns 400."""
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Bad Type Test"})
    pid = create.json()["id"]

    resp = await client.post(
        f"/api/audit-profiles/{pid}/upload-source",
        files={"file": ("test.xlsx", io.BytesIO(b"dummy"), "application/octet-stream")},
        data={"document_type": "invalid_type"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_source_profile_not_found(client):
    resp = await client.post(
        "/api/audit-profiles/nonexistent-id/upload-source",
        files={"file": ("test.xlsx", io.BytesIO(b"data"), "application/octet-stream")},
        data={"document_type": "custom"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_source_documents(client, monkeypatch):
    """Upload a doc then verify it appears in the source-documents list."""
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        create = await client.post("/api/audit-profiles", json={"engagement_name": "List Docs Test"})
        pid = create.json()["id"]

        await client.post(
            f"/api/audit-profiles/{pid}/upload-source",
            files={"file": ("data.xlsx", io.BytesIO(_make_source_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"document_type": "prior_audit"},
        )

        resp = await client.get(f"/api/audit-profiles/{pid}/source-documents")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= 1
        assert docs[0]["original_filename"] == "data.xlsx"


# ═════════════════════════════════════════════════════════════════════════════
#  3. Profile Building
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_build_profile(client, monkeypatch):
    """Upload a source doc then build profile; verify merged JSON."""
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        create = await client.post("/api/audit-profiles", json={
            "engagement_name": "Build Test",
            "client_name": "Build Co",
            "period_end": "2024-12-31",
        })
        pid = create.json()["id"]

        # Upload source
        await client.post(
            f"/api/audit-profiles/{pid}/upload-source",
            files={"file": ("audit.xlsx", io.BytesIO(_make_source_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"document_type": "prior_audit"},
        )

        # Build
        resp = await client.post(f"/api/audit-profiles/{pid}/build-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        pj = data["profile_json"]
        assert "account_mapping" in pj
        assert "format_template" in pj
        assert "financial_data" in pj


@pytest.mark.asyncio
async def test_build_profile_no_docs(client):
    """Building with no uploaded docs should 400."""
    create = await client.post("/api/audit-profiles", json={"engagement_name": "No Docs"})
    pid = create.json()["id"]
    resp = await client.post(f"/api/audit-profiles/{pid}/build-profile")
    assert resp.status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
#  4. Account Mapping
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_account_mapping_empty(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Mapping Empty"})
    pid = create.json()["id"]
    resp = await client.get(f"/api/audit-profiles/{pid}/account-mapping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_accounts"] == 0
    assert data["account_mapping"] == {}


@pytest.mark.asyncio
async def test_update_account_mapping(client):
    # Create profile with initial profile_json containing mapping section
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Mapping Update"})
    pid = create.json()["id"]

    resp = await client.put(f"/api/audit-profiles/{pid}/account-mapping", json={
        "account_name": "Office Supplies",
        "mapped_to": "Operating Expenses",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_name"] == "Office Supplies"
    assert data["mapped_to"] == "Operating Expenses"
    assert data["total_accounts"] == 1

    # Verify via GET
    get_resp = await client.get(f"/api/audit-profiles/{pid}/account-mapping")
    mapping = get_resp.json()["account_mapping"]
    assert "Office Supplies" in mapping
    assert mapping["Office Supplies"]["source"] == "user_override"


@pytest.mark.asyncio
async def test_update_account_mapping_not_found(client):
    resp = await client.put("/api/audit-profiles/nonexistent-id/account-mapping", json={
        "account_name": "Cash", "mapped_to": "Current Assets",
    })
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
#  5. Format Template
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_format_template_empty(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Format Empty"})
    pid = create.json()["id"]
    resp = await client.get(f"/api/audit-profiles/{pid}/format-template")
    assert resp.status_code == 200
    data = resp.json()
    assert "format_template" in data
    assert "custom_requirements" in data


@pytest.mark.asyncio
async def test_update_format_template(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Format Update"})
    pid = create.json()["id"]

    new_template = {"columns": ["Account", "Notes", "AED"], "font_size": 11}
    resp = await client.put(f"/api/audit-profiles/{pid}/format-template", json={
        "format_template": new_template,
        "custom_requirements": {"currency": "USD"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["format_template"]["font_size"] == 11
    assert data["custom_requirements"]["currency"] == "USD"

    # Verify round-trip
    get_resp = await client.get(f"/api/audit-profiles/{pid}/format-template")
    assert get_resp.json()["format_template"]["columns"] == ["Account", "Notes", "AED"]


@pytest.mark.asyncio
async def test_update_format_template_not_found(client):
    resp = await client.put("/api/audit-profiles/nonexistent-id/format-template", json={
        "format_template": {"columns": []},
    })
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
#  6. Report Generation
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_report(client, monkeypatch):
    """Full pipeline: create profile → set mappings → upload TB → generate report."""
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        # Create profile with ready mappings
        create = await client.post("/api/audit-profiles", json={
            "engagement_name": "Report Gen",
            "client_name": "Report Co",
            "period_end": "31 December 2024",
        })
        pid = create.json()["id"]

        # Set profile_json with account_mapping directly via PUT
        await client.put(f"/api/audit-profiles/{pid}", json={
            "profile_json": SAMPLE_PROFILE_JSON,
        })

        # Upload trial balance and generate report
        resp = await client.post(
            f"/api/audit-profiles/{pid}/generate-report",
            files={"file": ("tb.xlsx", io.BytesIO(_make_tb_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={
                "company_name": "Report Co",
                "period_end": "31 December 2024",
                "auditor_name": "Auditor LLC",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_id"] == pid
        assert data["tb_rows_processed"] > 0
        report = data["report"]
        assert "metadata" in report
        assert "financial_statements" in report
        assert "auditor_opinion" in report
        assert "notes" in report
        assert report["metadata"]["company_name"] == "Report Co"


@pytest.mark.asyncio
async def test_generate_report_no_profile_data(client, monkeypatch):
    """Generating report without profile data should 400."""
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        create = await client.post("/api/audit-profiles", json={"engagement_name": "No Data"})
        pid = create.json()["id"]

        resp = await client.post(
            f"/api/audit-profiles/{pid}/generate-report",
            files={"file": ("tb.xlsx", io.BytesIO(_make_tb_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={},
        )
        assert resp.status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
#  7. Report Export (PDF / DOCX / XLSX)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_report_pdf(client, monkeypatch):
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        create = await client.post("/api/audit-profiles", json={
            "engagement_name": "Export PDF", "client_name": "Export Co",
        })
        pid = create.json()["id"]
        await client.put(f"/api/audit-profiles/{pid}", json={"profile_json": SAMPLE_PROFILE_JSON})

        resp = await client.post(
            f"/api/audit-profiles/{pid}/export-report/pdf",
            files={"file": ("tb.xlsx", io.BytesIO(_make_tb_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"company_name": "Export Co"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 100
        assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_export_report_docx(client, monkeypatch):
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        create = await client.post("/api/audit-profiles", json={
            "engagement_name": "Export DOCX", "client_name": "Export Co",
        })
        pid = create.json()["id"]
        await client.put(f"/api/audit-profiles/{pid}", json={"profile_json": SAMPLE_PROFILE_JSON})

        resp = await client.post(
            f"/api/audit-profiles/{pid}/export-report/docx",
            files={"file": ("tb.xlsx", io.BytesIO(_make_tb_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"company_name": "Export Co"},
        )
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.headers["content-type"]
        assert len(resp.content) > 100
        assert resp.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_report_xlsx(client, monkeypatch):
    import api.audit_profiles as ap_mod
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(ap_mod, "PROFILE_UPLOAD_DIR", __import__("pathlib").Path(tmpdir))

        create = await client.post("/api/audit-profiles", json={
            "engagement_name": "Export XLSX", "client_name": "Export Co",
        })
        pid = create.json()["id"]
        await client.put(f"/api/audit-profiles/{pid}", json={"profile_json": SAMPLE_PROFILE_JSON})

        resp = await client.post(
            f"/api/audit-profiles/{pid}/export-report/xlsx",
            files={"file": ("tb.xlsx", io.BytesIO(_make_tb_xlsx()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"company_name": "Export Co"},
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert len(resp.content) > 100
        assert resp.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_report_unsupported_format(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Bad Fmt"})
    pid = create.json()["id"]
    await client.put(f"/api/audit-profiles/{pid}", json={"profile_json": SAMPLE_PROFILE_JSON})

    resp = await client.post(
        f"/api/audit-profiles/{pid}/export-report/csv",
        files={"file": ("tb.xlsx", io.BytesIO(_make_tb_xlsx()), "application/octet-stream")},
        data={},
    )
    assert resp.status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
#  8. Unit tests — core modules
# ═════════════════════════════════════════════════════════════════════════════


class TestDocumentAnalyzer:
    """Unit tests for core.document_analyzer.analyze_document."""

    def test_analyze_excel(self):
        from core.document_analyzer import analyze_document

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(_make_source_xlsx())
            f.flush()
            path = f.name
        try:
            result = analyze_document(path)
            assert result["doc_type"] == "excel"
            assert len(result["tables"]) >= 1
            assert result["text"]
            assert result["structure"]["has_tables"] is True
            assert result["metadata"]["file_size"] > 0
        finally:
            os.unlink(path)

    def test_analyze_unsupported_type(self):
        from core.document_analyzer import analyze_document

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"just text")
            f.flush()
            path = f.name
        try:
            result = analyze_document(path)
            assert result["doc_type"] == "unknown"
            assert result["tables"] == []
        finally:
            os.unlink(path)


class TestStructuredReportGenerator:
    """Unit tests for core.structured_report_generator.generate_audit_report."""

    def test_generate_basic_report(self):
        from core.structured_report_generator import generate_audit_report

        tb = [
            {"account_name": "Cash at Bank", "debit": 50000, "credit": 0},
            {"account_name": "Trade Receivables", "debit": 120000, "credit": 0},
            {"account_name": "Trade Payables", "debit": 0, "credit": 60000},
            {"account_name": "Revenue", "debit": 0, "credit": 500000},
            {"account_name": "Cost of Sales", "debit": 300000, "credit": 0},
        ]

        report = generate_audit_report(
            trial_balance=tb,
            profile=SAMPLE_PROFILE_JSON,
            company_info={"company_name": "Unit Test Co", "period_end": "2024-12-31"},
        )

        assert "metadata" in report
        assert "financial_statements" in report
        assert "auditor_opinion" in report
        assert "notes" in report
        assert report["metadata"]["company_name"] == "Unit Test Co"

        fs = report["financial_statements"]
        assert fs["statement_of_financial_position"] is not None
        assert fs["statement_of_profit_or_loss"] is not None

    def test_generate_with_empty_tb(self):
        from core.structured_report_generator import generate_audit_report

        report = generate_audit_report(trial_balance=[], profile=SAMPLE_PROFILE_JSON)
        assert "metadata" in report
        assert "financial_statements" in report

    def test_auditor_opinion_types(self):
        from core.structured_report_generator import generate_audit_report

        profile_qualified = {**SAMPLE_PROFILE_JSON, "custom_requirements": {"opinion_type": "qualified"}}
        report = generate_audit_report(trial_balance=[], profile=profile_qualified)
        assert report["auditor_opinion"]["opinion_type"] == "qualified"
        assert "except for" in report["auditor_opinion"]["opinion_text"].lower()


class TestFormatApplier:
    """Unit tests for core.format_applier.apply_format."""

    def test_apply_format_pdf(self):
        from core.format_applier import apply_format

        result = apply_format(SAMPLE_REPORT_JSON, output_format="pdf")
        assert isinstance(result, bytes)
        assert len(result) > 100
        assert result[:4] == b"%PDF"

    def test_apply_format_docx(self):
        from core.format_applier import apply_format

        result = apply_format(SAMPLE_REPORT_JSON, output_format="docx")
        assert isinstance(result, bytes)
        assert len(result) > 100
        assert result[:2] == b"PK"

    def test_apply_format_xlsx(self):
        from core.format_applier import apply_format

        result = apply_format(SAMPLE_REPORT_JSON, output_format="xlsx")
        assert isinstance(result, bytes)
        assert len(result) > 100
        assert result[:2] == b"PK"

    def test_apply_format_unsupported(self):
        from core.format_applier import apply_format

        with pytest.raises(ValueError, match="Unsupported"):
            apply_format(SAMPLE_REPORT_JSON, output_format="html")

    def test_apply_format_with_template(self):
        from core.format_applier import apply_format

        tpl = {"currency_symbol": "USD", "font_size": 12}
        result = apply_format(SAMPLE_REPORT_JSON, format_template=tpl, output_format="pdf")
        assert isinstance(result, bytes)
        assert len(result) > 100


class TestAuditProfileBuilder:
    """Unit tests for core.audit_profile_builder."""

    def test_build_profile_from_documents(self):
        from core.audit_profile_builder import build_profile_from_documents

        docs = [{
            "doc_type": "excel",
            "file_name": "tb.xlsx",
            "pages": 1,
            "tables": [
                [
                    ["Account", "Debit", "Credit"],
                    ["Cash at Bank", "50000", "0"],
                    ["Trade Receivables", "120000", "0"],
                    ["Revenue", "0", "500000"],
                    ["Cost of Sales", "300000", "0"],
                    ["Salaries Expense", "150000", "0"],
                ],
            ],
            "text": "Cash at Bank | 50000 | 0",
            "structure": {"has_tables": True, "table_count": 1},
            "metadata": {"file_size": 1000},
        }]

        profile = build_profile_from_documents(docs, client_name="Builder Co", period_end="2024-12-31")
        assert profile["client_name"] == "Builder Co"
        assert "account_mapping" in profile
        assert "format_template" in profile
        assert "financial_data" in profile
        assert len(profile["source_summary"]) == 1
        # Keyword-inferred mappings should exist for known accounts
        assert len(profile["account_mapping"]) > 0

    def test_infer_account_mapping(self):
        from core.audit_profile_builder import infer_account_mapping

        doc = {
            "tables": [
                [
                    ["Account", "Amount"],
                    ["Cash at Bank", "50000"],
                    ["Trade Receivables", "120000"],
                    ["Salaries Expense", "80000"],
                    ["Revenue", "500000"],
                ],
            ],
        }
        mappings = infer_account_mapping(doc)
        assert "Cash at Bank" in mappings
        assert mappings["Cash at Bank"]["mapped_to"] == "Current Assets"
        assert "Revenue" in mappings
        assert mappings["Revenue"]["mapped_to"] == "Revenue"
        assert "Salaries Expense" in mappings
        assert mappings["Salaries Expense"]["mapped_to"] == "Operating Expenses"


# ═════════════════════════════════════════════════════════════════════════════
#  9. Bulk Account Mapping
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_bulk_update_account_mapping(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Bulk Map"})
    pid = create.json()["id"]

    resp = await client.put(f"/api/audit-profiles/{pid}/account-mapping/bulk", json={
        "mappings": {
            "Cash at Bank": "Current Assets",
            "Revenue": "Revenue",
            "Salary Expense": "Operating Expenses",
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated_count"] == 3
    assert data["total_accounts"] == 3

    # Verify
    get_resp = await client.get(f"/api/audit-profiles/{pid}/account-mapping")
    assert get_resp.json()["total_accounts"] == 3


# ═════════════════════════════════════════════════════════════════════════════
#  10. Update Profile (PUT)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_profile(client):
    create = await client.post("/api/audit-profiles", json={"engagement_name": "Update Me"})
    pid = create.json()["id"]

    resp = await client.put(f"/api/audit-profiles/{pid}", json={
        "engagement_name": "Updated Name",
        "client_name": "New Client",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["engagement_name"] == "Updated Name"
    assert data["client_name"] == "New Client"


@pytest.mark.asyncio
async def test_update_profile_not_found(client):
    resp = await client.put("/api/audit-profiles/nonexistent-id", json={
        "engagement_name": "Doesn't Matter",
    })
    assert resp.status_code == 404
