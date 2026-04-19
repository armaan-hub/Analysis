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


import json
import pytest
from unittest.mock import patch, AsyncMock
from core.chat.domain_classifier import classify_domain


@pytest.mark.asyncio
async def test_classify_vat_query():
    fake_json = '{"domain": "vat", "confidence": 0.95, "alternatives": [["corporate_tax", 0.03]]}'
    with patch("core.chat.domain_classifier._llm_complete", new=AsyncMock(return_value=fake_json)):
        r = await classify_domain("How do I reclaim input VAT on UAE imports?")
    assert r.domain == DomainLabel.VAT
    assert r.confidence == 0.95
    assert r.alternatives[0][0] == DomainLabel.CORPORATE_TAX


@pytest.mark.asyncio
async def test_classify_fallback_on_bad_json():
    with patch("core.chat.domain_classifier._llm_complete", new=AsyncMock(return_value="not json")):
        r = await classify_domain("ambiguous query")
    assert r.domain == DomainLabel.GENERAL_LAW
    assert r.confidence <= 0.5
