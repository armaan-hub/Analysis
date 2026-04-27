import { useState } from 'react';
import { Trash2 } from 'lucide-react';

interface Notebook {
  id: string;
  title: string;
  updated_at: string;
  source_count?: number;
  thumbnail_icon?: string;
  domain?: string;
  mode?: string;
}

const MODE_COLOURS: Record<string, string> = {
  fast: '#f59e0b',
  deep_research: '#6366f1',
  analyst: '#10b981',
};

const DOMAIN_ICONS: Record<string, string> = {
  finance: '💰',
  law: '⚖️',
  audit: '🔍',
  general: '💬',
  vat: '📋',
  aml: '🛡️',
  legal: '⚖️',
  corporate_tax: '🏢',
  vat_peppol: '📄',
  analyst: '📊',
};

const getDomainIcon = (domain?: string) => domain ? (DOMAIN_ICONS[domain] ?? '📁') : '📁';

interface Props {
  notebook: Notebook;
  onClick: (id: string) => void;
  onDelete?: (id: string) => void;
  view?: 'grid' | 'list';
  selectionMode?: boolean;
  selected?: boolean;
  onToggleSelect?: (id: string) => void;
}

function titleToGradient(title: string): string {
  let hash = 0;
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h1 = Math.abs(hash % 360);
  const h2 = (h1 + 40 + Math.abs((hash >> 8) % 40)) % 360;
  return `linear-gradient(135deg, hsl(${h1}, 60%, 35%), hsl(${h2}, 50%, 25%))`;
}

export function NotebookCard({ notebook, onClick, onDelete, view = 'grid', selectionMode, selected, onToggleSelect }: Props) {
  const [hovered, setHovered] = useState(false);

  const dateStr = new Date(notebook.updated_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });

  const gradient = titleToGradient(notebook.title);
  const isList = view === 'list';

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete?.(notebook.id);
  };

  const cardStyle: React.CSSProperties = isList
    ? { display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '12px' }
    : {};

  const thumbStyle: React.CSSProperties = {
    background: gradient,
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: isList ? '14px' : '20px',
    fontWeight: 700,
    letterSpacing: '0.5px',
    position: 'relative',
    ...(isList ? { width: '40px', height: '40px', minWidth: '40px', borderRadius: 'var(--s-r-md)' } : {}),
  };

  const deleteBtnStyle: React.CSSProperties = {
    position: 'absolute',
    background: 'var(--s-bg)',
    border: '1px solid var(--s-border)',
    borderRadius: 'var(--s-r-md)',
    padding: '4px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--s-text-2)',
    opacity: hovered ? 1 : 0,
    pointerEvents: hovered ? 'auto' : 'none',
    transition: 'opacity 150ms ease',
    ...(isList
      ? { right: '8px', top: '50%', transform: 'translateY(-50%)' }
      : { top: '6px', right: '6px' }),
  };

  return (
    <div
      className={`notebook-card${isList ? ' notebook-card--list' : ''}`}
      style={{ ...cardStyle, position: 'relative' }}
      onClick={() => onClick(notebook.id)}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(notebook.id); }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="notebook-card__thumb" style={thumbStyle}>
  <span style={{ fontSize: isList ? '22px' : '28px', lineHeight: 1, pointerEvents: 'none' }}>
    {getDomainIcon(notebook.domain)}
  </span>
  {notebook.mode && MODE_COLOURS[notebook.mode] && (
    <span
      data-testid="mode-dot"
      style={{
        position: 'absolute',
        top: '8px',
        right: '8px',
        width: '9px',
        height: '9px',
        borderRadius: '50%',
        background: MODE_COLOURS[notebook.mode],
        boxShadow: `0 0 6px ${MODE_COLOURS[notebook.mode]}`,
        pointerEvents: 'none',
      }}
    />
  )}
  {selectionMode && (
    <div
      style={{ position: 'absolute', top: 6, left: 6, zIndex: 2 }}
      onClick={e => { e.stopPropagation(); onToggleSelect?.(notebook.id); }}
    >
      <input
        type="checkbox"
        checked={!!selected}
        onChange={() => onToggleSelect?.(notebook.id)}
        style={{ width: 18, height: 18, cursor: 'pointer' }}
      />
    </div>
  )}
</div>
      <div className="notebook-card__info" style={isList ? { flex: 1, minWidth: 0 } : {}}>
        <div className="notebook-card__title">{notebook.title}</div>
        <div className="notebook-card__meta">
          {dateStr}{notebook.source_count != null ? ` · ${notebook.source_count} sources` : ''}
        </div>
      </div>
      {onDelete && !selectionMode && (
        <button
          aria-label="Delete notebook"
          style={deleteBtnStyle}
          onClick={handleDelete}
          onMouseEnter={() => setHovered(true)}
        >
          <Trash2 size={16} />
        </button>
      )}

    </div>
  );
}

interface CreateCardProps {
  onClick: () => void;
  view?: 'grid' | 'list';
}

export function CreateNotebookCard({ onClick, view = 'grid' }: CreateCardProps) {
  const isList = view === 'list';
  const createGradient = 'linear-gradient(135deg, hsl(210, 60%, 40%), hsl(230, 55%, 30%))';

  const cardStyle: React.CSSProperties = isList
    ? { display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '12px' }
    : {};

  const thumbStyle: React.CSSProperties = {
    background: createGradient,
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: isList ? '18px' : '24px',
    fontWeight: 700,
    position: 'relative',
    ...(isList ? { width: '40px', height: '40px', minWidth: '40px', borderRadius: 'var(--s-r-md)' } : {}),
  };

  return (
    <div
      className={`notebook-card notebook-card--create${isList ? ' notebook-card--list' : ''}`}
      style={cardStyle}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(); }}
    >
      <div className="notebook-card__thumb" style={thumbStyle}>+</div>
      <div className="notebook-card__info" style={isList ? { flex: 1, minWidth: 0 } : {}}>
        <div className="notebook-card__title" style={{ color: 'var(--s-accent)' }}>
          Create New Notebook
        </div>
        <div className="notebook-card__meta">Start from scratch</div>
      </div>
    </div>
  );
}

export type { Notebook };
