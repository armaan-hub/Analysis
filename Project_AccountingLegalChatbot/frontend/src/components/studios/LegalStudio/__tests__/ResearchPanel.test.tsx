import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ResearchPanel } from '../ResearchPanel';

describe('ResearchPanel', () => {
  it('renders empty state when idle', () => {
    render(<ResearchPanel steps={[]} answer={null} />);
    expect(screen.getByText(/Ask a question to begin deep research/i)).toBeInTheDocument();
  });

  it('renders steps', () => {
    render(<ResearchPanel steps={[{ text: 'Analyzing', status: 'done' }]} answer={null} />);
    expect(screen.getByText('Analyzing')).toHaveClass('research-step--done');
  });

  it('renders web and doc source lists when answer present', () => {
    render(
      <ResearchPanel
        steps={[{ text: 'done', status: 'done' }]}
        answer={{
          content: 'ans',
          sources: [{ filename: 'Policy.pdf', page: 4 }],
          web_sources: [{ title: 'UAE VAT Guide', url: 'https://example.com/vat' }],
        }}
      />,
    );
    expect(screen.getByText('UAE VAT Guide')).toBeInTheDocument();
    expect(screen.getByText(/Policy\.pdf/)).toBeInTheDocument();
  });
});
