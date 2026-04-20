import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, ScanSearch } from 'lucide-react';
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

type Domain = 'general' | 'finance' | 'law' | 'audit' | 'vat' | 'aml' | 'legal' | 'corporate_tax'
  | 'peppol' | 'e_invoicing' | 'labour' | 'commercial' | 'ifrs' | 'general_law';

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
    risk_flags: { severity: 'low' | 'medium' | 'high'; document: string; finding: string }[];
    anomalies: { severity: 'low' | 'medium' | 'high'; document: string; finding: string }[];
    compliance_gaps: { severity: 'low' | 'medium' | 'high'; document: string; finding: string }[];
    summary: string;
  } | null>(null);
  const [auditing, setAuditing] = useState(false);

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
        const doc = res.data.document ?? res.data;
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

  const handleDocPreview = useCallback((id: string) => {
    const doc = docs.find(d => d.id === id);
    if (doc) {
      setActiveSource({ source: doc.filename, page: '', score: 0, excerpt: doc.summary ?? '' });
      setSourcePanelOpen(true);
    }
  }, [docs]);

  // --- Load docs + conversations on mount ---
  useEffect(() => {
    // Never auto-load docs — user explicitly selects/uploads them per session
    setDocs([]);
    setSelectedDocIds([]);
    API.get('/api/chat/conversations').then(r => {
      onConversationsChange?.(r.data ?? []);
    }).catch(() => {});
  }, [initialConversationId, onConversationsChange]);

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

  // --- Chat send ---
  const sendMessage = useCallback(async (text: string, attachedFiles?: File[]) => {
    // Pre-upload any quick-attached files
    if (attachedFiles && attachedFiles.length > 0) {
      for (const file of attachedFiles) {
        const fd = new FormData();
        fd.append('file', file);
        try {
          const res = await API.post('/api/documents/upload', fd);
          const doc = res.data.document ?? res.data;
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
    if (userDomain) {
      setDomain(userDomain);
      setDetectedDomain(userDomain as DomainLabel);
    }

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
          if (!data.phase) return; // skip heartbeat events
          if (data.phase === 'completed') {
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
        <div className="legal-domain-chip-wrapper">
          <DomainChip
            value={detectedDomain}
            editable
            onChange={(d) => { setDetectedDomain(d); setDomain(d as Domain); }}
          />
        </div>
      )}

      {/* Toolbar */}
      <div className="legal-toolbar">
        {(mode === 'analyst' || domain === 'audit') && (
          <button
            type="button"
            className="legal-toolbar__btn legal-toolbar__btn--audit"
            onClick={handleRunAudit}
            disabled={selectedDocIds.length === 0 || auditing}
            aria-label={`Run audit on ${selectedDocIds.length} selected documents`}
          >
            {auditing
              ? <><Loader2 size={14} className="spin" style={{ verticalAlign: 'middle', marginRight: 4 }} />Auditing…</>
              : <><ScanSearch size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />Run Audit ({selectedDocIds.length})</>
            }
          </button>
        )}
      </div>

      {/* Scrollable chat area — audit result, messages, and research all scroll together */}
      <div className="legal-studio__chat legal-studio__chat-area">
        {auditResult && (
          <div className="legal-section-pad">
            <AuditorResultBubble
              risk_flags={auditResult.risk_flags}
              anomalies={auditResult.anomalies}
              compliance_gaps={auditResult.compliance_gaps}
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
          <div className="legal-section-pad">
            <ResearchBubble phases={researchPhases} report={researchReport} />
          </div>
        )}
      </div>

      {sourcePanelOpen && activeSources.length > 0 && (
        <SourcePeeker
          key={`source-peeker-${messages.length}`}
          sources={activeSources}
          isOpen={sourcePanelOpen}
          highlightedSource={activeSource?.source}
          onClose={() => { setSourcePanelOpen(false); setActiveSource(null); }}
        />
      )}

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
      right={<StudioPanel sourceIds={selectedDocIds} mode={mode} />}
    />
  );
}
