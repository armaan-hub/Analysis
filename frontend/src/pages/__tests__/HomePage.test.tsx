import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { API } from '../../lib/api';
import HomePage from '../HomePage';

vi.mock('../../lib/api', () => ({
  API: { get: vi.fn(), delete: vi.fn() },
}));

const mockConversations = [
  { id: 'c1', title: 'VAT Review',    updated_at: '2026-04-27T10:00:00Z', message_count: 2, source_count: 3, domain: 'vat',          mode: 'fast'          },
  { id: 'c2', title: 'Corp Tax Deep', updated_at: '2026-04-26T10:00:00Z', message_count: 4, source_count: 8, domain: 'corporate_tax', mode: 'deep_research' },
  { id: 'c3', title: 'IFRS Analyst',  updated_at: '2026-04-25T10:00:00Z', message_count: 3, source_count: 5, domain: 'audit',         mode: 'analyst'       },
];

function setup() {
  (API.get as any).mockResolvedValue({ data: mockConversations });
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>
  );
}

describe('HomePage — title', () => {
  it('shows "Compliance and Analysis Studio" as the page heading', async () => {
    setup();
    expect(await screen.findByText(/Compliance and Analysis Studio/i)).toBeInTheDocument();
  });

  it('does NOT show "Legal Studio" anywhere', async () => {
    setup();
    await screen.findByText(/Compliance and Analysis Studio/i);
    expect(screen.queryByText(/Legal Studio/i)).not.toBeInTheDocument();
  });
});

describe('HomePage — mode mapping', () => {
  it('maps mode from API response onto each notebook', async () => {
    setup();
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.getByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
    const dots = await screen.findAllByTestId('mode-dot');
    expect(dots).toHaveLength(3);
  });
});

describe('HomePage — mode filter bar', () => {
  beforeEach(() => {
    (API.get as any).mockResolvedValue({ data: mockConversations });
  });

  it('renders all four filter tags', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    await screen.findByText('VAT Review'); // wait for render
    const allModesBtn = screen.getByRole('button', { name: /all modes/i });
    const fastBtn = screen.getByRole('button', { name: /^fast$/i });
    const deepBtn = screen.getByRole('button', { name: /deep research/i });
    const analystBtn = screen.getByRole('button', { name: /^analyst$/i });
    expect(allModesBtn).toBeInTheDocument();
    expect(fastBtn).toBeInTheDocument();
    expect(deepBtn).toBeInTheDocument();
    expect(analystBtn).toBeInTheDocument();
  });

  it('shows all notebooks by default', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.getByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
  });

  it('filters to fast notebooks only when Fast tag is clicked', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    const fastBtn = await screen.findByRole('button', { name: /^fast$/i });
    fastBtn.click();
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.queryByText('Corp Tax Deep')).not.toBeInTheDocument();
    expect(screen.queryByText('IFRS Analyst')).not.toBeInTheDocument();
  });

  it('filters to analyst notebooks only when Analyst tag is clicked', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    const analystBtn = await screen.findByRole('button', { name: /^analyst$/i });
    analystBtn.click();
    expect(await screen.findByText('IFRS Analyst')).toBeInTheDocument();
    expect(screen.queryByText('VAT Review')).not.toBeInTheDocument();
    expect(screen.queryByText('Corp Tax Deep')).not.toBeInTheDocument();
  });

  it('clicking All Modes resets filter to show all', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    const fastBtn = await screen.findByRole('button', { name: /^fast$/i });
    fastBtn.click();
    const allBtn = screen.getByRole('button', { name: /all modes/i });
    allBtn.click();
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.getByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
  });

  it('auto-resets to All when last active mode is deselected', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    const fastBtn = await screen.findByRole('button', { name: /^fast$/i });
    fastBtn.click(); // activate Fast
    fastBtn.click(); // deactivate Fast → should reset to All
    expect(await screen.findByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
  });
});
