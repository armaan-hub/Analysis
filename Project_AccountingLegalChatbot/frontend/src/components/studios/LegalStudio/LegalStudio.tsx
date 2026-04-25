import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2, ScanSearch } from 'lucide-react';
import { API_BASE, API, fmtTime, type Message, type TextMessage, type Source, generateReportStreamUrl, detectReportMetadata } from '../../../lib/api';
import { ConfirmReportCard } from './ConfirmReportCard';
import { ArtifactPanel } from './ArtifactPanel';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { SourcePeeker } from './SourcePeeker';
import { SourcesSidebar, type SourceDoc } from './SourcesSidebar';
import { StudioPanel } from './StudioPanel';
import { ThreePaneLayout } from './ThreePaneLayout';
import { AnalystErrorBoundary } from './AnalystErrorBoundary';
import { ModePills } from './ModePills';
import { DomainChip, type DomainLabel } from './DomainChip';
import { QuestionnaireMessage, type PrefilledField } from './QuestionnaireMessage';
import { InlineResultCard } from './InlineResultCard';
import { CustomTemplatePicker } from './CustomTemplatePicker';
import { type AuditorFormat } from './AuditorFormatGrid';
import { REPORT_CONFIGS } from './reportConfigs';
import { toBackendFormat } from './auditorFormatUtils';
import { useNotebookMode } from '../../../hooks/useNotebookMode';
import { useDeepResearch } from '../../../hooks/useDeepResearch';
import { ChatOnlyLayout } from './ChatOnlyLayout';
import { ChatWithResearchLayout } from './ChatWithResearchLayout';
import { ResearchPanel } from './ResearchPanel';
import { useCouncil } from '../../../hooks/useCouncil';
import { CouncilPanel } from './CouncilPanel';
import { CouncilButton } from './CouncilButton';

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

function isRefinementInstruction(text: string): boolean {
  const REFINEMENT_STARTS = ['add', 'change', 'make', 'update', 'remove', 'include', 'shorten', 'expand'];
  return REFINEMENT_STARTS.some(s => text.toLowerCase().startsWith(s));
}

interface AuditFinding { severity: 'low' | 'medium' | 'high'; document: string; finding: string; }
interface AuditResultData {
  risk_flags: AuditFinding[];
  anomalies: AuditFinding[];
  compliance_gaps: AuditFinding[];
  summary: string;
}

