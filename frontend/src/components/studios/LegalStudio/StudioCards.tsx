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
