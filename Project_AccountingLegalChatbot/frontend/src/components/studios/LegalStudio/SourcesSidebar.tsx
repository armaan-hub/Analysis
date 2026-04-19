import { useRef } from 'react';

export interface SourceDoc {
  id: string;
  filename: string;
  summary?: string;
  key_terms?: string[];
  source: string;
  status?: 'uploading' | 'processing' | 'summarizing' | 'ready' | 'error';
}

interface Props {
  docs: SourceDoc[];
  selectedIds: string[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onUpload: (files: FileList) => void;
  onPreview: (id: string) => void;
}

export function SourcesSidebar({ docs, selectedIds, onSelect, onDelete, onUpload, onPreview }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <aside style={{
      width: 260,
      borderRight: '1px solid var(--s-border)',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--s-bg-2, #111)',
      overflow: 'hidden',
    }}>
      <div style={{ padding: 12, borderBottom: '1px solid var(--s-border)' }}>
        <input
          ref={fileRef}
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={e => e.target.files && onUpload(e.target.files)}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          aria-label="Upload documents"
          style={{
            width: '100%',
            padding: '8px 12px',
            borderRadius: 'var(--s-r-sm)',
            background: 'var(--s-accent)',
            color: '#fff',
            border: 'none',
            fontSize: 13,
            cursor: 'pointer',
            fontFamily: 'var(--s-font-ui)',
          }}
        >
          + Upload (multi-select)
        </button>
      </div>
      <ul style={{ flex: 1, overflow: 'auto', listStyle: 'none', margin: 0, padding: 0 }}>
        {docs.map(d => (
          <li key={d.id} style={{
            padding: 12,
            borderBottom: '1px solid var(--s-border)',
            display: 'flex',
            gap: 8,
            alignItems: 'flex-start',
          }}>
            <input
              type="checkbox"
              checked={selectedIds.includes(d.id)}
              onChange={() => onSelect(d.id)}
              aria-label={`Select ${d.filename}`}
              style={{ marginTop: 3 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <button
                type="button"
                onClick={() => onPreview(d.id)}
                aria-label={`Preview ${d.filename}`}
                style={{
                  textAlign: 'left',
                  width: '100%',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                <div style={{
                  fontSize: 13,
                  color: 'var(--s-text-1, #fff)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {d.filename}
                </div>
                {d.status && d.status !== 'ready' && (
                  <div style={{ fontSize: 11, color: '#f59e0b', marginTop: 2 }}>
                    {d.status}…
                  </div>
                )}
                {d.summary && (
                  <div style={{
                    fontSize: 11,
                    color: 'var(--s-text-2)',
                    marginTop: 4,
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}>
                    {d.summary}
                  </div>
                )}
                {d.key_terms && d.key_terms.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {d.key_terms.map(k => (
                      <span key={k} style={{
                        fontSize: 10,
                        padding: '2px 6px',
                        borderRadius: 'var(--s-r-sm)',
                        background: 'rgba(255,255,255,0.08)',
                        color: 'var(--s-text-2)',
                      }}>
                        {k}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            </div>
            <button
              type="button"
              onClick={() => onDelete(d.id)}
              aria-label={`Delete ${d.filename}`}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--s-text-2)',
                cursor: 'pointer',
                fontSize: 14,
                padding: 0,
              }}
              title="Delete"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
