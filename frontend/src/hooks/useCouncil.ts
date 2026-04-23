import { useState, useCallback, useRef } from 'react';
import { councilEndpoint } from '../lib/api';

export interface ExpertState { name: string; role?: string; content: string; status: 'idle'|'thinking'|'final' }

export function useCouncil() {
  const [experts, setExperts] = useState<Record<string, ExpertState>>({});
  const [synthesis, setSynthesis] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(async (question: string, baseAnswer: string) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setExperts({}); setSynthesis(''); setError(null); setRunning(true);
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const res = await fetch(councilEndpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ question, base_answer: baseAnswer }),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      reader = res.body?.getReader();
      if (!reader) throw new Error('no stream');
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'council_expert') {
              setExperts(prev => {
                const cur: ExpertState = prev[evt.expert] ?? { name: evt.expert, role: evt.role, content: '', status: 'thinking' };
                const next = { ...cur };
                if (evt.status === 'thinking') next.status = 'thinking';
                if (evt.delta) next.content = cur.content + evt.delta;
                if (evt.final) { next.content = evt.content; next.status = 'final'; }
                return { ...prev, [evt.expert]: next };
              });
            } else if (evt.type === 'council_synthesis') {
              if (evt.delta) setSynthesis(s => s + evt.delta);
              if (evt.final) setSynthesis(evt.content);
            } else if (evt.type === 'council_error') {
              setError(evt.error);
            } else if (evt.type === 'done') {
              if (evt.error) setError(evt.error);
              setRunning(false);
            }
          } catch { /* skip malformed event */ }
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        // cancelled — do nothing
      } else {
        setError(String(e));
      }
    } finally {
      await reader?.cancel().catch(() => {});
      setRunning(false);
    }
  }, []);

  const abort = useCallback(() => { abortRef.current?.abort(); }, []);

  return { experts, synthesis, running, error, run, abort };
}
