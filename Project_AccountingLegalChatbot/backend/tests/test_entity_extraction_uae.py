"""TDD tests for UAE-specific entity extraction in graph_rag._extract_entities."""
import pytest
from core.rag.graph_rag import _extract_entities


class TestFinanceTerms:
    def test_vat_extracted_as_metric(self):
        entities = _extract_entities("VAT applies at 5% on standard-rated supplies.")
        names = [n.lower() for n, _ in entities]
        assert "vat" in names

    def test_ifrs_extracted(self):
        entities = _extract_entities("Financial statements prepared under IFRS standards.")
        names = [n.lower() for n, _ in entities]
        assert "ifrs" in names

    def test_revenue_extracted_as_metric(self):
        entities = _extract_entities("Total revenue increased by 12% year on year.")
        names_types = {n.lower(): t for n, t in entities}
        assert "revenue" in names_types
        assert names_types["revenue"] == "METRIC"


class TestLegalTerms:
    def test_inheritance_extracted_as_legal(self):
        entities = _extract_entities("UAE inheritance law governs distribution of estate.")
        names_types = {n.lower(): t for n, t in entities}
        assert "inheritance" in names_types
        assert names_types["inheritance"] == "LEGAL"

    def test_shareholder_extracted(self):
        entities = _extract_entities("Shareholder approval is required for this transaction.")
        names = [n.lower() for n, _ in entities]
        assert "shareholder" in names


class TestUAELawRegex:
    def test_federal_decree_law_extracted_as_law(self):
        text = "Federal Decree-Law No. 47 of 2022 on corporate tax applies."
        entities = _extract_entities(text)
        names_types = {n: t for n, t in entities}
        law_entities = [n for n, t in entities if t == "LAW"]
        assert any("Federal Decree" in n or "No. 47" in n for n in law_entities), \
            f"Expected UAE law entity, got: {entities}"

    def test_cabinet_decision_extracted(self):
        text = "Cabinet Decision No. 56 of 2023 amends the VAT Executive Regulation."
        entities = _extract_entities(text)
        law_entities = [n for n, t in entities if t == "LAW"]
        assert any("Cabinet Decision" in n for n in law_entities), \
            f"Expected Cabinet Decision entity, got: {entities}"

    def test_article_reference_extracted(self):
        text = "As per Article 45 of the Federal Tax Procedures Law."
        entities = _extract_entities(text)
        law_entities = [n for n, t in entities if t == "LAW"]
        assert any("Article" in n for n in law_entities), \
            f"Expected Article entity, got: {entities}"


class TestAEDAmounts:
    def test_aed_amount_extracted_as_money(self):
        text = "The mandatory VAT registration threshold is AED 375,000."
        entities = _extract_entities(text)
        money_entities = [n for n, t in entities if t == "MONEY"]
        assert any("375" in n or "AED" in n for n in money_entities), \
            f"Expected AED money entity, got: {entities}"

    def test_aed_decimal_extracted(self):
        text = "Late payment fee of AED 1,000.00 per month."
        entities = _extract_entities(text)
        money_entities = [n for n, t in entities if t == "MONEY"]
        assert len(money_entities) >= 1


class TestDeduplication:
    def test_duplicate_entities_removed(self):
        text = "VAT is due. VAT applies. VAT registration required."
        entities = _extract_entities(text)
        names_lower = [n.lower() for n, _ in entities]
        assert names_lower.count("vat") == 1, "Duplicates must be removed"

    def test_cap_at_40_entities(self):
        # Generate text with many unique entities
        text = " ".join([f"AED {i},000" for i in range(1, 60)])
        entities = _extract_entities(text)
        assert len(entities) <= 40, f"Must cap at 40, got {len(entities)}"


class TestEInvoicingTerms:
    """Graph entity extraction must capture e-invoicing domain terms."""

    def test_einvoicing_term_extracted(self):
        from core.rag.graph_rag import _extract_entities
        entities = _extract_entities("The FTA requires e-invoicing via Peppol network.")
        terms = {name.lower() for name, _ in entities}
        assert "e-invoicing" in terms or "fta" in terms, \
            f"Expected 'e-invoicing' and/or 'fta' entity, got: {terms}"
        assert "peppol" in terms, \
            f"Expected 'peppol' entity in: {terms}"

    def test_peppol_term_extracted(self):
        from core.rag.graph_rag import _extract_entities
        entities = _extract_entities("Peppol service providers must register with FTA portal.")
        terms = {name.lower() for name, _ in entities}
        assert "peppol" in terms, \
            f"Expected 'peppol' entity in: {terms}"
        assert "fta" in terms, \
            f"Expected 'fta' entity in: {terms}"

    def test_invoice_term_extracted(self):
        from core.rag.graph_rag import _extract_entities
        entities = _extract_entities("Electronic invoice must comply with VAT regulations.")
        terms = {name.lower() for name, _ in entities}
        assert "electronic invoice" in terms or "invoice" in terms, \
            f"Expected 'electronic invoice' or 'invoice' entity, got: {terms}"
