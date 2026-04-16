"""
Tests for document_format_analyzer — verifies PDF structural extraction.

Each test creates a programmatic PDF via PyMuPDF so no external fixtures needed.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytest

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.document_format_analyzer import analyze_audit_document


# ── Helpers ────────────────────────────────────────────────────────

def _tmp_pdf_path(tmp_path: Path, name: str = "test.pdf") -> str:
    """Return an OS path string inside pytest's tmp_path."""
    return str(tmp_path / name)


def _save_doc(doc: fitz.Document, path: str) -> str:
    doc.save(path)
    doc.close()
    return path


# ═══════════════════════════════════════════════════════════════════
# 1. Empty PDF
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_analyze_empty_pdf(tmp_path):
    """A minimal PDF with no text should return a valid empty structure."""
    doc = fitz.open()
    doc.new_page()
    pdf_path = _save_doc(doc, _tmp_pdf_path(tmp_path, "empty.pdf"))

    result = await analyze_audit_document(pdf_path)

    assert "document_structure" in result
    assert "account_grouping" in result
    assert "terminology" in result
    assert "formatting_rules" in result

    ds = result["document_structure"]
    assert ds["pages"] == 1 or ds["pages"] == 0
    assert isinstance(ds["sections"], list)
    assert isinstance(result["account_grouping"], dict)


# ═══════════════════════════════════════════════════════════════════
# 2. Financial PDF with known headings + table rows
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_analyze_financial_pdf(tmp_path):
    """PDF with audit headings and numeric rows should detect sections."""
    doc = fitz.open()

    # Page 1: cover / heading
    page1 = doc.new_page()
    page1.insert_text((72, 60), "ABC COMPANY LLC", fontsize=18)
    page1.insert_text((72, 90), "Financial Statements", fontsize=16)
    page1.insert_text((72, 115), "For the year ended 31 December 2024", fontsize=11)

    # Page 2: Statement of Financial Position
    page2 = doc.new_page()
    page2.insert_text((72, 60), "STATEMENT OF FINANCIAL POSITION", fontsize=14)
    page2.insert_text((72, 90), "As at 31 December 2024", fontsize=10)
    page2.insert_text((72, 120), "                                    2024          2023", fontsize=10)
    page2.insert_text((72, 140), "                                    AED           AED", fontsize=10)
    page2.insert_text((72, 170), "Cash and Bank Balances    1,234,567    987,654", fontsize=10)
    page2.insert_text((72, 190), "Trade Receivables         2,345,678    1,876,543", fontsize=10)
    page2.insert_text((72, 210), "Total Current Assets      3,580,245    2,864,197", fontsize=10)

    # Page 3: Statement of Profit or Loss
    page3 = doc.new_page()
    page3.insert_text((72, 60), "STATEMENT OF PROFIT OR LOSS", fontsize=14)
    page3.insert_text((72, 90), "For the year ended 31 December 2024", fontsize=10)
    page3.insert_text((72, 120), "Revenue                   5,000,000    4,200,000", fontsize=10)
    page3.insert_text((72, 140), "Cost of Sales            (3,500,000)  (2,900,000)", fontsize=10)
    page3.insert_text((72, 160), "Gross Profit              1,500,000    1,300,000", fontsize=10)

    pdf_path = _save_doc(doc, _tmp_pdf_path(tmp_path, "financial.pdf"))
    result = await analyze_audit_document(pdf_path)

    ds = result["document_structure"]
    assert ds["pages"] == 3

    # Should have detected financial statement sections
    section_titles = [s["title"] for s in ds["sections"]]
    assert any("FINANCIAL POSITION" in t.upper() for t in section_titles), (
        f"Expected 'Statement of Financial Position' heading, got: {section_titles}"
    )
    assert any("PROFIT" in t.upper() for t in section_titles), (
        f"Expected 'Profit or Loss' heading, got: {section_titles}"
    )

    # Sections should have required keys
    for section in ds["sections"]:
        assert "section_id" in section
        assert "title" in section
        assert "level" in section
        assert section["level"] in (1, 2, 3)
        assert "start_page" in section
        assert "estimated_position" in section
        assert section["estimated_position"] in ("top", "middle", "bottom")
        assert "content_type" in section
        assert "table_structure" in section


