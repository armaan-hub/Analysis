interface Notebook {
  id: string;
  title: string;
  updated_at: string;
  source_count?: number;
  thumbnail_icon?: string;
}

interface Props {
  notebook: Notebook;
  onClick: (id: string) => void;
}

export function NotebookCard({ notebook, onClick }: Props) {
  const dateStr = new Date(notebook.updated_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });

  return (
    <div
      className="notebook-card"
      onClick={() => onClick(notebook.id)}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(notebook.id); }}
    >
      <div className="notebook-card__thumb">
        {notebook.thumbnail_icon ?? '📄'}
      </div>
      <div className="notebook-card__info">
        <div className="notebook-card__title">{notebook.title}</div>
        <div className="notebook-card__meta">
          {dateStr}{notebook.source_count != null ? ` · ${notebook.source_count} sources` : ''}
        </div>
      </div>
    </div>
  );
}

interface CreateCardProps {
  onClick: () => void;
}

export function CreateNotebookCard({ onClick }: CreateCardProps) {
  return (
    <div
      className="notebook-card notebook-card--create"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(); }}
    >
      <div className="notebook-card__thumb" style={{ color: 'var(--s-accent)' }}>+</div>
      <div className="notebook-card__info">
        <div className="notebook-card__title" style={{ color: 'var(--s-accent)' }}>
          Create New Notebook
        </div>
        <div className="notebook-card__meta">Start from scratch</div>
      </div>
    </div>
  );
}

export type { Notebook };
