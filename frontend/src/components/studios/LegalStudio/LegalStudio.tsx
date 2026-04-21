import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, ScanSearch } from 'lucide-react';
import { API_BASE, API, fmtTime, type Message, type ResearchMessage, type TextMessage, type Source } from '../../../lib/api';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { SourcePeeker } from './SourcePeeker';
import { SourcesSidebar, type SourceDoc } from './SourcesSidebar';
import { StudioPanel } from './StudioPanel';
import { ThreePaneLayout } from './ThreePaneLayout';
import { type ChatMode } from './ModePills';
import { DomainChip, type DomainLabel } from './DomainChip';
import { QuestionnaireMessage, type PrefilledField } from './QuestionnaireMessage';
import { InlineResultCard } from './InlineResultCard';
import { CustomTemplatePicker } from './CustomTemplatePicker';
import { type AuditorFormat } from './AuditorFormatGrid';
import { REPORT_CONFIGS } from './reportConfigs';

type Domain = 'general' | 'finance' | 'law' | 'audit' | 'vat' | 'aml' | 'legal' | 'corporate_tax'
  | 'peppol' | 'e_invoicing' | 'labour' | 'commercial' | 'ifrs' | 'general_law'
  | 'tax' | 'accounting';

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
  const [domainLocked, setDomainLocked] = useState(false);
  const [searchParams] = useSearchParams();

  const [docs, setDocs] = useState<SourceDoc[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [researching, setResearching] = useState(false);

  const [auditResult, setAuditResult] = useState<{
    risk_flags: { severity: 'low' | 'medium' | 'high'; document: string; finding: string }[];
    anomalies: { severity: 'low' | 'medium' | 'high'; document: string; finding: string }[];
    compliance_gaps: { severity: 'low' | 'medium' | 'high'; document: string; finding: string }[];
    summary: string;
  } | null>(null);
  const [auditing, setAuditing] = useState(false);

  // ── Report questionnaire flow state ──
  const [activeQuestionnaire, setActiveQuestionnaire] = useState<{
    reportType: string;
    fields: PrefilledField[];
    label: string;
  } | null>(null);
  const [reportGenerating, setReportGenerating] = useState(false);
  const [reportResults, setReportResults] = useState<Array<{
    reportType: string;
    date: string;
    content?: string;
    error?: string;
  }>>([]);

  const chatAreaBottomRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const persistSourcesRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isInitialLoadRef = useRef(false);

  const [auditorFormat, setAuditorFormat] = useState<AuditorFormat>('standard');
  const [showAuditQuestionnaire, setShowAuditQuestionnaire] = useState(false);
  const [customTemplatePickerOpen, setCustomTemplatePickerOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<{ id: string; name: string } | null>(null);
  const [auditGenerating, setAuditGenerating] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const initialValue = searchParams.get('q') ?? '';

  // --- Document handlers ---
  const handleDocSelect = useCallback((id: string) => {
    setSelectedDocIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }, []);

  const handleDocDelete = useCallback(async (id: string) => {
    const prevDocs = docs;
    const prevSelectedIds = selectedDocIds;
    setDocs(prev => prev.filter(d => d.id !== id));
    setSelectedDocIds(prev => prev.filter(x => x !== id));
    try {
      await API.delete(`/api/documents/${id}`);
    } catch (err) {
      console.error('Failed to delete document:', err);
      setDocs(prevDocs);
      setSelectedDocIds(prevSelectedIds);
      setDeleteError('Failed to delete document. Please try again.');
      setTimeout(() => setDeleteError(null), 3000);
    }
  }, [docs, selectedDocIds]);

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
      } catch (err) {
        console.error('Document upload failed:', err);
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
        const msgs = (r.data ?? []).map((m: any): TextMessage => ({
          role: m.role === 'user' ? 'user' : 'ai',
          text: m.content,
          time: fmtTime(),
          sources: m.sources ?? [],
          id: m.id,
          messageId: m.id,
        }));
        setMessages(msgs);
      })
      .catch(err => { console.error('Failed to load messages:', err); });
  }, [initialConversationId]);

  // --- Load sources for existing conversation ---
  useEffect(() => {
    if (!initialConversationId) return;
    if (!conversationId) return;
    // Reset at start of every sources-load (defensive: covers conversation switches)
    isInitialLoadRef.current = false;
    API.get(`/api/legal-studio/notebook/${initialConversationId}/sources`)
      .then(r => {
        const ids: string[] = r.data?.source_ids ?? [];
        if (ids.length > 0) {
          isInitialLoadRef.current = true;
          setSelectedDocIds(ids);
          setDocs(ids.map(id => ({
            id,
            filename: id,
            source: id,
            status: 'ready' as const,
          })));
        }
      })
      .catch(err => { console.error('Failed to load sources:', err); });
  }, [initialConversationId, conversationId]);

  // --- Persist sources when they change ---

  useEffect(() => {
    if (!conversationId) return;
    
    // Skip the save triggered by initial source load
    if (isInitialLoadRef.current) {
      isInitialLoadRef.current = false;
      return;
    }
    
    if (persistSourcesRef.current) clearTimeout(persistSourcesRef.current);
    persistSourcesRef.current = setTimeout(() => {
      API.post('/api/legal-studio/save-sources', {
        conversation_id: conversationId,
        source_ids: selectedDocIds,
      }).catch(err => { console.error('Failed to save sources:', err); });
    }, 500);
    
    return () => {
      if (persistSourcesRef.current) {
        clearTimeout(persistSourcesRef.current);
      }
    };
  }, [conversationId, selectedDocIds]);

  // --- Audit flow handlers ---
  const auditFields: PrefilledField[] = useMemo(() => [
    { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
    { key: 'period', label: 'Audit Period', value: new Date().getFullYear().toString(), editable: true },
    { key: 'format', label: 'Report Format', value: auditorFormat === 'custom' && selectedTemplate
      ? `custom:${selectedTemplate.name}` : (auditorFormat || 'standard'), editable: false },
    { key: 'scope', label: 'Scope', value: 'Full financial audit', editable: true },
  ], [auditorFormat, selectedTemplate]);

  const handleRunAudit = useCallback(() => {
    if (selectedDocIds.length === 0) return;
    if (auditorFormat === 'custom' && !selectedTemplate) {
      setCustomTemplatePickerOpen(true);
      return;
    }
    setShowAuditQuestionnaire(true);
    setAuditResult(null);
    setAuditError(null);
  }, [selectedDocIds, auditorFormat, selectedTemplate]);

  const handleAuditConfirm = useCallback(async (fields: Record<string, string>) => {
    setAuditGenerating(true);
    setAuditing(true);
    setAuditError(null);
    try {
      const res = await API.post('/api/legal-studio/auditor', {
        document_ids: selectedDocIds,
        entity_name: fields.entity_name,
        period: fields.period,
        format: fields.format,
        scope: fields.scope,
      });
      setAuditResult(res.data);
      setShowAuditQuestionnaire(false);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Audit failed. Please try again.';
      setAuditError(errorMsg);
      setShowAuditQuestionnaire(false);
    } finally {
      setAuditGenerating(false);
      setAuditing(false);
    }
  }, [selectedDocIds]);

  const handleAuditRetry = useCallback(() => {
    setAuditError(null);
    setAuditResult(null);
    setShowAuditQuestionnaire(true);
  }, []);

  const handleTemplateSelect = useCallback((templateId: string, templateName: string) => {
    setSelectedTemplate({ id: templateId, name: templateName });
    setCustomTemplatePickerOpen(false);
    setShowAuditQuestionnaire(true);
    setAuditResult(null);
    setAuditError(null);
  }, []);

  // --- Report questionnaire flow ---
  const handleReportRequest = useCallback(async (reportType: string) => {
    // Prevent concurrent calls (e.g. double-click or clicking two report types quickly)
    if (activeQuestionnaire) return;
    
    const config = REPORT_CONFIGS[reportType];
    if (!config) return;

    // Show questionnaire immediately with empty entity_name
    const fields = config.fields.map((f: PrefilledField) => ({ ...f }));
    setActiveQuestionnaire({
      reportType,
      fields,
      label: config.label,
    });
    setTimeout(() => chatAreaBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);

    // Extract entity name in background, update questionnaire when done
    if (conversationId && config.fields.some((f: PrefilledField) => f.key === 'entity_name')) {
      API.get(`/api/legal-studio/notebook/${conversationId}/entity-name`)
        .then(r => {
          const entityName = r.data?.entity_name ?? '';
          if (!entityName) return;
          setActiveQuestionnaire(prev => {
            if (!prev || prev.reportType !== reportType) return prev; // questionnaire may have been closed
            return {
              ...prev,
              fields: prev.fields.map(f =>
                f.key === 'entity_name'
                  ? { ...f, value: entityName, placeholder: 'Auto-detected from sources', autoDetected: true }
                  : f
              ),
            };
          });
        })
        .catch(() => { /* non-fatal */ });
    }
  }, [conversationId, activeQuestionnaire]);

  const handleQuestionnaireConfirm = useCallback(async (confirmedFields: Record<string, string>) => {
    if (!activeQuestionnaire) return;
    const { reportType, label } = activeQuestionnaire;
    setReportGenerating(true);

    try {
      const backendType = reportType === 'forecast' ? 'financial_analysis' : reportType;
      const res = await API.post(`/api/reports/generate/${backendType}`, {
        mapped_data: [],
        requirements: {},
        source_ids: selectedDocIds,
        company_name: confirmedFields.entity_name || 'Analysis',
        auditor_format: auditorFormat,
        ...confirmedFields,
        ...(reportType === 'forecast' ? { sub_type: 'forecast' } : {}),
      });
      const content = res.data.report_text ?? res.data.draft ?? 'Report generated successfully.';
      setReportResults(prev => [...prev, {
        reportType: label,
        date: new Date().toISOString(),
        content,
      }]);
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail ?? err?.message ?? 'Report generation failed. Please try again.';
      setReportResults(prev => [...prev, {
        reportType: label,
        date: new Date().toISOString(),
        error: errorMsg,
      }]);
    } finally {
      setReportGenerating(false);
      setActiveQuestionnaire(null);
      setTimeout(() => chatAreaBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  }, [activeQuestionnaire, selectedDocIds, auditorFormat]);

  const handleQuestionnaireCancel = useCallback(() => {
    setActiveQuestionnaire(null);
  }, []);

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
        } catch (err) { console.error('Document upload failed:', err); /* upload error - continue with chat */ }
      }
    }

    const userDomain = detectDomain(text);
    if (userDomain && !domainLocked) {
      setDomain(userDomain);
      setDetectedDomain(userDomain as DomainLabel);
    }

    const userMsg: Message = { role: 'user', text, time: fmtTime(), id: crypto.randomUUID() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setWebSearching(false);

    if (mode === 'deep_research') {
      setResearching(true);
      const researchId = crypto.randomUUID();
      const researchMsg: ResearchMessage = {
        role: 'research',
        id: researchId,
        query: text,
        phases: [],
        report: null,
        sources: [],
        time: fmtTime(),
      };
      setMessages(prev => [...prev, researchMsg]);

      try {
        const res = await API.post('/api/legal-studio/research', { query: text });
        const jobId = res.data.job_id;
        const evtSource = new EventSource(`${API_BASE}/api/legal-studio/research/${jobId}/stream`);
        eventSourceRef.current = evtSource;
        evtSource.onmessage = (e) => {
          const data = JSON.parse(e.data);
          if (!data.phase) return;
          if (data.phase === 'completed') {
            setMessages(prev => prev.map(m => {
              if (m.id === researchId && m.role === 'research') {
                return { ...m, report: data.report ?? '', sources: data.sources ?? [] };
              }
              return m;
            }));
            setResearching(false);
            setLoading(false);
            evtSource.close();
            eventSourceRef.current = null;
            return;
          }
          setMessages(prev => prev.map(m => {
            if (m.id === researchId && m.role === 'research') {
              return { ...m, phases: [...m.phases, data] };
            }
            return m;
          }));
        };
        evtSource.onerror = () => {
          evtSource.close();
          eventSourceRef.current = null;
          setResearching(false);
          setLoading(false);
        };
      } catch {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
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

      const aiMsg: Message = { role: 'ai', text: '', time: fmtTime(), id: crypto.randomUUID() };
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
              if (evt.detected_domain && !domainLocked) {
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
            } else if (evt.type === 'status' && evt.status === 'searching_web') {
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
                  copy[copy.length - 1] = { ...copy[copy.length - 1], messageId: evt.message_id };
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
      const msg = messages[i];
      if (msg.role === 'research') {
        if (msg.sources && msg.sources.length > 0) return msg.sources;
      } else if (msg.role === 'ai' || msg.role === 'assistant') {
        if (msg.sources && msg.sources.length > 0) return msg.sources;
      }
    }
    return [];
  }, [messages]);

  // Auto-open source peeker when response finishes with sources
  const prevLoadingRef = useRef(false);
  const activeSourcesRef = useRef(activeSources);
  // Keep ref in sync via effect (not during render) to be safe in Concurrent Mode
  useEffect(() => {
    activeSourcesRef.current = activeSources;
  }, [activeSources]);
  useEffect(() => {
    if (prevLoadingRef.current && !loading && activeSourcesRef.current.length > 0) {
      setSourcePanelOpen(true);
    }
    prevLoadingRef.current = loading;
  }, [loading]);

  // Auto-scroll to bottom of chat area when messages update
  useEffect(() => {
    chatAreaBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  // --- Render ---
  const centerContent = (
    <>
      {detectedDomain && (
        <div className="legal-domain-chip-wrapper">
          <DomainChip
            domain={detectedDomain}
            domainLocked={domainLocked}
            onDomainChange={(d, isManual) => {
              setDetectedDomain(d as DomainLabel);
              setDomain(d as Domain);
              if (isManual) setDomainLocked(true);
            }}
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
        {showAuditQuestionnaire && (
          <div className="legal-section-pad">
            <QuestionnaireMessage
              reportType="Audit Report"
              fields={auditFields}
              onConfirm={handleAuditConfirm}
              onCancel={() => setShowAuditQuestionnaire(false)}
              generating={auditGenerating}
            />
          </div>
        )}

        {auditResult && !showAuditQuestionnaire && (
          <div className="legal-section-pad">
            <InlineResultCard
              reportType="Audit Report"
              date={new Date().toISOString()}
              format={auditorFormat}
              auditData={auditResult}
            />
          </div>
        )}

        {auditError && !showAuditQuestionnaire && (
          <div className="legal-section-pad">
            <InlineResultCard
              reportType="Audit Report"
              date={new Date().toISOString()}
              error={auditError}
              onRetry={handleAuditRetry}
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

        {/* Report results from chat-redirect flow */}
        {reportResults.map((result, idx) => (
          <div key={`report-result-${idx}`} className="legal-section-pad">
            <InlineResultCard
              reportType={result.reportType}
              date={result.date}
              content={result.content}
              error={result.error}
              onRetry={result.error ? () => {
                const config = Object.values(REPORT_CONFIGS).find(c => c.label === result.reportType);
                if (config) handleReportRequest(config.type);
              } : undefined}
            />
          </div>
        ))}

        {/* Active questionnaire from report card click */}
        {activeQuestionnaire && (
          <div className="legal-section-pad">
            <QuestionnaireMessage
              reportType={activeQuestionnaire.label}
              fields={activeQuestionnaire.fields}
              onConfirm={handleQuestionnaireConfirm}
              onCancel={handleQuestionnaireCancel}
              generating={reportGenerating}
            />
          </div>
        )}

        <div ref={chatAreaBottomRef} />
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
    <>
    <ThreePaneLayout
      left={
        <>
          {deleteError && (
            <div className="legal-delete-error" role="alert">
              {deleteError}
            </div>
          )}
          <SourcesSidebar
            docs={docs}
            selectedIds={selectedDocIds}
            onSelect={handleDocSelect}
            onDelete={handleDocDelete}
            onUpload={handleDocUpload}
            onPreview={handleDocPreview}
          />
        </>
      }
      center={centerContent}
      right={<StudioPanel sourceIds={selectedDocIds} mode={mode} onReportRequest={handleReportRequest} auditorFormat={auditorFormat} onFormatChange={setAuditorFormat} />}
    />
    <CustomTemplatePicker
      isOpen={customTemplatePickerOpen}
      onSelect={handleTemplateSelect}
      onClose={() => setCustomTemplatePickerOpen(false)}
    />
    </>
  );
}
