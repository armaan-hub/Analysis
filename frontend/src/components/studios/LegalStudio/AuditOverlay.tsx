import { useCallback, useRef } from 'react';
import { useAuditOverlay } from '../../../context/AuditOverlayContext';

const SEVERITY_COLOR: Record<string, string> = {
  high: '#e53e3e',
  medium: '#dd6b20',
  low: '#38a169',
};

export function AuditOverlay() {
  const { overlayState, result, position, close, minimize, restore, setPosition } = useAuditOverlay();
  const dragOffset = useRef<{ dx: number; dy: number } | null>(null);

  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (e.currentTarget.setPointerCapture) {
      e.currentTarget.setPointerCapture(e.pointerId);
    }
    dragOffset.current = { dx: e.clientX - position.x, dy: e.clientY - position.y };
  }, [position]);

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragOffset.current) return;
    setPosition({ x: e.clientX - dragOffset.current.dx, y: e.clientY - dragOffset.current.dy });
  }, [setPosition]);

  const onPointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    dragOffset.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  }, []);

  if (overlayState === 'closed' || !result) return null;

  if (overlayState === 'minimized') {
    return (
      <div
        role="button"
        aria-label="restore"
        onClick={restore}
        style={{
          position: 'fixed', left: position.x, top: position.y,
          width: 56, height: 56, borderRadius: '50%',
          background: 'var(--s-brand, #4299e1)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', zIndex: 1000, fontSize: 24, boxShadow: '0 4px 16px rgba(0,0,0,.2)',
        }}
      >📊</div>
    );
  }

  return (
    <div style={{
      position: 'fixed', left: position.x, top: position.y,
      width: 340, maxHeight: 420, background: 'var(--s-bg-2, #fff)',
      border: '1px solid var(--s-border, #e2e8f0)', borderRadius: 12,
      boxShadow: '0 8px 32px rgba(0,0,0,.15)', zIndex: 1000,
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Draggable header */}
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        style={{
          padding: '10px 12px', background: 'var(--s-bg-3, #f7fafc)',
          borderBottom: '1px solid var(--s-border)', cursor: 'grab',
          display: 'flex', alignItems: 'center', gap: 8, userSelect: 'none',
        }}
      >
        <span style={{ flex: 1, fontWeight: 600, fontSize: 13 }}>📊 Audit Overview</span>
        <button aria-label="minimize" onClick={minimize}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16 }}>—</button>
        <button aria-label="close" onClick={close}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16 }}>✕</button>
      </div>

      {/* Scrollable content */}
      <div style={{ overflowY: 'auto', padding: '12px', flex: 1 }}>
        {result.summary && (
          <p style={{ margin: '0 0 12px', fontSize: 13 }}>{result.summary}</p>
        )}

        {result.risk_flags.length > 0 && (
          <section>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Risk Flags</div>
            {result.risk_flags.map((f, i) => (
              <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 4, alignItems: 'flex-start' }}>
                <span style={{
                  background: SEVERITY_COLOR[f.severity] ?? '#718096', color: '#fff',
                  borderRadius: 4, padding: '1px 5px', fontSize: 10, whiteSpace: 'nowrap',
                }}>{f.severity.toUpperCase()}</span>
                <span style={{ fontSize: 12 }}>{f.finding}</span>
              </div>
            ))}
          </section>
        )}

        {result.anomalies.length > 0 && (
          <section style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Anomalies</div>
            {result.anomalies.map((a, i) => (
              <div key={i} style={{ fontSize: 12, marginBottom: 3 }}>• {a.finding}</div>
            ))}
          </section>
        )}

        {result.compliance_gaps.length > 0 && (
          <section style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Compliance Gaps</div>
            {result.compliance_gaps.map((g, i) => (
              <div key={i} style={{ fontSize: 12, marginBottom: 3 }}>• {g.finding}</div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}
