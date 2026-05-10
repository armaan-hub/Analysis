import { render, screen, fireEvent } from '@testing-library/react';
import ApiKeyRow from './ApiKeyRow';

const CYCLE: Array<'masked' | 'hidden' | 'none'> = ['masked', 'hidden', 'none'];

test('renders key name', () => {
  render(<ApiKeyRow keyName="NVIDIA_API_KEY" mode="masked" onToggle={() => {}} />);
  expect(screen.getByText(/NVIDIA_API_KEY/i)).toBeInTheDocument();
});

test('renders masked badge when mode is masked', () => {
  render(<ApiKeyRow keyName="NVIDIA_API_KEY" mode="masked" onToggle={() => {}} />);
  expect(screen.getByText(/masked|sk-\*+/i)).toBeInTheDocument();
});

test('calls onToggle with next mode on button click', () => {
  const onToggle = vi.fn();
  render(<ApiKeyRow keyName="NVIDIA_API_KEY" mode="masked" onToggle={onToggle} />);
  fireEvent.click(screen.getByRole('button'));
  expect(onToggle).toHaveBeenCalledWith('NVIDIA_API_KEY', 'hidden');
});

test('cycles through masked→hidden→none→masked', () => {
  const onToggle = vi.fn();
  for (let i = 0; i < 3; i++) {
    const { unmount } = render(<ApiKeyRow keyName="K" mode={CYCLE[i]} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenLastCalledWith('K', CYCLE[(i + 1) % 3]);
    unmount();
  }
});

test('button disabled when loading', () => {
  render(<ApiKeyRow keyName="NVIDIA_API_KEY" mode="masked" onToggle={() => {}} loading />);
  expect(screen.getByRole('button')).toBeDisabled();
});
