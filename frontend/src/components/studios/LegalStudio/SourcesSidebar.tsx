import { useState, useMemo, useCallback } from 'react';
import { SourceTypeIcon } from './SourceTypeIcon';
import { SourceSearch } from './SourceSearch';
import { EmptySourcesState } from './EmptySourcesState';
import { AddSourcesOverlay } from './AddSourcesOverlay';

export interface SourceDoc {
  id: string;
  filename: string;
  summary?: string;
  key_terms?: string[];
  source: string;
  status?: 'uploading' | 'processing' | 'summarizing' | 'ready' | 'error';
  file_size?: number;
  created_at?: string;
}

interface Props {
  docs: SourceDoc[];
  selectedIds: string[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onUpload: (files: FileList) => void;
  onPreview: (id: string) => void;
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SourcesSidebar({ docs, selectedIds, onSelect, onDelete, onUpload, onPreview }: Props) {
  const [search, setSearch] = useState('');
  const [showOverlay, setShowOverlay] = useState(false);

  const filteredDocs = useMemo(() => {
    if (!search.trim()) return docs;
    const q = search.toLowerCase();
    return docs.filter(d => d.filename.toLowerCase().includes(q));
  }, [docs, search]);

  const allSelected = docs.length > 0 && docs.every(d => selectedIds.includes(d.id));

  const handleSelectAll = useCallback(() => {
    if (allSelected) {
      docs.forEach(d => {
        if (selectedIds.includes(d.id)) onSelect(d.id);
      });
    } else {
      docs.forEach(d => {
        if (!selectedIds.includes(d.id)) onSelect(d.id);
      });
    }
  }, [docs, selectedIds, allSelected, onSelect]);

  const handleUpload = useCallback((files: FileList) => {
    onUpload(files);
    setShowOverlay(false);
  }, [onUpload]);

  return (
    <aside className="sources-panel">
      <div className="sources-header">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span className="sources-header__title">
            {showOverlay ? 'Add Sources' : 'Sources'}
          </span>
          {!showOverlay && (
            <span className="sources-header__count">({docs.length})</span>
          )}
        </div>
        <button
          type="button"
          className="sources-add-btn"
          onClick={() => setShowOverlay(!showOverlay)}
          aria-label={showOverlay ? 'Close' : 'Add sources'}
          title={showOverlay ? 'Close' : 'Add sources'}
        >
          {showOverlay ? '✕' : '+'}
        </button>
      </div>

      {showOverlay ? (
        <AddSourcesOverlay onUpload={handleUpload} onClose={() => setShowOverlay(false)} />
      ) : docs.length === 0 ? (
        <EmptySourcesState onAddSources={() => setShowOverlay(true)} />
      ) : (
        <>
          <SourceSearch value={search} onChange={setSearch} />
          <button
            type="button"
            className="sources-select-all"
            onClick={handleSelectAll}
          >
            {allSelected ? 'Deselect all' : 'Select all'}
          </button>
          <ul className="source-list">
            {filteredDocs.map(d => (
              <li
                key={d.id}
                className={`source-item${selectedIds.includes(d.id) ? ' source-item--selected' : ''}`}
                onClick={() => onPreview(d.id)}
              >
                <input
                  type="checkbox"
                  className="source-checkbox"
                  checked={selectedIds.includes(d.id)}
                  onChange={e => { e.stopPropagation(); onSelect(d.id); }}
                  onClick={e => e.stopPropagation()}
                  aria-label={`Select ${d.filename}`}
                />
                <SourceTypeIcon filename={d.filename} />
                <div className="source-info">
                  <div className="source-info__name">{d.filename}</div>
                  <div className="source-info__meta">
                    {formatFileSize(d.file_size)}
                    {d.status && d.status !== 'ready' && (
                      <span style={{ color: 'var(--s-warning)', marginLeft: 6 }}>
                        {d.status}…
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={e => { e.stopPropagation(); onDelete(d.id); }}
                  aria-label={`Delete ${d.filename}`}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--s-text-3)',
                    cursor: 'pointer',
                    fontSize: 14,
                    padding: 0,
                    flexShrink: 0,
                  }}
                  title="Delete"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
