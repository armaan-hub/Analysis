import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useDeepResearch } from '../useDeepResearch';

let pushSse: (s: string) => void;
let closeSse: () => void;

beforeEach(() => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      pushSse = (s: string) => controller.enqueue(encoder.encode(s));
      closeSse = () => controller.close();
    },
  });
  global.fetch = vi.fn().mockResolvedValue({ ok: true, body: stream } as any);
});

describe('useDeepResearch', () => {
  it('starts empty', () => {
    const { result } = renderHook(() => useDeepResearch('c1'));
    expect(result.current.steps).toEqual([]);
    expect(result.current.answer).toBeNull();
    expect(result.current.running).toBe(false);
  });

  it('accumulates steps and stores answer on run()', async () => {
    const { result } = renderHook(() => useDeepResearch('c1'));

    act(() => { result.current.run('what is UAE VAT?', []); });

    await waitFor(() => expect(result.current.running).toBe(true));

    act(() => { pushSse('data: ' + JSON.stringify({ type: 'step', text: 'Analyzing query...' }) + '\n\n'); });
    act(() => { pushSse('data: ' + JSON.stringify({ type: 'step', text: 'Searching: uae vat' }) + '\n\n'); });
    act(() => { pushSse('data: ' + JSON.stringify({ type: 'answer', content: 'VAT is 5%', sources: [], web_sources: [{ url: 'u' }] }) + '\n\n'); });
    act(() => { pushSse('data: ' + JSON.stringify({ type: 'done' }) + '\n\n'); });
    act(() => { closeSse(); });

    await waitFor(() => expect(result.current.running).toBe(false));
    expect(result.current.steps.map(s => s.text)).toEqual([
      'Analyzing query...', 'Searching: uae vat',
    ]);
    expect(result.current.answer?.content).toBe('VAT is 5%');
  });
});
