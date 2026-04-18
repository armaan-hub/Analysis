import type { SourceDoc } from '../types';

interface Props { doc: SourceDoc; onDelete: (id: string) => void; }

export function DocumentCard({ doc, onDelete }: Props) {
  const warn = doc.confidence !== null && doc.confidence < 0.7;
  return (
    <div className="doc-card" data-testid={`doc-card-${doc.id}`}>
      <div className="doc-card__name">{doc.original_filename}</div>
      <div className="doc-card__type">{doc.document_type}</div>
      {warn && <span className="doc-card__warn">⚠ Review</span>}
      {doc.confidence !== null && (
        <div className="doc-card__confidence">
          <div className="bar" style={{ width: `${Math.round(doc.confidence * 100)}%` }} />
        </div>
      )}
      <button onClick={() => onDelete(doc.id)} aria-label="Delete doc">×</button>
    </div>
  );
}
