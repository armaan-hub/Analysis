import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AuditorFormat } from './AuditorFormatGrid';
import type { ReportType } from './StudioCards';

const FORMAT_LABELS: Record<AuditorFormat, string> = {
  standard: 'Standard Format',
  big4: 'Big 4 Format',
  legal: 'Legal Brief Format',
  compliance: 'Compliance Format',
  custom: 'Custom Format',
};

const REPORT_LABELS: Partial<Record<ReportType, string>> = {
  audit: 'Audit Report',
  summary: 'Case Summary',
  analysis: 'Analysis Report',
};

interface Props {
  reportType: ReportType;
  format: AuditorFormat;
  content: string;
  loading: boolean;
  onBack: () => void;
  onExport: () => void;
}

export function ReportPreview({ reportType, format, content, loading, onBack, onExport }: Props) {
  return (
    <div className="report-preview">
      <div className="report-preview__header">
        <button
          type="button"
          className="report-preview__back"
          onClick={onBack}
          aria-label="Back to studio cards"
        >
          ←
        </button>
        <span className="report-preview__title">{REPORT_LABELS[reportType]}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="report-preview__badge">{FORMAT_LABELS[format]}</span>
      </div>

      <div className="report-preview__content">
        {loading && !content ? (
          <div style={{ color: 'var(--s-text-3)', fontStyle: 'italic' }}>
            Generating report…
          </div>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content || 'No content generated yet.'}
          </ReactMarkdown>
        )}
      </div>

      <button
        type="button"
        className="export-btn"
        onClick={onExport}
        disabled={loading || !content}
      >
        📥 Export as PDF
      </button>
    </div>
  );
}
