import type { SourceDoc } from '../types';
import { FileSpreadsheet, FileText, File, X } from 'lucide-react';

interface Props { doc: SourceDoc; onDelete: (id: string) => void; selected: boolean; onToggle: (id: string) => void; }

const DOC_ICONS: Record<string, typeof FileText> = {
  trial_balance: FileSpreadsheet,
  chart_of_accounts: FileSpreadsheet,
  prior_audit: FileText,
  report_template: FileText,
};

export function DocumentCard({ doc, onDelete, selected, onToggle }: Props) {
  const warn = doc.confidence !== null && doc.confidence < 0.7;
  const Icon = DOC_ICONS[doc.document_type] ?? File;

  return (
    <div className="doc-card" data-testid={`doc-card-${doc.id}`}>
      <div className="doc-card__select">
        <input type="checkbox" checked={selected} onChange={() => onToggle(doc.id)} aria-label="Select doc" />
      </div>
      <div className="doc-card__icon">
        <Icon size={16} />
      </div>
      <div className="doc-card__info">
        <div className="doc-card__name">{doc.original_filename}</div>
        <div className="doc-card__type">{doc.document_type.replace(/_/g, ' ')}</div>
      </div>
      {warn && <span className="doc-card__warn">⚠ Review</span>}
      {doc.confidence !== null && (
        <div className="doc-card__confidence">
          <div className="bar" style={{ width: `${Math.round(doc.confidence * 100)}%` }} />
        </div>
      )}
      <button className="doc-card__delete" onClick={() => onDelete(doc.id)} aria-label="Delete doc">
        <X size={14} />
      </button>
    </div>
  );
}