# ═══════════════════════════════════════════════════════════════════
# 3. Account grouping extraction
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_account_grouping_extraction(tmp_path):
    """Accounts under a heading should be grouped by section title."""
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((72, 50), "STATEMENT OF FINANCIAL POSITION", fontsize=14)
    page.insert_text((72, 80), "Assets", fontsize=11)
    page.insert_text((72, 100), "Cash and Bank            1,234,567    987,654", fontsize=10)
    page.insert_text((90, 120), "  Current Accounts       500,000      400,000", fontsize=10)
    page.insert_text((90, 140), "  Savings Accounts       734,567      587,654", fontsize=10)
    page.insert_text((72, 170), "Trade Receivables        2,345,678    1,876,543", fontsize=10)
    page.insert_text((72, 200), "Total Assets             3,580,245    2,864,197", fontsize=10)

    pdf_path = _save_doc(doc, _tmp_pdf_path(tmp_path, "accounts.pdf"))
    result = await analyze_audit_document(pdf_path)

    ag = result["account_grouping"]
    # Should have at least one section grouping
    assert len(ag) > 0, f"Expected account groupings, got: {ag}"

    # Find the section containing our accounts
    all_accounts = []
    for section_title, accounts in ag.items():
        for acc in accounts:
            all_accounts.append(acc)
            assert "account_name" in acc
            assert "indent_level" in acc
            assert acc["indent_level"] in (0, 1, 2)
            assert "is_subtotal" in acc
            assert "is_total" in acc

    # Check that "Total Assets" is marked as total
    total_accs = [a for a in all_accounts if a["is_total"]]
    account_names = [a["account_name"].lower() for a in all_accounts]
    assert any("total" in name for name in account_names) or len(total_accs) > 0, (
        f"Expected at least one total line, accounts: {account_names}"
    )


# ═══════════════════════════════════════════════════════════════════
# 4. Terminology detection (currency)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_terminology_detection(tmp_path):
    """Currency AED should be detected from text containing AED patterns."""
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((72, 60), "ABC COMPANY LLC", fontsize=16)
    page.insert_text((72, 90), "STATEMENT OF FINANCIAL POSITION", fontsize=14)
    page.insert_text((72, 120), "Amounts in AED", fontsize=10)
    page.insert_text((72, 150), "                           AED           AED", fontsize=10)
    page.insert_text((72, 170), "Cash                  1,234,567       987,654", fontsize=10)
    page.insert_text((72, 190), "Receivables           2,345,678     1,876,543", fontsize=10)
    page.insert_text((72, 210), "The company operates in accordance with UAE laws", fontsize=10)

    pdf_path = _save_doc(doc, _tmp_pdf_path(tmp_path, "currency.pdf"))
    result = await analyze_audit_document(pdf_path)

    terminology = result["terminology"]
    assert terminology["currency"] == "AED", (
        f"Expected AED currency, got: {terminology['currency']}"
    )
    assert isinstance(terminology["headings_seen"], list)
    assert isinstance(terminology["common_phrases"], list)


# ═══════════════════════════════════════════════════════════════════
# 5. Formatting rules (negative number format)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_formatting_rules(tmp_path):
    """Parenthetical negatives should be detected when present."""
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((72, 60), "STATEMENT OF PROFIT OR LOSS", fontsize=14)
    page.insert_text((72, 90), "Revenue                   5,000,000    4,200,000", fontsize=10)
    page.insert_text((72, 110), "Cost of Sales            (3,500,000)  (2,900,000)", fontsize=10)
    page.insert_text((72, 130), "Admin Expenses             (800,000)    (700,000)", fontsize=10)
    page.insert_text((72, 150), "Finance Costs              (150,000)    (120,000)", fontsize=10)
    page.insert_text((72, 170), "Net Profit                  550,000      480,000", fontsize=10)

    pdf_path = _save_doc(doc, _tmp_pdf_path(tmp_path, "formatting.pdf"))
    result = await analyze_audit_document(pdf_path)

    fr = result["formatting_rules"]
    assert "table_formatting" in fr
    assert fr["table_formatting"]["negative_number_format"] == "(X,XXX)", (
        f"Expected parenthetical format, got: {fr['table_formatting']['negative_number_format']}"
    )
    assert fr["table_formatting"]["currency_format"] in ("#,##0", "#,##0.00")

    assert "font_hierarchy" in fr
    assert isinstance(fr["font_hierarchy"]["heading_1_bold"], bool)
    assert isinstance(fr["font_hierarchy"]["table_header_bold"], bool)

    assert "page_break_after_sections" in fr
    assert isinstance(fr["page_break_after_sections"], list)


