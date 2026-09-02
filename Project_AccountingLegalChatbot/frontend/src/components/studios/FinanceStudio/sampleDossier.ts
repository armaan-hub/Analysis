/**
 * Pre-configured realistic sample dossier for UAE Mainland Audit Report Generation.
 * Entity: Al-Noor Horizon General Trading LLC (Dubai DET Mainland)
 */

export const SAMPLE_DOC1_BALANCE_SHEET = `# TRIAL BALANCE & BALANCE SHEET SCHEDULE (2025 vs 2024)
Entity: Al-Noor Horizon General Trading LLC
Currency: Arab Emirates Dirham (AED)

| Account Code | Account Description | 31 Dec 2025 (AED) | 31 Dec 2024 (AED) |
| :--- | :--- | :--- | :--- |
| **ASSETS** | | | |
| **Non-Current Assets** | | | |
| 1101 | Leasehold Improvements & Office Fitouts | 480,000 | 320,000 |
| 1102 | Motor Vehicles & Delivery Vans | 350,000 | 350,000 |
| 1103 | Office Furniture & IT Equipment | 215,000 | 185,000 |
| 1109 | Accumulated Depreciation - PPE | (325,000) | (210,000) |
| 1201 | Right-of-Use Asset (Office Lease) | 410,000 | 560,000 |
| **Total Non-Current Assets** | | **1,130,000** | **1,205,000** |
| | | | |
| **Current Assets** | | | |
| 1301 | Inventories - Finished Goods for Trading | 1,840,000 | 1,420,000 |
| 1401 | Trade Accounts Receivable | 2,750,000 | 2,180,000 |
| 1409 | Allowance for Expected Credit Losses (ECL) | (85,000) | (55,000) |
| 1501 | Prepayments & Advance Payments to Suppliers | 320,000 | 240,000 |
| 1502 | Refundable Security Deposits & VAT Input Receivable | 95,000 | 75,000 |
| 1601 | Cash at Bank - Current Accounts (Emirates NBD / ADCB) | 1,460,000 | 980,000 |
| 1602 | Petty Cash on Hand | 25,000 | 15,000 |
| **Total Current Assets** | | **6,405,000** | **4,855,000** |
| **TOTAL ASSETS** | | **7,535,000** | **6,060,000** |
| | | | |
| **EQUITY & LIABILITIES** | | | |
| **Equity** | | | |
| 2001 | Paid-up Share Capital (300 shares @ AED 1,000) | 300,000 | 300,000 |
| 2002 | Statutory Reserve (10% of annual net profit) | 150,000 | 100,000 |
| 2003 | Retained Earnings / (Accumulated Losses) | 3,195,000 | 2,245,000 |
| **Total Equity** | | **3,645,000** | **2,645,000** |
| | | | |
| **Non-Current Liabilities** | | | |
| 2201 | Lease Liabilities - Non-Current Portion | 220,000 | 380,000 |
| 2202 | Provision for Employees' End of Service Benefits (EOSB) | 365,000 | 280,000 |
| **Total Non-Current Liabilities** | | **585,000** | **660,000** |
| | | | |
| **Current Liabilities** | | | |
| 2301 | Trade Accounts Payable | 1,890,000 | 1,620,000 |
| 2302 | Accrued Expenses & Other Current Payables | 435,000 | 315,000 |
| 2303 | Lease Liabilities - Current Portion | 190,000 | 180,000 |
| 2304 | VAT Output Payable (Federal Tax Authority) | 125,000 | 95,000 |
| 2305 | Provision for UAE Corporate Tax (9% CT Law No. 47) | 85,000 | 45,000 |
| 2401 | Due to Related Parties / Directors Current Account | 580,000 | 500,000 |
| **Total Current Liabilities** | | **3,305,000** | **2,755,000** |
| **TOTAL LIABILITIES** | | **3,890,000** | **3,415,000** |
| **TOTAL EQUITY AND LIABILITIES** | | **7,535,000** | **6,060,000** |
`;

export const SAMPLE_DOC2_PROFIT_LOSS = `# STATEMENT OF PROFIT OR LOSS AND OTHER COMPREHENSIVE INCOME
Entity: Al-Noor Horizon General Trading LLC
Period: For the Year Ended 31 December 2025 (with 2024 Comparatives)
Currency: Arab Emirates Dirham (AED)

| Statement Line Item | Financial Year 2025 (AED) | Financial Year 2024 (AED) |
| :--- | :--- | :--- |
| **Revenue from Contracts with Customers** | 12,450,000 | 9,800,000 |
| **Cost of Sales / Direct Trading Costs** | (8,100,000) | (6,500,000) |
| **GROSS PROFIT** | **4,350,000** | **3,300,000** |
| | | |
| General, Administrative & Staff Expenses | (2,120,000) | (1,680,000) |
| Selling, Marketing & Distribution Expenses | (680,000) | (520,000) |
| Depreciation of Property, Plant and Equipment | (115,000) | (95,000) |
| Amortization of Right-of-Use Lease Assets | (150,000) | (150,000) |
| Provision for Expected Credit Losses (ECL) on Receivables | (30,000) | (20,000) |
| Other Operating Income (Rental rebates & discounts) | 45,000 | 25,000 |
| **OPERATING PROFIT (EBIT)** | **1,300,000** | **860,000** |
| | | |
| Finance Costs (Bank charges & lease interest expense) | (65,000) | (50,000) |
| **PROFIT BEFORE TAX** | **1,235,000** | **810,000** |
| | | |
| UAE Corporate Tax Expense (Federal Decree-Law No. 47) | (85,000) | (45,000) |
| **PROFIT FOR THE YEAR AFTER TAX** | **1,150,000** | **765,000** |
| Other Comprehensive Income | - | - |
| **TOTAL COMPREHENSIVE INCOME FOR THE YEAR** | **1,150,000** | **765,000** |

### Supplementary Movement Notes:
- Statutory Reserve transfer: 10% of profit after tax (AED 50,000 in 2025, AED 50,000 in 2024) until reserve reached 50% of paid-up capital.
- Dividends distributed to partners during 2025: AED 150,000 (2024: AED 100,000).
`;

