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

function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url.slice(0, 40);
  }
}

export function SourcesChip({ sources, onSourceClick, resolveName }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!sources.length) return null;

  // Deduplicate by source key and group citations
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
        🔗 Sources ({fileCount} source{fileCount !== 1 ? 's' : ''}, {citationCount} result{citationCount !== 1 ? 's' : ''})
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
          {[...grouped.entries()].map(([sourceKey, citations]) => {
            const isWeb = citations[0].is_web === true;
            const label = isWeb
              ? (citations[0].title || getDomain(sourceKey))
              : (resolveName ?? getDisplayName)(sourceKey);
            const displayKey = isWeb ? getDomain(sourceKey) : null;

            return (
              <div key={sourceKey} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {/* Source button */}
                {isWeb ? (
                  <a
                    href={sourceKey}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      padding: '4px 8px',
                      borderRadius: 'var(--s-r-sm)',
                      border: '1px solid rgba(16,185,129,0.3)',
                      background: 'rgba(16,185,129,0.08)',
                      color: 'var(--s-text-1)',
                      textDecoration: 'none',
                      fontFamily: 'var(--s-font-ui, sans-serif)',
                      fontSize: '12px',
                      fontWeight: 600,
                      width: 'fit-content',
                      maxWidth: '100%',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={sourceKey}
                  >
                    🌐 {label}
                    {displayKey && label !== displayKey && (
                      <span style={{ opacity: 0.6, fontWeight: 400 }}> · {displayKey}</span>
                    )}
                    <span style={{ fontSize: '10px', opacity: 0.7 }}>↗</span>
                  </a>
                ) : (
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
                    title={sourceKey}
                  >
                    📄 {label} ({citations.length})
                  </button>
                )}

                {/* Cited excerpts */}
                {citations.map((c, i) => (
                  <div
                    key={`${sourceKey}:${c.page}:${i}`}
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
                    {!isWeb && c.page && c.page !== '?' ? `p.${c.page} — ` : ''}
                    {c.excerpt && c.excerpt.length > 120 ? c.excerpt.slice(0, 120) + '…' : (c.excerpt || '…')}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
