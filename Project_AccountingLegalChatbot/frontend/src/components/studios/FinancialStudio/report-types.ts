import type { ComponentType } from 'react';
import {
  FileText, Receipt, Building2, ShieldCheck,
  BarChart3, TrendingUp, Scale, Landmark, ArrowLeftRight,
  FileQuestion,
} from 'lucide-react';

export interface SelectOption { value: string; label: string; }

export interface ReportTypeConfig {
  key: string;
  label: string;
  category: string;
  description: string;
  icon: ComponentType<{ size?: number }>;
  uploadLabel: string;
  mapperFields: string[];
  reportFields: Array<{ key: string; label: string; type?: string; options?: SelectOption[] }>;
}

export const AUDIT_FIELDS = [
  'Current Assets', 'Non-Current Assets', 'Current Liabilities',
  'Non-Current Liabilities', 'Equity', 'Revenue', 'Cost of Sales',
  'Operating Expenses', 'Input VAT', 'Output VAT',
  'Cash and Cash Equivalents', 'Retained Earnings',
];
export const VAT_FIELDS = [
  'Standard Rated Sales', 'Zero Rated Sales', 'Exempt Sales',
  'Output Tax', 'Standard Rated Purchases', 'Input Tax',
  'Reverse Charge', 'Adjustments',
];
export const CORP_TAX_FIELDS = [
  'Gross Revenue', 'Operating Expenses', 'Depreciation',
  'Interest Income', 'Interest Expense', 'Exempt Income',
  'Disallowed Expenses', 'Prior Year Losses',
];
export const MIS_FIELDS = [
  'Revenue', 'Cost of Sales', 'Gross Profit', 'Operating Expenses',
  'EBITDA', 'Net Profit', 'Cash Position', 'Trade Receivables',
];
export const IFRS_FIELDS = [
  'Current Assets', 'Non-Current Assets', 'Current Liabilities',
  'Non-Current Liabilities', 'Equity', 'Revenue', 'Cost of Sales',
  'Operating Expenses', 'Finance Costs', 'Tax Expense',
  'Cash and Cash Equivalents', 'Retained Earnings', 'Share Capital',
];
export const CASH_FLOW_FIELDS = [
  'Operating Activities', 'Investing Activities', 'Financing Activities',
  'Opening Balance', 'Closing Balance',
];
export const BUDGET_FIELDS = [
  'Budgeted Revenue', 'Actual Revenue', 'Budgeted Expenses',
  'Actual Expenses', 'Capital Budget', 'Actual Capital',
];
export const COMPLIANCE_FIELDS = [
  'Revenue', 'Operating Expenses', 'Tax Paid',
  'Regulatory Fees', 'Penalties', 'Interest on Late Payment',
];
export const FINANCIAL_ANALYSIS_FIELDS = [
  'Current Assets', 'Current Liabilities', 'Total Assets',
  'Total Liabilities', 'Revenue', 'Net Profit', 'Equity', 'Operating Cash Flow',
];

export const REPORT_TYPE_CONFIG: ReportTypeConfig[] = [
  {
    key: 'audit', label: 'Audit Report', category: 'Tax & Compliance',
    description: 'Full audit with findings, risk flags, and management letter',
    icon: FileText,
    uploadLabel: 'Upload Trial Balance',
    mapperFields: AUDIT_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'auditor_name', label: 'Auditor Name' },
      { key: 'period_end', label: 'Period End Date', type: 'date' },
    ],
  },
  {
    key: 'vat', label: 'VAT Return', category: 'Tax & Compliance',
    description: 'UAE VAT return with FTA-ready commentary and calculations',
    icon: Receipt,
    uploadLabel: 'Upload VAT Return Data',
    mapperFields: VAT_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'trn', label: 'Tax Registration Number (TRN)' },
      { key: 'period', label: 'VAT Return Period' },
    ],
  },
  {
    key: 'corporate_tax', label: 'Corporate Tax', category: 'Tax & Compliance',
    description: 'UAE Corporate Tax computation per Decree-Law No. 47',
    icon: Building2,
    uploadLabel: 'Upload Corporate Tax Data',
    mapperFields: CORP_TAX_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'trn', label: 'Tax Registration Number (TRN)' },
      { key: 'tax_period', label: 'Tax Period (e.g. 2024)' },
    ],
  },
  {
    key: 'compliance', label: 'Compliance Report', category: 'Tax & Compliance',
    description: 'Regulatory compliance checklist with findings and references',
    icon: ShieldCheck,
    uploadLabel: 'Upload Compliance Data',
    mapperFields: COMPLIANCE_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'period', label: 'Review Period' },
      { key: 'regulatory_body', label: 'Regulatory Body' },
    ],
  },
  {
    key: 'mis', label: 'MIS Report', category: 'Management',
    description: 'Executive summary, KPIs, trend analysis, and commentary',
    icon: BarChart3,
    uploadLabel: 'Upload Management Data',
    mapperFields: MIS_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'period', label: 'Reporting Period' },
      { key: 'prepared_by', label: 'Prepared By' },
    ],
  },
  {
    key: 'financial_analysis', label: 'Financial Analysis', category: 'Management',
    description: 'Ratio analysis: liquidity, profitability, leverage, with narrative',
    icon: TrendingUp,
    uploadLabel: 'Upload Financial Statements',
    mapperFields: FINANCIAL_ANALYSIS_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'period', label: 'Analysis Period' },
      { key: 'industry', label: 'Industry / Sector' },
    ],
  },
  {
    key: 'budget_vs_actual', label: 'Budget vs Actual', category: 'Management',
    description: 'Variance analysis highlighting over/under-budget items',
    icon: Scale,
    uploadLabel: 'Upload Budget vs Actual Data',
    mapperFields: BUDGET_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'period', label: 'Budget Period' },
    ],
  },
  {
    key: 'ifrs', label: 'IFRS Financial Statements', category: 'Statutory',
    description: 'Full IFRS-compliant financial statements with notes',
    icon: Landmark,
    uploadLabel: 'Upload Trial Balance',
    mapperFields: IFRS_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'period_end', label: 'Period End Date', type: 'date' },
      { key: 'functional_currency', label: 'Functional Currency' },
    ],
  },
  {
    key: 'cash_flow', label: 'Cash Flow Statement', category: 'Statutory',
    description: 'Direct or indirect method cash flow per IFRS',
    icon: ArrowLeftRight,
    uploadLabel: 'Upload Cash Flow Data',
    mapperFields: CASH_FLOW_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'period', label: 'Period' },
      { key: 'method', label: 'Method (Direct / Indirect)' },
    ],
  },
  {
    key: 'custom', label: 'Custom Report', category: 'Other',
    description: 'Freestyle analysis — map any columns, describe what you need',
    icon: FileQuestion,
    uploadLabel: 'Upload Your Data File',
    mapperFields: AUDIT_FIELDS,
    reportFields: [
      { key: 'company_name', label: 'Company Name' },
      { key: 'report_title', label: 'Report Title' },
      { key: 'instructions', label: 'Instructions for AI' },
      { key: 'auditor_format', label: 'Output Format', type: 'select', options: [
        { value: 'standard', label: 'Standard' },
        { value: 'custom', label: 'Custom Template' },
      ]},
      { key: 'custom_format_file', label: 'Custom Format Template', type: 'file' },
    ],
  },
];
