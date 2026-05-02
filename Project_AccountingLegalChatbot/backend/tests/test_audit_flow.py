"""Tests for new audit flow endpoints."""
import io
import pytest


@pytest.mark.asyncio
async def test_extract_template_txt(client):
    content = b"Section 1: Auditor Opinion\nSection 2: Key Findings"
    resp = await client.post(
        "/api/reports/extract-template",
        files={"file": ("template.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "Auditor Opinion" in data["text"]


@pytest.mark.asyncio
async def test_extract_template_unsupported_type(client):
    resp = await client.post(
        "/api/reports/extract-template",
        files={"file": ("bad.zip", io.BytesIO(b"data"), "application/zip")},
    )
    assert resp.status_code == 400


import openpyxl


def _make_tb_xlsx() -> bytes:
    """Create a minimal trial balance Excel file."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Account Code", "Account Name", "Debit", "Credit"])
    ws.append(["1001", "Cash at Bank", 50000, 0])
    ws.append(["1100", "Trade Receivables", 120000, 0])
    ws.append(["2001", "Trade Payables", 0, 80000])
    ws.append(["3001", "Share Capital", 0, 200000])
    ws.append(["4001", "Revenue", 0, 500000])
    ws.append(["5001", "Cost of Sales", 300000, 0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_trial_balance_audit_returns_grouped_rows(client, monkeypatch):
    """upload-trial-balance with report_type=audit should return grouped_rows."""
    async def _mock_group(rows):
        return [
            {"account": "Cash at Bank", "mappedTo": "Cash and Cash Equivalents", "amount": 50000.0},
            {"account": "Trade Receivables", "mappedTo": "Current Assets", "amount": 120000.0},
        ]
    import api.reports as reports_mod
    monkeypatch.setattr(reports_mod, "_group_tb_with_llm", _mock_group)

    resp = await client.post(
        "/api/reports/upload-trial-balance",
        files={"file": ("tb.xlsx", io.BytesIO(_make_tb_xlsx()),
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"report_type": "audit"},
    )
    if resp.status_code != 200:
        print(f"DEBUG: {resp.status_code} - {resp.text}")
    assert resp.status_code == 200
    data = resp.json()
    assert "grouped_rows" in data
    assert len(data["grouped_rows"]) == 2
    assert data["grouped_rows"][0]["mappedTo"] == "Cash and Cash Equivalents"


@pytest.mark.asyncio
async def test_draft_report_returns_markdown(client, monkeypatch):
    from core.llm_manager import LLMResponse
    class MockProvider:
        async def chat(self, messages, temperature=0.2, max_tokens=None):
            return LLMResponse("## Audit Report\nAll looks good.", "mock", "mock")
    
    def _mock_get_provider(provider=None):
        return MockProvider()
        
    import api.reports as reports_mod
    monkeypatch.setattr(reports_mod, "get_llm_provider", _mock_get_provider)

    resp = await client.post("/api/reports/draft", json={
        "grouped_rows": [{"account": "Cash", "mappedTo": "Current Assets", "amount": 100000}],
        "company_name": "Test Co",
        "auditor_name": "Jane Doe",
        "period_end": "2024-12-31",
    })
    assert resp.status_code == 200
    assert "report_text" in resp.json()


@pytest.mark.asyncio
async def test_format_report_returns_markdown(client, monkeypatch):
    from core.llm_manager import LLMResponse
    class MockProvider:
        async def chat(self, messages, temperature=0.2, max_tokens=None):
            return LLMResponse("## Big 4 Formatted Report\nKAMs: ...", "mock", "mock")
    
    def _mock_get_provider(provider=None):
        return MockProvider()
        
    import api.reports as reports_mod
    monkeypatch.setattr(reports_mod, "get_llm_provider", _mock_get_provider)

    resp = await client.post("/api/reports/format", json={
        "draft": "## Draft\nSome content",
        "format": "big4",
    })
    assert resp.status_code == 200
    assert "report_text" in resp.json()
