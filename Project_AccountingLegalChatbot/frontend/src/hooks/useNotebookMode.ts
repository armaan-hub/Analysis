import { useCallback, useEffect, useRef, useState } from 'react';
import { getConversation, patchConversationMode } from '../lib/api';
import type { ChatMode } from '../components/studios/LegalStudio/ModePills';

export function useNotebookMode(conversationId: string | null) {
  const [mode, setModeLocal] = useState<ChatMode>('fast');
  const manuallySet = useRef(false);

  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    manuallySet.current = false;
    getConversation(conversationId)
      .then(r => {
        if (cancelled || manuallySet.current) return;
        const m = (r?.mode as ChatMode) ?? 'fast';
        setModeLocal(m === 'deep_research' || m === 'analyst' || m === 'fast' ? m : 'fast');
      })
      .catch(() => { /* leave default */ });
    return () => { cancelled = true; };
  }, [conversationId]);

  const setMode = useCallback(async (newMode: ChatMode) => {
    manuallySet.current = true;
    setModeLocal(newMode);
    if (conversationId) {
      try {
        await patchConversationMode(conversationId, newMode);
      } catch {
        /* best effort — UI already switched */
      }
    }
  }, [conversationId]);

  return { mode, setMode };
}
