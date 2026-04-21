import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConfirmReportCard } from '../ConfirmReportCard';

const defaultProps = {
  reportType: 'audit',
  reportLabel: 'ISA 700 Audit Report',
  entityName: 'ABC Trading LLC',
  periodEnd: 'FY ended 31 Dec 2024',
  documentsCount: 3,
  format: 'big4' as const,
  confidence: 'high' as const,
  onGenerate: vi.fn(),
  onEdit: vi.fn(),
};

describe('ConfirmReportCard', () => {
  it('renders report type label', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    expect(screen.getByText(/ISA 700 Audit Report/i)).toBeInTheDocument();
  });

  it('renders detected entity and period', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    expect(screen.getByText(/ABC Trading LLC/i)).toBeInTheDocument();
    expect(screen.getByText(/31 Dec 2024/i)).toBeInTheDocument();
  });

  it('calls onGenerate when Generate Report button clicked', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /Generate Report/i }));
    expect(defaultProps.onGenerate).toHaveBeenCalledWith({
      entityName: 'ABC Trading LLC',
      periodEnd: 'FY ended 31 Dec 2024',
      format: 'big4',
    });
  });

  it('shows edit fields when Edit Details clicked', () => {
    render(<ConfirmReportCard {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /Edit Details/i }));
    expect(screen.getByLabelText(/entity/i)).toBeInTheDocument();
  });

  it('shows low-confidence warning when confidence is low', () => {
    render(<ConfirmReportCard {...defaultProps} confidence="low" />);
    expect(screen.getByText(/Please verify/i)).toBeInTheDocument();
  });
});
