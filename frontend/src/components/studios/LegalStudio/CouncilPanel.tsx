import type { ExpertState } from '../../../hooks/useCouncil';

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
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, marginTop: 8, margin: '8px 0 0' }}>{e?.content ?? ''}</pre>
          </div>
        );
      })}
      {synthesis && (
        <div style={{ borderTop: '2px solid #1a365d', paddingTop: 12 }}>
          <strong>Council Synthesis</strong>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 14, marginTop: 8, margin: '8px 0 0' }}>{synthesis}</pre>
        </div>
      )}
    </div>
  );
}
