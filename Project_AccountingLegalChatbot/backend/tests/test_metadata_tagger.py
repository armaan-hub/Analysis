import pytest
import json
from unittest.mock import MagicMock

_SAMPLE_METADATA_JSON = json.dumps({
    "domain": "banking_compliance",
    "jurisdiction": "uae_federal",
    "law_number": "Decree Law 50 of 2022",
    "subjects": ["cheque bouncing", "penalties"],
    "effective_date": "2022-09-01",
    "summary": "Federal decree governing bounced cheques.",
})


@pytest.mark.asyncio
async def test_extract_metadata_returns_dataclass():
    from core.llm_manager import LLMManager, MetadataResult
    mgr = LLMManager.__new__(LLMManager)
    mgr._provider = MagicMock()
    async def _chat(messages, **kw):
        from core.llm_manager import LLMResponse
        return LLMResponse(content=_SAMPLE_METADATA_JSON, model="m", usage={})
    mgr._provider.chat = _chat
    result = await mgr.extract_metadata(
        filename="DecreeLaw_50_2022_pdf.pdf",
        text="text sample",
        source_dir="law",
    )
    assert isinstance(result, MetadataResult)
    assert result.domain == "banking_compliance"
    assert result.jurisdiction == "uae_federal"
    assert "cheque bouncing" in result.subjects
    assert result.effective_date == "2022-09-01"


@pytest.mark.asyncio
async def test_extract_metadata_handles_malformed_json():
    from core.llm_manager import LLMManager, MetadataResult
    mgr = LLMManager.__new__(LLMManager)
    mgr._provider = MagicMock()
    async def _chat(messages, **kw):
        from core.llm_manager import LLMResponse
        return LLMResponse(content="this is not JSON", model="m", usage={})
    mgr._provider.chat = _chat
    result = await mgr.extract_metadata("test.pdf", "text", "law")
    assert isinstance(result, MetadataResult)
    assert result.domain == "general"
