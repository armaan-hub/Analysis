import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SourcesChip } from './SourcesChip';
import { API_BASE, type Source } from '../../../lib/api';

interface ResearchPhase {
  phase: string;
  message: string;
  sub_questions?: string[];
  progress?: number;
  total?: number;
  report?: string;
}

interface Props {
  phases: ResearchPhase[];
  report: string | null;
  sources?: Source[];
  query?: string;
  onSourceClick?: (source: Source) => void;
}

const exportBtnBase: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  padding: '5px 12px',
  borderRadius: 'var(--s-r-sm)',
  border: '1px solid rgba(59,130,246,0.25)',
  background: 'rgba(59,130,246,0.08)',
  color: 'rgba(59,130,246,0.9)',
  cursor: 'pointer',
  fontFamily: 'var(--s-font-ui, sans-serif)',
  fontSize: 12,
  fontWeight: 600,
  transition: 'background 0.15s, border-color 0.15s',
};

export function ResearchBubble({ phases, report, sources, query, onSourceClick }: Props) {
  const currentPhase = phases[phases.length - 1];
  const [exporting, setExporting] = useState<string | null>(null);

  const handleExport = async (format: 'pdf' | 'docx' | 'xlsx') => {
    try {
      setExporting(format);
      const res = await fetch(`${API_BASE}/api/chat/export-deep-research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: report || '', sources: sources || [], format, query: query || '' }),
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `research-${format === 'docx' ? 'doc' : format}.${format === 'docx' ? 'docx' : format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div style={{
      borderRadius: 'var(--s-r-sm)',
      background: 'rgba(59,130,246,0.06)',
      border: '1px solid rgba(59,130,246,0.15)',
      padding: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      <div style={{ fontSize: 11, color: 'var(--s-accent, var(--teal))' }}>🔬 Deep Research</div>

      {/* Progress phases */}
      {phases.map((p, i) => (
        <div key={i} style={{ fontSize: 12, color: 'var(--s-text-2)' }}>
          {p.phase === 'planned' && p.sub_questions ? (
            <div>
              <div style={{ fontWeight: 500 }}>Research plan:</div>
              <ol style={{ margin: '4px 0', paddingLeft: 20 }}>
                {p.sub_questions.map((q, j) => (
                  <li key={j} style={{ marginBottom: 2 }}>{q}</li>
                ))}
              </ol>
            </div>
          ) : p.phase === 'gathering' && p.progress ? (
            <div>
              ⏳ {p.message} ({p.progress}/{p.total})
            </div>
          ) : p.phase === 'completed' ? null : (
            <div>{p.message}</div>
          )}
        </div>
      ))}

      {/* Loading indicator */}
      {currentPhase && currentPhase.phase !== 'completed' && currentPhase.phase !== 'failed' && (
        <div style={{ fontSize: 12, color: 'var(--s-accent, var(--teal))', opacity: 0.7 }}>
          ⏳ {currentPhase.message}
        </div>
      )}

      {/* Final report — rendered as Markdown */}
      {report && (
        <div className="report-markdown" style={{ marginTop: 8 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report}
          </ReactMarkdown>
        </div>
      )}

      {/* Source citations */}
      {sources && sources.length > 0 && onSourceClick && (
        <div style={{ marginTop: 4 }}>
          <SourcesChip sources={sources} onSourceClick={onSourceClick} />
        </div>
      )}

      {/* Export bar */}
      {report && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginTop: 4,
          paddingTop: 8,
          borderTop: '1px solid rgba(59,130,246,0.1)',
        }}>
          <span style={{ fontSize: 11, color: 'var(--s-text-2)', marginRight: 4 }}>Export:</span>
          <button
            type="button"
            style={{ ...exportBtnBase, opacity: exporting === 'pdf' ? 0.6 : 1 }}
            disabled={!!exporting}
            onClick={() => handleExport('pdf')}
          >
            📄 PDF
          </button>
          <button
            type="button"
            style={{ ...exportBtnBase, opacity: exporting === 'docx' ? 0.6 : 1 }}
            disabled={!!exporting}
            onClick={() => handleExport('docx')}
          >
            📝 Word
          </button>
          <button
            type="button"
            style={{ ...exportBtnBase, opacity: exporting === 'xlsx' ? 0.6 : 1 }}
            disabled={!!exporting}
            onClick={() => handleExport('xlsx')}
          >
            📊 Excel
          </button>
        </div>
      )}
    </div>
  );
}
