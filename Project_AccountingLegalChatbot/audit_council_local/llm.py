"""
Multi-Provider LLM Client for Local & Remote Execution.

Supports:
- OpenCode Zen (Free Tier: laguna-s-2.1-free, deepseek-v4-flash-free, minimax-m3-free, etc.)
- OpenAI-compatible endpoints (Local Proxy http://127.0.0.1:4001/v1, LM Studio, vLLM, Ollama)
- Anthropic Claude Messages API
- Zero required external libraries (graceful fallback using stdlib urllib / asyncio)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

# Default OpenCode Zen credentials and configuration
DEFAULT_OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"
DEFAULT_OPENCODE_MODEL = "laguna-s-2.1-free"
DEFAULT_OPENCODE_KEY = "sk-hNWrtbTRmZFwpq1PYsdH0f2zZNFkCUzugrz8P2kwmCCldwfjFDWnokBIMafwP9yG"

# Known OpenCode Free Tier models
OPENCODE_FREE_MODELS = [
    "laguna-s-2.1-free",
    "deepseek-v4-flash-free",
    "minimax-m3-free",
    "mimo-v2.5-free",
    "nemotron-3-super-free",
]


class BaseLLMClient:
    """Base interface for audit council LLM providers."""

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 3000,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 3000,
        temperature: float = 0.2,
    ) -> str:
        chunks = []
        async for chunk in self.chat_stream(messages, max_tokens=max_tokens, temperature=temperature):
            chunks.append(chunk)
        return "".join(chunks)


class OpenAICompatibleLLM(BaseLLMClient):
    """
    Client for any OpenAI-compatible API (OpenCode Zen, Local Proxy, Ollama, LM Studio, etc.).
    Uses stdlib or httpx for zero-dependency portability.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENCODE_BASE_URL,
        model: str = DEFAULT_OPENCODE_MODEL,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENCODE_API_KEY") or os.environ.get("OPENAI_API_KEY") or DEFAULT_OPENCODE_KEY
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 3000,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        # Try httpx if available in environment
        try:
            import httpx  # type: ignore

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        raise RuntimeError(f"LLM API Error {response.status_code}: {err_body.decode('utf-8', errors='replace')}")
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
            return
        except ImportError:
            pass

        # Fallback to standard library asyncio + urllib executor
        loop = asyncio.get_running_loop()

        def _sync_request():
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            try:
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                return resp
            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"LLM API Error {e.code}: {err_text}") from e

        resp = await loop.run_in_executor(None, _sync_request)

        # Stream lines from urllib response
        while True:
            line_bytes = await loop.run_in_executor(None, resp.readline)
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk_data = json.loads(data_str)
                choices = chunk_data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
            except json.JSONDecodeError:
                continue


class AnthropicLLM(BaseLLMClient):
    """Native Anthropic Claude Client."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 3000,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Separate system prompt if present
        system_content = ""
        user_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            else:
                user_messages.append(m)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if system_content:
            payload["system"] = system_content

        try:
            import httpx  # type: ignore

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        raise RuntimeError(f"Anthropic API Error {response.status_code}: {err_body.decode('utf-8', errors='replace')}")
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            try:
                                data = json.loads(data_str)
                                if data.get("type") == "content_block_delta":
                                    delta = data.get("delta", {})
                                    text = delta.get("text", "")
                                    if text:
                                        yield text
                            except json.JSONDecodeError:
                                continue
        except ImportError:
            raise RuntimeError("httpx is required for Anthropic streaming client. Install with: pip install httpx")


def get_llm_client(
    provider: str = "opencode",
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseLLMClient:
    """
    Factory creating configured LLM client.
    """
    prov = (provider or "opencode").lower().strip()
    if prov in ("opencode", "zen", "opencode_zen"):
        return OpenAICompatibleLLM(
            api_key=api_key or os.environ.get("OPENCODE_API_KEY") or DEFAULT_OPENCODE_KEY,
            base_url=base_url or os.environ.get("OPENCODE_BASE_URL") or DEFAULT_OPENCODE_BASE_URL,
            model=model or os.environ.get("OPENCODE_MODEL") or DEFAULT_OPENCODE_MODEL,
        )
    elif prov in ("openai", "proxy", "local_proxy", "custom", "ollama", "vllm"):
        return OpenAICompatibleLLM(
            api_key=api_key or os.environ.get("OPENAI_API_KEY") or "dummy-key",
            base_url=base_url or os.environ.get("OPENAI_BASE_URL") or "http://127.0.0.1:4001/v1",
            model=model or os.environ.get("OPENAI_MODEL") or "gpt-4o",
        )
    elif prov in ("anthropic", "claude"):
        return AnthropicLLM(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            model=model or "claude-haiku-4-5-20251001",
        )
    else:
        # Default fallback to OpenAI Compatible
        return OpenAICompatibleLLM(
            api_key=api_key or DEFAULT_OPENCODE_KEY,
            base_url=base_url or DEFAULT_OPENCODE_BASE_URL,
            model=model or DEFAULT_OPENCODE_MODEL,
        )
