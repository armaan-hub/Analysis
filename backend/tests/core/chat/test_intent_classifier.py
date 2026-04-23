import pytest
from core.chat.intent_classifier import classify_intent, Intent


class _FakeLLM:
    def __init__(self, response): self.response = response
    async def chat(self, messages, **kw):
        from types import SimpleNamespace
        return SimpleNamespace(content=self.response)


@pytest.mark.asyncio
async def test_classify_explanation_request():
    llm = _FakeLLM('{"output_type":"explanation","topic":"VAT zero-rated"}')
    intent = await classify_intent("Explain VAT zero-rating", llm)
    assert intent.output_type == "explanation"
    assert "VAT" in intent.topic

@pytest.mark.asyncio
async def test_classify_falls_back_to_answer_on_bad_json():
    llm = _FakeLLM("not json at all")
    intent = await classify_intent("question", llm)
    assert intent.output_type == "answer"

@pytest.mark.asyncio
async def test_classify_falls_back_on_exception():
    class _BrokenLLM:
        async def chat(self, messages, **kw):
            raise RuntimeError("connection error")
    intent = await classify_intent("question", _BrokenLLM())
    assert intent.output_type == "answer"

@pytest.mark.asyncio
async def test_classify_list_type():
    llm = _FakeLLM('{"output_type":"list","topic":"VAT exempt items"}')
    intent = await classify_intent("Give me a list of VAT exempt items", llm)
    assert intent.output_type == "list"
    assert "VAT" in intent.topic

@pytest.mark.asyncio
async def test_classify_falls_back_to_answer_on_unknown_output_type():
    llm = _FakeLLM('{"output_type":"essay","topic":"VAT"}')
    intent = await classify_intent("Explain VAT", llm)
    assert intent.output_type == "answer"  # "essay" is not a valid type
