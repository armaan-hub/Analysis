# 6-Subagent Financial Audit Council (Standalone Local CLI)

A zero-dependency, multi-agent AI council designed to process raw corporate financial statements and generate statutory UAE Comparative Mainland Audit Reports in full compliance with **IFRS**, **UAE Commercial Companies Law (Federal Decree-Law No. 32 of 2021)**, and **UAE Corporate Tax Law (Federal Decree-Law No. 47 of 2022)**.

---

## 🏛️ The 6-Agent Council Pipeline

| Stage | Subagent | Role | Key Function |
|:---:|:---|:---|:---|
| **1/6** | ⚖️ **Corporate Legal Extractor** | `legal_extraction` | Extracts Trade License, MOA, shareholding structure, General Manager authority, and licensed activities. |
| **2/6** | 📊 **Trial Balance Auditor** | `tb_audit` | Analyzes 2025/2024 Trial Balances, debit/credit parity, asset classification, and ledger mappings. |
| **3/6** | 📈 **Profit & Loss Analyst** | `pl_analysis` | Audits revenue streams, Cost of Sales, G&A expenses, 9% Corporate Tax computation, and profit appropriations. |
| **4/6** | 📑 **Comparative Mainland Mapper** | `mainland_mapping` | Enforces strict **2025-first / 2024-second** chronological presentation, Note indexing, and `-` zero notation. |
| **5/6** | 🖋️ **Audit Report Synthesis Chair** | `report_synthesis` | Synthesizes full statutory report: Corporate Directory, Unqualified Opinion, SOFP, SOPL, SOCE, CFS, and Notes 1–29. |
| **6/6** | 🔍 **Audit Math Verification Critic** | `math_qc` | Performs line-by-line tie-out ($\text{Assets} = \text{Liabilities} + \text{Equity}$), checks retained earnings roll-forward, and flags discrepancies. |

---

## 🚀 Quick Start

### 1. Run with Built-in Sample Data (Instant Test)
```bash
python3 run_audit_council.py --sample
```
Or from within `audit_council_local/`:
```bash
python3 -m audit_council_local.cli --sample
```

### 2. Run on Your Own Financial & Legal Documents
```bash
python3 run_audit_council.py \
  --doc1 path/to/balance_sheet_trial_balance.txt \
  --doc2 path/to/profit_and_loss.txt \
  --doc3 path/to/trade_license_and_moa.txt \
  --doc4 path/to/custom_template_notes.txt \
  --output my_audit_report.md
```

### 3. List Available OpenCode Free Tier Models
```bash
python3 run_audit_council.py --list-free-models
```

---

## ⚙️ LLM Providers & Models

### OpenCode Zen Free Tier (Default Active Provider)
The tool comes pre-configured with OpenCode Zen Free Tier models:
- `laguna-s-2.1-free` (Default)
- `deepseek-v4-flash-free`
- `minimax-m3-free`
- `mimo-v2.5-free`
- `nemotron-3-super-free`

```bash
# Run with a specific free model
python3 run_audit_council.py --sample --model deepseek-v4-flash-free

# Provide custom OpenCode key
python3 run_audit_council.py --sample --api-key "sk-..."
```

### Local Proxy / LM Studio / Ollama (OpenAI Compatible)
If running a local LLM proxy at `http://127.0.0.1:4001/v1` or LM Studio / vLLM:
```bash
python3 run_audit_council.py --sample \
  --provider proxy \
  --base-url "http://127.0.0.1:4001/v1" \
  --model "gpt-4o"
```

### Native Anthropic Claude
```bash
python3 run_audit_council.py --sample \
  --provider anthropic \
  --model "claude-haiku-4-5-20251001" \
  --api-key "sk-ant-..."
```

---

## 📋 Mandatory Statutory Rules Enforced

1. **Strict Chronological Presentation**:
   - Column 1 (Left): **2025** (Current Reporting Period)
   - Column 2 (Right): **2024** (Prior Comparative Period)
   - Never reversed across all statements and disclosure tables.
2. **Corporate Context Integration**:
   - Entity name in English & Arabic.
   - License Number, DET Registration, Chamber of Commerce No.
   - Complete Shareholder table (Names, Nationalities, Share Counts, % stakes, Capital in AED).
   - General Manager powers and authorized signatory clauses.
3. **Audit-Grade Zero Notation**:
   - Nil, empty, or zero balances are rendered as `-` (standard accounting presentation).
4. **Mathematical Tie-outs**:
   - $\text{Total Assets} = \text{Total Liabilities} + \text{Total Equity}$ ($0.00$ variance).
   - $\text{Net Profit} = \text{EBIT} - \text{Finance Costs} - \text{Corporate Tax (9\%)}$.
   - Retained earnings reconciliation matching dividends and statutory reserve transfers (10% capped at 50% share capital).

---

## 🧪 Testing the Local Package

Run the standalone unit test suite with zero dependencies:
```bash
python3 -m unittest audit_council_local/test_local_council.py
```
All 6 test cases verify persona system prompts, template constants, currency formatters, sample files, free tier catalog, and mock streaming execution.
