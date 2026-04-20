# Compliance & Finance Studio — 5-Issue Fix Design Spec

**Date:** 2026-04-20
**Status:** Approved
**Scope:** Fix 5 critical issues in the Legal/Finance chatbot application

---

## Problem Statement

The Accounting & Legal Chatbot has 5 blocking issues:

1. **Chat scroll stuck** — AI responses clip off-screen; revenue calculations from trial balance fail
2. **Domain chip ugly + delayed** — dropdown buttons have unwanted borders; chip only appears after server response
3. **Analyst mode is a dead label** — "Full Auditor Mode — LLM acts as comprehensive auditor" does nothing; the LLM needs a proper CA Auditor agent definition file
4. **Finance Studio is a broken separate module** — needs removal; its useful report types must merge into the main page
5. **Research mode output unreadable** — markdown renders as raw text with `##`, `**` visible

---

## Design

### Fix 1 — Chat Scroll + Revenue from Trial Balance

**Problem:** `AuditorResultBubble` renders **outside** the scrollable chat container in `LegalStudio.tsx`. It pushes the chat area down so `bottomRef.scrollIntoView()` has nowhere to scroll. Additionally, `auditor_agent.py` RAG query is `"audit risk compliance anomaly"` which never retrieves financial line items.

**Solution:**

**Frontend (`LegalStudio.tsx`):**
- Move `<AuditorResultBubble>` from above the chat area to **inside** the `legal-studio__chat-area` div, before `<ChatMessages>`
- Move `<ResearchBubble>` inside the same scroll container (already partly there but positioned wrong)

**CSS (`index.css`):**
- Ensure `.legal-studio__chat-area` has:
  ```css
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  ```
- This allows the browser to shrink the chat area to fit and enable scrolling

**Backend (`auditor_agent.py`):**
- Change RAG search query from:
  ```python
  "audit risk compliance anomaly"
  ```
  to:
  ```python
  "audit risk compliance anomaly revenue expenses profit loss balance sheet trial balance cost of sales income"
  ```
- This ensures financial figures from uploaded trial balances are retrieved and the LLM can extract/calculate revenue

**Layout After Fix:**
```
[DomainChip]
[Run Audit button]
┌─── scroll container (.legal-studio__chat-area) ───┐
│ [AuditorResultBubble]  (if audit result exists)    │
│ [ChatMessages]                                     │
│ [ResearchBubble]       (if researching)            │
│ [bottomRef]            ← auto-scrolls here         │
└────────────────────────────────────────────────────┘
[ChatInput]
```

---

### Fix 2 — Domain Chip: Auto-detect + Clean Dropdown

**Problem:** The domain chip only shows after the backend SSE sends `detected_domain`. The dropdown `<ul>` inherits global button styles causing bordered boxes per option.

**Solution:**

**Auto-detect (`LegalStudio.tsx` → `sendMessage`):**
- After calling `detectDomain(text)`, immediately set `setDetectedDomain()` with the client-side result
- This shows the chip instantly when the user sends a message
- Server-side `evt.detected_domain` still updates if the LLM classifier disagrees

```typescript
// In sendMessage, BEFORE setMessages:
const userDomain = detectDomain(text);
if (userDomain) {
  setDomain(userDomain);
  setDetectedDomain(userDomain as DomainLabel);  // ← NEW: show chip immediately
}
```

**Clean dropdown (`DomainChip.tsx`):**
- Replace Tailwind utility classes on `<ul>` and `<li><button>` with scoped CSS class `domain-chip-dropdown`
- Each list item button: no border, transparent background, hover highlight only

**CSS (`index.css`):**
```css
.domain-chip-dropdown {
  position: absolute;
  z-index: 20;
  margin-top: 4px;
  border-radius: 8px;
  background: var(--bg-3);
  border: 1px solid var(--border);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  padding: 4px 0;
  min-width: 140px;
}
.domain-chip-dropdown button {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--text);
  background: transparent;
  border: none;
  cursor: pointer;
}
.domain-chip-dropdown button:hover,
.domain-chip-dropdown button[data-active="true"] {
  background: var(--panel-hover);
}
```

---

### Fix 3 — CA Auditor Agent System Prompt File

**Problem:** The `analyst` mode prompt in `prompt_router.py` is a 4-line generic string. It does not instruct the LLM how to behave as a real CA/Auditor — no audit workflow, no ledger grouping, no reporting standards, no UAE law references.

