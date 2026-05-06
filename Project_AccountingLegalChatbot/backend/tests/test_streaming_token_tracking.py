"""Tests that NvidiaProvider.chat_stream captures tokens_used from the final usage chunk."""
import json
import pytest
import httpx
import respx
from core.llm_manager import NvidiaProvider


@pytest.mark.asyncio
async def test_nvidia_provider_captures_usage_chunk():
    """chat_stream must set _last_stream_tokens from the final usage chunk (stream_options)."""
    provider = NvidiaProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://test.nvidia.api",
    )
    assert provider._last_stream_tokens == 0

    # Simulate NVIDIA streaming: content chunks + final usage chunk + [DONE]
    stream_body = (
        'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"world."}}]}\n\n'
        'data: {"choices":[{"delta":{"content":""}}],"usage":{"total_tokens":42,"prompt_tokens":10,"completion_tokens":32}}\n\n'
        'data: [DONE]\n\n'
    )

    with respx.mock:
        respx.post("https://test.nvidia.api/chat/completions").mock(
            return_value=httpx.Response(
                200,
                text=stream_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        chunks = []
        async for chunk in provider.chat_stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

    assert "".join(chunks) == "Hello world.", f"Content chunks wrong: {''.join(chunks)}"
    assert provider._last_stream_tokens == 42, (
        f"Expected 42 tokens from usage chunk, got {provider._last_stream_tokens}"
    )


@pytest.mark.asyncio
async def test_nvidia_provider_stream_options_in_payload():
    """_build_payload must include stream_options.include_usage=True when stream=True."""
    provider = NvidiaProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://test.nvidia.api",
    )
    messages = [{"role": "user", "content": "test"}]
    payload = provider._build_payload(messages, max_tokens=None, temperature=0.7, stream=True)
    assert payload.get("stream_options") == {"include_usage": True}, (
        f"stream_options not set in streaming payload: {payload}"
    )
    # Non-streaming payload must NOT include stream_options
    payload_ns = provider._build_payload(messages, max_tokens=None, temperature=0.7, stream=False)
    assert "stream_options" not in payload_ns, (
        f"stream_options should not be in non-streaming payload: {payload_ns}"
    )
