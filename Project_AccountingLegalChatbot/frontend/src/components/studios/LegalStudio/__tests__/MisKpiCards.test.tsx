import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MisKpiCards } from '../MisKpiCards';

describe('MisKpiCards', () => {
  it('renders KPI cards with labels and values', () => {
    render(
      <MisKpiCards kpis={[
        { label: 'Revenue', value: 'AED 1,000,000' },
        { label: 'Net Profit', value: 'AED 200,000' },
      ]} />
    );
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('AED 1,000,000')).toBeInTheDocument();
    expect(screen.getByText('Net Profit')).toBeInTheDocument();
  });

  it('renders nothing when kpis is empty', () => {
    const { container } = render(<MisKpiCards kpis={[]} />);
    const cards = container.querySelectorAll('[data-testid="kpi-card"]');
    expect(cards.length).toBe(0);
  });
});
