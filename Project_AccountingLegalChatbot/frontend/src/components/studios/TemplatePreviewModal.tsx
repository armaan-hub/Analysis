import { useEffect, useState } from 'react';
import { API } from '../../lib/api';

interface TemplateStructure {
  sections: { title: string; level: number; line_number: number }[];
  variables: { name: string; line_number: number }[];
  tables: { header_line: number; columns: string[] }[];
  line_count: number;
  word_count: number;
}

interface PreviewData {
  template_id: string;
  rendered: string;
  structure: TemplateStructure;
  sample_data: Record<string, unknown>;
}

interface Props {
  templateId: string;
  onClose: () => void;
}

export function TemplatePreviewModal({ templateId, onClose }: Props) {
  const [data, setData] = useState<PreviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'preview' | 'structure'>('preview');

  useEffect(() => {
    API.get(`/api/templates/${templateId}/preview`)
      .then(r => setData(r.data))
      .catch(e => setError(e?.response?.data?.detail || 'Failed to load preview'));
  }, [templateId]);

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.6)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }} onClick={onClose}>
      <div
        style={{
          width: '80vw',
          maxWidth: 900,
          maxHeight: '85vh',
          background: 'var(--s-bg-2, #1a1a1a)',
          borderRadius: 'var(--s-r-md, 8px)',
          border: '1px solid var(--s-border)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--s-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--s-text-1, #fff)' }}>
              Template Preview
            </span>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['preview', 'structure'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--s-r-sm)',
                    background: tab === t ? 'var(--s-accent)' : 'transparent',
                    color: tab === t ? '#fff' : 'var(--s-text-2)',
                    border: 'none',
                    fontSize: 12,
                    cursor: 'pointer',
                  }}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--s-text-2)',
              cursor: 'pointer',
              fontSize: 16,
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {error && (
            <div style={{ color: '#ef4444', fontSize: 13 }}>{error}</div>
          )}
          {!data && !error && (
            <div style={{ color: 'var(--s-text-2)', fontSize: 13 }}>Loading preview…</div>
          )}
          {data && tab === 'preview' && (
            <pre style={{
              whiteSpace: 'pre-wrap',
              fontSize: 13,
              color: 'var(--s-text-1, #fff)',
              lineHeight: 1.6,
              fontFamily: 'var(--s-font-mono, monospace)',
            }}>
              {data.rendered}
            </pre>
          )}
          {data && tab === 'structure' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--s-text-2)', marginBottom: 4 }}>
                  {data.structure.line_count} lines · {data.structure.word_count} words
                </div>
              </div>
              {data.structure.sections.length > 0 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--s-text-1)', marginBottom: 4 }}>Sections</div>
                  {data.structure.sections.map((s, i) => (
                    <div key={i} style={{ fontSize: 12, color: 'var(--s-text-2)', paddingLeft: (s.level - 1) * 16, marginBottom: 2 }}>
                      {'#'.repeat(s.level)} {s.title} <span style={{ opacity: 0.5 }}>L{s.line_number}</span>
                    </div>
                  ))}
                </div>
              )}
              {data.structure.variables.length > 0 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--s-text-1)', marginBottom: 4 }}>Variables ({data.structure.variables.length})</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {data.structure.variables.map((v, i) => (
                      <span key={i} style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 'var(--s-r-sm)',
                        background: 'rgba(59,130,246,0.1)',
                        color: '#3b82f6',
                        fontFamily: 'var(--s-font-mono, monospace)',
                      }}>
                        {'${' + v.name + '}'}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {data.structure.tables.length > 0 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--s-text-1)', marginBottom: 4 }}>Tables ({data.structure.tables.length})</div>
                  {data.structure.tables.map((t, i) => (
                    <div key={i} style={{ fontSize: 12, color: 'var(--s-text-2)' }}>
                      Table at L{t.header_line}: {t.columns.join(' | ')}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
