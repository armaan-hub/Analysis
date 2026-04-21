import type { PrefilledField } from './QuestionnaireMessage';

export interface ReportConfig {
  type: string;
  label: string;
  icon: string;
  fields: PrefilledField[];
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
  },
  'audit': {
    type: 'audit',
    label: 'Audit Report',
    icon: '📝',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'period_end', label: 'Period End', value: todayISO, editable: true },
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
  },
  'analysis': {
    type: 'analysis',
    label: 'Analysis Report',
    icon: '📊',
    fields: [
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'analysis_scope', label: 'Analysis Scope', value: 'Full', editable: true },
    ],
  },
};
