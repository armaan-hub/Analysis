import { render, screen, fireEvent } from '@testing-library/react';
import ModeSelector from './ModeSelector';

test('renders all 4 mode tabs', () => {
  render(<ModeSelector value="chat" onChange={() => {}} />);
  expect(screen.getByText(/Chat/i)).toBeInTheDocument();
  expect(screen.getByText(/Research/i)).toBeInTheDocument();
  expect(screen.getByText(/Analysis/i)).toBeInTheDocument();
  expect(screen.getByText(/Council/i)).toBeInTheDocument();
});

test('calls onChange when tab is clicked', () => {
  const onChange = vi.fn();
  render(<ModeSelector value="chat" onChange={onChange} />);
  fireEvent.click(screen.getByText(/Research/i));
  expect(onChange).toHaveBeenCalledWith('research');
});

test('active tab has different visual state', () => {
  const { rerender } = render(<ModeSelector value="chat" onChange={() => {}} />);
  const chatTab = screen.getByText(/Chat/i).closest('button');
  // active tab has both class 'active' and aria-selected="true"
  expect(chatTab).toHaveClass('active');
  expect(chatTab?.getAttribute('aria-selected')).toBe('true');
  rerender(<ModeSelector value="research" onChange={() => {}} />);
  const researchTab = screen.getByText(/Research/i).closest('button');
  // just verify it doesn't throw when switching
  expect(researchTab).toBeInTheDocument();
});

test('disabled prop prevents onChange', () => {
  const onChange = vi.fn();
  render(<ModeSelector value="chat" onChange={onChange} disabled />);
  fireEvent.click(screen.getByText(/Research/i));
  expect(onChange).not.toHaveBeenCalled();
});

test('switching from research back to chat fires onChange with chat', () => {
  const onChange = vi.fn();
  render(<ModeSelector value="research" onChange={onChange} />);
  fireEvent.click(screen.getByText(/Chat/i));
  expect(onChange).toHaveBeenCalledWith('chat');
});
