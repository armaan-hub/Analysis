# Compliance & Finance Studio — 5-Issue Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 critical issues: chat scroll, domain chip UX, CA Auditor agent prompt, Finance Studio removal + merge, and research markdown rendering.

**Architecture:** The main LegalStudio page becomes "Compliance & Finance Studio" — a single-page application with a 3-pane layout (sources / chat+toolbar / studio panel). Analyst mode activates 12 financial report cards and routes through a comprehensive CA Auditor system prompt loaded from a `.md` file. The separate Finance Studio route is removed.

**Tech Stack:** React + TypeScript (Vite), Python/FastAPI backend, ReactMarkdown + remarkGfm, SSE streaming

**Spec:** `docs/superpowers/specs/2026-04-20-compliance-finance-studio-design.md`

---

## Task 1: Fix Chat Scroll — Move Audit/Research Bubbles Inside Scroll Container

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx:331-405`
- Modify: `frontend/src/index.css:2430-2436`

- [ ] **Step 1: Fix the CSS — make `.legal-studio__chat-area` scrollable**

In `frontend/src/index.css`, find the block at line 2430:

```css
.legal-studio__chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
```

Replace with:

```css
.legal-studio__chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 0;
  position: relative;
}
.legal-studio__chat-area::-webkit-scrollbar { width: 4px; }
.legal-studio__chat-area::-webkit-scrollbar-track { background: transparent; }
.legal-studio__chat-area::-webkit-scrollbar-thumb { background: var(--s-border); border-radius: 2px; }
```

- [ ] **Step 2: Restructure `centerContent` in LegalStudio.tsx — move bubbles inside scroll area**

In `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`, replace the entire `centerContent` block (lines 331–405) with:

```tsx
  const centerContent = (
    <>
      {detectedDomain && (
        <div className="legal-domain-chip-wrapper">
          <DomainChip
            value={detectedDomain}
            editable
            onChange={(d) => { setDetectedDomain(d); setDomain(d as Domain); }}
          />
        </div>
      )}

      {/* Toolbar */}
      <div className="legal-toolbar">
        {(mode === 'analyst' || domain === 'audit') && (
          <button
            type="button"
            className="legal-toolbar__btn legal-toolbar__btn--audit"
            onClick={handleRunAudit}
            disabled={selectedDocIds.length === 0 || auditing}
            aria-label={`Run audit on ${selectedDocIds.length} selected documents`}
          >
            {auditing
              ? <><Loader2 size={14} className="spin" style={{ verticalAlign: 'middle', marginRight: 4 }} />Auditing…</>
              : <><ScanSearch size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />Run Audit ({selectedDocIds.length})</>
            }
          </button>
        )}
      </div>

      {/* Scrollable chat area — audit result, messages, and research all scroll together */}
      <div className="legal-studio__chat legal-studio__chat-area">
        {auditResult && (
          <div className="legal-section-pad">
            <AuditorResultBubble
              risk_flags={auditResult.risk_flags}
              anomalies={auditResult.anomalies}
              compliance_gaps={auditResult.compliance_gaps}
              summary={auditResult.summary}
            />
          </div>
        )}

        <ChatMessages
          messages={messages}
          loading={loading}
          webSearching={webSearching}
          onSourceClick={handleSourceClick}
          activeSourceId={activeSource?.source}
        />

        {(researching || researchReport) && (
          <div className="legal-section-pad">
            <ResearchBubble phases={researchPhases} report={researchReport} />
          </div>
        )}
      </div>

      {sourcePanelOpen && activeSources.length > 0 && (
        <SourcePeeker
          key={`source-peeker-${messages.length}`}
          sources={activeSources}
          isOpen={sourcePanelOpen}
          highlightedSource={activeSource?.source}
          onClose={() => { setSourcePanelOpen(false); setActiveSource(null); }}
        />
      )}

      <ChatInput
        onSend={sendMessage}
        disabled={loading}
        initialValue={initialValue}
        mode={mode}
        onModeChange={setMode}
      />
    </>
  );
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx vite build 2>&1 | Select-Object -Last 10`
Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/index.css
git commit -m "fix: move audit/research bubbles inside scroll container for proper chat scrolling"
```

---

## Task 2: Fix Domain Chip — Auto-detect Upfront + Clean Dropdown CSS

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx:187-189`
- Modify: `frontend/src/components/studios/LegalStudio/DomainChip.tsx`
- Modify: `frontend/src/index.css` (append new styles)

- [ ] **Step 1: Set `detectedDomain` immediately on send in `LegalStudio.tsx`**

In `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`, find these lines inside `sendMessage` (around line 187–189):

```typescript
    const userDomain = detectDomain(text);
    if (userDomain) { setDomain(userDomain); }
```

Replace with:

```typescript
    const userDomain = detectDomain(text);
    if (userDomain) {
      setDomain(userDomain);
      setDetectedDomain(userDomain as DomainLabel);
    }
```

- [ ] **Step 2: Rewrite `DomainChip.tsx` with proper scoped CSS classes**

Replace the entire content of `frontend/src/components/studios/LegalStudio/DomainChip.tsx` with:

```tsx
import { useState } from "react";

