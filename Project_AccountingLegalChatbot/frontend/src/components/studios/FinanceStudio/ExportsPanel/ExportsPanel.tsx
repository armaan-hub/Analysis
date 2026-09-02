import { FormatPicker } from './FormatPicker';
import { ExportCard } from './ExportCard';
import { VersionCompare } from './VersionCompare';
import { useFinanceStudio } from '../FinanceStudioContext';
import { Sparkles } from 'lucide-react';
import type { OutputType } from '../types';

const OUTPUTS: { type: OutputType; label: string }[] = [
  { type: 'audit_report',      label: 'Audit Report' },
  { type: 'profit_loss',       label: 'Profit & Loss' },
  { type: 'balance_sheet',     label: 'Balance Sheet' },
  { type: 'cash_flow',         label: 'Cash Flow' },
  { type: 'tax_schedule',      label: 'Tax Schedule' },
  { type: 'management_report', label: 'Management Report' },
  { type: 'custom',            label: 'Custom Export' },
];

export function ExportsPanel() {
  const { setIsCouncilModalOpen } = useFinanceStudio();

  return (
    <div className="exports-panel">
      <div
        className="council-launch-card"
        onClick={() => setIsCouncilModalOpen(true)}
        title="Launch 6-Subagent Financial Audit Council Orchestrator"
      >
        <div className="council-launch-card__icon">
          <Sparkles size={18} color="#60a5fa" />
        </div>
        <div className="council-launch-card__info">
          <div className="council-launch-card__title">
            Financial Audit Council
          </div>
          <div className="council-launch-card__sub">
            6-Agent Comparative Mainland Audit
          </div>
        </div>
        <div className="council-launch-card__btn">
          Launch
        </div>
      </div>

      <FormatPicker />
      <div className="exports-panel__cards">
        {OUTPUTS.map(o => <ExportCard key={o.type} outputType={o.type} label={o.label} />)}
      </div>
      <VersionCompare />
    </div>
  );
}
