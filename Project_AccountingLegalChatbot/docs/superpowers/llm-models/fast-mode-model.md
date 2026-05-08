# Fast Mode LLM Model Specification

> **For agentic workers:** This model defines the Fast Mode configuration for the Accounting & Legal AI Chatbot.

**Goal:** Provide fast, responsive answers for quick queries with high throughput.

**Architecture:** Optimized for speed with smaller models, higher temperature, and reduced token budgets.

**Tech Stack:** NVIDIA NIM (primary), OpenAI, Anthropic Claude, Mistral, Groq, Ollama.

---

## Model Configuration

### NVIDIA NIM (Primary)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `mistralai/devstral-2-123b-instruct-2512` | Fast Mistral model for quick responses |
| **Fallback Model** | `mistralai/mistral-small-4-119b-2603` | Used when devstral is DEGRADED |
| **Context Window** | 131,072 tokens | 128K context for large documents |
| **Temperature** | 0.20 | Low for precision, higher than deep mode |
| **Max Tokens** | 12,385 | DeepSeek v3.1-terminus spec |
| **Top K Results** | 15 | Higher retrieval budget |
| **Reasoning Effort** | `high` | Mistral models support high/none |
| **API Key** | `nvidia_fast_api_key` (optional) | Separate key for fast mode |

### OpenAI

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `gpt-4o` | Fast GPT-4 Omni |
| **Context Window** | 128,000 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 12,385 | |

### Anthropic Claude

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `claude-sonnet-4-20250514` | Balanced speed/quality |
| **Context Window** | 200,000 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 32,768 | |

### Mistral

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `mistral-large-latest` | Fast large model |
| **Context Window** | 131,072 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 12,385 | |

### Groq

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `llama-3.1-8b-instant` | Ultra-fast inference |
| **Context Window** | 131,072 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 12,385 | |

### Ollama (Local)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `llama3` | Local model |
| **Context Window** | 8,192 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 16,384 | |

---

## Use Cases

**Fast Mode is optimized for:**

1. **Quick factual queries** - "What is the VAT rate in UAE?"
2. **Simple explanations** - "Explain IFRS 15"
3. **Rapid document lookup** - Find specific clauses
4. **Real-time chat** - Conversational interactions
5. **Initial research** - Quick scoping before deep dive

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **TTFB (Time to First Byte)** | 1-3 seconds |
| **Streaming** | Enabled |
| **Response Quality** | Good for quick answers |
| **Cost Efficiency** | High (lower token budget) |
| **Accuracy** | 85-90% for straightforward queries |

---

## Temperature Settings

| Mode | Temperature | Use Case |
|------|-------------|----------|
| **Fast** | 0.20 | Precise, factual answers |
| **Deep Research** | 1.00 | Creative, exploratory analysis |
| **Analyst** | 0.20 | Professional, structured output |

---

## Implementation Notes

### Model Selection (llm_manager.py)

```python
# Fast mode on NVIDIA uses devstral-2-123b
if name == "nvidia" and mode == "fast":
    provider = NvidiaProvider(
        api_key=fast_api_key,
        model=settings.nvidia_fast_model,  # devstral-2-123b
        base_url=settings.nvidia_base_url,
        thinking_enabled=True,
    )
```

### Token Budget

- **Fast Mode:** 12,385 tokens (DeepSeek v3.1-terminus)
- **Deep/Analyst:** 15,649 tokens (DeepSeek v3.2)
- **Safety Buffer:** 500 tokens reserved

### Retrieval Strategy

- **Fast Mode:** 15 top-k results (broader retrieval)
- **Deep/Analyst:** 8 top-k results (focused retrieval)

---

## Configuration File (.env)

```bash
# NVIDIA Fast Mode
NVIDIA_FAST_MODEL=mistralai/devstral-2-123b-instruct-2512
NVIDIA_FAST_API_KEY=  # Optional - separate key for fast mode
NVIDIA_FAST_REASONING_EFFORT=high

# Fast Mode Settings
FAST_TEMPERATURE=0.20
FAST_MAX_TOKENS=12385
FAST_TOP_K=15
```

---

## Testing Checklist

- [ ] Fast mode responds in <5 seconds for simple queries
- [ ] Streaming works correctly
- [ ] Token budget enforced
- [ ] Fallback model works when primary is DEGRADED
- [ ] No hallucinations in factual answers
- [ ] Proper error handling for API failures

---

## Related Files

- `backend/core/llm_manager.py` - Model factory and configuration
- `backend/config.py` - Settings definitions
- `backend/api/chat.py` - Mode routing logic

---

## Version History

| Date | Change |
|------|--------|
| 2026-05-08 | Initial specification |
