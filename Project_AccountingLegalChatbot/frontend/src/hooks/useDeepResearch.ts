import { useCallback, useEffect, useRef, useState } from 'react';
import { deepResearchUrl } from '../lib/api';

export interface ResearchStep {
  text: string;
  status: 'done' | 'active' | 'error' | 'pending';
}

export interface ResearchAnswer {
  content: string;
  sources: Array<{ filename: string; page?: number }>;
  web_sources: Array<{ title?: string; url: string }>;
}

export function useDeepResearch(conversationId: string) {
  const [steps, setSteps] = useState<ResearchStep[]>([]);
  const [answer, setAnswer] = useState<ResearchAnswer | null>(null);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleFrame = (raw: string) => {
    if (!raw.startsWith('data: ')) return;
    try {
      const ev = JSON.parse(raw.slice(6));
      if (ev.type === 'step') {
        setSteps(prev => [...prev, { text: ev.text, status: 'done' }]);
      } else if (ev.type === 'answer') {
        setAnswer({
          content: ev.content,
          sources: ev.sources ?? [],
          web_sources: ev.web_sources ?? [],
        });
      } else if (ev.type === 'done') {
        setRunning(false);
      } else if (ev.type === 'error') {
        setSteps(prev => [...prev, { text: ev.text ?? 'Error', status: 'error' }]);
        setRunning(false);
      }
    } catch {
      /* malformed frame — ignore */
    }
  };

  // Abort in-flight fetch on unmount to prevent setState on unmounted component
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  const run = useCallback(async (query: string, selected_doc_ids: string[]) => {
    // Abort any prior request before setting state so its catch won't interfere
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setSteps([]);
    setAnswer(null);
    setRunning(true);

    try {
      const resp = await fetch(deepResearchUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ conversation_id: conversationId, query, selected_doc_ids }),
        signal: ac.signal,
      });
      if (!resp.ok || !resp.body) {
        if (!ac.signal.aborted) setRunning(false);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // Flush any remaining bytes and process leftover frame
          buf += decoder.decode();
          if (buf.trim()) handleFrame(buf.trim());
          break;
        }
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          handleFrame(frame.trim());
        }
      }
    } catch {
      if (!ac.signal.aborted) setRunning(false);
    }
  }, [conversationId]);

  return { steps, answer, running, run };
}
