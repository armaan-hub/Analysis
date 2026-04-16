import { REPORT_TYPE_CONFIG } from './report-types';

interface Props {
  onSelect: (key: string) => void;
}

const GROUPS = [
  { label: 'TAX & COMPLIANCE', keys: ['audit', 'vat', 'corporate_tax', 'compliance'] },
  { label: 'MANAGEMENT', keys: ['mis', 'financial_analysis', 'budget_vs_actual'] },
  { label: 'STATUTORY', keys: ['ifrs', 'cash_flow'] },
  { label: 'OTHER', keys: ['custom'] },
];

export function NewReportPanel({ onSelect }: Props) {
  const configMap = Object.fromEntries(REPORT_TYPE_CONFIG.map(c => [c.key, c]));

  return (
    <div style={{ padding: '8px 8px 4px' }}>
      <div style={{
        fontFamily: 'var(--s-font-ui)',
        fontSize: '10px',
        fontWeight: 700,
        color: 'var(--s-text-2)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        padding: '4px 4px 8px',
      }}>
        New Report
      </div>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}>
        {GROUPS.map(group => {
          const items = group.keys.map(k => configMap[k]).filter(Boolean);
          if (items.length === 0) return null;
          return (
            <div key={group.label}>
              <div style={{
                fontFamily: 'var(--s-font-ui)',
                fontSize: '10px',
                fontWeight: 700,
                color: 'var(--s-text-2)',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                marginBottom: '4px',
              }}>
                {group.label}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {items.map(cfg => (
                  <button
                    key={cfg.key}
                    onClick={() => onSelect(cfg.key)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '5px 8px',
                      borderRadius: 'var(--s-r-sm)',
                      border: '1px solid transparent',
                      background: 'transparent',
                      color: 'var(--s-text-1)',
                      fontFamily: 'var(--s-font-ui)',
                      fontSize: '12px',
                      cursor: 'pointer',
                      transition: 'var(--s-ease)',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLButtonElement).style.background = 'rgba(107,140,255,0.08)';
                      (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-border)';
                      (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-accent)';
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                      (e.currentTarget as HTMLButtonElement).style.borderColor = 'transparent';
                      (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-text-1)';
                    }}
                  >
                    {cfg.label}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
