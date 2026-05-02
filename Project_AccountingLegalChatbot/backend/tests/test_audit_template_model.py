"""
Tests for AuditTemplate and TemplateSection ORM models.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone

from db.models import AuditTemplate, TemplateSection


# ── Unit tests (pure model instantiation, no DB) ─────────────────

class TestAuditTemplateModel:
    def test_create_with_all_fields(self):
        tpl = AuditTemplate(
            id="tpl-001",
            company_name="Acme Corp",
            audit_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
            document_structure={"sections": ["balance_sheet", "income_statement"]},
            account_grouping={"assets": ["cash", "receivables"], "liabilities": ["payables"]},
            terminology={"revenue": "turnover", "profit": "surplus"},
            formatting_rules={"font": "Arial", "size": 12, "margins": {"top": 1, "bottom": 1}},
            extraction_method="llm_parse",
            confidence=0.92,
            status="approved",
            source_filename="acme_audit_2025.pdf",
        )

        assert tpl.id == "tpl-001"
        assert tpl.company_name == "Acme Corp"
        assert tpl.confidence == 0.92
        assert tpl.status == "approved"
        assert tpl.source_filename == "acme_audit_2025.pdf"
        assert tpl.extraction_method == "llm_parse"

    def test_json_fields_hold_complex_dicts(self):
        complex_structure = {
            "sections": [
                {"title": "Balance Sheet", "subsections": [
                    {"title": "Current Assets", "accounts": ["cash", "receivables"]},
                    {"title": "Non-Current Assets", "accounts": ["ppe", "intangibles"]},
                ]},
            ],
            "metadata": {"version": 2, "nested": {"deep": True}},
        }
        tpl = AuditTemplate(
            company_name="Test Co",
            document_structure=complex_structure,
            account_grouping={"groups": [{"name": "assets", "items": [1, 2, 3]}]},
            terminology={"terms": ["a", "b"], "mapping": {"x": "y"}},
            formatting_rules={"rules": [{"type": "bold", "selector": "h1"}]},
        )

        assert tpl.document_structure["metadata"]["nested"]["deep"] is True
        assert len(tpl.account_grouping["groups"][0]["items"]) == 3
        assert tpl.terminology["mapping"]["x"] == "y"

    def test_defaults_at_construction(self):
        """Column defaults are applied at flush, not construction.
        Verify explicitly-set defaults work."""
        tpl = AuditTemplate(company_name="Defaults Co", status="draft", confidence=0.0)
        assert tpl.status == "draft"
        assert tpl.confidence == 0.0

    def test_status_values(self):
        for status in ("draft", "approved", "rejected"):
            tpl = AuditTemplate(company_name="S", status=status)
            assert tpl.status == status


class TestTemplateSectionModel:
    def test_create_section(self):
        sec = TemplateSection(
            section_id="sec-001",
            template_id="tpl-001",
            title="Balance Sheet",
            level=1,
            start_page=5,
            position=0,
            content_type="table",
            table_structure={"columns": ["Account", "Amount"], "rows": 15},
            accounts=["cash", "receivables", "payables"],
        )

        assert sec.section_id == "sec-001"
        assert sec.template_id == "tpl-001"
        assert sec.title == "Balance Sheet"
        assert sec.level == 1
        assert sec.table_structure["rows"] == 15
        assert "cash" in sec.accounts


class TestRelationship:
    def test_template_sections_relationship(self):
        tpl = AuditTemplate(id="tpl-rel", company_name="Rel Co")
        sec1 = TemplateSection(section_id="s1", template_id="tpl-rel", title="Section A")
        sec2 = TemplateSection(section_id="s2", template_id="tpl-rel", title="Section B")

        tpl.sections = [sec1, sec2]

        assert len(tpl.sections) == 2
        assert tpl.sections[0].title == "Section A"
        assert tpl.sections[1].template_id == "tpl-rel"


# ── Integration tests (async DB round-trip) ──────────────────────

@pytest.mark.asyncio
async def test_persist_and_query_template(db_session):
    tpl = AuditTemplate(
        company_name="Persist Co",
        document_structure={"sections": ["a"]},
        account_grouping={"g": 1},
        terminology={"t": "v"},
        formatting_rules={"f": True},
        extraction_method="regex",
        confidence=0.85,
        status="draft",
        source_filename="persist.pdf",
    )
    db_session.add(tpl)
    await db_session.flush()

    fetched = await db_session.get(AuditTemplate, tpl.id)
    assert fetched is not None
    assert fetched.company_name == "Persist Co"
    assert fetched.document_structure == {"sections": ["a"]}
    assert fetched.confidence == 0.85


@pytest.mark.asyncio
async def test_persist_template_with_sections(db_session):
    tpl = AuditTemplate(
        company_name="Sections Co",
        status="approved",
    )
    sec = TemplateSection(
        template_id=tpl.id,
        title="Income Statement",
        level=1,
        position=0,
        content_type="table",
        table_structure={"cols": ["Account", "CY", "PY"]},
        accounts=["revenue", "cogs"],
    )
    tpl.sections.append(sec)
    db_session.add(tpl)
    await db_session.flush()

    fetched = await db_session.get(AuditTemplate, tpl.id)
    assert len(fetched.sections) == 1
    assert fetched.sections[0].title == "Income Statement"
    assert fetched.sections[0].accounts == ["revenue", "cogs"]
