import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';

export function LearnedProfileTree() {
  const { activeProfile } = useFinanceStudio();
  const [open, setOpen] = useState<Record<string, boolean>>({});

  if (!activeProfile) return <div className="muted">No profile loaded</div>;

  const sections = [
    { key: 'account_mappings', label: 'Account Mappings' },
    { key: 'financial_periods', label: 'Financial Periods' },
    { key: 'risks', label: 'Flagged Risks' },
  ];

  return (
    <div className="profile-tree">
      <h4>Learned Profile — {activeProfile.engagement_name}</h4>
      {sections.map(s => (
        <div key={s.key} className="profile-tree__section">
          <button onClick={() => setOpen(o => ({ ...o, [s.key]: !o[s.key] }))}>
            {open[s.key] ? '▾' : '▸'} {s.label}
          </button>
          {open[s.key] && (
            <div className="profile-tree__body muted">
              (loaded lazily from GET /audit-profiles/{activeProfile.id}/{s.key})
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
