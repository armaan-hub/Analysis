import { useEffect, useState, useRef } from 'react';
import { X, Copy, FileText, Table2 } from 'lucide-react';
import { API } from '../../../lib/api';
import type { Source } from '../../../lib/api';

interface Props {
  sources: Source[];
  isOpen?: boolean;
  highlightedSource?: string;
  onClose: () => void;
}

function hasMarkdownTable(text: string): boolean {
  return /^\|.+\|$/m.test(text);
}

function getDisplayName(sourcePath: string): string {
  const filename = sourcePath.split('/').pop() ?? sourcePath;
  return filename.replace(/^[0-9a-f]{8,}_/i, '');
}

export function SourcePeeker({ sources, isOpen: isOpenProp, highlightedSource, onClose }: Props) {
  const [fullTexts, setFullTexts] = useState<Record<string, string>>({});
  const [copying, setCopying] = useState<string | null>(null);
  const highlightRef = useRef<HTMLDivElement | null>(null);
  const isOpen = isOpenProp !== undefined ? isOpenProp : sources.length > 0;

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  // Load full text for each source — only when panel is open.
  // The cancelled flag prevents stale fetch callbacks from updating state after
  // the effect re-runs (e.g. panel close/reopen or sources change mid-stream).
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    sources.forEach(source => {
      const key = `${source.source}:${source.page}`;
      if (fullTexts[key] !== undefined) return;
      const params = new URLSearchParams({ source: source.source });
      if (source.page && source.page !== '?') params.set('page', String(source.page));
      API.get(`/api/documents/source-content?${params.toString()}`)
        .then(r => { if (!cancelled) setFullTexts(prev => ({ ...prev, [key]: r.data.text as string })); })
        .catch(() => { if (!cancelled) setFullTexts(prev => ({ ...prev, [key]: source.excerpt ?? '' })); });
    });
    return () => { cancelled = true; };
  }, [sources, isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll highlighted source into view — only when panel is open
  useEffect(() => {
    if (!isOpen) return;
    if (highlightedSource && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [highlightedSource, isOpen]);

  if (!isOpen) return null;

  const handleCopy = async (text: string, key: string) => {
    await navigator.clipboard.writeText(text).catch(() => {});
    setCopying(key);
    setTimeout(() => setCopying(null), 1500);
  };

  const handleWordDownload = async (text: string, displayName: string) => {
    try {
      const resp = await API.post('/api/documents/export-source-docx', { text, filename: displayName }, { responseType: 'blob' });
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = displayName.replace(/\.[^.]+$/, '') + '_source.docx';
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
  };

  const handleExcelDownload = async (text: string, displayName: string) => {
    try {
      const resp = await API.post('/api/documents/export-source-xlsx', { text, filename: displayName }, { responseType: 'blob' });
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = displayName.replace(/\.[^.]+$/, '') + '_source.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
  };

  return (
    <div className={`source-peeker ${isOpen ? 'source-peeker--open' : ''}`}>
      <div className="source-peeker__header">
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', fontWeight: 600, color: 'var(--s-text-1)' }}>
          Sources ({sources.length})
        </div>
        <button className="source-peeker__close" onClick={onClose} title="Close (Esc)">
          <X size={16} />
        </button>
      </div>

      <div className="source-peeker__body" style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '12px 16px', overflowY: 'auto' }}>
        {sources.map(source => {
          const key = `${source.source}:${source.page}`;
          const displayName = getDisplayName(source.source);
          const text = fullTexts[key] ?? source.excerpt ?? '';
          const scorePercent = Math.round(source.score * 100);
          const isHighlighted = source.source === highlightedSource;
          const showExcel = hasMarkdownTable(text);

          return (
            <div
              key={key}
              ref={isHighlighted ? highlightRef : null}
              style={{
                border: `1px solid ${isHighlighted ? 'var(--s-accent)' : 'var(--s-border)'}`,
                borderRadius: 'var(--s-r-sm)',
                background: isHighlighted ? 'var(--s-accent-dim)' : 'var(--s-surface)',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              {/* Header row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={source.source}>
                    {displayName}
                  </div>
                  {source.page && source.page !== '?' && (
                    <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}>
                      Page {source.page}
                    </div>
                  )}
                </div>
                <div style={{ fontFamily: 'var(--s-font-mono, monospace)', fontSize: '11px', color: 'var(--s-accent)', background: 'var(--s-accent-dim)', padding: '2px 6px', borderRadius: 'var(--s-r-sm)', flexShrink: 0 }}>
                  {scorePercent}%
                </div>
              </div>

              {/* Content */}
              <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)', whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: '120px', overflowY: 'auto' }}>
                {text || '…'}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <button
                  onClick={() => handleCopy(text, key)}
                  style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                  title="Copy to clipboard"
                >
                  <Copy size={11} />
                  {copying === key ? 'Copied!' : 'Copy'}
                </button>
                <button
                  onClick={() => handleWordDownload(text, displayName)}
                  style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                  title="Download as Word"
                >
                  <FileText size={11} />
                  Word
                </button>
                {showExcel && (
                  <button
                    onClick={() => handleExcelDownload(text, displayName)}
                    style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                    title="Download as Excel"
                  >
                    <Table2 size={11} />
                    Excel
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
