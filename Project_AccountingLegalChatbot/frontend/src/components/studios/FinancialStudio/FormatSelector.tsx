import { useState } from 'react';

interface FormatSelectorProps {
  templateId: string | null;
  templateConfidence: number;
  onSelectFormat: (format: string) => void;
  selectedFormat: string;
}

const FORMAT_OPTIONS: Array<{
  value: string;
  label: string;
  description: string;
  requiresTemplate?: boolean;
}> = [
  {
    value: 'prior_year_template',
    label: 'Prior Year Template',
    description: 'Reuse the exact structure extracted from your prior year audit report',
    requiresTemplate: true,
  },
  { value: 'big4',  label: 'Big 4 Standard',            description: 'ISA 700/701 with Key Audit Matters, Management Letter, and Big 4 disclosures' },
  { value: 'isa',   label: 'Local Standard (ISA 700)',   description: 'ISA 700/701/705/706 full structure with all mandatory audit sections' },
  { value: 'ifrs',  label: 'IFRS Financial Statements',  description: 'IFRS-compliant financial statement format with full disclosure notes' },
  { value: 'custom', label: 'Custom',                    description: "Manual format instructions — paste your firm's template or describe the layout" },
];

export function FormatSelector({
  templateId,
  templateConfidence,
  onSelectFormat,
  selectedFormat,
}: FormatSelectorProps) {
  const [selected, setSelected] = useState(
    selectedFormat || (templateId ? 'prior_year_template' : 'big4'),
  );

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', flex: 1,
      padding: '32px 40px', gap: '24px',
      maxWidth: '640px', margin: '0 auto', width: '100%', overflowY: 'auto',
    }}>
      <div>
        <div style={{
          fontFamily: 'var(--s-font-display)', fontSize: '18px',
          fontWeight: 600, color: 'var(--s-text-1)', marginBottom: '4px',
        }}>
          Select Audit Format
        </div>
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
          A prior year template was detected. You can reuse its structure or pick another format.
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {FORMAT_OPTIONS.map(f => {
          const disabled = f.requiresTemplate && !templateId;
          const isSelected = selected === f.value;

          return (
            <button
              key={f.value}
              disabled={disabled}
              onClick={() => { if (!disabled) setSelected(f.value); }}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '4px',
                padding: '14px 16px', borderRadius: 'var(--s-r-sm)', textAlign: 'left',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.45 : 1,
                border: `1px solid ${isSelected ? 'var(--s-accent)' : 'var(--s-border)'}`,
                background: isSelected ? 'var(--s-accent-dim)' : 'var(--s-surface)',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontFamily: 'var(--s-font-ui)', fontSize: '13px', fontWeight: 600,
                  color: isSelected ? 'var(--s-accent)' : 'var(--s-text-1)',
                }}>
                  {f.label}
                </span>

                {f.requiresTemplate && templateId && (
                  <span style={{
                    fontFamily: 'var(--s-font-ui)', fontSize: '10px', fontWeight: 600,
                    padding: '2px 6px', borderRadius: '9999px',
                    background: templateConfidence >= 0.8 ? 'var(--s-success, #22c55e)' : 'var(--s-accent)',
                    color: '#fff',
                  }}>
                    {(templateConfidence * 100).toFixed(0)}% match
                  </span>
                )}

                {f.requiresTemplate && templateId && (
                  <span style={{
                    fontFamily: 'var(--s-font-ui)', fontSize: '10px', fontWeight: 600,
                    padding: '2px 6px', borderRadius: '9999px',
                    background: 'var(--s-accent)', color: '#fff',
                  }}>
                    Recommended
                  </span>
                )}
              </span>

              <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
                {f.description}
              </span>
            </button>
          );
        })}
      </div>

      <button
        className="btn-primary"
        onClick={() => onSelectFormat(selected)}
        style={{ alignSelf: 'flex-start' }}
      >
        Generate Final Report →
      </button>
    </div>
  );
}
