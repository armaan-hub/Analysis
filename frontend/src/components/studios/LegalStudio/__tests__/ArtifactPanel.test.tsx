import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ArtifactPanel } from '../ArtifactPanel';

describe('ArtifactPanel', () => {
  it('renders null when not open', () => {
    const { container } = render(
      <ArtifactPanel
        open={false}
        title="MIS Report"
        reportType="mis"
        content=""
        loading={false}
        onClose={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders loading state', () => {
    render(
      <ArtifactPanel
        open={true}
        title="MIS Report"
        reportType="vat"
        content=""
        loading={true}
        onClose={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText(/Generating/i)).toBeInTheDocument();
  });

  it('renders report title and export button when content available', () => {
    render(
      <ArtifactPanel
        open={true}
        title="VAT Return"
        reportType="vat"
        content="## VAT Return\nBox 1: AED 100,000"
        loading={false}
        onClose={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText('VAT Return')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(
      <ArtifactPanel
        open={true}
        title="Report"
        reportType="audit"
        content="content"
        loading={false}
        onClose={onClose}
        onExport={vi.fn()}
      />
    );
    const closeBtn = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
