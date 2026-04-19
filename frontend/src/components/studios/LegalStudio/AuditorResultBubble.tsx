interface Finding {
  severity: 'low' | 'medium' | 'high';
  document: string;
  finding: string;
}

interface Props {
  risk_flags: Finding[];
  anomalies: Finding[];
  compliance_gaps: Finding[];
  summary: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  high: 'var(--red, #ef4444)',
  medium: 'var(--amber, #f59e0b)',
  low: 'var(--text-2, #6b7280)',
};

function Section({ title, rows, titleColor }: { title: string; rows: Finding[]; titleColor: string }) {
  if (!rows.length) return null;
  return (
    <details open>
      <summary style={{ fontSize: 13, fontWeight: 500, color: titleColor, cursor: 'pointer' }}>
        {title} ({rows.length})
      </summary>
      <ul style={{ listStyle: 'disc', paddingLeft: 20, margin: '4px 0' }}>
        {rows.map((r, i) => (
          <li key={i} style={{ fontSize: 12, color: 'var(--s-text-2)', marginBottom: 4 }}>
            <span style={{
              textTransform: 'uppercase',
              fontSize: 10,
              color: SEVERITY_COLORS[r.severity] || '#6b7280',
              opacity: 0.9,
            }}>
              {r.severity}
            </span>
            {' — '}
            <span style={{ color: 'var(--s-text-2)' }}>{r.document}:</span>{' '}
            {r.finding}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function AuditorResultBubble({ risk_flags, anomalies, compliance_gaps, summary }: Props) {
  return (
    <div style={{
      borderRadius: 'var(--s-r-sm)',
      background: 'rgba(255,255,255,0.04)',
      padding: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      <div style={{ fontSize: 11, color: 'var(--s-text-2)' }}>🔎 Auditor report</div>
      <div style={{ fontSize: 13, color: 'var(--s-text-1, #fff)' }}>{summary}</div>
      <Section title="Risk Flags" rows={risk_flags} titleColor="var(--red, #ef4444)" />
      <Section title="Anomalies" rows={anomalies} titleColor="var(--amber, #f59e0b)" />
      <Section title="Compliance Gaps" rows={compliance_gaps} titleColor="var(--teal, #a78bfa)" />
    </div>
  );
}
