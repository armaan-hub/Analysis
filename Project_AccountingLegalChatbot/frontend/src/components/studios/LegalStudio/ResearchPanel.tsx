import type { ResearchStep, ResearchAnswer } from '../../../hooks/useDeepResearch';

interface Props {
  steps: ResearchStep[];
  answer: ResearchAnswer | null;
  streamingContent?: string;
}

export function ResearchPanel({ steps, answer, streamingContent }: Props) {
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
          <div className="research-panel__streaming-label" style={{fontSize:'0.75rem', opacity:0.7, marginBottom:'4px'}}>Synthesising…</div>
          <div style={{fontSize:'0.875rem', whiteSpace:'pre-wrap', opacity:0.85}}>{streamingContent}</div>
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
        </>
      )}
    </aside>
  );
}
