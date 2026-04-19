from enum import Enum
from pydantic import BaseModel


class DomainLabel(str, Enum):
    VAT = "vat"
    CORPORATE_TAX = "corporate_tax"
    PEPPOL = "peppol"
    E_INVOICING = "e_invoicing"
    LABOUR = "labour"
    COMMERCIAL = "commercial"
    IFRS = "ifrs"
    GENERAL_LAW = "general_law"


class ClassifierResult(BaseModel):
    domain: DomainLabel
    confidence: float
    alternatives: list[tuple[DomainLabel, float]]
