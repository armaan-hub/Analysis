export interface ResearchStep {
  text: string;
  status: 'pending' | 'active' | 'done' | 'error';
}

interface Props {
  steps: ResearchStep[];
}

export function ResearchPanel({ steps }: Props) {
  return (
    <aside className="research-panel">
      <div className="research-panel__header">🔬 Research Log</div>
      {steps.length === 0 ? (
        <div className="research-panel__empty">
          Ask a question to begin deep research. Results and sources will appear here.
        </div>
      ) : (
        <ul className="research-steps">
          {steps.map((s, i) => (
            <li key={i} className={`research-step research-step--${s.status}`}>
              {s.text}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
