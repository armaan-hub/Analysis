import { useEffect, useState, useRef } from 'react';
import React from 'react';
import { X, Copy, FileText, Table2 } from 'lucide-react';
import { API } from '../../../lib/api';
import type { Source } from '../../../lib/api';

const DOMAIN_COLORS: Record<string, string> = {
  vat: "bg-blue-100 text-blue-800",
  corporate_tax: "bg-purple-100 text-purple-800",
  labour: "bg-green-100 text-green-800",
  commercial: "bg-yellow-100 text-yellow-800",
  ifrs: "bg-orange-100 text-orange-800",
  e_invoicing: "bg-cyan-100 text-cyan-800",
  peppol: "bg-cyan-100 text-cyan-800",
  general_law: "bg-gray-100 text-gray-700",
};

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
  const [expandedKeys, setExpandedKeys] = React.useState<Set<number>>(new Set([0]));
  const highlightRef = useRef<HTMLDivElement | null>(null);
  const isOpen = isOpenProp !== undefined ? isOpenProp : sources.length > 0;

  // Auto-expand first card when sources change
  React.useEffect(() => {
    if (sources && sources.length > 0) {
      setExpandedKeys(new Set([0]));
    }
  }, [sources]);

  const toggleExpanded = (index: number) => {
    setExpandedKeys(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const domainBadge = (domain: string | undefined) => {
    if (!domain) return null;
    const colorClass = DOMAIN_COLORS[domain] ?? "bg-gray-100 text-gray-700";
    const label = domain.replace(/_/g, " ").toUpperCase();
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
        {label}
      </span>
    );
  };

  const scoreBadge = (score: number) => {
    const pct = Math.round(score * 100);
    const colorClass =
      score >= 0.8 ? "bg-green-100 text-green-800" :
      score >= 0.6 ? "bg-yellow-100 text-yellow-800" :
                     "bg-red-100 text-red-800";
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
        {pct}%
      </span>
    );
  };

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
        .catch((err) => { if (!cancelled) setFullTexts(prev => ({ ...prev, [key]: source.excerpt ?? '' })); console.error('Failed to load source text:', err); });
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
    } catch (err) { console.error('Export failed:', err); }
  };

  const handleExcelDownload= async (text: string, displayName: string) => {
    try {
      const resp = await API.post('/api/documents/export-source-xlsx', { text, filename: displayName }, { responseType: 'blob' });
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = displayName.replace(/\.[^.]+$/, '') + '_source.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) { console.error('Export failed:', err); }
  };

  return (
    <div className={`source-peeker ${isOpen ? 'source-peeker--open' : ''}`}>
      <div className="source-peeker__header">
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', fontWeight: 600, color: 'var(--s-text-1)' }}>
          Sources ({sources.length})
        </div>
        <button type="button" className="source-peeker__close" onClick={onClose} title="Close (Esc)">
          <X size={16} />
        </button>
      </div>

      <div className="source-peeker__body" style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '12px 16px', overflowY: 'auto' }}>
        {sources.map((source, index) => {
          const key = `${source.source}:${source.page}`;
          const displayName = source.original_name ?? getDisplayName(source.source);
          const text = fullTexts[key] ?? source.excerpt ?? '';
          const isHighlighted = source.source === highlightedSource;
          const showExcel = hasMarkdownTable(text);
          const isExpanded = expandedKeys.has(index);

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
              {/* Header row - always visible */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, minWidth: 0, flexWrap: 'wrap' }}>
                  <div style={{ overflow: 'hidden', minWidth: 0 }}>
                    <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={source.source}>
                      {displayName}
                    </div>
                    {source.page && source.page !== '?' && (
                      <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}>
                        Page {source.page}
                      </div>
                    )}
                  </div>
                  {domainBadge(source.domain)}
                  {scoreBadge(source.score)}
                </div>
                <button
                  type="button"
                  onClick={() => toggleExpanded(index)}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--s-text-2)', flexShrink: 0, padding: '2px 4px', fontSize: '11px', lineHeight: 1 }}
                  aria-label={isExpanded ? "Collapse" : "Expand"}
                >
                  {isExpanded ? '▲' : '▼'}
                </button>
              </div>

              {/* Body - only when expanded */}
              {isExpanded && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {/* Content */}
                  <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)', whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: '120px', overflowY: 'auto' }}>
                    {text || '…'}
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={() => handleCopy(text, key)}
                      style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                      title="Copy to clipboard"
                    >
                      <Copy size={11} />
                      {copying === key ? 'Copied!' : 'Copy'}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleWordDownload(text, displayName)}
                      style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                      title="Download as Word"
                    >
                      <FileText size={11} />
                      Word
                    </button>
                    {showExcel && (
                      <button
                        type="button"
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
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