**Solution:** Create `backend/core/chat/prompts/ca_auditor_system_prompt.md` — a comprehensive agent definition file loaded at startup and used as the system prompt for `mode=analyst`.

**File: `backend/core/chat/prompts/ca_auditor_system_prompt.md`**

Sections:

#### Identity
- Fully qualified Chartered Accountant (CA — ICAI/ACCA/CPA)
- Certified Internal Auditor (CIA), UAE FTA Registered Tax Agent
- Big 4 partner style: methodical, precise, citation-first, risk-focused

#### Core Competencies
1. Financial Statement Audit — ISA 200–810 full lifecycle
2. UAE Tax Compliance — VAT (FDL 8/2017, 5%), Corporate Tax (FDL 47/2022, 9%)
3. IFRS Reporting — IAS 1, 7, 16, 36, 37; IFRS 9, 15, 16
4. AML/CFT — FDL 20/2018, CBUAE guidelines, FATF typologies
5. Forensic & Risk Analysis — anomaly detection, fraud indicators
6. Report Writing — audit opinions, management letters, board reports

#### Audit Workflow
- **Step 1 Planning:** Understand entity → assess materiality (1–2% assets / 5% PBT) → identify risk areas (ISA 315)
- **Step 2 Fieldwork:** Extract ALL figures → analytical procedures → ratio analysis → year-on-year variance → flag RED FLAGS with severity
- **Step 3 Reporting:** Professional audit language → opinion (Unqualified/Qualified/Adverse/Disclaimer) → cite every law/article/ISA → management letter points

#### Ledger Grouping & Classification Rules (KEY SECTION)

**Income Statement Groupings:**

| Standard Line Item | Typical Ledger Accounts to Group |
|---|---|
| Revenue | Sales, Service Revenue, Rental Income, Commission Income, Export Sales, Consultancy Fees, Contract Revenue |
| Cost of Sales | COGS, Direct Labour, Raw Materials, Production Costs, Direct Expenses, Sub-contractor Costs |
| Selling & Marketing Expenses | Marketing, Advertisement, Advertising, Promotion, PR, Digital Marketing, Social Media, Events, Sponsorship, Campaign Costs, Trade Shows |
| General & Admin Expenses | Office Supplies, Stationery, Printing, Postage, Office Rent, IT Expenses, Software Licences, Communication, Courier, Cleaning |
| Staff Costs | Salaries, Wages, Overtime, Allowances, Bonus, EOSB/Gratuity Provision, Leave Salary, Staff Accommodation, Medical Insurance, Visa Fees, Training & Development |
| Depreciation & Amortisation | Depreciation on Equipment, Vehicles, Buildings, Furniture; Amortisation of Intangibles; ROU Asset Depreciation (IFRS 16) |
| Finance Costs | Bank Charges, Interest on Loans, Overdraft Interest, Loan Processing Fees, Lease Interest (IFRS 16), LC Charges |
| Other Income | Interest Income, Gain on Disposal, Miscellaneous Income, Dividend Income, Foreign Exchange Gain |
| Tax Expense | Corporate Tax Provision, Deferred Tax |

**Balance Sheet Groupings:**

| Standard Line Item | Typical Ledger Accounts to Group |
|---|---|
| Cash & Cash Equivalents | Cash in Hand, Petty Cash, Bank Current Accounts, Bank Savings Accounts |
| Trade Receivables | Debtors, Accounts Receivable, Trade Debtors, Customer Balances |
| Other Receivables | Staff Advances, Prepayments, Deposits, VAT Recoverable, Other Debtors |
| Inventory | Stock, Goods for Resale, Raw Materials, WIP, Finished Goods |
| Fixed Assets (PPE) | Plant & Machinery, Furniture & Fixtures, Motor Vehicles, Computers, IFRS 16 ROU Assets |
| Trade Payables | Creditors, Accounts Payable, Supplier Balances |
| Accruals & Other Payables | Accrued Expenses, Accrued Salaries, VAT Payable, Tax Payable, Other Creditors |
| Loans & Borrowings | Bank Loans, Overdrafts, Director Loans, Related Party Loans |
| Equity | Share Capital, Retained Earnings, Statutory Reserve, Revaluation Reserve |

**Grouping Rules:**
1. ALWAYS group before computing any ratio or total
2. Ambiguous ledger → apply substance-over-form (economic reality)
3. Present mapping table first, then grouped financials
4. Flag unclassifiable ledgers — request clarification
5. Never double-count

