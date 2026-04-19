"""Tests for DomainLabel enum and ClassifierResult model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chat.domain_classifier import DomainLabel, ClassifierResult


def test_domain_label_values():
    assert DomainLabel.VAT.value == "vat"
    assert DomainLabel.CORPORATE_TAX.value == "corporate_tax"
    assert DomainLabel.PEPPOL.value == "peppol"
    assert DomainLabel.E_INVOICING.value == "e_invoicing"
    assert DomainLabel.LABOUR.value == "labour"
    assert DomainLabel.COMMERCIAL.value == "commercial"
    assert DomainLabel.IFRS.value == "ifrs"
    assert DomainLabel.GENERAL_LAW.value == "general_law"


def test_classifier_result_shape():
    r = ClassifierResult(
        domain=DomainLabel.VAT,
        confidence=0.92,
        alternatives=[(DomainLabel.CORPORATE_TAX, 0.05)],
    )
    assert r.domain == DomainLabel.VAT
    assert r.confidence == 0.92
    assert r.alternatives[0][0] == DomainLabel.CORPORATE_TAX