export const SAMPLE_DOC3_CORPORATE_LEGAL = `# COMMERCIAL TRADE LICENSE & MEMORANDUM OF ASSOCIATION (MOA)

## 1. Commercial License Details
- **Issuing Authority**: Government of Dubai — Department of Economy and Tourism (DET) / Commercial Registration Division
- **License Number**: 849201
- **Commercial Register Number**: 142088
- **Legal Form**: Limited Liability Company (LLC) (ذ.م.م)
- **Company Name (English)**: Al-Noor Horizon General Trading LLC
- **Company Name (Arabic)**: شركة الأفق للنور للتجارة العامة ذ.م.م
- **Date of Incorporation**: 14 March 2020
- **License Issue Date**: 14 March 2020
- **License Expiry Date**: 13 March 2026
- **Registered Office & Address**: Office 1402, Al-Moosa Tower 1, Sheikh Zayed Road, Trade Centre First, Dubai, United Arab Emirates
- **P.O. Box**: 88312, Dubai, UAE
- **Telephone / Contact**: +971 4 388 9120 | info@alnoor-horizon.ae

## 2. Shareholding Structure & Capitalization (per MOA and Amendments)
- **Total Authorized & Paid-up Capital**: AED 300,000 (Three Hundred Thousand UAE Dirhams)
- **Total Shares**: 300 shares of nominal value AED 1,000 each.

| Partner / Shareholder Name | Nationality | Legal Capacity | Shares Count | Share Percentage (%) | Capital Value (AED) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Mr. Tariq Mansoor Al-Falasi** | United Arab Emirates | Partner & Managing Director | 153 | 51.00% | AED 153,000 |
| **Ms. Elena Rostova** | Republic of Cyprus | Partner & Commercial Director | 147 | 49.00% | AED 147,000 |
| **TOTAL** | | | **300** | **100.00%** | **AED 300,000** |

## 3. Management & Representation Powers
- **General Manager / Managing Director**: Mr. Tariq Mansoor Al-Falasi (Emirati National)
- **Powers & Authority Granted**: Full administrative, operational, legal, and financial authority to represent the company before all UAE ministries, banks, civil courts, customs authorities, and arbitration tribunals; full authority to execute commercial contracts, open and operate corporate bank accounts, issue powers of attorney, and sign audited financial statements.

## 4. Licensed Commercial Activities
1. **General Trading** (Activity Code: 469001)
2. **Wholesale & Import of Industrial Machinery & Spare Parts** (Activity Code: 465902)
3. **Electronic & Telecommunication Equipment Trading** (Activity Code: 465201)
4. **Consumer Goods & Packaged Household Products Trading** (Activity Code: 463004)

## 5. Auditor Appointment & Reporting
- **Statutory Auditors**: Independent Licensed Audit Firm under UAE Federal Decree-Law No. 32 of 2021 on Commercial Companies.
- **Reporting Framework**: International Financial Reporting Standards (IFRS) as issued by the IASB.
`;

export const SAMPLE_DOC4_TEMPLATE_NOTES = `# TARGET AUDIT TEMPLATE: "COMPARATIVE MAINLAND" SPECIFICATION
Target Framework: IFRS Accounting Standards & UAE Commercial Companies Law (Federal Decree-Law No. 32 of 2021)

Mandatory Output Sections:
1. Cover Page & Corporate Information Directory
2. Independent Auditor's Report (Unqualified Clean Opinion)
3. Statement of Financial Position (SOFP) — 2025 (Col 1) / 2024 (Col 2)
4. Statement of Profit or Loss and Other Comprehensive Income (SOPL) — 2025 / 2024
5. Statement of Changes in Equity (SOCE) — 2025 / 2024
6. Statement of Cash Flows (CFS) — 2025 / 2024 (Indirect Method)
7. Notes to the Financial Statements (Notes 1 to 15):
   - Note 1: Legal Status & Commercial Activities
   - Note 2: Basis of Preparation & Statement of Compliance (IFRS)
   - Note 3: Significant Accounting Policies (Revenue, Leases, PPE, Taxes)
   - Note 4: Property, Plant and Equipment Schedule
   - Note 5: Right-of-Use Assets & Lease Liabilities
   - Note 6: Inventories
   - Note 7: Trade and Other Receivables & ECL
   - Note 8: Cash and Cash Equivalents
   - Note 9: Share Capital & Legal / Statutory Reserve
   - Note 10: Employees' End of Service Benefits (EOSB)
   - Note 11: Trade and Other Payables
   - Note 12: Related Party Transactions & Balances
   - Note 13: Revenue & Segmental Performance
   - Note 14: UAE Corporate Tax Computation
   - Note 15: Financial Instruments, Risk Management & Contingencies

Formatting & Rule Constraints:
- Chronology: Present 2025 first, 2024 second in all tables.
- Zero Notation: Use '-' for zero or nil balances.
- Balance Sheet Tie-Out: Total Assets must equal Total Liabilities and Equity.
`;
