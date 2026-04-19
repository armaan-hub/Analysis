import { useFinanceStudio } from '../FinanceStudioContext';
import type { OutputType } from '../types';
import {
  FileText, TrendingUp, Scale, ArrowRightLeft,
  Calculator, Presentation, FileOutput,
  ChevronRight, Download,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface Props { outputType: OutputType; label: string; }

const CARD_CONFIG: Record<OutputType, { icon: LucideIcon }> = {
  audit_report:      { icon: FileText },
  profit_loss:       { icon: TrendingUp },
  balance_sheet:     { icon: Scale },
  cash_flow:         { icon: ArrowRightLeft },
  tax_schedule:      { icon: Calculator },
  management_report: { icon: Presentation },
  custom:            { icon: FileOutput },
};

export function ExportCard({ outputType, label }: Props) {
  const { outputs, generateOutput, selectedTemplateId } = useFinanceStudio();
  const latest = outputs
    .filter(o => o.output_type === outputType)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];

  const disabled = !selectedTemplateId || latest?.status === 'processing' || latest?.status === 'pending';
  const config = CARD_CONFIG[outputType];
  const Icon = config.icon;
  const status = latest?.status ?? 'not started';

  return (
    <div
      className="export-card"
      data-testid={`export-${outputType}`}
      data-type={outputType}
      data-status={status}
      onClick={() => { if (!disabled) generateOutput(outputType); }}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' && !disabled) generateOutput(outputType); }}
    >
      <div className="export-card__icon-row">
        <div className="export-card__icon">
          <Icon size={22} />
        </div>
        <span className="export-card__chevron">
          <ChevronRight size={14} />
        </span>
      </div>
      <div className="export-card__label">{label}</div>
      <div className="export-card__status">{status}</div>
      {latest?.status === 'failed' && (
        <div className="export-card__error">{latest.error_message ?? 'Generation failed'}</div>
      )}
      {latest?.status === 'ready' && latest.download_url && (
        <a
          className="export-card__download"
          href={`http://localhost:8000${latest.download_url}`}
          onClick={e => e.stopPropagation()}
        >
          <Download size={12} /> Download
        </a>
      )}
    </div>
  );
}
