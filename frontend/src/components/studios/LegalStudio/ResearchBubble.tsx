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
}

export function ResearchBubble({ phases, report }: Props) {
  const currentPhase = phases[phases.length - 1];

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
      <div style={{ fontSize: 11, color: '#3b82f6' }}>🔬 Deep Research</div>

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
        <div style={{ fontSize: 12, color: '#3b82f6', opacity: 0.7 }}>
          ⏳ {currentPhase.message}
        </div>
      )}

      {/* Final report */}
      {report && (
        <div style={{
          fontSize: 13,
          color: 'var(--s-text-1, #fff)',
          whiteSpace: 'pre-wrap',
          marginTop: 8,
          lineHeight: 1.6,
        }}>
          {report}
        </div>
      )}
    </div>
  );
}
