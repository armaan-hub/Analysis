import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SettingsPage from '../SettingsPage';
import { API } from '../../lib/api';

vi.mock('../../lib/api', () => ({
  API: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  API_BASE: 'http://localhost:8001',
  getErrMsg: (_e: unknown, fallback: string) => fallback,
}));

const baseSettings = {
  llm_provider: 'nvidia',
  llm_model: 'meta/llama',
  temperature: 0.2,
  max_tokens: 2048,
  top_k_results: 6,
  providers: {
    nvidia: { api_key: '***', model: 'meta/llama', base_url: 'https://integrate.api.nvidia.com/v1', fast_api_key: '', fast_model: '' },
    local: { api_key: '', model: '', base_url: '', fast_api_key: '', fast_model: '' },
  },
};

const localScanData = {
  scan_time: null,
  cache_age_s: 0,
  servers: [
    { provider: 'ollama', base_url: 'http://localhost:11434', online: true, models: ['qwen2.5:7b', 'nomic-embed-text'], latency_ms: 22 },
    { provider: 'lmstudio', base_url: 'http://localhost:1234', online: false, models: [], latency_ms: 0 },
  ],
};

const embeddingConfig = {
  provider: 'nvidia',
  model: 'nv-embedqa-e5-v5',
  chunk_size: 1200,
  dimension: 1024,
  fingerprint: 'fp1',
  note: '',
};

const reindexStatus = {
  needs_reindex: false,
  documents_pending: 0,
  fingerprint: 'fp1',
};

const makeGetMock = (keysData?: Record<string, string>) =>
  (url: string) => {
    if (url === '/api/settings/current') return Promise.resolve({ data: baseSettings });
    if (url === '/api/documents/embedding-config') return Promise.resolve({ data: embeddingConfig });
    if (url === '/api/documents/reindex-status') return Promise.resolve({ data: reindexStatus });
    if (url === '/api/settings/local-scan') return Promise.resolve({ data: localScanData });
    if (url === '/api/settings/keys') return keysData
      ? Promise.resolve({ data: keysData })
      : Promise.reject(new Error('keys not mocked'));
    if (url.includes('/api/settings/providers/')) return Promise.resolve({ data: [] });
    return Promise.reject(new Error(`Unhandled GET: ${url}`));
  };

describe('SettingsPage local models section', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (API.get as any).mockImplementation(makeGetMock());

    (API.post as any).mockImplementation((url: string) => {
      if (url === '/api/settings/local-scan/refresh') return Promise.resolve({ data: localScanData });
      if (url === '/api/settings/providers/test') return Promise.resolve({ data: { success: true, message: 'ok', model: 'meta/llama' } });
      return Promise.reject(new Error(`Unhandled POST: ${url}`));
    });

    (API.put as any).mockResolvedValue({ data: {} });
  });

  it('renders online/offline local servers and allows selecting online server', async () => {
    render(<SettingsPage />);

    expect(await screen.findByText('Local Models')).toBeInTheDocument();
    expect(await screen.findByText('LM Studio')).toBeInTheDocument();
    expect(await screen.findByText('2 models')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Ollama'));
    const baseUrlInput = await screen.findByDisplayValue('http://localhost:11434');
    expect(baseUrlInput).toHaveValue('http://localhost:11434');
  });

  it('refreshes local scan when refresh button is clicked', async () => {
    render(<SettingsPage />);

    const refreshBtn = await screen.findByTitle('Refresh local model scan');
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(API.post).toHaveBeenCalledWith('/api/settings/local-scan/refresh');
    });
  });
});

describe('SettingsPage API key toggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (API.get as any).mockImplementation(
      makeGetMock({ NVIDIA_API_KEY: 'masked' }),
    );

    (API.post as any).mockImplementation((url: string) => {
      if (url === '/api/settings/local-scan/refresh') return Promise.resolve({ data: localScanData });
      if (url === '/api/settings/providers/test') return Promise.resolve({ data: { success: true, message: 'ok', model: 'meta/llama' } });
      return Promise.reject(new Error(`Unhandled POST: ${url}`));
    });

    (API.put as any).mockResolvedValue({ data: {} });
  });

  it('reverts mode to previous value on PUT failure', async () => {
    (API.put as any).mockRejectedValue(new Error('Network error'));

    render(<SettingsPage />);

    // Wait for the key row to appear (loading finishes)
    const toggleBtn = await screen.findByRole('button', {
      name: /toggle visibility for NVIDIA_API_KEY/i,
    });

    // Click to trigger optimistic update (masked → hidden) followed by PUT failure
    fireEvent.click(toggleBtn);

    // After PUT failure the mode should revert back to masked
    // (button aria-label reflects current mode)
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /toggle visibility for NVIDIA_API_KEY/i });
      expect(btn).toHaveAttribute('aria-label', expect.stringContaining('currently masked'));
    });

    // Error flash must be visible
    await waitFor(() => {
      expect(screen.getByText(/Failed to update key visibility/i)).toBeInTheDocument();
    });
  });
});
