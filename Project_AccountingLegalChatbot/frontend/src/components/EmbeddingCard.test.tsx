import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EmbeddingCard from './EmbeddingCard';

beforeEach(() => {
  vi.spyOn(global, 'fetch').mockImplementation((url: RequestInfo | URL) => {
    const urlStr = String(url);
    if (urlStr.includes('embedding-status')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          provider: 'nvidia',
          status: 'green',
          latency_ms: 45.2,
          model: 'nvidia/nv-embedqa-e5-v5',
          chunk_count: 7106,
          available_providers: ['nvidia', 'openai', 'local'],
        }),
      } as Response);
    }
    if (urlStr.includes('embedding-switch')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
    }
    return Promise.reject(new Error('Unknown URL'));
  });
});

afterEach(() => { vi.restoreAllMocks(); });

test('renders provider name after load', async () => {
  render(<EmbeddingCard />);
  await waitFor(() => expect(screen.getByText(/nvidia/i)).toBeInTheDocument());
});

test('shows green status indicator', async () => {
  render(<EmbeddingCard />);
  await waitFor(() => {
    const indicator = document.querySelector('[data-status="green"]')
      || screen.queryByText(/green/i)
      || screen.queryByTitle(/green/i);
    expect(indicator).toBeTruthy();
  });
});

test('shows chunk count', async () => {
  render(<EmbeddingCard />);
  await waitFor(() => expect(screen.getByText(/7[,.]?106/)).toBeInTheDocument());
});

test('calls embedding-switch when provider changed', async () => {
  render(<EmbeddingCard />);
  await waitFor(() => screen.getByRole('combobox'));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'openai' } });
  await waitFor(() => {
    const calls = (global.fetch as ReturnType<typeof vi.spyOn>).mock.calls as unknown[][];
    expect(calls.some((args: unknown[]) => String(args[0]).includes('embedding-switch'))).toBe(true);
  });
});

test('shows error state when fetch fails', async () => {
  vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Network error'));
  render(<EmbeddingCard />);
  await waitFor(() => expect(screen.getByText(/error|unavailable|failed/i)).toBeInTheDocument());
});
