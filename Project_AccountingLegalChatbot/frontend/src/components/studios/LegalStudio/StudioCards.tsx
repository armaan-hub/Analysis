import React from 'react';
import { ClipboardList, FileSearch, BarChart3 } from 'lucide-react';

export type ReportType = 'audit' | 'summary' | 'analysis';

const CARDS: { type: ReportType; icon: React.ReactNode; title: string; desc: string }[] = [
  { type: 'audit', icon: <ClipboardList size={18} />, title: 'Audit Report', desc: 'Generate compliance audit from sources' },
  { type: 'summary', icon: <FileSearch size={18} />, title: 'Case Summary', desc: 'AI brief of key findings and risks' },
  { type: 'analysis', icon: <BarChart3 size={18} />, title: 'Analysis Report', desc: 'Deep analysis with citations' },
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
