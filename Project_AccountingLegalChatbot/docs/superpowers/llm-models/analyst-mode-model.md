# Analyst Mode LLM Model Specification

> **For agentic workers:** This model defines the Analyst Mode configuration for the Accounting & Legal AI Chatbot.

**Goal:** Provide professional, structured analysis for financial and legal matters with precise formatting and citations.

**Architecture:** Optimized for professional output with balanced temperature, medium token budgets, and structured responses.

**Tech Stack:** NVIDIA NIM (primary), OpenAI, Anthropic Claude, Mistral, Groq, Ollama.

---

## Model Configuration

### NVIDIA NIM (Primary)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `mistralai/mistral-large-3-675b-instruct-2512` | Large general-purpose chat model |
| **Context Window** | 131,072 tokens | 128K context for extensive documents |
| **Temperature** | 0.20 | Low for professional precision |
| **Max Tokens** | 15,649 | DeepSeek v3.2 spec |
| **Top K Results** | 8 | Focused retrieval |
| **Reasoning Effort** | `high` | Deep reasoning enabled |
| **API Key** | `nvidia_api_key` | Main API key |

### OpenAI

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `gpt-4o` | Professional grade |
| **Context Window** | 128,000 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 15,649 | |

### Anthropic Claude

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `claude-sonnet-4-20250514` | Professional grade |
| **Context Window** | 200,000 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 32,768 | |

### Mistral

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `mistral-large-latest` | Professional grade |
| **Context Window** | 131,072 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 15,649 | |

### Groq

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `llama-3.3-70b-versatile` | Professional grade |
| **Context Window** | 131,072 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 15,649 | |

### Ollama (Local)

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Model** | `llama3` | Local model |
| **Context Window** | 8,192 tokens | |
| **Temperature** | 0.20 | |
| **Max Tokens** | 16,384 | |

---

## Use Cases

**Analyst Mode is optimized for:**

1. **Financial analysis** - IFRS compliance, financial reporting
2. **Legal compliance** - VAT, corporate tax, regulatory filings
3. **Audit preparation** - Risk assessment, control evaluation
4. **Document review** - Contract analysis, clause extraction
5. **Regulatory research** - UAE law, FTA guidance
6. **Professional reports** - Structured, citation-ready output

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **TTFB (Time to First Byte)** | 3-10 seconds |
| **Streaming** | Enabled |
| **Response Quality** | Professional-grade |
| **Cost Efficiency** | Medium (balanced token budget) |
| **Accuracy** | 95%+ for professional queries |

---

## Temperature Settings

| Mode | Temperature | Use Case |
|------|-------------|----------|
| **Fast** | 0.20 | Precise, factual answers |
| **Deep Research** | 1.00 | Creative, exploratory analysis |
| **Analyst** | 0.20 | Professional, structured output |

---

## Analyst Mode Output Format

### Standard Structure

```
## Analysis Title

### Background
[Context and relevant facts]

### Key Findings
- Finding 1 with citation
- Finding 2 with citation
- Finding 3 with citation

### Calculations
[Step-by-step numerical analysis]

### Risks
- Risk 1 (Critical/High/Medium/Low)
- Risk 2 (Critical/High/Medium/Low)

### Recommendations
1. Action item with regulatory reference
2. Action item with regulatory reference

### Regulatory References
- Federal Decree-Law No. X of 2017, Article Y
- Cabinet Decision No. Z of 2017
```

---

## Domain-Specific Prompts

### Finance Domain

```python
"You are an expert AI assistant specialising in financial accounting, IFRS, 
UAE Corporate Tax (9% rate from June 2023), VAT (5% standard rate), FTA 
compliance, and financial reporting. When answering: cite the relevant 
standard or article, use AED as the default currency, present calculations 
step-by-step, and be precise with numbers, dates, and regulatory references."
```

### Law Domain

```python
"You are an expert AI assistant specialising in UAE law, civil and commercial 
legislation, contract law, company law (Federal Decree-Law No. 32 of 2021), 
employment law, and legal compliance. When answering: cite the relevant law, 
decree-law, or article number, clarify jurisdictional nuances (mainland vs 
free-zone), and be precise with numbers, dates, and regulatory references."
```

