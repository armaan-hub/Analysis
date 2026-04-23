import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AnalystErrorBoundary } from '../AnalystErrorBoundary';

const Bomb = ({ shouldThrow }: { shouldThrow: boolean }) => {
  if (shouldThrow) throw new Error('boom');
  return <div>OK</div>;
};

describe('AnalystErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders children when no error', () => {
    render(
      <AnalystErrorBoundary>
        <Bomb shouldThrow={false} />
      </AnalystErrorBoundary>
    );
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('renders error UI when child throws', () => {
    render(
      <AnalystErrorBoundary>
        <Bomb shouldThrow={true} />
      </AnalystErrorBoundary>
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Analyst mode crashed/i)).toBeInTheDocument();
    expect(screen.getByText(/boom/i)).toBeInTheDocument();
  });

  it('calls onReset when Reset button is clicked', () => {
    const onReset = vi.fn();
    render(
      <AnalystErrorBoundary onReset={onReset}>
        <Bomb shouldThrow={true} />
      </AnalystErrorBoundary>
    );
    fireEvent.click(screen.getByRole('button', { name: /Reset Analyst/i }));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it('calls onError with error info when child throws', () => {
    const onError = vi.fn();
    render(
      <AnalystErrorBoundary onError={onError}>
        <Bomb shouldThrow={true} />
      </AnalystErrorBoundary>
    );
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'boom' }),
      expect.objectContaining({ componentStack: expect.any(String) })
    );
  });
});
