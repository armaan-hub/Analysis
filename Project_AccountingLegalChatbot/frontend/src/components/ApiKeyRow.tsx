import React from 'react';

export type KeyMode = 'masked' | 'hidden' | 'none';

export interface ApiKeyRowProps {
  keyName: string;
  mode: KeyMode;
  onToggle: (keyName: string, newMode: KeyMode) => void;
  loading?: boolean;
}

const CYCLE: KeyMode[] = ['masked', 'hidden', 'none'];

const BADGE: Record<KeyMode, { label: string; icon: string; color: string }> = {
  masked: { label: 'masked',  icon: '👁️',  color: 'rgba(99,102,241,0.2)'  },
  hidden: { label: '🔒',     icon: '🚫',  color: 'rgba(239,68,68,0.15)'  },
  none:   { label: 'visible', icon: '👁️‍🗨️', color: 'rgba(34,197,94,0.15)' },
};

export default function ApiKeyRow({ keyName, mode, onToggle, loading = false }: ApiKeyRowProps) {
  const nextMode = CYCLE[(CYCLE.indexOf(mode) + 1) % CYCLE.length];
  const badge = BADGE[mode];

  const rowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 0',
    borderBottom: '1px solid var(--border, rgba(255,255,255,0.08))',
  };

  const nameStyle: React.CSSProperties = {
    flex: '0 0 200px',
    fontFamily: 'monospace',
    fontSize: '0.82rem',
    color: 'var(--text-1, #fff)',
    userSelect: 'text' as const,
  };

  const badgeStyle: React.CSSProperties = {
    flex: '0 0 120px',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '3px 10px',
    borderRadius: '999px',
    fontSize: '0.75rem',
    fontWeight: 600,
    background: badge.color,
    color: 'var(--text-1, #fff)',
  };

  const btnStyle: React.CSSProperties = {
    marginLeft: 'auto',
    background: 'transparent',
    border: '1px solid var(--border, rgba(255,255,255,0.15))',
    borderRadius: '6px',
    padding: '4px 10px',
    cursor: loading ? 'not-allowed' : 'pointer',
    color: 'var(--text-2, rgba(255,255,255,0.6))',
    fontSize: '0.75rem',
    opacity: loading ? 0.5 : 1,
    transition: 'opacity 150ms',
  };

  return (
    <div style={rowStyle}>
      <span style={nameStyle}>{keyName}</span>
      <span style={badgeStyle}>
        {mode === 'masked' ? 'sk-****…' : badge.label}
      </span>
      <button
        type="button"
        style={btnStyle}
        disabled={loading}
        aria-label={`Toggle visibility for ${keyName}: currently ${mode}, switch to ${nextMode}`}
        onClick={() => onToggle(keyName, nextMode)}
      >
        {loading ? '⟳' : badge.icon} cycle
      </button>
    </div>
  );
}
