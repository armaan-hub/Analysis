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
  fields: PrefilledField[];            // existing — keep for backward compat
  sections?: ReportSection[];           // new
  supportedFormats?: AuditorFormat[];   // new
  detectFields?: string[];              // new
  regulatoryNote?: string;              // new
  chartTypes?: string[];                // new
  category?: 'financial' | 'regulatory' | 'audit' | 'custom';  // new
}

const currentYear = new Date().getFullYear();
const todayISO = new Date().toISOString().split('T')[0];

export const REPORT_CONFIGS: Record<string, ReportConfig> = {
  // ── Analyst-mode cards ────────────────────────────────────────────
  'financial_analysis': {
    type: 'financial_analysis',
    label: 'Profit & Loss Statement',
    icon: '📈',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'currency', label: 'Currency', value: 'USD', editable: true },
      { key: 'comparative', label: 'Comparative Period', value: 'Previous Year', editable: true },
    ],
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
  },
  'ifrs': {
    type: 'ifrs',
    label: 'Balance Sheet (IFRS)',
    icon: '📊',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'as_of_date', label: 'As of Date', value: todayISO, editable: true },
      { key: 'currency', label: 'Currency', value: 'USD', editable: true },
    ],
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
  },
  'cash_flow': {
    type: 'cash_flow',
    label: 'Cash Flow Statement',
    icon: '💰',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'method', label: 'Method', value: 'Indirect', editable: true },
    ],
    category: 'financial',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'big4'],
    sections: [
      { id: 'cashflow', label: 'Cash Flow Statement', type: 'table',
        extractionPrompt: 'Extract operating, investing, financing cash flows', required: true },
    ],
  },
  'mis': {
    type: 'mis',
    label: 'MIS Report',
    icon: '📋',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'departments', label: 'Departments', value: 'All', editable: true },
    ],
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
  },
  'budget_vs_actual': {
    type: 'budget_vs_actual',
    label: 'Budget vs Actual',
    icon: '🎯',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'currency', label: 'Currency', value: 'USD', editable: true },
    ],
    category: 'financial',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: ['bar'],
    supportedFormats: ['standard', 'big4'],
    sections: [
      { id: 'variance', label: 'Budget vs Actual Variance', type: 'table',
        extractionPrompt: 'Extract budget and actual figures and variance %', required: true },
    ],
  },
  'forecast': {
    type: 'forecast',
    label: 'Financial Forecast',
    icon: '📈',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Forecast Period', value: '12 months', editable: true },
      { key: 'base_year', label: 'Base Year', value: currentYear.toString(), editable: true },
    ],
    category: 'financial',
    detectFields: ['entity_name'],
    chartTypes: ['line'],
    supportedFormats: ['standard'],
    sections: [
      { id: 'forecast_table', label: 'Forecast Table', type: 'table',
        extractionPrompt: 'Extract historical data and project forward', required: true },
    ],
  },
  'vat': {
    type: 'vat',
    label: 'VAT Return',
    icon: '🧮',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'trn', label: 'TRN', value: '', editable: true },
      { key: 'tax_period', label: 'Tax Period', value: `Q${Math.ceil((new Date().getMonth() + 1) / 3)} ${currentYear}`, editable: true },
    ],
    category: 'regulatory',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'compliance'],
    regulatoryNote: 'Based on UAE FTA VAT-201 form structure',
    sections: [
      { id: 'vat_form', label: 'VAT-201 Return', type: 'regulatory_form',
        extractionPrompt: 'Extract values for VAT-201 Boxes 1–9 from accounting documents', required: true },
    ],
  },
  'corporate_tax': {
    type: 'corporate_tax',
    label: 'Corporate Tax Computation',
    icon: '🏢',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'tax_year', label: 'Tax Year', value: currentYear.toString(), editable: true },
      { key: 'jurisdiction', label: 'Jurisdiction', value: 'UAE', editable: true },
    ],
    category: 'regulatory',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'compliance'],
    regulatoryNote: 'Based on UAE CT Decree-Law No. 47 of 2022',
    sections: [
      { id: 'ct_computation', label: 'CT Computation', type: 'table',
        extractionPrompt: 'Extract accounting profit, adjustments, exempt income, CT payable', required: true },
    ],
  },
  'audit': {
    type: 'audit',
    label: 'Audit Report',
    icon: '📝',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period_end', label: 'Period End', value: todayISO, editable: true },
    ],
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
  },
  'compliance': {
    type: 'compliance',
    label: 'Board / Compliance Report',
    icon: '📊',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period', label: 'Period', value: `FY ${currentYear}`, editable: true },
      { key: 'jurisdiction', label: 'Jurisdiction', value: 'UAE', editable: true },
    ],
    category: 'regulatory',
    detectFields: ['entity_name', 'period_end'],
    chartTypes: [],
    supportedFormats: ['standard', 'compliance'],
    sections: [
      { id: 'compliance_summary', label: 'Compliance Summary', type: 'narrative',
        extractionPrompt: 'Executive summary of regulatory compliance status', required: true },
    ],
  },
  'custom': {
    type: 'custom',
    label: 'Custom Report',
    icon: '📄',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'report_title', label: 'Report Title', value: '', editable: true },
      { key: 'instructions', label: 'Instructions', value: '', editable: true },
    ],
    category: 'custom',
    detectFields: ['entity_name'],
    chartTypes: [],
    supportedFormats: ['standard', 'big4', 'legal', 'compliance', 'custom'],
    sections: [],
  },

  // ── Legal-mode cards ──────────────────────────────────────────────
  'summary': {
    type: 'summary',
    label: 'Case Summary',
    icon: '🔍',
    fields: [
      { key: 'entity_name', label: 'Entity / Case Name', value: '', editable: true },
      { key: 'focus_area', label: 'Focus Area', value: 'Key findings and risks', editable: true },
    ],
    category: 'custom',
    detectFields: ['entity_name'],
    chartTypes: [],
    supportedFormats: ['standard'],
    sections: [
      { id: 'summary', label: 'Case Summary', type: 'narrative',
        extractionPrompt: 'Summarize key findings and risks', required: true },
    ],
  },
  'analysis': {
    type: 'analysis',
    label: 'Analysis Report',
    icon: '📊',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'analysis_scope', label: 'Analysis Scope', value: 'Full', editable: true },
    ],
    category: 'custom',
    detectFields: ['entity_name'],
    chartTypes: [],
    supportedFormats: ['standard'],
    sections: [
      { id: 'analysis', label: 'Analysis', type: 'narrative',
        extractionPrompt: 'Comprehensive analysis of the subject matter', required: true },
    ],
  },
};
