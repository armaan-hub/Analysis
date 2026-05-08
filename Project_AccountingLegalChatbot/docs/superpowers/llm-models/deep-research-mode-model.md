# Deep Research Mode LLM Model Specification

> **For agentic workers:** This model defines the Deep Research Mode configuration for the Accounting & Legal AI Chatbot.

**Goal:** Provide comprehensive, thorough analysis for complex research tasks with deep reasoning and extensive document analysis.

**Architecture:** Optimized for depth with larger models, higher temperature, extended token budgets, and iterative research.

**Tech Stack:** NVIDIA NIM (primary), OpenAI, Anthropic Claude, Mistral, Groq, Ollama.

---

## Model Configuration

### NVIDIA NIM (Primary)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `mistralai/mistral-large-3-675b-instruct-2512` | Large general-purpose chat model |
| **Context Window** | 131,072 tokens | 128K context for extensive documents |
| **Temperature** | 1.00 | High for creative exploration |
| **Max Tokens** | 15,649 | DeepSeek v3.2 spec |
| **Top K Results** | 8 | Focused retrieval |
| **Reasoning Effort** | `high` | Deep reasoning enabled |
| **API Key** | `nvidia_api_key` | Main API key |

### OpenAI

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `gpt-4o` | Advanced reasoning |
| **Context Window** | 128,000 tokens | |
| **Temperature** | 1.00 | |
| **Max Tokens** | 15,649 | |

### Anthropic Claude

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `claude-sonnet-4-20250514` | Strong reasoning |
| **Context Window** | 200,000 tokens | |
| **Temperature** | 1.00 | |
| **Max Tokens** | 32,768 | |

### Mistral

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `mistral-large-latest` | Large model |
| **Context Window** | 131,072 tokens | |
| **Temperature** | 1.00 | |
| **Max Tokens** | 15,649 | |

### Groq

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `llama-3.3-70b-versatile` | High-quality model |
| **Context Window** | 131,072 tokens | |
| **Temperature** | 1.00 | |
| **Max Tokens** | 15,649 | |

### Ollama (Local)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `llama3` | Local model |
| **Context Window** | 8,192 tokens | |
| **Temperature** | 1.00 | |
| **Max Tokens** | 16,384 | |

---

## Use Cases

**Deep Research Mode is optimized for:**

1. **Complex legal analysis** - Multi-jurisdictional contract review
2. **Financial research** - IFRS compliance analysis, tax planning
3. **Regulatory monitoring** - Comprehensive regulatory changes
4. **Document synthesis** - Multi-document analysis and summarization
5. **Strategic recommendations** - In-depth business intelligence
6. **Cross-referencing** - Connecting information across domains

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **TTFB (Time to First Byte)** | 5-15 seconds |
| **Streaming** | Enabled |
| **Response Quality** | Excellent for complex tasks |
| **Cost Efficiency** | Medium (higher token budget) |
| **Accuracy** | 95%+ for complex queries |

---

## Temperature Settings

| Mode | Temperature | Use Case |
|------|-------------|----------|
| **Fast** | 0.20 | Precise, factual answers |
| **Deep Research** | 1.00 | Creative, exploratory analysis |
| **Analyst** | 0.20 | Professional, structured output |

---

## Deep Research Workflow

### 1. Query Understanding
```
User Query: "Analyze VAT implications of hotel apartment sale in Dubai"
```

### 2. Multi-Document Retrieval
```
- UAE VAT Law (Federal Decree-Law No. 8 of 2017)
- FTA Real Estate Guide (VATGRE1)
- Cabinet Decision No. 52 of 2017
- FTA Public Clarifications
```

### 3. Deep Analysis
```
- Identify relevant articles and clauses
- Cross-reference jurisdictional nuances
- Calculate VAT obligations
- Assess penalties and compliance risks
```

### 4. Comprehensive Output
```
- Structured legal analysis
- Citations with article numbers
- Step-by-step calculations
- Risk assessment
- Regulatory references
```

---

## Implementation Notes

### Model Selection (llm_manager.py)

```python
# Deep research uses main model (mistral-large-3-675b)
if name == "nvidia" and mode == "deep_research":
    provider = NvidiaProvider(
        api_key=settings.nvidia_api_key,
        model=settings.nvidia_model,   # mistral-large-3-675b
        base_url=settings.nvidia_base_url,
        thinking_enabled=True,
    )
```

### Token Budget

- **Deep Research:** 15,649 tokens (DeepSeek v3.2)
- **Fast Mode:** 12,385 tokens (DeepSeek v3.1-terminus)
- **Safety Buffer:** 500 tokens reserved

### Retrieval Strategy

- **Deep Research:** 8 top-k results (focused, high-quality)
- **Fast Mode:** 15 top-k results (broader, faster)

### Domain Filtering

Deep research applies strict domain filtering:
- Confidence threshold: 0.60
- Fallback threshold: 0.39
- General law minimum: 0.35

---

## Configuration File (.env)

```bash
# NVIDIA Main Model (Deep Research)
NVIDIA_MODEL=mistralai/mistral-large-3-675b-instruct-2512
NVIDIA_API_KEY=your_key_here

# Deep Research Settings
TEMPERATURE=1.00
MAX_TOKENS=15649
TOP_K_RESULTS=8
```

---

## Model Comparison

| Provider | Model | Context | Temp | Max Tokens | Best For |
|----------|-------|---------|------|------------|----------|
| **NVIDIA** | mistral-large-3-675b | 128K | 1.0 | 15,649 | Complex legal |
| **OpenAI** | gpt-4o | 128K | 1.0 | 15,649 | General research |
| **Claude** | sonnet-4 | 200K | 1.0 | 32,768 | Long documents |
| **Mistral** | mistral-large | 128K | 1.0 | 15,649 | Balanced |
| **Groq** | llama-3.3-70b | 128K | 1.0 | 15,649 | Fast inference |
| **Ollama** | llama3 | 8K | 1.0 | 16,384 | Local |

---

## Testing Checklist

- [ ] Deep research responds in <30 seconds for complex queries
- [ ] Streaming works correctly
- [ ] Token budget enforced (15,649 max)
- [ ] Domain filtering applied correctly
- [ ] High temperature produces varied output
- [ ] Citations are accurate
- [ ] No hallucinations in legal references
- [ ] Proper error handling for API failures

---

## Related Files

- `backend/core/llm_manager.py` - Model factory and configuration
- `backend/config.py` - Settings definitions
- `backend/api/chat.py` - Mode routing logic
- `backend/core/rag_engine.py` - RAG configuration
- `backend/core/prompt_router.py` - System prompts

---

## Version History

| Date | Change |
|------|--------|
| 2026-05-08 | Initial specification |