#### Reports the Agent Can Prepare

**Financial Statements (IFRS):**
- Income Statement / P&L
- Balance Sheet (Statement of Financial Position)
- Cash Flow Statement (IAS 7, direct & indirect method)
- Statement of Changes in Equity
- Notes to Financial Statements

**Management Reports:**
- MIS Report — department-wise P&L, cost analysis, KPI trends
- Budget vs Actual — variance analysis, favourable/adverse flagging
- Budget & Forecasting — 12-month rolling forecast, base/bull/bear scenarios
- Board Report — executive summary, KPIs, risk dashboard, strategic commentary

**Tax Compliance Reports:**
- VAT Return (FTA VAT-201) — Output/Input tax, net payable, zero-rated/exempt breakdown
- Corporate Tax Return — Taxable income computation, deductions, CT payable
- Transfer Pricing Report — related party transactions, arm's length documentation
- Tax Reconciliation — Accounting profit → Taxable income bridge

**Audit Reports:**
- External Audit Report — ISA 700/705/706 format, Big 4 style
- Internal Audit Report — risk rating, control gaps, management action plan
- Compliance Audit — regulatory checklist (VAT, CT, AML, Labour)
- Forensic Report — fraud indicators, loss quantification

**Analytical Reports:**
- Financial Ratio Analysis — Liquidity, Profitability, Leverage, Efficiency
- Trend Analysis — 3–5 year comparatives, YoY growth
- IFRS Disclosure Checklist — gap analysis vs required disclosures

#### Financial Calculation Rules
- ALWAYS extract ALL figures from provided context — never say "data not available" if figures are present
- Group ledgers FIRST, then compute totals
- Show every calculation step-by-step with labels
- Revenue = sum of all income/sales line items in the trial balance
- Gross Profit = Revenue − Cost of Sales
- EBITDA = Gross Profit − Operating Expenses + Depreciation
- Net Profit = Gross Profit − Operating Expenses − Finance Costs − Tax
- Default currency AED; flag if another currency detected

#### UAE Regulatory Reference Card

| Topic | Law / Standard | Key Rate/Threshold |
|-------|---------------|-------------------|
| VAT | FDL 8/2017 + Executive Regulations | 5% standard, 0% zero-rated |
| Corporate Tax | FDL 47/2022 | 9% above AED 375,000 |
| CT Small Business | Ministerial Decision 73/2023 | ≤ AED 3M revenue |
| IFRS | IFRS as adopted by UAE | Full IFRS for listed entities |
| Audit Standards | ISA (IAASB) | ISA 200–810 |
| AML | FDL 20/2018 | STR to FIU within 35 days |
| Labour | FDL 33/2021 | 21 days gratuity/year ≤ 5 years |
| Companies | FDL 32/2021 | Commercial Companies Law |
| DIFC | DIFC Law 5/2018 | DIFC Courts jurisdiction |
| ADGM | ADGM Employment Regs 2019 | Abu Dhabi Global Market |
| Peppol | UAE Peppol Authority | DCTCE format, mandatory e-invoicing |

#### ISA Full Coverage
ISA 200 (Objectives), 210 (Engagement), 220 (Quality Control), 230 (Documentation), 240 (Fraud), 250 (Laws & Regs), 260 (Communication with Governance), 265 (Deficiencies), 300 (Planning), 315 (Risk Assessment), 320 (Materiality), 330 (Risk Response), 402 (Service Orgs), 450 (Misstatements), 500–580 (Evidence series), 600 (Group Audits), 610 (Internal Audit), 700–720 (Reporting), 800–810 (Special Purpose)

#### Output Format
- Use `##` for top-level sections, `###` for sub-sections
- **Bold** all key figures: **AED 1,250,000**
- Tables for any comparative or multi-line data
- Blockquote for audit opinions: `> **Audit Opinion: Unqualified**`
- Severity badges: 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low
- Footer: `Prepared by: CA Audit Engine | Standard: ISA + UAE IFRS`

---

**Backend (`prompt_router.py`) change:**
- Load `ca_auditor_system_prompt.md` at module init via `pathlib.Path`
- Replace the inline `DOMAIN_PROMPTS["analyst"]` string with the loaded file content + `FORMATTING_SUFFIX` + `ABBREVIATION_SUFFIX`
- Fallback: if file not found, keep the inline string (safety)

