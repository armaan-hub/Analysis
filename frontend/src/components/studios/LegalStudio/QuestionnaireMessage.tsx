import { useState } from 'react';

interface PrefilledField {
  key: string;
  label: string;
  value: string;
  editable: boolean;
  placeholder?: string;
  autoDetected?: boolean;
}

interface Props {
  reportType: string;
  fields: PrefilledField[];
  onConfirm: (confirmedFields: Record<string, string>) => void;
  onCancel: () => void;
  generating?: boolean;
}

export function QuestionnaireMessage({ reportType, fields, onConfirm, onCancel, generating }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map(f => [f.key, f.value]))
  );

  const handleChange = (key: string, val: string) =>
    setValues(prev => ({ ...prev, [key]: val }));

  return (
    <div style={{
      borderRadius: 'var(--s-r-sm)',
      background: 'rgba(59,130,246,0.06)',
      border: '1px solid rgba(59,130,246,0.15)',
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      {/* AI Assistant header */}
      <div style={{ fontSize: 11, color: 'var(--s-accent, var(--teal))', fontWeight: 500 }}>
        ◆ AI Assistant
      </div>

      {/* Title */}
      <div style={{ fontSize: 13, color: 'var(--s-text-1, #fff)' }}>
        Generating <strong>{reportType}</strong>. Let me confirm a few details first…
      </div>

      {/* Field list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {fields.map(f => (
          <div key={f.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{
              minWidth: 140,
              fontSize: 12,
              color: 'var(--s-text-2)',
              flexShrink: 0,
            }}>
              {f.label}
            </label>

            {f.editable ? (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <input
                  value={values[f.key] ?? ''}
                  onChange={e => handleChange(f.key, e.target.value)}
                  disabled={generating}
                  placeholder={f.placeholder ?? ''}
                  style={{
                    fontSize: 12,
                    padding: '4px 8px',
                    borderRadius: 'var(--s-r-sm)',
                    border: '1px solid var(--s-border, rgba(255,255,255,0.1))',
                    background: 'rgba(255,255,255,0.05)',
                    color: 'var(--s-text-1, #fff)',
                    outline: 'none',
                  }}
                />
                {f.autoDetected && values[f.key] && (
                  <span style={{ fontSize: 11, color: 'var(--s-text-2)', fontStyle: 'italic' }}>
                    Auto-detected from sources
                  </span>
                )}
              </div>
            ) : (
              <span style={{ fontSize: 12, color: 'var(--s-text-1, #fff)' }}>
                {values[f.key]}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button
          onClick={() => onConfirm(values)}
          disabled={generating}
          style={{
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: 500,
            borderRadius: 'var(--s-r-sm)',
            border: 'none',
            background: generating ? 'rgba(59,130,246,0.4)' : 'rgba(59,130,246,0.8)',
            color: '#fff',
            cursor: generating ? 'not-allowed' : 'pointer',
            opacity: generating ? 0.7 : 1,
          }}
        >
          {generating ? '⏳ Generating…' : `✨ Generate ${reportType}`}
        </button>

        <button
          onClick={onCancel}
          disabled={generating}
          style={{
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: 500,
            borderRadius: 'var(--s-r-sm)',
            border: '1px solid var(--s-border, rgba(255,255,255,0.12))',
            background: 'transparent',
            color: 'var(--s-text-2)',
            cursor: generating ? 'not-allowed' : 'pointer',
            opacity: generating ? 0.5 : 1,
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export type { PrefilledField };
