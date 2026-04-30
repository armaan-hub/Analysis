import type { ExpertState } from '../../../hooks/useCouncil';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { normalizeMarkdown } from '../../../lib/utils/normalizeMarkdown';

interface Props {
  experts: Record<string, ExpertState>;
  synthesis: string;
  running: boolean;
  error: string | null;
}

// Must match Expert.name values in backend/core/council/personas.py
const ORDER = ['Senior CA', 'CPA', 'CMA', 'Financial Analyst'];

export function CouncilPanel({ experts, synthesis, running, error }: Props) {
  return (
    <div className="council-panel" style={{ display: 'grid', gap: 12, padding: 16 }}>
      <h3 style={{ margin: 0 }}>🏛️ LLM Council {running && <em style={{ fontWeight: 'normal', fontSize: 14 }}>— deliberating…</em>}</h3>
      {error && <div style={{ color: '#9b2226', padding: '8px 12px', background: '#fff5f5', borderRadius: 6 }}>Error: {error}</div>}
      {ORDER.map(name => {
        const e = experts[name];
        return (
          <div key={name} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12 }}>
            <strong>{name}</strong>{e?.status === 'thinking' && <em style={{ marginLeft: 8, color: '#718096' }}>thinking…</em>}
            {e?.status === 'final' && <span style={{ marginLeft: 8, color: '#276749', fontSize: 12 }}>✓</span>}
            <div className="report-markdown" style={{ marginTop: 8 }}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
                  ),
                }}
              >{normalizeMarkdown(e?.content ?? '')}</ReactMarkdown>
            </div>
          </div>
        );
      })}
      {synthesis && (
        <div style={{ borderTop: '2px solid #1a365d', paddingTop: 12 }}>
          <strong>Council Synthesis</strong>
          <div className="report-markdown" style={{ marginTop: 8 }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
                ),
              }}
            >{normalizeMarkdown(synthesis)}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
