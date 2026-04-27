import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { NotebookCard, type Notebook } from '../NotebookCard';

const baseNotebook: Notebook = {
  id: 'nb-1',
  title: 'Test Notebook',
  updated_at: '2026-04-27T00:00:00Z',
};

describe('NotebookCard — mode dot', () => {
  it('renders no mode dot when mode is undefined', () => {
    render(
      <NotebookCard notebook={baseNotebook} onClick={() => {}} />
    );
    expect(screen.queryByTestId('mode-dot')).not.toBeInTheDocument();
  });

  it('renders a mode dot when mode is "fast"', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'fast' }} onClick={() => {}} />
    );
    const dot = screen.getByTestId('mode-dot');
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveStyle({ background: '#f59e0b', boxShadow: '0 0 6px #f59e0b' });
  });

  it('renders a mode dot when mode is "deep_research"', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'deep_research' }} onClick={() => {}} />
    );
    const dot = screen.getByTestId('mode-dot');
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveStyle({ background: '#6366f1', boxShadow: '0 0 6px #6366f1' });
  });

  it('renders a mode dot when mode is "analyst"', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'analyst' }} onClick={() => {}} />
    );
    const dot = screen.getByTestId('mode-dot');
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveStyle({ background: '#10b981', boxShadow: '0 0 6px #10b981' });
  });

  it('renders no dot for an unknown mode value', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'unknown_mode' as any }} onClick={() => {}} />
    );
    expect(screen.queryByTestId('mode-dot')).not.toBeInTheDocument();
  });
});
