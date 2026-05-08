# LLM Models Overview - Accounting & Legal AI Chatbot

> **For agentic workers:** Comprehensive reference for all LLM model configurations across Fast, Deep Research, and Analyst modes.

**Goal:** Complete documentation of all LLM model configurations and their use cases.

**Architecture:** Three-mode system optimized for different query types and use cases.

**Tech Stack:** NVIDIA NIM (primary), OpenAI, Anthropic Claude, Mistral, Groq, Ollama.

---

## Quick Reference Table

| Mode | Model | Temperature | Max Tokens | Top K | Use Case |
|------|-------|-------------|------------|-------|----------|
| **Fast** | devstral-2-123b | 0.20 | 12,385 | 15 | Quick factual queries |
| **Deep Research** | mistral-large-3-675b | 1.00 | 15,649 | 8 | Complex research analysis |
| **Analyst** | mistral-large-3-675b | 0.20 | 15,649 | 8 | Professional reports |

---

## Mode Comparison

### Fast Mode

**Purpose:** Fast, responsive answers for quick queries.

**Characteristics:**
- Lower temperature (0.20) for precision
- Higher retrieval budget (15 top-k)
- Reduced token budget (12,385)
- Optimized for speed

**Best For:**
- Quick factual queries
- Simple explanations
- Rapid document lookup
- Real-time chat
- Initial research

**Performance:**
- TTFB: 1-3 seconds
- Accuracy: 85-90%
- Cost: High efficiency

### Deep Research Mode

**Purpose:** Comprehensive analysis for complex research tasks.

**Characteristics:**
- Higher temperature (1.00) for exploration
- Focused retrieval (8 top-k)
- Extended token budget (15,649)
- Optimized for depth

**Best For:**
- Complex legal analysis
- Financial research
- Regulatory monitoring
- Document synthesis
- Strategic recommendations

**Performance:**
- TTFB: 5-15 seconds
- Accuracy: 95%+
- Cost: Medium efficiency

### Analyst Mode

**Purpose:** Professional, structured analysis for financial/legal matters.

**Characteristics:**
- Low temperature (0.20) for precision
- Focused retrieval (8 top-k)
- Extended token budget (15,649)
- Optimized for professional output

**Best For:**
- Financial analysis
- Legal compliance
- Audit preparation
- Document review
- Regulatory research
- Professional reports

**Performance:**
- TTFB: 3-10 seconds
- Accuracy: 95%+
- Cost: Medium efficiency

---

## NVIDIA NIM Configuration

### Fast Mode

```python
# backend/config.py:28
nvidia_fast_model: str = "mistralai/devstral-2-123b-instruct-2512"
nvidia_fast_reasoning_effort: Literal["none", "high"] = "high"
nvidia_fast_api_key: str = ""  # Optional separate key
```

### Deep Research / Analyst Mode

```python
# backend/config.py:25
nvidia_model: str = "mistralai/mistral-large-3-675b-instruct-2512"
```

### Model Selection (llm_manager.py:1123)

```python
if name == "nvidia" and mode == "fast":
    fast_model = settings.nvidia_fast_model  # devstral-2-123b
    provider = NvidiaProvider(
        api_key=fast_api_key,
        model=fast_model,
        base_url=settings.nvidia_base_url,
        thinking_enabled=True,
    )
else:
    provider = NvidiaProvider(
        api_key=settings.nvidia_api_key,
        model=settings.nvidia_model,  # mistral-large-3-675b
        base_url=settings.nvidia_base_url,
    )
```

---

## All Provider Configurations

### NVIDIA NIM

| Mode | Model | Context | Temp | Max Tokens |
|------|-------|---------|------|------------|
| Fast | devstral-2-123b | 128K | 0.20 | 12,385 |
| Deep Research | mistral-large-3-675b | 128K | 1.00 | 15,649 |
| Analyst | mistral-large-3-675b | 128K | 0.20 | 15,649 |

### OpenAI

| Mode | Model | Context | Temp | Max Tokens |
|------|-------|---------|------|------------|
| Fast | gpt-4o | 128K | 0.20 | 12,385 |
| Deep Research | gpt-4o | 128K | 1.00 | 15,649 |
| Analyst | gpt-4o | 128K | 0.20 | 15,649 |

### Anthropic Claude

| Mode | Model | Context | Temp | Max Tokens |
|------|-------|---------|------|------------|
| Fast | claude-sonnet-4 | 200K | 0.20 | 32,768 |
| Deep Research | claude-sonnet-4 | 200K | 1.00 | 32,768 |
| Analyst | claude-sonnet-4 | 200K | 0.20 | 32,768 |

