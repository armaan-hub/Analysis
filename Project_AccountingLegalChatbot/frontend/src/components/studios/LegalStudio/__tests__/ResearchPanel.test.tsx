import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ResearchPanel } from '../ResearchPanel';

describe('ResearchPanel (A-placeholder)', () => {
  it('renders empty state when no steps', () => {
    render(<ResearchPanel steps={[]} />);
    expect(screen.getByText(/Ask a question to begin deep research/i)).toBeInTheDocument();
  });

  it('renders each step with its status class', () => {
    render(
      <ResearchPanel
        steps={[
          { text: 'Analyzing', status: 'done' },
          { text: 'Searching', status: 'active' },
        ]}
      />,
    );
    expect(screen.getByText('Analyzing')).toHaveClass('research-step--done');
    expect(screen.getByText('Searching')).toHaveClass('research-step--active');
  });
});
