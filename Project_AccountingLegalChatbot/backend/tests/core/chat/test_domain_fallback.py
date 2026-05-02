
import pytest
from unittest.mock import patch, AsyncMock
from core.chat.domain_classifier import classify_domain, DomainLabel

@pytest.mark.asyncio
async def test_classify_domain_hotel_apartment_fallback():
    # Mock LLM to fail (trigger exception)
    with patch("core.chat.domain_classifier.get_llm_provider") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = Exception("API Error")
        mock_get_llm.return_value = mock_llm
        
        query = "I sold a Hotel Apartment and need to pay VAT"
        result = await classify_domain(query)
        
        # Currently, it falls back to GENERAL_LAW
        # We want it to detect 'vat' based on keywords
        assert result.domain == DomainLabel.VAT