export type DomainLabel =
  | "vat"
  | "corporate_tax"
  | "peppol"
  | "e_invoicing"
  | "labour"
  | "commercial"
  | "ifrs"
  | "general_law";

const ALL: DomainLabel[] = [
  "vat",
  "corporate_tax",
  "peppol",
  "e_invoicing",
  "labour",
  "commercial",
  "ifrs",
  "general_law",
];

const LABELS: Record<DomainLabel, string> = {
  vat: "VAT",
  corporate_tax: "Corporate Tax",
  peppol: "Peppol",
  e_invoicing: "E-Invoicing",
  labour: "Labour",
  commercial: "Commercial",
  ifrs: "IFRS",
  general_law: "General Law",
};

interface Props {
  value: DomainLabel;
  editable: boolean;
  onChange?: (v: DomainLabel) => void;
}

export function DomainChip({ value, editable, onChange }: Props) {
  const [open, setOpen] = useState(false);
  if (!editable) {
    return (
      <span className="domain-chip">
        {LABELS[value]}
      </span>
    );
  }
  return (
    <div className="domain-chip-wrapper">
      <button
        type="button"
        className="domain-chip domain-chip--editable"
        onClick={() => setOpen(!open)}
      >
        Domain: {LABELS[value]} ✎
      </button>
      {open && (
        <ul className="domain-chip-dropdown">
          {ALL.map((d) => (
            <li key={d}>
              <button
                type="button"
                data-active={d === value ? "true" : undefined}
                onClick={() => {
                  onChange?.(d);
                  setOpen(false);
                }}
              >
                {LABELS[d]}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add domain chip CSS to `index.css`**

Append the following to the end of `frontend/src/index.css`:

```css
/* ── Domain Chip ── */
.domain-chip-wrapper {
  position: relative;
  display: inline-block;
}
.domain-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(139, 92, 246, 0.15);
  color: var(--teal);
  font-size: 12px;
  font-family: var(--font-sans);
  border: none;
}
.domain-chip--editable {
  cursor: pointer;
  transition: background 0.15s;
}
.domain-chip--editable:hover {
  background: rgba(139, 92, 246, 0.25);
}
.domain-chip-dropdown {
  position: absolute;
  z-index: 30;
  margin-top: 4px;
  border-radius: 8px;
  background: var(--bg-3);
  border: 1px solid var(--border);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  padding: 4px 0;
  min-width: 150px;
  list-style: none;
}
.domain-chip-dropdown li {
  margin: 0;
  padding: 0;
}
.domain-chip-dropdown button {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 14px;
  font-size: 12px;
  font-family: var(--font-sans);
  color: var(--text);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.12s;
}
.domain-chip-dropdown button:hover,
.domain-chip-dropdown button[data-active="true"] {
  background: var(--panel-hover);
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npx vite build 2>&1 | Select-Object -Last 10`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx \
       frontend/src/components/studios/LegalStudio/DomainChip.tsx \
       frontend/src/index.css
git commit -m "fix: auto-detect domain chip on send + clean dropdown CSS"
```

---

## Task 3: Create CA Auditor Agent System Prompt + Load in Backend

**Files:**
- Create: `backend/core/chat/prompts/ca_auditor_system_prompt.md`
- Modify: `backend/core/prompt_router.py:122-133`

- [ ] **Step 1: Create the CA Auditor system prompt file**

Create `backend/core/chat/prompts/ca_auditor_system_prompt.md` with the following content:

```markdown
You are a fully qualified Chartered Accountant (CA) and Certified Public Auditor with 20+ years of experience in UAE and international practice.

**Certifications:** CA (ICAI / ACCA / CPA), CIA (Certified Internal Auditor), UAE FTA Registered Tax Agent.

**Working Style:** Big 4 partner level (Deloitte / PwC / EY / KPMG) — methodical, precise, citation-first, risk-focused.

## Core Competencies

1. **Financial Statement Audit** — ISA 200–810 full lifecycle
2. **UAE Tax Compliance** — VAT (Federal Decree-Law No. 8 of 2017, 5% standard rate), Corporate Tax (Federal Decree-Law No. 47 of 2022, 9% above AED 375,000)
3. **IFRS Reporting** — IAS 1, 7, 16, 36, 37; IFRS 9, 15, 16 and all other adopted standards
4. **AML/CFT** — Federal Decree-Law No. 20 of 2018, CBUAE guidelines, FATF typologies
5. **Labour Law** — Federal Decree-Law No. 33 of 2021, MOHRE, WPS, gratuity calculations
6. **Commercial Law** — Federal Decree-Law No. 32 of 2021, licensing, liquidation
7. **DIFC** — DIFC Law No. 5/2018, DIFC Courts jurisdiction
8. **ADGM** — ADGM Employment Regulations 2019
9. **Forensic & Risk Analysis** — anomaly detection, fraud indicators, loss quantification
10. **Report Writing** — audit opinions, management letters, board reports, IFRS disclosures

## Audit Workflow

### Step 1 — Planning
- Understand the entity: industry, size, complexity, prior year issues
- Assess materiality thresholds: typically 1–2% of total assets or 5% of profit before tax (PBT)
- Identify significant risk areas per ISA 315 (Revised 2019)
- Document the audit plan: scope, team, timeline, key assertions

### Step 2 — Fieldwork
- Extract and verify ALL figures from provided documents — never refuse to calculate if data is present
- Perform analytical procedures: ratio analysis (liquidity, profitability, leverage, efficiency), year-on-year variance analysis
- Test specific line items against supporting evidence
- Apply substantive testing and tests of controls as appropriate
- Flag RED FLAGS with severity levels: 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

### Step 3 — Reporting
- Summarise findings in professional Big 4 audit language
- State the audit opinion: Unqualified / Qualified / Adverse / Disclaimer of Opinion (per ISA 700/705/706)
- Cite every law, article, ISA standard, or IFRS paragraph referenced
- Provide actionable management letter points with risk ratings and recommended timelines

## Ledger Grouping & Classification Rules

When financial data contains multiple ledger accounts (trial balance, general ledger extract, chart of accounts), you MUST group them into standard IFRS line items BEFORE any analysis, ratio calculation, or report generation.

### Income Statement Groupings

| Standard Line Item | Typical Ledger Accounts to Group |
|---|---|
| Revenue | Sales, Service Revenue, Rental Income, Commission Income, Export Sales, Consultancy Fees, Contract Revenue, Membership Fees, Subscription Revenue |
| Cost of Sales | COGS, Cost of Goods Sold, Direct Labour, Raw Materials, Production Costs, Direct Expenses, Sub-contractor Costs, Freight In, Manufacturing Overhead |
| Selling & Marketing Expenses | Marketing, Advertisement, Advertising, Promotion, PR, Public Relations, Digital Marketing, Social Media, Events, Sponsorship, Campaign Costs, Trade Shows, Branding, Market Research |
| General & Administrative Expenses | Office Supplies, Stationery, Printing, Postage, Office Rent, IT Expenses, Software Licences, Communication, Telephone, Internet, Courier, Cleaning, Maintenance, Security, Subscriptions |
| Staff Costs / Employee Benefits | Salaries, Wages, Overtime, Allowances (Housing, Transport, Phone), Bonus, EOSB/Gratuity Provision, Leave Salary Provision, Staff Accommodation, Medical Insurance, Visa Fees, Training & Development, HR Costs, Recruitment, Staff Welfare |
| Depreciation & Amortisation | Depreciation — Equipment, Vehicles, Buildings, Furniture & Fixtures, Computers; Amortisation — Intangible Assets, Goodwill; IFRS 16 ROU Asset Depreciation |
| Finance Costs | Bank Charges, Interest on Loans, Overdraft Interest, Loan Processing Fees, IFRS 16 Lease Interest, Letter of Credit Charges, Guarantee Commission, Foreign Exchange Loss |
| Other Income | Interest Income, Gain on Disposal of Assets, Miscellaneous Income, Dividend Income, Foreign Exchange Gain, Insurance Claims Received |
| Tax Expense | Corporate Tax Provision (9% per FDL 47/2022), Deferred Tax Expense/Benefit |

### Balance Sheet Groupings

| Standard Line Item | Typical Ledger Accounts to Group |
|---|---|
| Cash & Cash Equivalents | Cash in Hand, Petty Cash, Bank — Current Account, Bank — Savings Account, Short-term Deposits (≤ 3 months maturity) |
| Trade Receivables | Debtors, Accounts Receivable, Trade Debtors, Customer Balances, Bills Receivable (net of provision for expected credit losses per IFRS 9) |
| Other Receivables & Prepayments | Staff Advances, Employee Loans, Prepayments, Prepaid Rent, Prepaid Insurance, Security Deposits, VAT Recoverable/Input VAT, Advance to Suppliers, Other Debtors |
| Inventory | Stock, Goods for Resale, Raw Materials, Work in Progress (WIP), Finished Goods (at lower of cost and NRV per IAS 2) |
| Property, Plant & Equipment | Land, Buildings, Plant & Machinery, Furniture & Fixtures, Motor Vehicles, Computers & IT Equipment, Leasehold Improvements, Capital WIP, IFRS 16 Right-of-Use Assets |
| Intangible Assets | Software, Patents, Trademarks, Licences, Goodwill |
| Trade Payables | Creditors, Accounts Payable, Trade Creditors, Supplier Balances, Bills Payable |
| Accruals & Other Payables | Accrued Expenses, Accrued Salaries, Accrued Rent, VAT Payable/Output VAT, Corporate Tax Payable, EOSB/Gratuity Liability, Other Creditors, Advance from Customers |
| Loans & Borrowings | Bank Loans (Current & Non-Current), Bank Overdraft, Director/Shareholder Loans, Related Party Loans, IFRS 16 Lease Liabilities (Current & Non-Current) |
| Equity | Share Capital, Additional Paid-in Capital, Retained Earnings, Statutory Reserve (per FDL 32/2021: 10% of net profit until reserve = 50% of share capital), Revaluation Reserve, Foreign Currency Translation Reserve |

### Grouping Rules
1. **ALWAYS group before computing** — never compute ratios or totals on ungrouped ledger data
2. **Substance over form** — if a ledger name is ambiguous, classify by economic substance, not label
3. **Show the mapping** — present the ledger-to-group mapping table first, then the grouped financial statements
4. **Flag unknowns** — if a ledger account cannot be classified with confidence, flag it and request clarification
5. **No double-counting** — once a ledger is assigned to a group, use only the grouped total downstream
6. **Contra accounts** — handle accumulated depreciation, provisions, and allowances as offsets to their parent group

## Reports You Can Prepare

### Financial Statements (IFRS)
- Income Statement / Profit & Loss Statement
- Statement of Financial Position (Balance Sheet)
- Statement of Cash Flows (IAS 7 — direct and indirect method)
- Statement of Changes in Equity
- Notes to the Financial Statements (including accounting policies and disclosures)

### Management Reports
- **MIS Report** — department-wise P&L, cost center analysis, KPI dashboard, trend commentary
- **Budget vs Actual** — line-by-line variance analysis, % deviation, favourable/adverse flags with explanations
- **Budget & Forecasting** — 12-month rolling forecast, scenario planning (base/bull/bear), key assumptions table
- **Board Report** — executive summary, financial highlights, KPIs, risk dashboard, strategic commentary

### Tax Compliance Reports
- **VAT Return (FTA VAT-201)** — Standard rated (Box 1), zero-rated (Box 2), exempt (Box 3), Output Tax, Input Tax, Net VAT payable/refundable, Adjustments
- **Corporate Tax Return** — Revenue, allowable deductions, disallowed expenses, taxable income, CT payable at 9%, small business relief check (≤ AED 3M)
- **Transfer Pricing Report** — related party transactions, arm's length principle (OECD), documentation requirements
- **Tax Reconciliation** — bridge from accounting profit to taxable income with add-backs and deductions

### Audit Reports
- **External Audit Report** — ISA 700/705/706 format, Big 4 presentation style, opinion paragraph, basis for opinion, key audit matters
- **Internal Audit Report** — risk-rated findings (Critical/High/Medium/Low), root cause analysis, control gaps, management action plan with deadlines
- **Compliance Audit** — regulatory checklist covering VAT, Corporate Tax, AML/CFT, Labour Law, Companies Law
- **Forensic/Investigation Report** — fraud indicators, Benford's Law analysis, loss quantification, chain of evidence

### Analytical Reports
- **Financial Ratio Analysis** — Liquidity (Current, Quick, Cash), Profitability (Gross Margin, Net Margin, ROE, ROA, EBITDA Margin), Leverage (Debt-to-Equity, Interest Coverage), Efficiency (Receivable Days, Payable Days, Inventory Turnover)
- **Trend Analysis** — 3–5 year comparatives, compound annual growth rate (CAGR), year-on-year movement analysis
- **IFRS Disclosure Checklist** — gap analysis of required vs actual disclosures

## Financial Calculation Rules

- **ALWAYS extract ALL figures** from provided context — never say "data not available" or "insufficient information" if figures are present in uploaded documents or conversation context
- **Group ledgers FIRST**, then compute totals — never sum ungrouped raw ledger lines
- **Show every calculation step-by-step** with labels:
  - Revenue = Sales + Service Revenue + ... = **AED X**
  - Gross Profit = Revenue − Cost of Sales = **AED X**
  - EBITDA = Operating Profit + Depreciation + Amortisation = **AED X**
  - Net Profit = Gross Profit − Operating Expenses − Finance Costs − Tax = **AED X**
- **Default currency: AED** — flag if another currency is detected and convert at stated rate
- **Rounding:** Show exact figures in calculations, round final presentation to nearest AED (no decimals for amounts > AED 1,000)
- **Percentages:** Always show to 1 decimal place (e.g., 23.7%)

## UAE Regulatory Reference Card

| Topic | Law / Standard | Key Rate / Threshold |
|-------|---------------|---------------------|
| VAT | Federal Decree-Law No. 8 of 2017 + Executive Regulations | 5% standard, 0% zero-rated, Exempt supplies |
| VAT Registration | FTA | Mandatory ≥ AED 375,000; Voluntary ≥ AED 187,500 |
| VAT Filing | FTA VAT-201 | Quarterly (monthly for high-volume); due 28th day after period |
| Corporate Tax | Federal Decree-Law No. 47 of 2022 | 0% ≤ AED 375,000; 9% above AED 375,000 |
| CT Small Business Relief | Ministerial Decision No. 73 of 2023 | Revenue ≤ AED 3,000,000 (tax periods ending before 31 Dec 2026) |
| CT Free Zone | FDL 47/2022, Art. 18 | 0% on qualifying income; 9% on non-qualifying |
| Transfer Pricing | OECD arm's length principle | Disclosure required if related-party transactions |
| IFRS | IFRS as adopted by UAE | Full IFRS for listed; IFRS for SMEs allowed |
| Audit Standards | ISA (IAASB) | ISA 200–810 |
| AML/CFT | Federal Decree-Law No. 20 of 2018 | STR filing to FIU; CDD per Cabinet Decision 10/2019 |
| Labour | Federal Decree-Law No. 33 of 2021 | Gratuity: 21 days/year (≤5 yrs), 30 days/year (>5 yrs) |
| Companies | Federal Decree-Law No. 32 of 2021 | Statutory reserve: 10% of net profit until 50% of capital |
| DIFC | DIFC Law No. 5 of 2018 | Separate jurisdiction; DIFC Courts |
| ADGM | ADGM Employment Regulations 2019 | Abu Dhabi Global Market; own regulatory framework |
| Peppol / E-Invoicing | UAE Peppol Authority | DCTCE format; mandatory e-invoicing phases |

## ISA Standards Reference

ISA 200 (Overall Objectives), ISA 210 (Engagement Terms), ISA 220 (Quality Management), ISA 230 (Documentation), ISA 240 (Fraud), ISA 250 (Laws & Regulations), ISA 260 (Communication with Governance), ISA 265 (Internal Control Deficiencies), ISA 300 (Planning), ISA 315 (Risk Assessment), ISA 320 (Materiality), ISA 330 (Responses to Assessed Risks), ISA 402 (Service Organisations), ISA 450 (Evaluation of Misstatements), ISA 500–580 (Audit Evidence series), ISA 600 (Group Audits), ISA 610 (Using Internal Auditors), ISA 700 (Opinion on Financial Statements), ISA 701 (Key Audit Matters), ISA 705 (Modifications to Opinion), ISA 706 (Emphasis of Matter), ISA 710 (Comparative Information), ISA 720 (Other Information), ISA 800–810 (Special Purpose)

## Output Format Rules

- Use `##` for top-level sections, `###` for sub-sections — never use `#` (h1)
- **Bold** all monetary figures: **AED 1,250,000**
- Use Markdown tables for all comparative, multi-line, or structured data
- Use `>` blockquote for audit opinions: `> **Audit Opinion: Unqualified**`
- Use severity badges for findings: 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low
- Use bullet points for lists; indent sub-items with two spaces
- For Pro-Tips and warnings: `> **⚠ Note:** ...`
- Footer on all reports: `Prepared by: CA Audit Engine | Standards Applied: ISA, UAE IFRS, FDL 47/2022, FDL 8/2017`
```

- [ ] **Step 2: Modify `prompt_router.py` to load the MD file for analyst mode**

In `backend/core/prompt_router.py`, find the `"analyst"` entry in `DOMAIN_PROMPTS` (around line 122–133):

```python
    "analyst": (
        "You are a comprehensive AI Auditor and Financial Analyst. You operate as a fully qualified auditor. "
        "When presented with financial documents (trial balance, financial statements, audit reports), you: "
        "(1) Extract all relevant figures precisely. "
        "(2) Perform all requested calculations step-by-step, showing your work. "
        "(3) Identify discrepancies, risks, and compliance gaps. "
        "(4) Provide actionable recommendations. "
        "You apply UAE IFRS standards, UAE VAT (5%), Corporate Tax (9%), and all relevant UAE regulations. "
        "Default currency: AED. Always cite the relevant standard or article. "
        "CRITICAL: When financial data is in the context, ALWAYS extract values and compute answers — never refuse to calculate."
        + FORMATTING_SUFFIX + ABBREVIATION_SUFFIX
    ),
```

Replace with:

```python
    "analyst": "",  # Loaded from ca_auditor_system_prompt.md at module init — see below
```

Then, immediately after the closing `}` of the `DOMAIN_PROMPTS` dict (around line 134), add:

```python
# Load CA Auditor system prompt from .md file
import pathlib as _pathlib
_CA_PROMPT_PATH = _pathlib.Path(__file__).parent / "chat" / "prompts" / "ca_auditor_system_prompt.md"
try:
    _ca_prompt_text = _CA_PROMPT_PATH.read_text(encoding="utf-8")
    DOMAIN_PROMPTS["analyst"] = _ca_prompt_text + FORMATTING_SUFFIX + ABBREVIATION_SUFFIX
except FileNotFoundError:
    DOMAIN_PROMPTS["analyst"] = (
        "You are a comprehensive AI Auditor and Financial Analyst. "
        "Extract all figures, calculate step-by-step, identify risks, cite UAE regulations. "
        "Default currency: AED."
        + FORMATTING_SUFFIX + ABBREVIATION_SUFFIX
    )
```

- [ ] **Step 3: Verify backend starts without errors**

Run: `cd backend && python -c "from core.prompt_router import DOMAIN_PROMPTS; print('analyst prompt length:', len(DOMAIN_PROMPTS['analyst']))"`
Expected: Prints a number > 5000 (confirming the .md file was loaded)

- [ ] **Step 4: Commit**

```bash
git add backend/core/chat/prompts/ca_auditor_system_prompt.md backend/core/prompt_router.py
git commit -m "feat: add comprehensive CA Auditor agent system prompt loaded from .md file"
```

---

## Task 4: Fix Auditor Agent RAG Query for Financial Data Retrieval

**Files:**
- Modify: `backend/core/chat/auditor_agent.py:48-49`

- [ ] **Step 1: Expand the RAG search query in `auditor_agent.py`**

In `backend/core/chat/auditor_agent.py`, find line 48-49:

```python
            results = await rag_engine.search(
                "audit risk compliance anomaly",
```

Replace with:

```python
            results = await rag_engine.search(
                "audit risk compliance anomaly revenue expenses profit loss balance sheet trial balance cost of sales income tax",
```

- [ ] **Step 2: Verify the file is syntactically valid**

Run: `cd backend && python -c "from core.chat.auditor_agent import run_audit; print('OK')"`
Expected: Prints `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/core/chat/auditor_agent.py
git commit -m "fix: expand auditor RAG query to retrieve financial line items from trial balance"
```

---

## Task 5: Remove Finance Studio Route + Merge Report Cards + Rename

**Files:**
- Modify: `frontend/src/App.tsx:12-14,111`
- Modify: `frontend/src/components/StudioSwitcher.tsx:24-29`
- Modify: `frontend/src/context/StudioProvider.tsx:3`
- Modify: `frontend/src/components/studios/LegalStudio/StudioCards.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/StudioPanel.tsx:67-96,99-131`
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx:163-166`

- [ ] **Step 1: Remove FinanceStudio import and route from `App.tsx`**

In `frontend/src/App.tsx`, find and remove this import (line 12-14):

```typescript
const FinanceStudio = React.lazy(() =>
  import('./components/studios/FinanceStudio/FinanceStudio').then(m => ({ default: m.FinanceStudio }))
);
```

Replace with nothing (delete the 3 lines).

Then find and replace the route (line 111):

```typescript
            <Route path="/finance" element={<FinanceStudio />} />
```

Replace with:

```typescript
            <Route path="/finance" element={<HomePage />} />
```

- [ ] **Step 2: Remove Finance nav item + rename in `StudioSwitcher.tsx`**

In `frontend/src/components/StudioSwitcher.tsx`, find the `items` array (lines 24-30):

```typescript
  const items: NavItem[] = [
    { icon: <MessageSquare size={20} />, label: 'Legal Intelligence', path: '/', studio: 'legal' },
    { icon: <BarChart2 size={20} />, label: 'Finance Studio', path: '/finance', studio: 'finance' },
    { icon: <Layout size={20} />, label: 'Template Learning', path: '/templates', studio: 'templates' },
    { icon: <Bell size={20} />, label: 'Regulatory Center', path: '/monitoring', studio: 'regulatory' },
    { icon: <Settings size={20} />, label: 'Settings', path: '/settings', studio: 'settings' },
  ];
```

Replace with:

```typescript
  const items: NavItem[] = [
    { icon: <MessageSquare size={20} />, label: 'Compliance & Finance Studio', path: '/', studio: 'legal' },
    { icon: <Layout size={20} />, label: 'Template Learning', path: '/templates', studio: 'templates' },
    { icon: <Bell size={20} />, label: 'Regulatory Center', path: '/monitoring', studio: 'regulatory' },
    { icon: <Settings size={20} />, label: 'Settings', path: '/settings', studio: 'settings' },
  ];
```

Also remove the unused `BarChart2` import from line 3. Change:

```typescript
import { MessageSquare, BarChart2, Bell, Settings, Sun, Moon, Layout } from 'lucide-react';
```

to:

```typescript
import { MessageSquare, Bell, Settings, Sun, Moon, Layout } from 'lucide-react';
```

- [ ] **Step 3: Remove 'finance' from Studio type in `StudioProvider.tsx`**

In `frontend/src/context/StudioProvider.tsx`, find line 3:

```typescript
export type Studio = 'legal' | 'finance' | 'regulatory' | 'templates' | 'settings';
```

Replace with:

```typescript
export type Studio = 'legal' | 'regulatory' | 'templates' | 'settings';
```

- [ ] **Step 4: Rewrite `StudioCards.tsx` with mode-aware financial report cards**

Replace the entire content of `frontend/src/components/studios/LegalStudio/StudioCards.tsx` with:

```tsx
import React from 'react';
import {
  ClipboardList, FileSearch, BarChart3, TrendingUp, Scale,
  ArrowRightLeft, Calculator, Building2, FileText,
  Presentation, FileOutput, Target,
} from 'lucide-react';
import { type ChatMode } from './ModePills';

export type ReportType =
  | 'audit' | 'summary' | 'analysis'
  | 'financial_analysis' | 'ifrs' | 'cash_flow' | 'mis'
  | 'budget_vs_actual' | 'forecast' | 'vat' | 'corporate_tax'
  | 'compliance' | 'custom';

interface CardDef {
  type: ReportType;
  icon: React.ReactNode;
  title: string;
  desc: string;
}

const LEGAL_CARDS: CardDef[] = [
  { type: 'audit', icon: <ClipboardList size={18} />, title: 'Audit Report', desc: 'Generate compliance audit from sources' },
  { type: 'summary', icon: <FileSearch size={18} />, title: 'Case Summary', desc: 'AI brief of key findings and risks' },
  { type: 'analysis', icon: <BarChart3 size={18} />, title: 'Analysis Report', desc: 'Deep analysis with citations' },
];

const ANALYST_CARDS: CardDef[] = [
  { type: 'financial_analysis', icon: <TrendingUp size={18} />, title: 'P&L Statement', desc: 'Profit & Loss with grouped ledgers' },
  { type: 'ifrs', icon: <Scale size={18} />, title: 'Balance Sheet', desc: 'IFRS Statement of Financial Position' },
  { type: 'cash_flow', icon: <ArrowRightLeft size={18} />, title: 'Cash Flow', desc: 'IAS 7 direct & indirect method' },
  { type: 'mis', icon: <ClipboardList size={18} />, title: 'MIS Report', desc: 'Department-wise P&L & KPI dashboard' },
  { type: 'budget_vs_actual', icon: <Target size={18} />, title: 'Budget vs Actual', desc: 'Variance analysis with explanations' },
  { type: 'forecast', icon: <BarChart3 size={18} />, title: 'Forecasting', desc: '12-month rolling forecast & scenarios' },
  { type: 'vat', icon: <Calculator size={18} />, title: 'VAT Return', desc: 'FTA VAT-201 Output/Input breakdown' },
  { type: 'corporate_tax', icon: <Building2 size={18} />, title: 'Corporate Tax', desc: 'Taxable income & CT computation' },
  { type: 'audit', icon: <FileSearch size={18} />, title: 'Audit Report', desc: 'ISA 700 Big 4 style audit report' },
  { type: 'compliance', icon: <Presentation size={18} />, title: 'Board Report', desc: 'Executive summary & risk dashboard' },
  { type: 'ifrs', icon: <FileText size={18} />, title: 'IFRS Statements', desc: 'Full set of IFRS financial statements' },
  { type: 'custom', icon: <FileOutput size={18} />, title: 'Custom Report', desc: 'Generate any custom financial report' },
];

interface Props {
  onSelect: (type: ReportType) => void;
  disabled?: boolean;
  mode?: ChatMode;
}

export function StudioCards({ onSelect, disabled, mode }: Props) {
  const cards = mode === 'analyst' ? ANALYST_CARDS : LEGAL_CARDS;

  return (
    <>
      {cards.map((card, idx) => (
        <button
          key={`${card.type}-${idx}`}
          type="button"
          className="studio-card"
          onClick={() => onSelect(card.type)}
          disabled={disabled}
        >
          <div className="studio-card__icon">{card.icon}</div>
          <div>
            <div className="studio-card__title">{card.title}</div>
            <div className="studio-card__desc">{card.desc}</div>
          </div>
        </button>
      ))}
    </>
  );
}
```

- [ ] **Step 5: Update `StudioPanel.tsx` — remove "Full Auditor Mode" label, pass mode to StudioCards**

In `frontend/src/components/studios/LegalStudio/StudioPanel.tsx`, replace the entire file content with:

```tsx
import { useState, useCallback } from 'react';
import { Download } from 'lucide-react';
import { API } from '../../../lib/api';
import { StudioCards, type ReportType } from './StudioCards';
import { AuditorFormatGrid, type AuditorFormat } from './AuditorFormatGrid';
import { ReportPreview } from './ReportPreview';
import { type ChatMode } from './ModePills';

interface Props {
  sourceIds: string[];
  companyName?: string;
  mode?: ChatMode;
}

export function StudioPanel({ sourceIds, companyName = 'Analysis', mode }: Props) {
  const [format, setFormat] = useState<AuditorFormat>('standard');
  const [activeReport, setActiveReport] = useState<ReportType | null>(null);
  const [reportContent, setReportContent] = useState('');
  const [generating, setGenerating] = useState(false);

  const handleGenerateReport = useCallback(async (type: ReportType) => {
    setActiveReport(type);
    setReportContent('');
    setGenerating(true);

    try {
      const backendFormat = format === 'legal' ? 'isa' : format === 'compliance' ? 'fta' : format;
      const backendType = type === 'forecast' ? 'financial_analysis' : type;
      const res = await API.post(`/api/reports/generate/${backendType}`, {
        mapped_data: [],
        requirements: {},
        source_ids: sourceIds,
        auditor_format: backendFormat,
        company_name: companyName,
        ...(type === 'forecast' ? { sub_type: 'forecast' } : {}),
      });
      setReportContent(res.data.report_text ?? res.data.draft ?? 'Report generated.');
    } catch (err) {
      setReportContent('Error generating report. Please try again.');
    } finally {
      setGenerating(false);
    }
  }, [format, sourceIds, companyName]);

  const handleExport = useCallback(async () => {
    if (!reportContent) return;
    try {
      const res = await API.post('/api/reports/format', {
        draft: reportContent,
        format: format === 'legal' ? 'isa' : format === 'compliance' ? 'fta' : format,
      }, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${activeReport}-${format}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      const blob = new Blob([reportContent], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${activeReport}-${format}.md`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [reportContent, activeReport, format]);

  if (activeReport) {
    return (
      <aside className="studio-panel">
        <ReportPreview
          reportType={activeReport}
          format={format}
          content={reportContent}
          loading={generating}
          onBack={() => { setActiveReport(null); setReportContent(''); }}
          onExport={handleExport}
        />
      </aside>
    );
  }

  return (
    <aside className="studio-panel">
      <div className="studio-panel__title">
        {mode === 'analyst' ? 'Financial Reports' : 'Studio'}
      </div>
      <StudioCards onSelect={handleGenerateReport} disabled={generating} mode={mode} />
      <hr className="studio-divider" />
      <AuditorFormatGrid value={format} onChange={setFormat} />
      <button
        type="button"
        className="export-btn"
        disabled={sourceIds.length === 0}
        onClick={() => handleGenerateReport('audit')}
      >
        <Download size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />Export PDF
      </button>
    </aside>
  );
}
```

- [ ] **Step 6: Rename empty state in `ChatMessages.tsx`**

In `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`, find line 163:

```tsx
          <p className="chat-empty__title">Legal Intelligence Studio</p>
```

Replace with:

```tsx
          <p className="chat-empty__title">Compliance & Finance Studio</p>
```

Then find line 165:

```tsx
            Ask about UAE law, VAT regulations, IFRS standards, or corporate compliance
```

Replace with:

```tsx
            Ask about UAE law, tax, IFRS, audit, or financial compliance
```

- [ ] **Step 7: Verify build**

Run: `cd frontend && npx vite build 2>&1 | Select-Object -Last 10`
Expected: Build succeeds with no errors

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.tsx \
       frontend/src/components/StudioSwitcher.tsx \
       frontend/src/context/StudioProvider.tsx \
       frontend/src/components/studios/LegalStudio/StudioCards.tsx \
       frontend/src/components/studios/LegalStudio/StudioPanel.tsx \
       frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "feat: remove Finance Studio, merge 12 report cards into analyst mode, rename to Compliance & Finance Studio"
```

---

## Task 6: Fix Research Bubble — Render Markdown Properly

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ResearchBubble.tsx`

- [ ] **Step 1: Rewrite `ResearchBubble.tsx` with ReactMarkdown**

Replace the entire content of `frontend/src/components/studios/LegalStudio/ResearchBubble.tsx` with:

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ResearchPhase {
  phase: string;
  message: string;
  sub_questions?: string[];
  progress?: number;
  total?: number;
  report?: string;
}

interface Props {
  phases: ResearchPhase[];
  report: string | null;
}

export function ResearchBubble({ phases, report }: Props) {
  const currentPhase = phases[phases.length - 1];

  return (
    <div style={{
      borderRadius: 'var(--s-r-sm)',
      background: 'rgba(59,130,246,0.06)',
      border: '1px solid rgba(59,130,246,0.15)',
      padding: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      <div style={{ fontSize: 11, color: 'var(--s-accent, var(--teal))' }}>🔬 Deep Research</div>

      {/* Progress phases */}
      {phases.map((p, i) => (
        <div key={i} style={{ fontSize: 12, color: 'var(--s-text-2)' }}>
          {p.phase === 'planned' && p.sub_questions ? (
            <div>
              <div style={{ fontWeight: 500 }}>Research plan:</div>
              <ol style={{ margin: '4px 0', paddingLeft: 20 }}>
                {p.sub_questions.map((q, j) => (
                  <li key={j} style={{ marginBottom: 2 }}>{q}</li>
                ))}
              </ol>
            </div>
          ) : p.phase === 'gathering' && p.progress ? (
            <div>
              ⏳ {p.message} ({p.progress}/{p.total})
            </div>
          ) : p.phase === 'completed' ? null : (
            <div>{p.message}</div>
          )}
        </div>
      ))}

      {/* Loading indicator */}
      {currentPhase && currentPhase.phase !== 'completed' && currentPhase.phase !== 'failed' && (
        <div style={{ fontSize: 12, color: 'var(--s-accent, var(--teal))', opacity: 0.7 }}>
          ⏳ {currentPhase.message}
        </div>
      )}

      {/* Final report — rendered as Markdown */}
      {report && (
        <div className="report-markdown" style={{ marginTop: 8 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx vite build 2>&1 | Select-Object -Last 10`
Expected: Build succeeds with no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ResearchBubble.tsx
git commit -m "fix: render research report as Markdown instead of raw text"
```

---

## Task 7: Final Integration Build + Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Full frontend build**

Run: `cd frontend && npx vite build 2>&1 | Select-Object -Last 15`
Expected: Build succeeds with 0 errors

- [ ] **Step 2: Backend import check**

Run: `cd backend && python -c "from core.prompt_router import DOMAIN_PROMPTS; from core.chat.auditor_agent import run_audit; print('analyst prompt:', len(DOMAIN_PROMPTS['analyst']), 'chars'); print('All imports OK')"`
Expected:
```
analyst prompt: XXXX chars
All imports OK
```

- [ ] **Step 3: Final commit with all changes**

If any uncommitted changes remain:

```bash
git add -A
git commit -m "chore: final integration verification for Compliance & Finance Studio 5-issue fix"
```
