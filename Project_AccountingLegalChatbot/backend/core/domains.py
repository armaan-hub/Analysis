from enum import Enum
from typing import Dict, List, Set


class DomainLabel(str, Enum):
    VAT = "vat"
    CORPORATE_TAX = "corporate_tax"
    PEPPOL = "peppol"
    E_INVOICING = "e_invoicing"
    LABOUR = "labour"
    COMMERCIAL = "commercial"
    IFRS = "ifrs"
    GENERAL_LAW = "general_law"
    GENERAL = "general"


# Master keyword mapping for query classification and metadata inference
DOMAIN_KEYWORDS: Dict[DomainLabel, List[str]] = {
    DomainLabel.VAT: [
        "vat", "value added tax", "tax invoice", "input tax", "output tax",
        "zero rating", "hotel apartment", "commercial property", "trn",
        "reverse charge", "excise", "zero rated", "exempt supply",
        "profit margin scheme", "togc", "public transportation", "farms",
        "disbursement", "reimbursement", "dubai owners association",
        "manpower vs visa", "e-commerce vat", "vat public clarif",
    ],
    DomainLabel.CORPORATE_TAX: [
        "corporate tax", "corporate", "ct", "qualifying income", "free zone person",
        "transfer pricing", "permanent establishment", "withholding tax",
        "corporate income", "taxable income", "small business relief",
        "free zone entit", "ctgfzp", "qualifying activities", "excluded activities",
        "public benefit entit", "charit", "ct amend", "ct de registr",
        "ctp0", "ct registration", "ct deregistr", "ct edit",
        "federal decree law no. 47", "law no. 47", "taxation of",
        "business restructuring", "qualifying group", "foreign source income",
        "extractive", "registration of juridical person", "registration of natural person",
        "exempt person", "investment fund", "master guide",
        "accounting standards guide", "explanatory guide", "determination of taxable",
        "automotive sector", "financial services", "insurance", "natural resource",
        "natural person", "qualifying public benefit", "public benefit entity",
    ],
    DomainLabel.PEPPOL: [
        "peppol", "peppol bis", "peppol network", "access point", "peppol id",
    ],
    DomainLabel.E_INVOICING: [
        "e-invoice", "einvoice", "electronic invoice", "e invoicing",
        "e invoice", "digital invoice", "e invoic", "einvoic",
        "243 & 244", "243&244", "243 244", "implementing einvoic",
    ],
    DomainLabel.LABOUR: [
        "labour", "labor", "employment", "visa", "gratuity", "termination",
        "end of service", "worker", "employee", "wages", "mohre", "wps",
    ],
    DomainLabel.COMMERCIAL: [
        "commercial", "company law", "llc", "partnership", "trading licence",
        "commercial register", "agency", "licensing", "business setup",
        "rakez", "dwc", "hamriyah", "dubai south", "rak free",
    ],
    DomainLabel.IFRS: [
        "ifrs", "ias", "financial statement", "accounting standard",
        "consolidation", "revenue recognition", "lease", "impairment",
        "fair value", "disclosure",
    ],
    DomainLabel.GENERAL_LAW: [
        "wills", "will and testament", "inheritance", "inherit",
        "probate", "testator", "beneficiary", "estate planning",
        "succession", "guardian appointment", "last will", "testamentary",
        "heir", "heirs", "testatrix", "executor", "guardian", "trust",
        "endowment", "waqf", "personal status", "family law", "divorce",
        "custody", "alimony", "obligation", "liability",
        "penalty", "compensation", "corporate governance", "shareholder",
        "board of directors",
    ],
}

# Mapping of query domain to searchable document domains
# Some query domains can search across multiple document tags.
DOMAIN_TO_DOC_DOMAINS: Dict[str, List[str]] = {
    DomainLabel.VAT: ["vat", "e_invoicing", "general"],
    DomainLabel.E_INVOICING: ["e_invoicing", "peppol", "vat", "general"],
    DomainLabel.PEPPOL: ["peppol", "e_invoicing", "vat", "general"],
    DomainLabel.CORPORATE_TAX: ["corporate_tax", "general"],
    DomainLabel.LABOUR: ["labour", "general"],
    DomainLabel.COMMERCIAL: ["commercial", "general"],
    DomainLabel.IFRS: ["ifrs", "general"],
    DomainLabel.GENERAL_LAW: ["general_law", "general"],
}

GENERAL_DOMAINS: Set[str] = {"general", "general_law", ""}


def infer_domain_from_name(name: str) -> str:
    """Infer document domain from filename for metadata tagging.
    
    Normalises hyphens/underscores to spaces before matching.
    Order matters: check more-specific patterns before broad ones.
    """
    n = name.lower().replace("-", " ").replace("_", " ")

    # Priority 1: E-invoicing (peppol mentioned in finance too but specific here)
    if any(kw in n for kw in DOMAIN_KEYWORDS[DomainLabel.E_INVOICING]):
        return DomainLabel.E_INVOICING.value

    # Priority 2: Corporate Tax (matches many broad terms, must precede VAT/Commercial)
    if any(kw in n for kw in DOMAIN_KEYWORDS[DomainLabel.CORPORATE_TAX]):
        return DomainLabel.CORPORATE_TAX.value

    # Priority 3: Labour
    if any(kw in n for kw in DOMAIN_KEYWORDS[DomainLabel.LABOUR]):
        return DomainLabel.LABOUR.value

    # Priority 4: IFRS
    if any(kw in n for kw in DOMAIN_KEYWORDS[DomainLabel.IFRS]):
        return DomainLabel.IFRS.value

    # Priority 5: Commercial (broad terms like 'free zone' removed from here)
    if any(kw in n for kw in DOMAIN_KEYWORDS[DomainLabel.COMMERCIAL]):
        return DomainLabel.COMMERCIAL.value

    # Priority 6: VAT
    if any(kw in n for kw in DOMAIN_KEYWORDS[DomainLabel.VAT]):
        return DomainLabel.VAT.value

    # Priority 7: General Law
    if any(kw in n for kw in DOMAIN_KEYWORDS[DomainLabel.GENERAL_LAW]):
        return DomainLabel.GENERAL_LAW.value

    return DomainLabel.GENERAL.value
