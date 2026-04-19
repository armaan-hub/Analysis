import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_BASE, API, fmtTime, type Message, type Source } from '../../../lib/api';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { SourcePeeker } from './SourcePeeker';
import { type ChatMode } from './ModeDropdown';
import { DomainChip, type DomainLabel } from './DomainChip';

type Domain = 'general' | 'finance' | 'law' | 'audit' | 'vat' | 'aml' | 'legal' | 'corporate_tax';

const DOMAIN_KEYWORDS: Array<{ keywords: string[]; domain: Domain }> = [
  { keywords: ['vat', 'trn', 'fta', '5%', 'zero-rated', 'zero rated', 'exempt supply', 'input tax', 'output tax', 'export service', 'export of services', 'zero-rated supply', 'zero rated export', 'place of supply', 'recipient outside uae', 'import of services', 'designated zone', 'reverse charge', 'article 29', 'article 31'], domain: 'vat' },
  { keywords: ['corporate tax', 'ct ', '9%', 'taxable income', 'decree-law 47', 'small business relief'], domain: 'corporate_tax' },
  { keywords: ['aml', 'kyc', ' str ', 'cft', 'suspicious', 'beneficial owner'], domain: 'aml' },
  { keywords: ['audit', 'isa ', 'internal control', 'assurance', 'auditor'], domain: 'audit' },
  { keywords: ['ifrs', 'balance sheet', 'financial statement', 'revenue recognition'], domain: 'finance' },
  { keywords: ['legal', 'contract', 'civil law', 'employment law', 'company law'], domain: 'legal' },
];

function detectDomain(text: string): Domain | null {
  const lower = text.toLowerCase();
  for (const { keywords, domain } of DOMAIN_KEYWORDS) {
    if (keywords.some(kw => lower.includes(kw))) return domain;
  }
  return null;
}

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface LegalStudioProps {
  onConversationsChange?: (convos: Conversation[]) => void;
  initialConversationId?: string;
}