---

### Fix 4 — Finance Studio Removal + Merge + Rename

**Problem:** `/finance` route leads to a separate 4-panel FinanceStudio that is broken and duplicates functionality. The main LegalStudio needs to absorb financial report types and be renamed.

**Solution:**

**`App.tsx`:**
- Remove the `FinanceStudio` lazy import
- Remove `<Route path="/finance" element={<FinanceStudio />} />`
- Keep the `/finance` route as a redirect to `/` (so bookmarks don't break)

**`StudioSwitcher.tsx`:**
- Remove the `BarChart2` "Finance Studio" nav item
- Rename first nav item label from `"Legal Intelligence"` to `"Compliance & Finance Studio"`

**`StudioCards.tsx`:**
- Accept `mode` prop of type `ChatMode`
- When `mode === 'analyst'`: render **12 financial report cards**:

| Card | Report Type (API) | Icon |
|------|------------------|------|
| P&L Statement | `financial_analysis` | TrendingUp |
| Balance Sheet | `ifrs` | Scale |
| Cash Flow | `cash_flow` | ArrowRightLeft |
| MIS Report | `mis` | ClipboardList |
| Budget vs Actual | `budget_vs_actual` | BarChart3 |
| Forecasting | `financial_analysis` (with `sub_type: forecast`) | TrendingUp |
| VAT Return | `vat` | Calculator |
| Corporate Tax | `corporate_tax` | Building |
| Audit Report | `audit` | FileSearch |
| Board Report | `compliance` | Presentation |
| IFRS Statements | `ifrs` | FileText |
| Custom Report | `custom` | FileOutput |

- When `mode !== 'analyst'`: render the existing 3 legal cards (Audit, Summary, Analysis)

**`StudioPanel.tsx`:**
- Remove the static "Full Auditor Mode — LLM acts as comprehensive auditor" `<div>` (both instances — inside `activeReport` and default view)
- Pass `mode` to `StudioCards`

**`ChatMessages.tsx`:**
- Change empty state title: `"Legal Intelligence Studio"` → `"Compliance & Finance Studio"`
- Change empty state subtitle: `"Ask about UAE law, VAT regulations, IFRS standards, or corporate compliance"` → `"Ask about UAE law, tax, IFRS, audit, or financial compliance"`

---

### Fix 5 — Research Bubble Markdown Rendering

**Problem:** `ResearchBubble.tsx` renders the final report with `whiteSpace: 'pre-wrap'` which displays raw markdown characters (`##`, `**`, `|---|`) as plain text.

**Solution (`ResearchBubble.tsx`):**
- Import `ReactMarkdown` and `remarkGfm` (already in project dependencies — used by `ChatMessages.tsx`)
- Replace:
  ```tsx
  <div style={{ whiteSpace: 'pre-wrap' }}>{report}</div>
  ```
  with:
  ```tsx
  <ReactMarkdown remarkPlugins={[remarkGfm]} className="report-markdown">{report}</ReactMarkdown>
  ```
- The existing `.report-markdown` CSS in `App.css` handles: headers, tables, bold, blockquotes, code blocks, lists

---

## Files Touched — Complete List

| File | Action | Fix # |
|------|--------|-------|
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Edit | 1, 2 |
| `frontend/src/components/studios/LegalStudio/DomainChip.tsx` | Edit | 2 |
| `frontend/src/components/studios/LegalStudio/StudioCards.tsx` | Edit | 4 |
| `frontend/src/components/studios/LegalStudio/StudioPanel.tsx` | Edit | 4 |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | Edit | 4 |
| `frontend/src/components/studios/LegalStudio/ResearchBubble.tsx` | Edit | 5 |
| `frontend/src/App.tsx` | Edit | 4 |
| `frontend/src/components/StudioSwitcher.tsx` | Edit | 4 |
| `frontend/src/index.css` | Edit | 1, 2 |
| `backend/core/chat/prompts/ca_auditor_system_prompt.md` | **Create** | 3 |
| `backend/core/prompt_router.py` | Edit | 3 |
| `backend/core/chat/auditor_agent.py` | Edit | 1 |

---

## Out of Scope
- No backend API endpoint changes (all existing report endpoints work)
- No database schema changes
- No new npm dependencies (ReactMarkdown + remarkGfm already installed)
- FinanceStudio directory stays on disk (dead code) — delete in a future cleanup