### Audit Domain

```python
"You are an expert AI assistant specialising in audit, assurance, internal 
controls, ISA standards, UAE regulatory filings, AML/CFT compliance, and risk 
assessment. When answering: reference the relevant ISA or regulatory framework, 
outline key audit procedures, highlight red flags, and indicate when external 
auditor sign-off is required."
```

### VAT Domain

```python
"You are a UAE VAT Specialist. You operate under Federal Decree-Law No. 8 of 2017 
and its Executive Regulations. Cite the specific Article and Cabinet Decision 
number, calculate VAT at 5% standard rate (or 0% / exempt where applicable), 
reference FTA public clarifications, and flag partial exemption situations."
```

---

## Implementation Notes

### Model Selection (llm_manager.py)

```python
# Analyst mode uses main model (mistral-large-3-675b)
if name == "nvidia" and mode == "analyst":
    provider = NvidiaProvider(
        api_key=settings.nvidia_api_key,
        model=settings.nvidia_model,    # mistral-large-3-675b
        base_url=settings.nvidia_base_url,
        thinking_enabled=True,
    )
```

### Token Budget

- **Analyst:** 15,649 tokens (DeepSeek v3.2)
- **Fast Mode:** 12,385 tokens (DeepSeek v3.1-terminus)
- **Safety Buffer:** 500 tokens reserved

### Retrieval Strategy

- **Analyst:** 8 top-k results (focused, high-quality)
- **Fast Mode:** 15 top-k results (broader, faster)

### Domain Filtering

Analyst mode applies strict domain filtering:
- Confidence threshold: 0.60
- Fallback threshold: 0.39
- General law minimum: 0.35

---

## Configuration File (.env)

```bash
# NVIDIA Main Model (Analyst)
NVIDIA_MODEL=mistralai/mistral-large-3-675b-instruct-2512
NVIDIA_API_KEY=your_key_here

# Analyst Settings
TEMPERATURE=0.20
MAX_TOKENS=15649
TOP_K_RESULTS=8
```

---

## Model Comparison

| Provider | Model | Context | Temp | Max Tokens | Best For |
|----------|-------|---------|------|------------|----------|
| **NVIDIA** | mistral-large-3-675b | 128K | 0.2 | 15,649 | Professional analysis |
| **OpenAI** | gpt-4o | 128K | 0.2 | 15,649 | Financial reports |
| **Claude** | sonnet-4 | 200K | 0.2 | 32,768 | Long documents |
| **Mistral** | mistral-large | 128K | 0.2 | 15,649 | Balanced |
| **Groq** | llama-3.3-70b | 128K | 0.2 | 15,649 | Fast inference |
| **Ollama** | llama3 | 8K | 0.2 | 16,384 | Local |

---

## Formatting Rules

### Required Formatting

1. **Headers:** Use `##` for top-level, `###` for sub-sections
2. **Bold:** Key terms, figures, concepts with `**text**`
3. **Lists:** Bullet points `- item` with two-space indent for sub-items
4. **Tables:** Markdown tables for comparative data
5. **Blockquotes:** `> **Pro-Tip:** ...` for warnings/callouts

### Prohibited Formatting

- Never use `#` (h1) - only `##` and below
- Never nest more than 2 levels deep
- Short answers (1-2 sentences) should omit structure

---

## Testing Checklist

- [ ] Analyst mode produces structured output
- [ ] Citations include article numbers and decree references
- [ ] Calculations are step-by-step and accurate
- [ ] Risk levels are properly classified
- [ ] Temperature 0.20 produces consistent output
- [ ] Token budget enforced (15,649 max)
- [ ] Domain filtering works correctly
- [ ] No hallucinations in regulatory references

---

## Related Files

- `backend/core/llm_manager.py` - Model factory and configuration
- `backend/config.py` - Settings definitions
- `backend/api/chat.py` - Mode routing logic
- `backend/core/prompt_router.py` - Domain prompts and formatting
- `backend/core/rag_engine.py` - RAG configuration

---

## Version History

| Date | Change |
|------|--------|
| 2026-05-08 | Initial specification |