# ═══════════════════════════════════════════════════════════════════
# 6. Non-existent file handling
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_nonexistent_file():
    """Passing a bad path should return empty result, not crash."""
    result = await analyze_audit_document("/nonexistent/path/fake.pdf")

    assert result["document_structure"]["pages"] == 0
    assert result["document_structure"]["sections"] == []
    assert result["account_grouping"] == {}


# ═══════════════════════════════════════════════════════════════════
# 7. Multi-page section detection
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_multipage_page_break_detection(tmp_path):
    """Headings at top of subsequent pages should appear in page_break list."""
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((72, 60), "INDEPENDENT AUDITOR'S REPORT", fontsize=14)
    p1.insert_text((72, 100), "We have audited the financial statements.", fontsize=10)

    p2 = doc.new_page()
    p2.insert_text((72, 60), "STATEMENT OF FINANCIAL POSITION", fontsize=14)
    p2.insert_text((72, 100), "Cash    1,000,000    900,000", fontsize=10)

    p3 = doc.new_page()
    p3.insert_text((72, 60), "NOTES TO THE FINANCIAL STATEMENTS", fontsize=14)
    p3.insert_text((72, 100), "Note 1: Accounting policies", fontsize=10)

    pdf_path = _save_doc(doc, _tmp_pdf_path(tmp_path, "multipage.pdf"))
    result = await analyze_audit_document(pdf_path)

    ds = result["document_structure"]
    assert ds["pages"] == 3

    section_titles = [s["title"] for s in ds["sections"]]
    assert any("AUDITOR" in t.upper() for t in section_titles)
    assert any("FINANCIAL POSITION" in t.upper() for t in section_titles)
    assert any("NOTES" in t.upper() for t in section_titles)

    # Page break sections should include headings from pages 2+
    pbs = result["formatting_rules"]["page_break_after_sections"]
    assert len(pbs) >= 1, f"Expected page break sections, got: {pbs}"


# ═══════════════════════════════════════════════════════════════════
# 8. Result schema completeness
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_result_schema_completeness(tmp_path):
    """Verify all top-level and nested keys are present in the result."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sample Audit Report", fontsize=14)
    page.insert_text((72, 100), "Some content here 1,234 AED", fontsize=10)
    pdf_path = _save_doc(doc, _tmp_pdf_path(tmp_path, "schema.pdf"))

    result = await analyze_audit_document(pdf_path)

    # Top-level keys
    assert set(result.keys()) == {
        "document_structure", "account_grouping", "terminology", "formatting_rules"
    }

    # document_structure keys
    ds = result["document_structure"]
    for key in ("title", "date_range", "company_name", "auditor_name", "pages", "sections"):
        assert key in ds, f"Missing key in document_structure: {key}"

    # terminology keys
    term = result["terminology"]
    for key in ("headings_seen", "common_phrases", "currency"):
        assert key in term, f"Missing key in terminology: {key}"

    # formatting_rules keys
    fr = result["formatting_rules"]
    for key in ("page_break_after_sections", "table_formatting", "font_hierarchy"):
        assert key in fr, f"Missing key in formatting_rules: {key}"

    tf = fr["table_formatting"]
    assert "currency_format" in tf
    assert "negative_number_format" in tf

    fh = fr["font_hierarchy"]
    assert "heading_1_bold" in fh
    assert "table_header_bold" in fh
