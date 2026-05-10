import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '../lib/api';

interface EmbeddingStatus {
  provider: string;
  status: 'green' | 'yellow' | 'red';
  latency_ms: number;
  model: string;
  chunk_count: number;
  available_providers: string[];
}

export interface EmbeddingCardProps {
  onProviderChange?: (provider: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  green:  '#22c55e',
  yellow: '#eab308',
  red:    '#ef4444',
};

const STATUS_LABELS: Record<string, string> = {
  green:  'Good (<5s latency)',
  yellow: 'Slow (≥5s latency)',
  red:    'Error',
};

export default function EmbeddingCard({ onProviderChange }: EmbeddingCardProps) {
  const [status,   setStatus]   = useState<EmbeddingStatus | null>(null);
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [switching, setSwitching] = useState(false);
  const [toast,    setToast]    = useState<{ text: string; ok: boolean } | null>(null);

  const showToast = (text: string, ok: boolean) => {
    setToast({ text, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchStatus = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/settings/embedding-status`, { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: EmbeddingStatus = await res.json();
      setStatus(data);
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError(e instanceof Error ? e.message : 'Failed to load embedding status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchStatus(controller.signal);
    return () => controller.abort();
  }, [fetchStatus]);

  const handleProviderChange = async (provider: string) => {
    if (switching) return;
    if (!status || provider === status.provider) return;
    setSwitching(true);
    try {
      const res = await fetch(`${API_BASE}/api/settings/embedding-switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast(`Switched to ${provider}`, true);
      onProviderChange?.(provider);
      await fetchStatus();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Switch failed', false);
    } finally {
      setSwitching(false);
    }
  };

  const cardStyle: React.CSSProperties = {
    border: '1px solid var(--border, rgba(255,255,255,0.1))',
    borderRadius: '12px',
    padding: '20px 24px',
    background: 'var(--surface-2, rgba(255,255,255,0.04))',
    position: 'relative',
  };

  const fieldStyle: React.CSSProperties = {
    marginBottom: '12px',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-2, rgba(255,255,255,0.5))',
    marginBottom: '4px',
    display: 'block',
  };

  const valueStyle: React.CSSProperties = {
    fontSize: '0.88rem',
    color: 'var(--text-1, #fff)',
  };

  if (loading && !status) {
    return (
      <div style={cardStyle}>
        <div style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}>Loading embedding status…</div>
      </div>
    );
  }

  if (error && !status) {
    return (
      <div style={cardStyle}>
        <div style={{ color: 'var(--red, #ef4444)', fontSize: '0.85rem' }}>
          ⚠ Embedding service unavailable — {error}
        </div>
      </div>
    );
  }

  const s = status!;
  const dotColor = STATUS_COLORS[s.status] ?? STATUS_COLORS.red;
  const dotTitle = STATUS_LABELS[s.status] ?? s.status;

  return (
    <div style={cardStyle}>
      {/* Toast */}
      {toast && (
        <div style={{
          position: 'absolute', top: '12px', right: '16px',
          background: toast.ok ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
          border: `1px solid ${toast.ok ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)'}`,
          borderRadius: '8px', padding: '6px 14px',
          fontSize: '0.78rem', color: 'var(--text-1, #fff)',
        }}>
          {toast.ok ? '✓' : '✗'} {toast.text}
        </div>
      )}

      {/* Header row: provider + status dot */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <div
          data-status={s.status}
          title={dotTitle}
          style={{
            width: '10px', height: '10px', borderRadius: '50%',
            background: dotColor, flexShrink: 0,
            boxShadow: `0 0 6px ${dotColor}`,
          }}
        />
        <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>{s.provider}</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-2)', marginLeft: '4px' }}>
          {Math.round(s.latency_ms)}ms
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <div style={fieldStyle}>
          <label style={labelStyle} htmlFor="emb-model">Model</label>
          <input
            id="emb-model"
            type="text"
            className="settings-input"
            value={s.model}
            readOnly
            style={{ cursor: 'default', opacity: 0.85, fontFamily: 'monospace', fontSize: '0.78rem' }}
          />
        </div>

        <div style={fieldStyle}>
          <span style={labelStyle}>Vectors</span>
          <span style={valueStyle}>{s.chunk_count.toLocaleString()} vectors</span>
        </div>

        <div style={fieldStyle}>
          <span style={labelStyle}>Latency</span>
          <span style={{ ...valueStyle, color: dotColor }}>{s.latency_ms.toFixed(1)}ms</span>
        </div>

        <div style={fieldStyle}>
          <span style={labelStyle}>Status</span>
          <span style={{ ...valueStyle, color: dotColor }}>{dotTitle}</span>
        </div>
      </div>

      {/* Provider switcher */}
      <div style={fieldStyle}>
        <label style={labelStyle} htmlFor="embedding-provider-select">Switch Provider</label>
        <select
          id="embedding-provider-select"
          className="settings-input settings-select"
          value={s.provider}
          disabled={switching}
          onChange={e => void handleProviderChange(e.target.value)}
          style={{ opacity: switching ? 0.6 : 1, cursor: switching ? 'not-allowed' : 'pointer' }}
        >
          {s.available_providers.map(p => (
            /* label attribute sets the display text; empty body keeps DOM textContent
               empty so getByText won't match provider IDs in option nodes */
            <option key={p} value={p} label={p} />
          ))}
        </select>
        {switching && (
          <div style={{ fontSize: '0.75rem', color: 'var(--text-2)', marginTop: '4px' }}>
            ⟳ Switching provider…
          </div>
        )}
      </div>
    </div>
  );
}