function formatAuditResultAsMarkdown(data: AuditResultData): string {
  const lines: string[] = ['## Audit Analysis Result\n'];
  if (data.summary) { lines.push('### Summary\n', data.summary, ''); }
  const sections: Array<{ key: keyof Pick<AuditResultData, 'risk_flags' | 'anomalies' | 'compliance_gaps'>; label: string }> = [
    { key: 'risk_flags', label: 'Risk Flags' },
    { key: 'anomalies', label: 'Anomalies' },
    { key: 'compliance_gaps', label: 'Compliance Gaps' },
  ];
  for (const { key, label } of sections) {
    const rows = data[key] ?? [];
    if (rows.length) {
      lines.push(`### ${label}\n`);
       for (const f of rows) { lines.push(`- **[${(f.severity ?? 'unknown').toUpperCase()}]** ${f.document}: ${f.finding}`); }
      lines.push('');
    }
  }
  return lines.join('\n');
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
  const { mode, setMode } = useNotebookMode(conversationId ?? null);
  const { steps, answer, streamingContent, running: researchRunning, error: researchError, run: runDeepResearch } = useDeepResearch(conversationId ?? '');
  const [detectedDomain, setDetectedDomain] = useState<DomainLabel | null>(null);
  const [domainLocked, setDomainLocked] = useState(false);
  const [searchParams] = useSearchParams();

  const [docs, setDocs] = useState<SourceDoc[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [auditResult, setAuditResult] = useState<{
    risk_flags: AuditFinding[];
    anomalies: AuditFinding[];
    compliance_gaps: AuditFinding[];
    summary: string;
  } | null>(null);
  const [auditing, setAuditing] = useState(false);

  const chatAreaBottomRef = useRef<HTMLDivElement>(null);
  const persistSourcesRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isInitialLoadRef = useRef(false);
  const lastResearchQuery = useRef<string>('');

  const council = useCouncil();
  const [councilOpen, setCouncilOpen] = useState(false);
  const [lastQuestion, setLastQuestion] = useState('');
  const [lastAnswer, setLastAnswer] = useState('');

  const [auditorFormat, setAuditorFormat] = useState<AuditorFormat>('standard');
  const [showAuditQuestionnaire, setShowAuditQuestionnaire] = useState(false);
  const [customTemplatePickerOpen, setCustomTemplatePickerOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<{ id: string; name: string } | null>(null);
  const [auditGenerating, setAuditGenerating] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  // ── Analyst: ConfirmReportCard + ArtifactPanel state ──
  const [confirmCard, setConfirmCard] = useState<{
    reportType: string;
    reportLabel: string;
    entityName: string;
    periodEnd: string;
    confidence: 'high' | 'low' | 'none';
    format: AuditorFormat;
  } | null>(null);

  const [artifactOpen, setArtifactOpen] = useState(false);
  const [artifactTitle, setArtifactTitle] = useState('');
  const [artifactReportType, setArtifactReportType] = useState('');
  const [artifactContent, setArtifactContent] = useState('');
  const [artifactLoading, setArtifactLoading] = useState(false);
  const abortReportRef = useRef<AbortController | null>(null);
  const sendMessageAbortRef = useRef<AbortController | null>(null);
  const [artifactEntityName, setArtifactEntityName] = useState('');
  const [artifactPeriodEnd, setArtifactPeriodEnd] = useState('');

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
      fd.append('studio', 'legal');
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
        const rawSources: Array<{ id: string; name: string }> =
          r.data?.sources ?? [];
        if (rawSources.length > 0) {
          isInitialLoadRef.current = true;
          setSelectedDocIds(rawSources.map(s => s.id));
          setDocs(rawSources.map(s => ({
            id: s.id,
            filename: s.name,
            original_name: s.name,
            source: s.name,
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

  useEffect(() => {
    return () => {
      sendMessageAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const { abort } = council;
    return () => { abort(); };
  }, [council.abort]); // eslint-disable-line react-hooks/exhaustive-deps

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
      // Route audit results to ArtifactPanel right pane
      const auditMd = formatAuditResultAsMarkdown(res.data);
      setArtifactTitle('🔍 Audit Analysis Result');
      setArtifactReportType('audit');
      setArtifactContent(auditMd);
      setArtifactOpen(true);
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
    const config = REPORT_CONFIGS[reportType];
    if (!config) return;

    // Auto-detect entity and period from docs
    let entity_name = '';
    let period_end = '';
    let confidence: 'high' | 'low' | 'none' = 'none';
    try {
      const detected = await detectReportMetadata(reportType, selectedDocIds);
      entity_name = detected.entity_name;
      period_end = detected.period_end;
      confidence = detected.confidence;
    } catch {
      // Fallback — show card with empty fields
    }

    setConfirmCard({
      reportType,
      reportLabel: config.label,
      entityName: entity_name,
      periodEnd: period_end,
      confidence,
      format: auditorFormat,
    });
    setTimeout(() => chatAreaBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  }, [selectedDocIds, auditorFormat]);

  const handleGenerateReport = useCallback(async (params: {
    entityName: string;
    periodEnd: string;
    format: AuditorFormat;
  }) => {
    if (!confirmCard) return;
    setConfirmCard(null);

    const config = REPORT_CONFIGS[confirmCard.reportType];
    const title = `${config?.icon ?? '📊'} ${config?.label ?? confirmCard.reportType} — ${params.entityName}`;
    setArtifactTitle(title);
    setArtifactReportType(confirmCard.reportType);
    setArtifactEntityName(params.entityName);
    setArtifactPeriodEnd(params.periodEnd);
    setArtifactContent('');
    setArtifactLoading(true);
    setArtifactOpen(true);

    abortReportRef.current?.abort();
    const ac = new AbortController();
    abortReportRef.current = ac;

    try {
      const resp = await fetch(generateReportStreamUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({
          report_type: confirmCard.reportType,
          selected_doc_ids: selectedDocIds,
          entity_name: params.entityName,
          period_end: params.periodEnd,
          auditor_format: toBackendFormat(params.format),
        }),
        signal: ac.signal,
      });
      if (!resp.ok || !resp.body) {
        setArtifactContent(`⚠ Failed to generate report (HTTP ${resp.status}). Please try again.`);
        setArtifactLoading(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      setArtifactLoading(false);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const frame = buf.slice(0, idx).trim();
          buf = buf.slice(idx + 2);
          if (!frame.startsWith('data: ')) continue;
          try {
            const ev = JSON.parse(frame.slice(6));
            if (ev.type === 'chunk') setArtifactContent(prev => prev + ev.content);
            else if (ev.type === 'error') setArtifactContent(`⚠ Generation error: ${ev.message ?? 'unknown'}`);
          } catch { /* malformed */ }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setArtifactContent('⚠ Report generation interrupted. Please try again.');
      }
      setArtifactLoading(false);
    }
  }, [confirmCard, selectedDocIds]);

  const handleRefinement = useCallback(async (instruction: string) => {
    if (!artifactReportType || !artifactContent) return;
    setArtifactLoading(true);
    const prevContent = artifactContent;
    setArtifactContent('');

    abortReportRef.current?.abort();
    const ac = new AbortController();
    abortReportRef.current = ac;

    try {
      const resp = await fetch(generateReportStreamUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({
          report_type: artifactReportType,
          selected_doc_ids: selectedDocIds,
          entity_name: artifactEntityName,
          period_end: artifactPeriodEnd,
          refinement_instruction: instruction,
          current_report_content: prevContent,
        }),
        signal: ac.signal,
      });
      if (!resp.ok || !resp.body) { setArtifactContent(prevContent); setArtifactLoading(false); return; }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      setArtifactLoading(false);
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const frame = buf.slice(0, idx).trim();
          buf = buf.slice(idx + 2);
          if (!frame.startsWith('data: ')) continue;
          try {
            const ev = JSON.parse(frame.slice(6));
            if (ev.type === 'chunk') setArtifactContent(prev => prev + ev.content);
            else if (ev.type === 'error') setArtifactContent(`⚠ Generation error: ${ev.message ?? 'unknown'}`);
          } catch { /* ignore */ }
        }
      }
    } catch {
      setArtifactContent(prevContent);
      setArtifactLoading(false);
    }
  }, [artifactReportType, artifactContent, selectedDocIds, artifactEntityName, artifactPeriodEnd]);

  // --- Chat send ---
  const sendMessage = useCallback(async (text: string, attachedFiles?: File[]) => {
    // Pre-upload any quick-attached files
    if (attachedFiles && attachedFiles.length > 0) {
      for (const file of attachedFiles) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('studio', 'legal');
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

    // Route to refinement if artifact is open and the message looks like a refinement instruction
    if (artifactOpen && artifactContent && isRefinementInstruction(text)) {
      handleRefinement(text);
      return;
    }

    if (text.trim().startsWith('/council')) {
      if (!lastAnswer) {
        setMessages(prev => [...prev, {
          role: 'ai' as const,
          text: '⚠️ Ask a question first before running the council.',
          time: fmtTime(),
          id: crypto.randomUUID(),
        }]);
        return;
      }
      setCouncilOpen(true);
      council.run(lastQuestion, lastAnswer);
      return;
    }

    const userMsg: Message = { role: 'user', text, time: fmtTime(), id: crypto.randomUUID() };
    setMessages(prev => [...prev, userMsg]);
    setLastQuestion(text);
    setLoading(true);
    setWebSearching(false);

    if (mode === 'deep_research') {
      setLoading(false);
      lastResearchQuery.current = text;
      try {
        await runDeepResearch(text, selectedDocIds);
      } catch (err) {
        console.error('[sendMessage] deep_research failed', err);
        setMessages(prev => [...prev, {
          role: 'ai',
          text: '⚠️ Deep research failed. Please try again.',
          time: fmtTime(),
          id: crypto.randomUUID(),
        }]);
      }
      return;
    }

    const aiMsgId = crypto.randomUUID();
    sendMessageAbortRef.current?.abort();
    const controller = new AbortController();
    sendMessageAbortRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), 90_000);

    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;

    try {
      const body: any = {
        message: text, conversation_id: conversationId,
        stream: true, domain: userDomain ?? domain, mode,
        ...(selectedDocIds.length > 0 && { selected_doc_ids: selectedDocIds }),
      };
      const response = await fetch(`${API_BASE}/api/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      reader = response.body!.getReader();

      let aiText = '';
      let sources: Source[] = [];
      const decoder = new TextDecoder();

      const aiMsg: Message = { role: 'ai', text: '', time: fmtTime(), id: aiMsgId };
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
                const last = copy[copy.length - 1];
                if (last.role === 'research') return copy;
                copy[copy.length - 1] = { ...last, text: aiText };
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
                const last = copy[copy.length - 1];
                if (last.role === 'research') return copy;
                copy[copy.length - 1] = { ...last, sources };
                return copy;
              });
            } else if (evt.type === 'status' && evt.status === 'searching_web') {
              setWebSearching(true);
            } else if (evt.event === 'queries_run') {
              setMessages(prev => {
                const copy = [...prev];
                const last = copy[copy.length - 1];
                if (last.role === 'research') return copy;
                copy[copy.length - 1] = { ...last, queriesRun: evt.queries ?? evt.data };
                return copy;
              });
            } else if (evt.event === 'done' || evt.type === 'done') {
              if (evt.message_id) {
                setMessages(prev => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last.role === 'research') return copy;
                  copy[copy.length - 1] = { ...last, messageId: evt.message_id };
                  return copy;
                });
              }
            }
          } catch { /* skip unparseable lines */ }
        }
      }
      setLastAnswer(aiText);
    } catch (err) {
      const isAbort = err instanceof Error && err.name === 'AbortError';
      console.error('[sendMessage] failed', err);
      setMessages(prev => {
        const withoutPartial = prev.filter(m => m.id !== aiMsgId);
        return [...withoutPartial, {
          role: 'ai',
          text: isAbort
            ? '⚠️ Request timed out (30s). Please try again.'
            : '⚠️ Request failed. Please check your connection and try again.',
          time: fmtTime(),
          id: crypto.randomUUID(),
        }];
      });
    } finally {
      clearTimeout(timeoutId);
      reader?.cancel();
      setLoading(false);
      setWebSearching(false);
    }

    // Refresh conversations
    API.get('/api/chat/conversations').then(r => {
      onConversationsChange?.(r.data ?? []);
    }).catch(() => {});
  }, [conversationId, domain, mode, onConversationsChange, domainLocked, artifactOpen, artifactContent, handleRefinement, selectedDocIds, runDeepResearch, council, lastQuestion, lastAnswer]);

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

  // Append deep-research answer as research message when it arrives
  useEffect(() => {
    if (!answer) return;
    setMessages(prev => [...prev, {
      role: 'research' as const,
      id: crypto.randomUUID(),
      query: lastResearchQuery.current,
      phases: steps.map(s => ({ phase: s.status, message: s.text })),
      report: answer.content,
      sources: answer.sources.map(s => ({ source: s.filename, page: s.page ?? '', score: 0, excerpt: '' })),
      time: fmtTime(),
    }]);
  }, [answer, steps]);

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
          docs={docs}
        />

        {/* ConfirmReportCard — analyst detect flow */}
        {confirmCard && (
          <div className="legal-section-pad">
            <ConfirmReportCard
              reportType={confirmCard.reportType}
              reportLabel={confirmCard.reportLabel}
              entityName={confirmCard.entityName}
              periodEnd={confirmCard.periodEnd}
              documentsCount={selectedDocIds.length}
              format={confirmCard.format}
              confidence={confirmCard.confidence}
              onGenerate={handleGenerateReport}
              onEdit={() => setConfirmCard(prev => prev ? { ...prev, confidence: 'none' } : null)}
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
        disabled={loading || researchRunning}
        initialValue={initialValue}
        mode={mode}
        onModeChange={mode === 'analyst' ? setMode : undefined}
      />
      {councilOpen && (
        <div style={{ borderTop: '1px solid #e2e8f0', maxHeight: 500, overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 16px', background: '#f7fafc' }}>
            <span style={{ fontWeight: 600 }}>Council Review</span>
            <button onClick={() => setCouncilOpen(false)} style={{ border: 'none', background: 'none', cursor: 'pointer' }}>✕</button>
          </div>
          <CouncilPanel
            experts={council.experts}
            synthesis={council.synthesis}
            running={council.running}
            error={council.error}
          />
        </div>
      )}
    </>
  );

  const modePills = (
    <>
      <ModePills value={mode} onChange={setMode} />
      <CouncilButton
        onClick={() => { setCouncilOpen(true); council.run(lastQuestion, lastAnswer); }}
        disabled={council.running || mode === 'fast' || !lastAnswer}
      />
    </>
  );

  const customTemplatePicker = (
    <CustomTemplatePicker
      isOpen={customTemplatePickerOpen}
      onSelect={handleTemplateSelect}
      onClose={() => setCustomTemplatePickerOpen(false)}
    />
  );

  if (mode === 'fast') {
    return (
      <>
        <ChatOnlyLayout modePills={modePills} chatArea={centerContent} />
        {customTemplatePicker}
      </>
    );
  }

  if (mode === 'deep_research') {
    return (
      <>
        <ChatWithResearchLayout
          modePills={modePills}
          chatArea={centerContent}
          researchPanel={
            <>
              {researchError && (
                <div className="error-banner" role="alert" style={{ marginBottom: 8 }}>
                  Deep research failed: {researchError}
                </div>
              )}
              <ResearchPanel steps={steps} answer={answer} streamingContent={streamingContent} query={lastResearchQuery.current} />
            </>
          }
        />
        {customTemplatePicker}
      </>
    );
  }

  // analyst mode — ThreePaneLayout
  return (
    <>
    <AnalystErrorBoundary onReset={() => setMode('fast')}>
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
      right={artifactOpen ? (
        <ArtifactPanel
          open={artifactOpen}
          title={artifactTitle}
          reportType={artifactReportType}
          content={artifactContent}
          loading={artifactLoading}
          onClose={() => setArtifactOpen(false)}
          onExport={() => {
            const blob = new Blob([artifactContent], { type: 'text/plain' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `${artifactReportType}-report.md`;
            a.click();
          }}
        />
      ) : (
        <StudioPanel sourceIds={selectedDocIds} mode={mode} onReportRequest={handleReportRequest} auditorFormat={auditorFormat} onFormatChange={setAuditorFormat} />
      )}
    />
    </AnalystErrorBoundary>
    {customTemplatePicker}
    </>
  );
}

