import { useState } from 'react';
import type { ResearchStep, ResearchAnswer } from '../../../hooks/useDeepResearch';
import { API_BASE } from '../../../lib/api';

interface Props {
  steps: ResearchStep[];
  answer: ResearchAnswer | null;
  streamingContent?: string;
  query?: string;
}

export function ResearchPanel({ steps, answer, streamingContent, query = '' }: Props) {
  const [downloading, setDownloading] = useState<'pdf' | 'docx' | null>(null);

  async function downloadResearch(format: 'pdf' | 'docx') {
    if (!answer) return;
    setDownloading(format);
    try {
      const allSources = [
        ...answer.sources.map(s => ({ filename: s.filename, page: s.page })),
        ...answer.web_sources.map(w => ({ title: w.title, url: w.url })),
      ];
      const res = await fetch(`${API_BASE}/api/chat/export-deep-research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: answer.content, sources: allSources, query, format }),
      });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `deep_research_report.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('[downloadResearch]', err);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <aside className="research-panel">
      <div className="research-panel__header">🔬 Research Log</div>

      {steps.length === 0 && !answer && (
        <div className="research-panel__empty">
          Ask a question to begin deep research. Results and sources will appear here.
        </div>
      )}

      {!answer && streamingContent && (
        <div className="research-panel__section">
          <div className="research-panel__streaming-label">Synthesising…</div>
          <div className="research-panel__streaming-preview">{streamingContent}</div>
        </div>
      )}

      {steps.length > 0 && (
        <ul className="research-steps">
          {steps.map((s, i) => (
            <li key={i} className={`research-step research-step--${s.status}`}>{s.text}</li>
          ))}
        </ul>
      )}

      {answer && (
        <>
          {answer.web_sources.length > 0 && (
            <section className="research-panel__section">
              <h4>Web Sources</h4>
              <ul>
                {answer.web_sources.map((w, i) => (
                  <li key={i}>
                    <a href={w.url} target="_blank" rel="noreferrer">
                      {w.title ?? w.url}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {answer.sources.length > 0 && (
            <section className="research-panel__section">
              <h4>Document Sources</h4>
              <ul>
                {answer.sources.map((d, i) => (
                  <li key={i}>
                    {d.filename}
                    {typeof d.page === 'number' ? ` — p.${d.page}` : ''}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 12, padding: '0 0 4px' }}>
            <button
              onClick={() => downloadResearch('pdf')}
              disabled={downloading !== null}
              style={{
                flex: 1, padding: '6px 10px', fontSize: 12, cursor: 'pointer',
                border: '1px solid var(--s-border, #e2e8f0)', borderRadius: 6,
                background: 'var(--s-bg-2, #f8fafc)', color: 'var(--s-text-1, #1e293b)',
              }}
            >
              {downloading === 'pdf' ? '⏳ Exporting…' : '⬇ Download PDF'}
            </button>
            <button
              onClick={() => downloadResearch('docx')}
              disabled={downloading !== null}
              style={{
                flex: 1, padding: '6px 10px', fontSize: 12, cursor: 'pointer',
                border: '1px solid var(--s-border, #e2e8f0)', borderRadius: 6,
                background: 'var(--s-bg-2, #f8fafc)', color: 'var(--s-text-1, #1e293b)',
              }}
            >
              {downloading === 'docx' ? '⏳ Exporting…' : '⬇ Download DOCX'}
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
