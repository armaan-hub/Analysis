import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_BASE, API, fmtTime, type Message, type Source } from '../../../lib/api';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { SourcePeeker } from './SourcePeeker';
import { SourcesSidebar, type SourceDoc } from './SourcesSidebar';
import { StudioPanel } from './StudioPanel';
import { ThreePaneLayout } from './ThreePaneLayout';
import { type ChatMode } from './ModePills';
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

interface Conversation { id: string; title: string; updated_at: string; }
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

  const [researchPhases, setResearchPhases] = useState<Array<{
    phase: string; message: string; sub_questions?: string[];
    progress?: number; total?: number; report?: string;
  }>>([]);
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

  // --- Document handlers ---
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
    } catch { /* ignore */ }
  }, []);

  const handleDocUpload = useCallback(async (files: FileList) => {
    for (const file of Array.from(files)) {
      const tempId = `uploading-${Date.now()}-${file.name}`;
      setDocs(prev => [...prev, {
        id: tempId, filename: file.name, source: file.name,
        status: 'uploading',
      }]);
      const fd = new FormData();
      fd.append('file', file);
      try {
        const res = await API.post('/api/documents/upload', fd);
        const doc = res.data;
        setDocs(prev => prev.map(d =>
          d.id === tempId ? {
            id: doc.id, filename: doc.original_name ?? doc.filename,
            source: doc.source ?? doc.filename, status: 'ready',
            summary: doc.summary, key_terms: doc.key_terms,
            file_size: doc.file_size,
          } : d
        ));
        setSelectedDocIds(prev => [...prev, doc.id]);
      } catch {
        setDocs(prev => prev.map(d =>
          d.id === tempId ? { ...d, status: 'error' } : d
        ));
      }
    }
  }, []);

  const handleDocPreview = useCallback((_id: string) => {
    // Preview handled by SourcePeeker or StudioPanel now
  }, []);

  // --- Load docs + conversations on mount ---
  useEffect(() => {
    API.get('/api/documents/').then(r => {
      const list = Array.isArray(r.data) ? r.data : (r.data.documents ?? []);
      setDocs(list.map((d: any) => ({
        id: d.id, filename: d.original_name ?? d.filename,
        source: d.source ?? d.filename, status: d.status === 'indexed' ? 'ready' : d.status,
        summary: d.summary, key_terms: d.key_terms,
        file_size: d.file_size,
      })));
    }).catch(() => {});
    API.get('/api/chat/conversations').then(r => {
      onConversationsChange?.(r.data ?? []);
    }).catch(() => {});
  }, [onConversationsChange]);

  // --- Load messages for existing conversation ---
  useEffect(() => {
    if (!initialConversationId) return;
    setConversationId(initialConversationId);
    API.get(`/api/chat/conversations/${initialConversationId}/messages`)
      .then(r => {
        const msgs = (r.data ?? []).map((m: any) => ({
          role: m.role === 'user' ? 'user' as const : 'ai' as const,
          text: m.content,
          time: fmtTime(),
          sources: m.sources ?? [],
          id: m.id,
        }));
        setMessages(msgs);
      })
      .catch(() => {});
  }, [initialConversationId]);

  // --- Audit handler ---
  const handleRunAudit = useCallback(async () => {
    if (selectedDocIds.length === 0) return;
    setAuditing(true);
    setAuditResult(null);
    try {
      const res = await API.post('/api/legal-studio/auditor', { document_ids: selectedDocIds });
      setAuditResult(res.data);
    } catch { /* ignore */ }
    setAuditing(false);
  }, [selectedDocIds]);

  // --- Analyst handoff ---
  const handleAnalystHandoff = useCallback(async () => {
    setHandingOff(true);
    try {
      const summary = messages.slice(-6).map(m => `${m.role}: ${m.text.slice(0, 200)}`).join('\n');
      await API.post('/api/legal-studio/sessions', {
        title: 'Legal → Finance Handoff',
        domain: 'finance',
        context_summary: summary,
      });
      window.location.href = '/finance';
    } catch { /* ignore */ }
    setHandingOff(false);
  }, [messages]);

  // --- Chat send ---
  const sendMessage = useCallback(async (text: string, attachedFiles?: File[]) => {
    // Pre-upload any quick-attached files
    if (attachedFiles && attachedFiles.length > 0) {
      for (const file of attachedFiles) {
        const fd = new FormData();
        fd.append('file', file);
        try {
          const res = await API.post('/api/documents/upload', fd);
          const doc = res.data;
          setDocs(prev => [...prev, {
            id: doc.id, filename: doc.original_name ?? doc.filename,
            source: doc.source ?? doc.filename, status: 'ready',
            summary: doc.summary, key_terms: doc.key_terms,
            file_size: doc.file_size,
          }]);
          setSelectedDocIds(prev => [...prev, doc.id]);
        } catch { /* upload error - continue with chat */ }
      }
    }

    const userDomain = detectDomain(text);
    if (userDomain) { setDomain(userDomain); }

    const userMsg: Message = { role: 'user', text, time: fmtTime() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setWebSearching(false);

    if (mode === 'deep_research') {
      setResearching(true);
      setResearchPhases([]);
      setResearchReport(null);
      try {
        const res = await API.post('/api/legal-studio/research', { query: text });
        const jobId = res.data.job_id;
        const evtSource = new EventSource(`${API_BASE}/api/legal-studio/research/${jobId}/stream`);
        evtSource.onmessage = (e) => {
          const data = JSON.parse(e.data);
          if (data.phase === 'done') {
            setResearchReport(data.report ?? '');
            setResearching(false);
            setLoading(false);
            evtSource.close();
            return;
          }
          setResearchPhases(prev => [...prev, data]);
        };
        evtSource.onerror = () => { evtSource.close(); setResearching(false); setLoading(false); };
      } catch {
        setResearching(false);
        setLoading(false);
      }
      return;
    }

    try {
      const body: any = {
        message: text, conversation_id: conversationId,
        stream: true, domain: userDomain ?? domain, mode,
      };
      const response = await fetch(`${API_BASE}/api/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const reader = response.body?.getReader();
      if (!reader) { setLoading(false); return; }

      let aiText = '';
      let sources: Source[] = [];
      const decoder = new TextDecoder();

      const aiMsg: Message = { role: 'ai', text: '', time: fmtTime() };
      setMessages(prev => [...prev, aiMsg]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.event === 'chunk' || evt.type === 'chunk') {
              aiText += evt.content ?? evt.data ?? '';
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], text: aiText };
                return copy;
              });
            } else if (evt.event === 'meta' || evt.type === 'meta') {
              if (evt.conversation_id) setConversationId(evt.conversation_id);
              if (evt.detected_domain) {
                const d = evt.detected_domain as DomainLabel;
                setDetectedDomain(d);
              }
            } else if (evt.event === 'sources' || evt.type === 'sources') {
              sources = evt.sources ?? evt.data ?? [];
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], sources };
                return copy;
              });
            } else if (evt.event === 'status' && evt.data === 'searching_web') {
              setWebSearching(true);
            } else if (evt.event === 'queries_run') {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], queriesRun: evt.queries ?? evt.data };
                return copy;
              });
            } else if (evt.event === 'done' || evt.type === 'done') {
              if (evt.message_id) {
                setMessages(prev => {
                  const copy = [...prev];
                  copy[copy.length - 1] = { ...copy[copy.length - 1], id: evt.message_id };
                  return copy;
                });
              }
            }
          } catch { /* skip unparseable lines */ }
        }
      }
    } catch { /* ignore */ }

    setLoading(false);
    setWebSearching(false);

    // Refresh conversations
    API.get('/api/chat/conversations').then(r => {
      onConversationsChange?.(r.data ?? []);
    }).catch(() => {});
  }, [conversationId, domain, mode, onConversationsChange]);

  // --- Source click handler ---
  const handleSourceClick = useCallback((source: Source) => {
    setActiveSource(source);
    setSourcePanelOpen(true);
  }, []);

  // Latest sources for SourcePeeker
  const activeSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sources && messages[i].sources!.length > 0) {
        return messages[i].sources!;
      }
    }
    return [];
  }, [messages]);

  // Auto-open source peeker when response finishes with sources
  const prevLoadingRef = useRef(false);
  const activeSourcesRef = useRef(activeSources);
  activeSourcesRef.current = activeSources;
  useEffect(() => {
    if (prevLoadingRef.current && !loading && activeSourcesRef.current.length > 0) {
      setSourcePanelOpen(true);
    }
    prevLoadingRef.current = loading;
  }, [loading]);

  // --- Render ---
  const centerContent = (
    <>
      {detectedDomain && (
        <div style={{ padding: '16px 40px 0', flexShrink: 0 }}>
          <DomainChip
            value={detectedDomain}
            editable
            onChange={(d) => { setDetectedDomain(d); setDomain(d as unknown as Domain); }}
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
              padding: '6px 14px', borderRadius: 'var(--s-r-sm)',
              background: 'rgba(168, 85, 247, 0.15)', color: '#a78bfa',
              border: '1px solid rgba(168, 85, 247, 0.3)', fontSize: 12,
              cursor: handingOff ? 'default' : 'pointer',
              opacity: handingOff ? 0.5 : 1, fontFamily: 'var(--s-font-ui)',
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
            padding: '6px 14px', borderRadius: 'var(--s-r-sm)',
            background: selectedDocIds.length > 0 ? 'var(--s-accent)' : 'rgba(255,255,255,0.06)',
            color: '#fff', border: 'none', fontSize: 12,
            cursor: selectedDocIds.length > 0 ? 'pointer' : 'default',
            opacity: selectedDocIds.length > 0 ? 1 : 0.5, fontFamily: 'var(--s-font-ui)',
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

      <div className={`legal-studio__chat ${sourcePanelOpen ? 'legal-studio__chat--peeked' : ''}`}
           style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
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
        <SourcePeeker
          key={`source-peeker-${messages.length}`}
          sources={activeSources}
          isOpen={sourcePanelOpen}
          highlightedSource={activeSource?.source}
          onClose={() => { setSourcePanelOpen(false); setActiveSource(null); }}
        />
      </div>

      <ChatInput
        onSend={sendMessage}
        disabled={loading}
        initialValue={initialValue}
        mode={mode}
        onModeChange={setMode}
      />
    </>
  );

  return (
    <ThreePaneLayout
      left={
        <SourcesSidebar
          docs={docs}
          selectedIds={selectedDocIds}
          onSelect={handleDocSelect}
          onDelete={handleDocDelete}
          onUpload={handleDocUpload}
          onPreview={handleDocPreview}
        />
      }
      center={centerContent}
      right={<StudioPanel sourceIds={selectedDocIds} />}
    />
  );
}