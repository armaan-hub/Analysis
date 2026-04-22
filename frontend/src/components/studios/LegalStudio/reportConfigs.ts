import type { PrefilledField } from './QuestionnaireMessage';
import type { AuditorFormat } from './AuditorFormatGrid';

export interface ReportSection {
  id: string;
  label: string;
  type: 'kpi_cards' | 'chart' | 'table' | 'narrative' | 'regulatory_form' | 'signature_block';
  extractionPrompt: string;
  required: boolean;
}

export interface ReportConfig {
  type: string;
  label: string;
  icon: string;
  fields: PrefilledField[];
  sections?: ReportSection[];
  supportedFormats?: AuditorFormat[];
  detectFields?: string[];
  regulatoryNote?: string;
  chartTypes?: string[];
  category?: 'financial' | 'regulatory' | 'audit' | 'custom';
  audience?: string;
  purpose?: string;
  keyPoints?: string[];
}

const currentYear = new Date().getFullYear();
const todayISO = new Date().toISOString().split('T')[0];

export const REPORT_CONFIGS: Record<string, ReportConfig> = {
  // ── Analyst-mode cards ────────────────────────────────────────────
  'financial_analysis': {
    type: 'financial_analysis',
    label: 'Profit & Loss Statement',
    icon: '📈',
    category: 'financial',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: ['bar', 'line'],
    supportedFormats: ['standard', 'big4'],
    sections: [
      { id: 'pnl', label: 'P&L Statement', type: 'table',
        extractionPrompt: 'Extract revenue, expenses, net profit', required: true },
      { id: 'narrative', label: 'Narrative Analysis', type: 'narrative',
        extractionPrompt: 'Provide ratio analysis and commentary', required: false },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'currency', label: 'Currency', value: 'USD', editable: true },
      { key: 'comparative', label: 'Comparative Period', value: 'Previous Year', editable: true },
    ],
    audience: 'CFO, Management, Investors',
    purpose: 'Analyse financial performance, trends, and ratios',
    keyPoints: [
      'Profitability ratios (ROE, ROA, margins)',
      'Liquidity ratios',
      'Leverage and solvency',
      'Efficiency ratios',
      'Period-over-period trends',
      'Benchmarking vs industry',
    ],
  },
  'ifrs': {
    type: 'ifrs',
    label: 'Balance Sheet (IFRS)',
    icon: '📊',
    category: 'financial',
    detectFields: ['entity_name', 'as_of_date'],
    chartTypes: [],
    supportedFormats: ['standard', 'big4'],
    sections: [
      { id: 'sfp', label: 'Statement of Financial Position', type: 'table',
        extractionPrompt: 'Extract assets, liabilities, equity for balance sheet', required: true },
      { id: 'pnl', label: 'P&L Statement', type: 'table',
        extractionPrompt: 'Extract revenue, expenses, net profit', required: true },
      { id: 'cashflow', label: 'Cash Flow Statement', type: 'table',
        extractionPrompt: 'Extract operating, investing, financing activities', required: true },
      { id: 'notes', label: 'Notes to Financial Statements', type: 'narrative',
        extractionPrompt: 'IFRS accounting policies and significant estimates', required: false },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'as_of_date', label: 'As of Date', value: todayISO, editable: true },
      { key: 'currency', label: 'Currency', value: 'USD', editable: true },
    ],
  },
  'cash_flow': {
    type: 'cash_flow',
    label: 'Cash Flow Statement',
    icon: '💰',
    category: 'financial',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: ['bar'],
    supportedFormats: ['standard', 'big4'],
    sections: [
      { id: 'cashflow', label: 'Cash Flow Statement', type: 'table',
        extractionPrompt: 'Extract operating, investing, financing cash flows', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'method', label: 'Method', value: 'Indirect', editable: true },
    ],
  },
  'mis': {
    type: 'mis',
    label: 'MIS Report',
    icon: '📋',
    category: 'financial',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: ['bar', 'line'],
    supportedFormats: ['standard', 'big4'],
    sections: [
      { id: 'kpi', label: 'KPI Cards', type: 'kpi_cards',
        extractionPrompt: 'Extract Revenue, Expenses, Net Profit, Gross Margin from documents', required: true },
      { id: 'chart', label: 'Revenue vs Expenses Chart', type: 'chart',
        extractionPrompt: 'Extract revenue and expenses by period for chart data', required: true },
      { id: 'pl_table', label: 'Department P&L Table', type: 'table',
        extractionPrompt: 'Extract department-level P&L figures from documents', required: false },
      { id: 'narrative', label: 'Narrative Summary', type: 'narrative',
        extractionPrompt: 'Write a 2-paragraph summary of financial performance citing sources', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'departments', label: 'Departments', value: 'All', editable: true },
    ],
    audience: 'Management, CFO, Board',
    purpose: 'Provide management with key operational and financial metrics for decision-making',
    keyPoints: [
      'Revenue vs Budget variance',
      'Cost centre analysis',
      'Cash position',
      'KPI performance',
      'Rolling forecast',
      'Action items',
    ],
  },
  'budget_vs_actual': {
    type: 'budget_vs_actual',
    label: 'Budget vs Actual',
    icon: '🎯',
    category: 'financial',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: ['bar'],
    supportedFormats: ['standard', 'big4'],
    sections: [
      { id: 'variance', label: 'Budget vs Actual Variance', type: 'table',
        extractionPrompt: 'Extract budget and actual figures and variance %', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'currency', label: 'Currency', value: 'USD', editable: true },
    ],
  },
  'forecast': {
    type: 'forecast',
    label: 'Financial Forecast',
    icon: '📈',
    category: 'financial',
    detectFields: ['entity_name'],
    chartTypes: ['line'],
    supportedFormats: ['standard'],
    sections: [
      { id: 'forecast_table', label: 'Forecast Table', type: 'table',
        extractionPrompt: 'Extract historical data and project forward', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Forecast Period', value: '12 months', editable: true },
      { key: 'base_year', label: 'Base Year', value: currentYear.toString(), editable: true },
    ],
  },
  'vat': {
    type: 'vat',
    label: 'VAT Return',
    icon: '🧮',
    category: 'regulatory',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'compliance'],
    regulatoryNote: 'Based on UAE FTA VAT-201 form structure',
    sections: [
      { id: 'vat_form', label: 'VAT-201 Return', type: 'regulatory_form',
        extractionPrompt: 'Extract values for VAT-201 Boxes 1–9 from accounting documents', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'trn', label: 'TRN', value: '', editable: true },
      { key: 'tax_period', label: 'Tax Period', value: `Q${Math.ceil((new Date().getMonth() + 1) / 3)} ${currentYear}`, editable: true },
    ],
    audience: 'UAE Federal Tax Authority (FTA)',
    purpose: 'Report VAT obligations for the tax period',
    keyPoints: [
      'Total taxable supplies',
      'Standard-rated supplies (5%)',
      'Zero-rated supplies',
      'Exempt supplies',
      'Input VAT recoverable',
      'Net VAT payable/refundable',
      'Adjustments from prior periods',
    ],
  },
  'corporate_tax': {
    type: 'corporate_tax',
    label: 'Corporate Tax Computation',
    icon: '🏢',
    category: 'regulatory',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'compliance'],
    regulatoryNote: 'Based on UAE CT Decree-Law No. 47 of 2022',
    sections: [
      { id: 'ct_computation', label: 'CT Computation', type: 'table',
        extractionPrompt: 'Extract accounting profit, adjustments, exempt income, CT payable', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'tax_year', label: 'Tax Year', value: currentYear.toString(), editable: true },
      { key: 'jurisdiction', label: 'Jurisdiction', value: 'UAE', editable: true },
    ],
  },
  'audit': {
    type: 'audit',
    label: 'Audit Report',
    icon: '📝',
    category: 'audit',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'big4', 'legal', 'compliance'],
    regulatoryNote: 'Based on ISA 700 Big 4 structure',
    sections: [
      { id: 'opinion', label: "Independent Auditor's Report", type: 'narrative',
        extractionPrompt: 'Generate ISA 700 opinion paragraph', required: true },
      { id: 'basis', label: 'Basis for Opinion', type: 'narrative',
        extractionPrompt: 'State standards applied and evidence obtained', required: true },
      { id: 'kam', label: 'Key Audit Matters', type: 'narrative',
        extractionPrompt: 'Identify key audit matters from document contents', required: false },
      { id: 'responsibilities', label: 'Responsibilities', type: 'narrative',
        extractionPrompt: 'Management vs auditor responsibilities per ISA 700.33', required: true },
      { id: 'signature', label: 'Signature Block', type: 'signature_block',
        extractionPrompt: 'Firm name, date, location — auto-detect or leave editable', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period_end', label: 'Period End', value: todayISO, editable: true },
    ],
    audience: 'Board of Directors, Shareholders, Regulators',
    purpose: 'Express an independent opinion on the financial statements',
    keyPoints: [
      "Auditor's opinion (clean/qualified/adverse/disclaimer)",
      'Key Audit Matters',
      'Going concern assessment',
      'Internal control weaknesses',
      'Material misstatements found',
      'Subsequent events',
    ],
  },
  'compliance': {
    type: 'compliance',
    label: 'Board / Compliance Report',
    icon: '📊',
    category: 'regulatory',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'compliance'],
    sections: [
      { id: 'compliance_summary', label: 'Compliance Summary', type: 'narrative',
        extractionPrompt: 'Executive summary of regulatory compliance status', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'jurisdiction', label: 'Jurisdiction', value: 'UAE', editable: true },
    ],
    audience: 'Compliance Officer, Regulators, Board',
    purpose: 'Document compliance status with applicable regulations',
    keyPoints: [
      'Regulatory framework coverage',
      'Compliance gaps identified',
      'Risk ratings',
      'Control effectiveness',
      'Remediation actions',
      'Compliance officer sign-off',
    ],
  },
  'custom': {
    type: 'custom',
    label: 'Custom Report',
    icon: '📄',
    category: 'custom',
    detectFields: ['entity_name'],
    chartTypes: [],
    supportedFormats: ['standard', 'big4', 'legal', 'compliance', 'custom'],
    sections: [],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'report_title', label: 'Report Title', value: '', editable: true },
      { key: 'instructions', label: 'Instructions', value: '', editable: true },
    ],
  },

  // ── Legal-mode cards ──────────────────────────────────────────────
  'summary': {
    type: 'summary',
    label: 'Case Summary',
    icon: '🔍',
    category: 'custom',
    detectFields: ['entity_name'],
    chartTypes: [],
    supportedFormats: ['standard'],
    sections: [
      { id: 'summary', label: 'Case Summary', type: 'narrative',
        extractionPrompt: 'Summarize key findings and risks', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity / Case Name', value: '', editable: true },
      { key: 'focus_area', label: 'Focus Area', value: 'Key findings and risks', editable: true },
    ],
  },
  'analysis': {
    type: 'analysis',
    label: 'Analysis Report',
    icon: '📊',
    category: 'custom',
    detectFields: ['entity_name'],
    chartTypes: [],
    supportedFormats: ['standard'],
    sections: [
      { id: 'analysis', label: 'Analysis', type: 'narrative',
        extractionPrompt: 'Comprehensive analysis of the subject matter', required: true },
    ],
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'analysis_scope', label: 'Analysis Scope', value: 'Full', editable: true },
    ],
  },
};
