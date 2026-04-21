import { useState } from 'react';
import type { Source } from '../../../lib/api';

interface Props {
  sources: Source[];
  onSourceClick: (source: Source) => void;
  resolveName?: (path: string) => string;
}

function getDisplayName(sourcePath: string): string {
  const filename = sourcePath.split('/').pop() ?? sourcePath;
  return filename.replace(/^[0-9a-f]{8,}_/i, '');
}

export function SourcesChip({ sources, onSourceClick, resolveName }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!sources.length) return null;

  // Deduplicate by filename and group citations
  const grouped = new Map<string, Source[]>();
  for (const s of sources) {
    const key = s.source;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(s);
  }

  const fileCount = grouped.size;
  const citationCount = sources.length;

  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', maxWidth: '100%' }}>
      {/* Chip button */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          padding: '5px 12px',
          borderRadius: 'var(--s-r-sm)',
          border: '1px solid rgba(59,130,246,0.3)',
          background: 'rgba(59,130,246,0.08)',
          color: 'rgba(59,130,246,0.9)',
          cursor: 'pointer',
          fontFamily: 'var(--s-font-ui, sans-serif)',
          fontSize: '12px',
          fontWeight: 600,
          lineHeight: 1.4,
          transition: 'background 0.15s, border-color 0.15s',
        }}
      >
        🔗 Sources ({fileCount} file{fileCount !== 1 ? 's' : ''}, {citationCount} citation{citationCount !== 1 ? 's' : ''})
        <span
          style={{
            display: 'inline-block',
            fontSize: '10px',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        >
          ▼
        </span>
      </button>

      {/* Expandable panel */}
      {expanded && (
        <div
          style={{
            marginTop: '8px',
            border: '1px solid var(--s-border)',
            borderRadius: 'var(--s-r-sm)',
            background: 'rgba(59,130,246,0.04)',
            padding: '10px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            maxHeight: '320px',
            overflowY: 'auto',
          }}
        >
          {[...grouped.entries()].map(([filename, citations]) => (
            <div key={filename} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {/* File button */}
              <button
                type="button"
                onClick={() => onSourceClick(citations[0])}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '4px 8px',
                  borderRadius: 'var(--s-r-sm)',
                  border: '1px solid rgba(59,130,246,0.25)',
                  background: 'rgba(59,130,246,0.1)',
                  color: 'var(--s-text-1)',
                  cursor: 'pointer',
                  fontFamily: 'var(--s-font-ui, sans-serif)',
                  fontSize: '12px',
                  fontWeight: 600,
                  textAlign: 'left',
                  width: 'fit-content',
                  maxWidth: '100%',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title={filename}
              >
                📄 {(resolveName ?? getDisplayName)(filename)} ({citations.length})
              </button>

              {/* Cited excerpts */}
              {citations.map((c, i) => (
                <div
                  key={`${filename}:${c.page}:${i}`}
                  style={{
                    marginLeft: '12px',
                    fontFamily: 'var(--s-font-ui, sans-serif)',
                    fontSize: '11px',
                    color: 'var(--s-text-2)',
                    lineHeight: 1.45,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    maxWidth: '100%',
                  }}
                  title={c.excerpt}
                >
                  {c.page && c.page !== '?' ? `p.${c.page} — ` : ''}
                  {c.excerpt && c.excerpt.length > 120 ? c.excerpt.slice(0, 120) + '…' : (c.excerpt || '…')}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
