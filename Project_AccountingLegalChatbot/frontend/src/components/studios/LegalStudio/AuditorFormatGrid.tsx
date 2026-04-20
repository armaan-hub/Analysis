import React from 'react';
import { FileText, Building2, Scale, ShieldCheck, Paperclip, Palette } from 'lucide-react';

export type AuditorFormat = 'standard' | 'big4' | 'legal' | 'compliance' | 'custom';

const FORMAT_OPTIONS: { value: AuditorFormat; label: string; icon: React.ReactNode; desc: string }[] = [
  { value: 'standard', icon: <FileText size={16} />, label: 'Standard', desc: 'Default format' },
  { value: 'big4', icon: <Building2 size={16} />, label: 'Big 4', desc: 'Deloitte/PwC style' },
  { value: 'legal', icon: <Scale size={16} />, label: 'Legal Brief', desc: 'Court format' },
  { value: 'compliance', icon: <ShieldCheck size={16} />, label: 'Compliance', desc: 'SOX/GDPR' },
  { value: 'custom', icon: <Palette size={16} />, label: 'Custom Template', desc: 'Your saved templates' },
];

interface Props {
  value: AuditorFormat;
  onChange: (format: AuditorFormat) => void;
}

export function AuditorFormatGrid({ value, onChange }: Props) {
  return (
    <div>
      <div style={{
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--s-text-1)',
        marginBottom: 8,
        fontFamily: 'var(--s-font-ui)',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        <Paperclip size={13} /> Auditor Format
      </div>
      <div className="format-grid">
        {FORMAT_OPTIONS.map(opt => (
          <button
            key={opt.value}
            type="button"
            className={`format-option${opt.value === value ? ' format-option--selected' : ''}`}
            onClick={() => onChange(opt.value)}
            aria-pressed={opt.value === value}
          >
            <div className="format-option__icon">{opt.icon}</div>
            <div className="format-option__name">{opt.label}</div>
            <div className="format-option__desc">{opt.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