export function LegalStudio({ onConversationsChange, initialConversationId }: LegalStudioProps = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false);
  const [webSearching, setWebSearching] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(initialConversationId ?? null);
  const [domain, setDomain] = useState<Domain>('law');
  const [mode, setMode] = useState<ChatMode>('normal');
  const [detectedDomain, setDetectedDomain] = useState<DomainLabel | null>(null);
  const [searchParams] = useSearchParams();

  const initialValue = searchParams.get('q') ?? '';

  // Load message history when an existing conversation is opened from sidebar
  useEffect(() => {
    if (!initialConversationId) return;
    API.get(`/api/chat/conversations/${initialConversationId}/messages`)
      .then(r => {
        const loaded: Message[] = (r.data || []).map((m: { role: string; content: string; created_at: string; sources?: Source[] }) => ({
          role: (m.role === 'assistant' ? 'assistant' : 'user') as Message['role'],
          text: m.content,
          time: new Date(m.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
          sources: m.sources,
        }));
        setMessages(loaded);
      })
      .catch(() => {});
  }, [initialConversationId]);

  // Fetch conversation list after each message for sidebar
  useEffect(() => {
    if (!onConversationsChange) return;
    API.get('/api/chat/conversations')
      .then(r => onConversationsChange(r.data || []))
      .catch(() => {});
  }, [messages.length, onConversationsChange]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    // Client-side domain detection before API call
    const clientDomain = detectDomain(text);
    if (clientDomain) setDomain(clientDomain);

    const userMsg: Message = { role: 'user', text, time: fmtTime() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    // Placeholder assistant message for streaming
    setMessages(prev => [...prev, { role: 'ai', text: '', time: fmtTime() }]);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000);

      const response = await fetch(`${API_BASE}/api/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          stream: true,
          domain,
          mode,
          domain_override: domain || undefined,
        }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({} as { detail?: string })) as { detail?: string };
        throw new Error(errData.detail || `Server error ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let evt: {
            type: string;
            content?: string;
            conversation_id?: string;
            detected_domain?: string;
            sources?: Source[];
            message?: string;
          } | null = null;
          try { evt = JSON.parse(line.slice(6)); } catch { continue; }
          if (!evt) continue;

          if (evt.type === 'meta') {
            if (evt.conversation_id && !conversationId) setConversationId(evt.conversation_id);
            if (evt.detected_domain) {
              setDomain(evt.detected_domain as Domain);
              setDetectedDomain(evt.detected_domain as DomainLabel);
            }
            if ((evt as unknown as { message_id?: string }).message_id) {
              const msgId = (evt as unknown as { message_id: string }).message_id;
              setMessages(prev => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = { ...last, id: msgId };
                return updated;
              });
            }
          } else if (evt.type === 'status' && (evt as unknown as { type: string; status?: string }).status === 'searching_web') {
            setWebSearching(true);
          } else if (evt.type === 'chunk' && evt.content) {
            setWebSearching(false);
            const chunk = evt.content;
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, text: last.text + chunk };
              return updated;
            });
          } else if (evt.type === 'sources' && evt.sources) {
            const srcs = evt.sources;
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, sources: srcs };
              return updated;
            });
          } else if (evt.type === 'error') {
            throw new Error(evt.message || 'Streaming error');
          } else if (evt.type === 'queries_run' && (evt as unknown as { queries?: string[] }).queries) {
            const queries = (evt as unknown as { queries: string[] }).queries;
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, queriesRun: queries };
              return updated;
            });
          } else if (evt.type === 'status' && (evt as unknown as { status?: string }).status === 'researching') {
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, isResearching: true };
              return updated;
            });
          }
        }
      }
    } catch {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'ai' && last.text === '') {
          return [...prev.slice(0, -1), {
            role: 'ai' as const,
            text: 'An error occurred. Please try again.',
            time: fmtTime(),
          }];
        }
        return prev;
      });
    } finally {
      setLoading(false);
      setWebSearching(false);
    }
  }, [loading, conversationId, domain, mode]);

  const handleSourceClick = (source: Source) => {
    if (activeSource?.source === source.source) {
      setActiveSource(null);
      setSourcePanelOpen(false);
    } else {
      setActiveSource(source);
      setSourcePanelOpen(true);
    }
  };

  const activeSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sources && messages[i].sources!.length > 0) {
        return messages[i].sources!;
      }
    }
    return [];
  }, [messages]);

  // Keep a ref so the loading effect can read the latest value without depending on it
  const activeSourcesRef = useRef(activeSources);
  activeSourcesRef.current = activeSources;

  // Open the sources panel only when a response finishes loading with sources.
  // Depends only on `loading` so message-state changes never re-trigger this.
  const prevLoadingRef = useRef(false);
  useEffect(() => {
    if (prevLoadingRef.current && !loading && activeSourcesRef.current.length > 0) {
      setSourcePanelOpen(true);
    }
    prevLoadingRef.current = loading;
  }, [loading]);

  return (
    <div className="legal-studio">
      <div className={`legal-studio__chat ${sourcePanelOpen ? 'legal-studio__chat--peeked' : ''}`}>
        {/* Domain chip (shown once classifier detects a domain) */}
        {detectedDomain && (
          <div style={{ padding: '16px 40px 0', flexShrink: 0 }}>
            <DomainChip
              value={detectedDomain}
              editable
              onChange={(d) => {
                setDetectedDomain(d);
                setDomain(d);
              }}
            />
          </div>
        )}

        <ChatMessages
          messages={messages}
          loading={loading}
          webSearching={webSearching}
          onSourceClick={handleSourceClick}
          activeSourceId={activeSource?.source}
        />
        <ChatInput
          onSend={sendMessage}
          disabled={loading}
          initialValue={initialValue}
          mode={mode}
          onModeChange={setMode}
        />
      </div>
      <SourcePeeker
        key={`source-peeker-${messages.length}`}
        sources={activeSources}
        isOpen={sourcePanelOpen}
        highlightedSource={activeSource?.source}
        onClose={() => { setSourcePanelOpen(false); setActiveSource(null); }}
      />
    </div>
  );
}
