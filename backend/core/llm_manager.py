"""
Pluggable LLM Manager – Factory pattern for swapping providers.

Supports: NVIDIA NIM, OpenAI, Anthropic Claude, Mistral, Ollama.
All providers expose the same interface: send a list of messages, get a response.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional
import httpx
from config import settings

logger = logging.getLogger(__name__)

# ── Context window registry ──────────────────────────────────────────
# Maps a model-name *substring* (lower-case) to total context window
# tokens.  The first matching key wins (longer/more-specific keys first).
_CONTEXT_WINDOWS: dict[str, int] = {
    "mistral-large":        131_072,
    "mistral-medium":       131_072,
    "mistral-small":         32_768,
    "mixtral":               32_768,
    "gemma-4-27b":        1_048_576,   # 27B has 1M context
    "gemma-4":              131_072,   # 9B; conservative NIM default
    "gemma-3-1b":            32_768,   # only the 1B variant is 32K
    "gemma-3":              131_072,   # 4B / 12B / 27B are 128K
    "llama-3.3":            131_072,
    "llama-3.2":            131_072,
    "llama-3.1":            131_072,
    "llama3.3":             131_072,
    "llama3.2":             131_072,
    "llama3.1":             131_072,
    "llama-3":                8_192,
    "llama3":                 8_192,
    "gpt-4o":               128_000,
    "gpt-4-turbo":          128_000,
    "gpt-4":                  8_192,
    "gpt-3.5-turbo-16k":    16_385,
    "gpt-3.5":              16_385,
    "claude":               200_000,
    "nemotron":             128_000,
}
_CONTEXT_WINDOW_FALLBACK: int = 8_192


class LLMResponse:
    """Standardized response from any LLM provider."""

    def __init__(self, content: str, model: str, provider: str,
                 tokens_used: int = 0, finish_reason: str = "stop"):
        self.content = content
        self.model = model
        self.provider = provider
        self.tokens_used = tokens_used
        self.finish_reason = finish_reason

    def to_dict(self):
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "finish_reason": self.finish_reason,
        }


class BaseLLMProvider:
    """Abstract base for all LLM providers."""

    _MIN_RESPONSE_TOKENS: int = 512  # minimum for professional legal/accounting responses
    _TOKEN_SAFETY_BUFFER: int = 500

    # Streaming: no read-timeout (TTFB for large models can be 60-90 s); connection still fails fast.
    _STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=5.0)
    # Non-streaming: generous read timeout for large-model completions.
    _DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)

    def __init__(self, api_key: str, model: str, base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider_name = "base"

    def get_context_window(self) -> int:
        """Return the context window (total tokens) for the active model.

        Matches by scanning ``_CONTEXT_WINDOWS`` keys as substrings of
        ``self.model`` (case-insensitive).  Returns the fallback (8 192) when
        no pattern matches.
        """
        model_lower = self.model.lower()
        for pattern, window in _CONTEXT_WINDOWS.items():
            if pattern in model_lower:
                return window
        return _CONTEXT_WINDOW_FALLBACK

    @staticmethod
    def _count_content_chars(content) -> int:
        """Return approximate char count for a message content value.

        Handles both str (plain text) and list-of-parts (OpenAI multi-modal format).
        Image bytes are intentionally ignored — only text parts are counted.
        """
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(
                len(part.get("text") or "")
                for part in content
                if isinstance(part, dict)
            )
        return 0

    def compute_safe_max_tokens(
        self,
        messages: list[dict],
        requested_max: Optional[int] = None,
    ) -> int:
        """Compute a safe output token ceiling that avoids context-window overflow.

        Algorithm:
            input_chars  = sum of all message content character lengths
            input_tokens = input_chars // 3   (≈ 3 chars per token — conservative for legal/accounting text)
            available    = context_window - input_tokens - safety_buffer

        If ``available`` ≤ 0 (input alone fills the window) returns
        ``_MIN_RESPONSE_TOKENS`` so the model can still reply.

        If ``requested_max`` is ``None`` (no ceiling requested), returns
        ``available``.  Otherwise returns ``min(requested_max, available)``.
        """
        input_chars = sum(self._count_content_chars(msg.get("content")) for msg in messages)
        input_tokens = input_chars // 3  # conservative: legal text ~3 chars/token
        available = self.get_context_window() - input_tokens - self._TOKEN_SAFETY_BUFFER
        if available <= 0:
            logger.warning(
                "compute_safe_max_tokens: estimated input (%d tokens) exceeds context "
                "window (%d). Returning minimum %d. Caller should truncate messages.",
                input_tokens,
                self.get_context_window(),
                self._MIN_RESPONSE_TOKENS,
            )
            return self._MIN_RESPONSE_TOKENS
        # Always enforce the professional-response floor (0 < available < _MIN_RESPONSE_TOKENS
        # would otherwise return a token budget too small for meaningful output).
        floor = self._MIN_RESPONSE_TOKENS
        if requested_max is None:
            return max(available, floor)
        return max(min(requested_max, available), floor)

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> LLMResponse:
        """Non-streaming chat. Use chat_stream() for streaming responses."""
        raise NotImplementedError

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError
        yield  # make it a generator


# ═══════════════════════════════════════════════════════════════════
# NVIDIA NIM Provider (OpenAI-compatible API)
# ═══════════════════════════════════════════════════════════════════

class NvidiaProvider(BaseLLMProvider):
    """NVIDIA NIM API – uses OpenAI-compatible chat completions endpoint."""

    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(api_key, model, base_url)
        self.provider_name = "nvidia"
        self._is_gemma = "gemma" in model.lower()

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Remove <thinking>...</thinking> blocks produced by Gemma 4 extended thinking."""
        import re
        return re.sub(r"<thinking>.*?</thinking>\s*", "", text, flags=re.DOTALL).strip()

    @staticmethod
    def _messages_contain_images(messages: list) -> bool:
        """Return True if any message has image_url content parts (vision request)."""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

    def _build_payload(
        self,
        messages,
        max_tokens,
        temperature,
        stream: bool,
        reasoning_effort: Optional[str] = None,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 1.00,
            "frequency_penalty": 0.00,
            "presence_penalty": 0.00,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        # enable_thinking is incompatible with vision/multimodal inputs — skip for image requests
        if self._is_gemma and not self._messages_contain_images(messages):
            payload["chat_template_kwargs"] = {"enable_thinking": True}
        return payload

    async def chat(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(messages, max_tokens, temperature, stream=False, reasoning_effort=reasoning_effort)

        has_images = self._messages_contain_images(messages)
        last_exc: Exception = RuntimeError(f"NVIDIA provider unreachable — check API key and network")
        # Vision requests can be large (multiple base64-encoded pages) — use a generous write timeout
        _timeout = (
            httpx.Timeout(None)
            if has_images
            else self._DEFAULT_TIMEOUT
        )
        for attempt in range(2):
            if attempt > 0:
                await asyncio.sleep(2 ** attempt)  # 2s
            try:
                async with httpx.AsyncClient(timeout=_timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < 1:
                        last_exc = httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}", request=resp.request, response=resp
                        )
                        logger.warning(f"NVIDIA API {resp.status_code}, retrying (attempt {attempt+1}/2)…")
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                choice = data["choices"][0]
                usage = data.get("usage", {})
                content = choice["message"]["content"] or ""
                if self._is_gemma:
                    content = self._strip_thinking(content)
                return LLMResponse(
                    content=content,
                    model=data.get("model", self.model),
                    provider=self.provider_name,
                    tokens_used=usage.get("total_tokens", 0),
                    finish_reason=choice.get("finish_reason", "stop"),
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                logger.warning(f"NVIDIA API network error (attempt {attempt+1}/2): {exc}")
        raise RuntimeError(f"NVIDIA provider unreachable after 2 attempts — check API key and network") from last_exc

    async def chat_stream(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = self._build_payload(messages, max_tokens, temperature, stream=True, reasoning_effort=reasoning_effort)

        # For Gemma thinking mode: buffer until </thinking> before yielding
        in_thinking = False
        thinking_buf = ""

        has_images = self._messages_contain_images(messages)
        _timeout = httpx.Timeout(None) if has_images else self._STREAM_TIMEOUT
        async with httpx.AsyncClient(timeout=_timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    err_text = body.decode("utf-8", errors="replace")[:400]
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}: {err_text}",
                        request=resp.request,
                        response=resp,
                    )
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # strip "data: "
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if not content:
                            continue

                        if not self._is_gemma:
                            yield content
                            continue

                        # Gemma: suppress <thinking>...</thinking> blocks in stream
                        thinking_buf += content
                        while True:
                            if in_thinking:
                                end = thinking_buf.find("</thinking>")
                                if end == -1:
                                    thinking_buf = ""  # still inside thinking block
                                    break
                                # Found end of thinking block
                                in_thinking = False
                                thinking_buf = thinking_buf[end + len("</thinking>"):].lstrip("\n")
                            else:
                                start = thinking_buf.find("<thinking>")
                                if start == -1:
                                    yield thinking_buf
                                    thinking_buf = ""
                                    break
                                # Yield text before the thinking block
                                if start > 0:
                                    yield thinking_buf[:start]
                                in_thinking = True
                                thinking_buf = thinking_buf[start + len("<thinking>"):]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


# ═══════════════════════════════════════════════════════════════════
# OpenAI Provider
# ═══════════════════════════════════════════════════════════════════

class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"):
        super().__init__(api_key, model, base_url)
        self.provider_name = "openai"

    async def chat(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=self._DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            provider=self.provider_name,
            tokens_used=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def chat_stream(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=self._STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


# ═══════════════════════════════════════════════════════════════════
# Anthropic Claude Provider
# ═══════════════════════════════════════════════════════════════════

class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com"):
        super().__init__(api_key, model, base_url)
        self.provider_name = "claude"

    async def chat(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        # Convert OpenAI-style messages to Anthropic format
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens if max_tokens is not None else 32768,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_msg:
            payload["system"] = system_msg

        async with httpx.AsyncClient(timeout=self._DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content_blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMResponse(
            content=text,
            model=data.get("model", self.model),
            provider=self.provider_name,
            tokens_used=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            finish_reason=data.get("stop_reason", "stop"),
        )

    async def chat_stream(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens if max_tokens is not None else 32768,
            "temperature": temperature,
            "messages": anthropic_messages,
            "stream": True,
        }
        if system_msg:
            payload["system"] = system_msg

        async with httpx.AsyncClient(timeout=self._STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                yield text
                    except (json.JSONDecodeError, KeyError):
                        continue


# ═══════════════════════════════════════════════════════════════════
# Mistral Provider (OpenAI-compatible)
# ═══════════════════════════════════════════════════════════════════

class MistralProvider(BaseLLMProvider):
    """Mistral AI API provider (OpenAI-compatible)."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.mistral.ai/v1"):
        super().__init__(api_key, model, base_url)
        self.provider_name = "mistral"

    async def chat(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=self._DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            provider=self.provider_name,
            tokens_used=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def chat_stream(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=self._STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


# ═══════════════════════════════════════════════════════════════════
# Ollama Provider (local, OpenAI-compatible)
# ═══════════════════════════════════════════════════════════════════

class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider (OpenAI-compatible API)."""

    def __init__(self, api_key: str, model: str, base_url: str = "http://localhost:11434"):
        super().__init__(api_key, model, base_url)
        self.provider_name = "ollama"

    async def chat(self, messages, temperature=0.7, max_tokens=16384, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=data.get("model", self.model),
            provider=self.provider_name,
            tokens_used=data.get("eval_count", 0),
            finish_reason="stop",
        )

    async def chat_stream(self, messages, temperature=0.7, max_tokens=16384, reasoning_effort=None):
        # reasoning_effort is NVIDIA-specific; silently ignored for this provider
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue


# ═══════════════════════════════════════════════════════════════════
# Factory – get_llm_provider()
# ═══════════════════════════════════════════════════════════════════

_PROVIDER_MAP = {
    "nvidia": lambda: NvidiaProvider(
        api_key=settings.nvidia_api_key,
        model=settings.nvidia_model,
        base_url=settings.nvidia_base_url,
    ),
    "openai": lambda: OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    ),
    "claude": lambda: ClaudeProvider(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    ),
    "mistral": lambda: MistralProvider(
        api_key=settings.mistral_api_key,
        model=settings.mistral_model,
    ),
    "ollama": lambda: OllamaProvider(
        api_key="",
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    ),
}


def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory function – returns an LLM provider instance.

    Args:
        provider_name: Override the default provider from settings.
                       If None, uses settings.llm_provider.

    Returns:
        An instance of BaseLLMProvider ready to call .chat() or .chat_stream().
    """
    name = (provider_name or settings.llm_provider).lower()
    factory = _PROVIDER_MAP.get(name)
    if not factory:
        raise ValueError(
            f"Unknown LLM provider '{name}'. "
            f"Available: {list(_PROVIDER_MAP.keys())}"
        )
    provider = factory()
    logger.info(f"LLM provider initialized: {provider.provider_name} / {provider.model}")
    return provider


def list_available_providers() -> list[dict]:
    """Return a list of all supported providers with their configured status."""
    # #11 fix: map provider names to their actual settings key names
    key_map = {
        "nvidia":  "nvidia_api_key",
        "openai":  "openai_api_key",
        "claude":  "anthropic_api_key",   # settings has anthropic_api_key, not claude_api_key
        "mistral": "mistral_api_key",
        "ollama":  None,                  # no key needed
    }
    result = []
    for name in _PROVIDER_MAP:
        key_name = key_map.get(name)
        has_key = bool(getattr(settings, key_name, "")) if key_name else (name == "ollama")
        result.append({
            "name": name,
            "configured": has_key,
            "is_active": name == settings.llm_provider,
        })
    return result
