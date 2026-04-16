"""
Audit Report JSON Schema — Pydantic models defining structured audit report output.

The audit_report.json is the intermediate representation between
raw data (trial balance + profile) and formatted output (PDF/DOCX/Excel).
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel


class ReportMetadata(BaseModel):
    report_id: str = ""
    profile_id: str = ""
    company_name: str = ""
    period_end: str = ""
    currency: str = "AED"
    auditor_name: str = ""
    audit_standard: str = "ISA"
    generated_at: str = ""


class AuditorOpinion(BaseModel):
    opinion_type: str = "unqualified"  # unqualified | qualified | adverse | disclaimer
    opinion_text: str = ""
    basis_text: str = ""
    key_audit_matters: list[str] = []
    going_concern: bool = False
    going_concern_note: str = ""


class LineItem(BaseModel):
    account_name: str
    notes_ref: Optional[str] = None
    current_year: float = 0.0
    prior_year: float = 0.0


class StatementSection(BaseModel):
    title: str
    line_items: list[LineItem] = []
    subtotal: Optional[LineItem] = None


class FinancialStatement(BaseModel):
    title: str
    sections: list[StatementSection] = []
    total: Optional[LineItem] = None


class FinancialStatements(BaseModel):
    statement_of_financial_position: Optional[FinancialStatement] = None
    statement_of_profit_or_loss: Optional[FinancialStatement] = None
    statement_of_changes_in_equity: Optional[FinancialStatement] = None
    statement_of_cash_flows: Optional[FinancialStatement] = None


class NoteSection(BaseModel):
    note_number: int = 0
    title: str = ""
    content: str = ""


class Notes(BaseModel):
    accounting_policies: str = ""
    critical_estimates: str = ""
    sections: list[NoteSection] = []


class AuditReportJSON(BaseModel):
    """Root model for the structured audit report."""
    metadata: ReportMetadata = ReportMetadata()
    auditor_opinion: AuditorOpinion = AuditorOpinion()
    financial_statements: FinancialStatements = FinancialStatements()
    notes: Notes = Notes()


def get_json_schema() -> dict:
    """Return the JSON Schema for validation."""
    return AuditReportJSON.model_json_schema()
