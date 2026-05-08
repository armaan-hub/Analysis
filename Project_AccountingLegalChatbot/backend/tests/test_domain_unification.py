import pytest
from core.domains import DOMAIN_TO_DOC_DOMAINS, DomainLabel, GENERAL_DOMAINS

def test_domains_config_completeness():
    """Verify core.domains contains all necessary keys for chat API."""
    # peppol is currently missing in core.domains.DOMAIN_TO_DOC_DOMAINS
    assert DomainLabel.PEPPOL in DOMAIN_TO_DOC_DOMAINS
    assert "peppol" in DOMAIN_TO_DOC_DOMAINS

def test_general_domains_consistency():
    """Verify GENERAL_DOMAINS is consistent."""
    assert "general" in GENERAL_DOMAINS
    assert "general_law" in GENERAL_DOMAINS
    assert "" in GENERAL_DOMAINS
