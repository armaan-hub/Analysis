import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AuditOverlayProvider, useAuditOverlay } from '../../../../context/AuditOverlayContext';
import { AuditOverlay } from '../AuditOverlay';

function TestHarness() {
  const { open } = useAuditOverlay();
  return (
    <>
      <button onClick={() => open({
        summary: 'Net profit margin 12%',
        risk_flags: [{ severity: 'high', document: 'TB.pdf', finding: 'Negative equity' }],
        anomalies: [],
        compliance_gaps: [],
      })}>Open</button>
      <AuditOverlay />
    </>
  );
}

describe('AuditOverlay', () => {
  it('is not visible when closed', () => {
    render(
      <AuditOverlayProvider>
        <AuditOverlay />
      </AuditOverlayProvider>
    );
    expect(screen.queryByText(/Audit Overview/i)).not.toBeInTheDocument();
  });

  it('shows summary and risk flags after open()', () => {
    render(
      <AuditOverlayProvider>
        <TestHarness />
      </AuditOverlayProvider>
    );
    fireEvent.click(screen.getByText('Open'));
    expect(screen.getByText(/Audit Overview/i)).toBeInTheDocument();
    expect(screen.getByText(/Negative equity/i)).toBeInTheDocument();
  });

  it('minimizes to pill on minimize click', () => {
    render(
      <AuditOverlayProvider>
        <TestHarness />
      </AuditOverlayProvider>
    );
    fireEvent.click(screen.getByText('Open'));
    const minBtn = screen.getByRole('button', { name: /minimize/i });
    fireEvent.click(minBtn);
    expect(screen.queryByText(/Negative equity/i)).not.toBeInTheDocument();
    expect(screen.getByText('📊')).toBeInTheDocument();
  });

  it('closes on close button', () => {
    render(
      <AuditOverlayProvider>
        <TestHarness />
      </AuditOverlayProvider>
    );
    fireEvent.click(screen.getByText('Open'));
    const closeBtn = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    expect(screen.queryByText(/Audit Overview/i)).not.toBeInTheDocument();
  });
});
