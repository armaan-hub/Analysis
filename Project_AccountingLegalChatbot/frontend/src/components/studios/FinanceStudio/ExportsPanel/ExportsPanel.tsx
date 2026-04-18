import { FormatPicker } from './FormatPicker';
import { ExportCard } from './ExportCard';
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
  return (
    <div className="exports-panel">
      <FormatPicker />
      <div className="exports-panel__cards">
        {OUTPUTS.map(o => <ExportCard key={o.type} outputType={o.type} label={o.label} />)}
      </div>
    </div>
  );
}
