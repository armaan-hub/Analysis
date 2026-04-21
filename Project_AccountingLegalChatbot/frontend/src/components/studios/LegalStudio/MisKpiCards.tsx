interface Kpi {
  label: string;
  value: string;
}

interface Props {
  kpis: Kpi[];
}

export function MisKpiCards({ kpis }: Props) {
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
      {kpis.map((k, i) => (
        <div
          key={i}
          data-testid="kpi-card"
          style={{
            flex: '1 1 140px', padding: '12px 16px',
            background: 'var(--s-bg-3, #f7fafc)',
            border: '1px solid var(--s-border, #e2e8f0)', borderRadius: 8,
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--s-text-2)', marginBottom: 4 }}>{k.label}</div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{k.value}</div>
        </div>
      ))}
    </div>
  );
}
