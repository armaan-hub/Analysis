export type ReportType = 'audit' | 'summary' | 'analysis';

const CARDS: { type: ReportType; icon: string; title: string; desc: string }[] = [
  { type: 'audit', icon: '📋', title: 'Audit Report', desc: 'Generate compliance audit from sources' },
  { type: 'summary', icon: '📑', title: 'Case Summary', desc: 'AI brief of key findings and risks' },
  { type: 'analysis', icon: '📊', title: 'Analysis Report', desc: 'Deep analysis with citations' },
];

interface Props {
  onSelect: (type: ReportType) => void;
  disabled?: boolean;
}

export function StudioCards({ onSelect, disabled }: Props) {
  return (
    <>
      {CARDS.map(card => (
        <button
          key={card.type}
          type="button"
          className="studio-card"
          onClick={() => onSelect(card.type)}
          disabled={disabled}
        >
          <div className="studio-card__icon">{card.icon}</div>
          <div>
            <div className="studio-card__title">{card.title}</div>
            <div className="studio-card__desc">{card.desc}</div>
          </div>
        </button>
      ))}
    </>
  );
}