### Mistral

| Mode | Model | Context | Temp | Max Tokens |
|------|-------|---------|------|------------|
| Fast | mistral-large-latest | 128K | 0.20 | 12,385 |
| Deep Research | mistral-large-latest | 128K | 1.00 | 15,649 |
| Analyst | mistral-large-latest | 128K | 0.20 | 15,649 |

### Groq

| Mode | Model | Context | Temp | Max Tokens |
|------|-------|---------|------|------------|
| Fast | llama-3.1-8b-instant | 128K | 0.20 | 12,385 |
| Deep Research | llama-3.3-70b-versatile | 128K | 1.00 | 15,649 |
| Analyst | llama-3.3-70b-versatile | 128K | 0.20 | 15,649 |

### Ollama (Local)

| Mode | Model | Context | Temp | Max Tokens |
|------|-------|---------|------|------------|
| Fast | llama3 | 8K | 0.20 | 16,384 |
| Deep Research | llama3 | 8K | 1.00 | 16,384 |
| Analyst | llama3 | 8K | 0.20 | 16,384 |

---

## Environment Variables (.env)

```bash
# Active Provider
LLM_PROVIDER=nvidia

# NVIDIA NIM
NVIDIA_API_KEY=your_key_here
NVIDIA_MODEL=mistralai/mistral-large-3-675b-instruct-2512
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_FAST_MODEL=mistralai/devstral-2-123b-instruct-2512
NVIDIA_FAST_API_KEY=  # Optional separate key
NVIDIA_FAST_REASONING_EFFORT=high

# OpenAI
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o

# Anthropic Claude
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Mistral
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=mistral-large-latest

# Groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FAST_MODEL=llama-3.1-8b-instant

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# RAG Settings
TEMPERATURE=0.20
FAST_TEMPERATURE=0.20
DEEP_TEMPERATURE=1.00
MAX_TOKENS=15649
FAST_MAX_TOKENS=12385
TOP_K_RESULTS=8
FAST_TOP_K=15
```

---

## Mode Routing (chat.py)

```python
# backend/api/chat.py
ConversationMode = Literal["fast", "deep_research", "analyst"]

# Route to appropriate mode
def create_conversation(mode: ConversationMode = "fast"):
    provider = get_llm_provider(mode=mode)
    # ... process request with mode-specific settings
```

---

## Temperature Guidelines

| Temperature | Use Case | Examples |
|-------------|----------|----------|
| **0.0-0.3** | Factual, precise | VAT rates, article numbers |
| **0.3-0.7** | Balanced | General explanations |
| **0.7-1.0** | Creative, exploratory | Research analysis, recommendations |

**Current Configuration:**
- Fast Mode: 0.20 (precise factual)
- Deep Research: 1.00 (exploratory)
- Analyst: 0.20 (professional precision)

---

## Token Budget Guidelines

| Mode | Max Tokens | Purpose |
|------|------------|---------|
| **Fast** | 12,385 | Quick responses |
| **Deep Research** | 15,649 | Comprehensive analysis |
| **Analyst** | 15,649 | Professional reports |

**Safety Buffer:** 500 tokens reserved for system messages

---

## Retrieval Strategy

| Mode | Top K | Strategy |
|------|-------|----------|
| **Fast** | 15 | Broad retrieval for speed |
| **Deep Research** | 8 | Focused, high-quality |
| **Analyst** | 8 | Focused, professional |

**Domain Filtering:**
- Confidence threshold: 0.60
- Fallback threshold: 0.39
- General law minimum: 0.35

---

## File References

| File | Purpose |
|------|---------|
| `backend/config.py` | Settings definitions |
| `backend/core/llm_manager.py` | Model factory |
| `backend/api/chat.py` | Mode routing |
| `backend/core/prompt_router.py` | System prompts |
| `backend/core/rag_engine.py` | RAG configuration |

---

## Documentation Files

| File | Description |
|------|-------------|
| `fast-mode-model.md` | Fast Mode complete specification |
| `deep-research-mode-model.md` | Deep Research Mode complete specification |
| `analyst-mode-model.md` | Analyst Mode complete specification |
| `llm-models-overview.md` | This overview document |

---

## Version History

| Date | Change |
|------|--------|
| 2026-05-08 | Initial specification |

---

## Related Specifications

- [Fast Mode Model](./fast-mode-model.md)
- [Deep Research Mode Model](./deep-research-mode-model.md)
- [Analyst Mode Model](./analyst-mode-model.md)
