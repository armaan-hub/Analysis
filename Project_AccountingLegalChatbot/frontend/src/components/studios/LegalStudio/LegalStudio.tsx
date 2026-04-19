import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_BASE, API, fmtTime, type Message, type Source } from '../../../lib/api';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { SourcePeeker } from './SourcePeeker';
import { SourcesSidebar, type SourceDoc } from './SourcesSidebar';
import { PreviewPane } from './PreviewPane';
import { type ChatMode } from './ModeDropdown';
import { DomainChip, type DomainLabel } from './DomainChip';
import { AuditorResultBubble } from './AuditorResultBubble';
import { ResearchBubble } from './ResearchBubble';

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

  const [docs, setDocs] = useState<SourceDoc[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);

  const [researchPhases, setResearchPhases] = useState<Array<{ phase: string; message: string; sub_questions?: string[]; progress?: number; total?: number; report?: string }>>([]);
  const [researchReport, setResearchReport] = useState<string | null>(null);
  const [researching, setResearching] = useState(false);

  const [auditResult, setAuditResult] = useState<{
    risk_flags: { severity: string; document: string; finding: string }[];
    anomalies: { severity: string; document: string; finding: string }[];
    compliance_gaps: { severity: string; document: string; finding: string }[];
    summary: string;
  } | null>(null);
  const [auditing, setAuditing] = useState(false);
  const [handingOff, setHandingOff] = useState(false);

  const initialValue = searchParams.get('q') ?? '';

  // --- Document handlers for SourcesSidebar ---
  const handleDocSelect = useCallback((id: string) => {
    setSelectedDocIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }, []);

  const handleDocDelete = useCallback(async (id: string) => {
    try {
      await API.delete(`/api/documents/${id}`);
      setDocs(prev => prev.filter(d => d.id !== id));
      setSelectedDocIds(prev => prev.filter(x => x !== id));
      if (previewDocId === id) setPreviewDocId(null);
    } catch { /* ignore */ }
  }, [previewDocId]);

  const handleDocUpload = useCallback(async (files: FileList) => {
    for (const file of Array.from(files)) {
      const fd = new FormData();
      fd.append('file', file);
      const tempId = crypto.randomUUID();
      setDocs(prev => [...prev, { id: tempId, filename: file.name, source: 'upload', status: 'uploading' }]);
      try {
        const resp = await API.post('/api/documents/upload', fd);
        const doc = resp.data.document;
        setDocs(prev => prev.map(d => d.id === tempId ? {
          id: doc.id,
          filename: doc.original_name,
          summary: doc.summary,
          key_terms: doc.key_terms,
          source: doc.source || 'upload',
          status: 'ready' as const,
        } : d));
      } catch {
        setDocs(prev => prev.map(d => d.id === tempId ? { ...d, status: 'error' as const } : d));
      }
    }
  }, []);

  const handleDocPreview = useCallback((id: string) => {
    setPreviewDocId(prev => prev === id ? null : id);
  }, []);

  const handleRunAudit = useCallback(async () => {
    if (selectedDocIds.length === 0 || auditing) return;
    setAuditing(true);
    setAuditResult(null);
    try {
      const resp = await API.post('/api/legal-studio/auditor', { document_ids: selectedDocIds });
      setAuditResult(resp.data);
    } catch {
      setAuditResult({ risk_flags: [], anomalies: [], compliance_gaps: [], summary: 'Audit failed. Please try again.' });
    } finally {
      setAuditing(false);
    }
  }, [selectedDocIds, auditing]);

  // Load documents on mount
  useEffect(() => {
    API.get('/api/documents').then(r => {
      const loaded: SourceDoc[] = (r.data || []).map((d: any) => ({
        id: d.id,
        filename: d.original_name || d.filename,
        summary: d.summary,
        key_terms: d.key_terms,
        source: d.source || 'upload',
        status: 'ready' as const,
      }));
      setDocs(loaded);
    }).catch(() => {});
  }, []);

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

    // Deep research mode — use research pipeline instead of normal chat
    if (mode === 'deep_research') {
      setResearching(true);
      setResearchPhases([]);
      setResearchReport(null);
      try {
        const startResp = await API.post('/api/legal-studio/research', { query: text });
        const jobId = startResp.data.job_id;

        // Connect to SSE stream
        const evtSource = new EventSource(`${API_BASE}/api/legal-studio/research/${jobId}/stream`);
        evtSource.onmessage = (e) => {
          try {
            const data = JSON.parse(e.data);
            if (data.type === 'heartbeat') return;
            setResearchPhases(prev => [...prev, data]);
            if (data.report) {
              setResearchReport(data.report);
              setMessages(prev => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = { ...last, text: data.report };
                return updated;
              });
            }
            if (data.phase === 'completed' || data.phase === 'failed') {
              evtSource.close();
              setResearching(false);
              setLoading(false);
            }
          } catch { /* ignore parse errors */ }
        };
        evtSource.onerror = () => {
          evtSource.close();
          setResearching(false);
          setLoading(false);
        };
      } catch {
        setResearching(false);
        setLoading(false);
      }
      return; // Skip normal chat flow
    }

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

  const handleAnalystHandoff = useCallback(async () => {
    if (handingOff) return;
    setHandingOff(true);
    try {
      const recentMsgs = messages.slice(-4).map(m => `${m.role}: ${m.text.slice(0, 200)}`).join('\n');
      const resp = await API.post('/api/legal-studio/sessions', {
        title: 'Analyst handoff from Legal Studio',
        domain: 'finance',
        context_summary: recentMsgs || 'Legal analysis session',
      });
      const { conversation_id } = resp.data;
      window.open(`/finance-studio?conversation=${conversation_id}`, '_blank');
    } catch {
      // Silently fail - user can try again
    } finally {
      setHandingOff(false);
    }
  }, [messages, handingOff]);

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
    <div className="legal-studio" style={{ display: 'flex', height: '100%' }}>
      <SourcesSidebar
        docs={docs}
        selectedIds={selectedDocIds}
        onSelect={handleDocSelect}
        onDelete={handleDocDelete}
        onUpload={handleDocUpload}
        onPreview={handleDocPreview}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
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

          {/* Toolbar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 40px 0', flexShrink: 0 }}>
            {mode === 'analyst' && (
              <button
                type="button"
                onClick={handleAnalystHandoff}
                disabled={handingOff}
                aria-label="Hand off conversation to Finance Studio"
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--s-r-sm)',
                  background: 'rgba(168, 85, 247, 0.15)',
                  color: '#a78bfa',
                  border: '1px solid rgba(168, 85, 247, 0.3)',
                  fontSize: 12,
                  cursor: handingOff ? 'default' : 'pointer',
                  opacity: handingOff ? 0.5 : 1,
                  fontFamily: 'var(--s-font-ui)',
                }}
              >
                {handingOff ? '⏳ Handing off…' : '📊 Hand off to Finance Studio'}
              </button>
            )}
            <button
              type="button"
              onClick={handleRunAudit}
              disabled={selectedDocIds.length === 0 || auditing}
              aria-label={`Run audit on ${selectedDocIds.length} selected documents`}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--s-r-sm)',
                background: selectedDocIds.length > 0 ? 'var(--s-accent)' : 'rgba(255,255,255,0.06)',
                color: '#fff',
                border: 'none',
                fontSize: 12,
                cursor: selectedDocIds.length > 0 ? 'pointer' : 'default',
                opacity: selectedDocIds.length > 0 ? 1 : 0.5,
                fontFamily: 'var(--s-font-ui)',
              }}
            >
              {auditing ? '⏳ Auditing…' : `🔎 Run Audit (${selectedDocIds.length})`}
            </button>
          </div>
          {auditResult && (
            <div style={{ padding: '8px 40px' }}>
              <AuditorResultBubble
                risk_flags={auditResult.risk_flags as any}
                anomalies={auditResult.anomalies as any}
                compliance_gaps={auditResult.compliance_gaps as any}
                summary={auditResult.summary}
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
          {(researching || researchReport) && (
            <div style={{ padding: '8px 40px' }}>
              <ResearchBubble phases={researchPhases} report={researchReport} />
            </div>
          )}
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
      <PreviewPane docId={previewDocId} onClose={() => setPreviewDocId(null)} />
    </div>
  );
}
