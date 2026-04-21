import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../lib/api', () => ({
  getConversation: vi.fn(),
  patchConversationMode: vi.fn(),
}));

import * as api from '../../lib/api';
import { useNotebookMode } from '../useNotebookMode';

describe('useNotebookMode', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('defaults to fast with no conversation id', () => {
    const { result } = renderHook(() => useNotebookMode(null));
    expect(result.current.mode).toBe('fast');
  });

  it('loads mode from the backend when conversation id changes', async () => {
    (api.getConversation as any).mockResolvedValue({ mode: 'analyst' });
    const { result } = renderHook(() => useNotebookMode('c1'));
    await waitFor(() => expect(result.current.mode).toBe('analyst'));
    expect(api.getConversation).toHaveBeenCalledWith('c1');
  });

  it('falls back to fast if the backend returns no mode', async () => {
    (api.getConversation as any).mockResolvedValue({});
    const { result } = renderHook(() => useNotebookMode('c1'));
    await waitFor(() => expect(result.current.mode).toBe('fast'));
  });

  it('updates local state immediately and calls PATCH in background', async () => {
    (api.getConversation as any).mockResolvedValue({ mode: 'fast' });
    (api.patchConversationMode as any).mockResolvedValue(undefined);
    const { result } = renderHook(() => useNotebookMode('c1'));
    await waitFor(() => expect(result.current.mode).toBe('fast'));

    await act(async () => {
      await result.current.setMode('deep_research');
    });

    expect(result.current.mode).toBe('deep_research');
    expect(api.patchConversationMode).toHaveBeenCalledWith('c1', 'deep_research');
  });
});
