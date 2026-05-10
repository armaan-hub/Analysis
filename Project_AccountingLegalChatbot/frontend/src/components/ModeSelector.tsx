import React from 'react';

export type ChatMode = 'chat' | 'research' | 'analysis' | 'council';

export interface ModeSelectorProps {
  value: ChatMode;
  onChange: (mode: ChatMode) => void;
  disabled?: boolean;
}

interface ModeConfig {
  id: ChatMode;
  icon: string;
  label: string;
  description: string;
}

const MODES: ModeConfig[] = [
  { id: 'chat',     icon: '💬', label: 'Chat',     description: 'Quick answers' },
  { id: 'research', icon: '🔬', label: 'Research',  description: 'Deep multi-source' },
  { id: 'analysis', icon: '📊', label: 'Analysis',  description: 'Spreadsheet & document' },
  { id: 'council',  icon: '🏛️', label: 'Council',   description: 'Multi-expert panel' },
];

export default function ModeSelector({ value, onChange, disabled = false }: ModeSelectorProps) {
  const containerStyle: React.CSSProperties = {
    display: 'inline-flex',
    gap: '4px',
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid var(--s-border, rgba(255,255,255,0.1))',
    borderRadius: '12px',
    padding: '4px',
  };

  const getTabStyle = (id: ChatMode): React.CSSProperties => {
    const active = id === value;
    return {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '7px 14px',
      borderRadius: '8px',
      border: 'none',
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontSize: '13px',
      fontWeight: active ? 600 : 400,
      transition: 'all 150ms ease',
      background: active
        ? 'var(--s-accent, #6366f1)'
        : 'transparent',
      color: active
        ? '#fff'
        : 'var(--s-text-2, rgba(255,255,255,0.55))',
      opacity: disabled && !active ? 0.5 : 1,
      userSelect: 'none' as const,
    };
  };

  return (
    <div role="tablist" aria-label="Chat mode" style={containerStyle}>
      {MODES.map(({ id, icon, label }) => {
        const active = id === value;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active}
            aria-label={label}
            className={active ? 'active' : undefined}
            style={getTabStyle(id)}
            disabled={disabled}
            onClick={() => {
              if (!disabled) onChange(id);
            }}
          >
            <span aria-hidden="true">{icon}</span>
            {label}
          </button>
        );
      })}
    </div>
  );
}
