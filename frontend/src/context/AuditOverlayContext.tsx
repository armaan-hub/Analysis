import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

export interface AuditResult {
  summary: string;
  risk_flags: Array<{ severity: 'low' | 'medium' | 'high'; document: string; finding: string }>;
  anomalies: Array<{ severity: 'low' | 'medium' | 'high'; document: string; finding: string }>;
  compliance_gaps: Array<{ severity: 'low' | 'medium' | 'high'; document: string; finding: string }>;
}

type OverlayState = 'full' | 'minimized' | 'closed';

interface AuditOverlayCtx {
  overlayState: OverlayState;
  result: AuditResult | null;
  position: { x: number; y: number };
  open: (result: AuditResult) => void;
  close: () => void;
  minimize: () => void;
  restore: () => void;
  setPosition: (pos: { x: number; y: number }) => void;
}

const AuditOverlayContext = createContext<AuditOverlayCtx | null>(null);

export function AuditOverlayProvider({ children }: { children: ReactNode }) {
  const [overlayState, setOverlayState] = useState<OverlayState>('closed');
  const [result, setResult] = useState<AuditResult | null>(null);
  const [position, setPosition] = useState({ x: 20, y: 20 });

  const open = useCallback((r: AuditResult) => {
    setResult(r);
    setOverlayState('full');
  }, []);

  const close = useCallback(() => setOverlayState('closed'), []);
  const minimize = useCallback(() => setOverlayState('minimized'), []);
  const restore = useCallback(() => setOverlayState('full'), []);

  return (
    <AuditOverlayContext.Provider value={{ overlayState, result, position, open, close, minimize, restore, setPosition }}>
      {children}
    </AuditOverlayContext.Provider>
  );
}

export function useAuditOverlay() {
  const ctx = useContext(AuditOverlayContext);
  if (!ctx) throw new Error('useAuditOverlay must be used inside AuditOverlayProvider');
  return ctx;
}
