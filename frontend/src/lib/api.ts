import axios, { AxiosError, isAxiosError } from 'axios';

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const API = axios.create({ baseURL: API_BASE, timeout: 180000 });

// ── Shared Types ──────────────────────────────────────────────────────────────
export interface Source { source: string; page: string | number; score: number; excerpt: string; original_name?: string; }

export interface TextMessage {
  role: 'user' | 'ai' | 'assistant';
  text: string;
  time: string;
  sources?: Source[];
  id?: string;
  messageId?: string;
  queriesRun?: string[];
  isResearching?: boolean;
}

export interface ResearchMessage {
  role: 'research';
  id: string;
  query: string;
  phases: Array<{ phase: string; message: string; sub_questions?: string[]; progress?: number; total?: number; report?: string }>;
  report: string | null;
  sources: Source[];
  time: string;
}

export type Message = TextMessage | ResearchMessage;
export interface Report { id:string; report_type:string; title:string; status:string; output_path?:string; error_message?:string; created_at:string; }
export interface Alert { id:string; title:string; source_name:string; summary?:string; diff_content?:string; severity:string; is_read:boolean; created_at:string; }
export interface MonitoringStatus { total_alerts?: number; next_run?: string; scheduler_running?: boolean; }
export interface MonitoredSourceItem { id: string; name: string; url: string; category: string; is_active: boolean; last_checked?: string; }
export interface IFRSFormData { company_name:string; revenue:string; cogs:string; operating_expenses:string; assets:string; liabilities:string; }
export interface VATFormData  { company_name:string; trn:string; sales_amount:string; purchases_amount:string; }
export interface CorpTaxFormData { company_name:string; net_income:string; disallowed_expenses:string; exempt_income:string; }

// ── Helpers ───────────────────────────────────────────────────────────────────
export const fmtDate = (s:string) => new Date(s).toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric'});
export const fmtTime = () => new Date().toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit'});
export const getErrMsg = (e: unknown, fallback: string): string => {
  if (isAxiosError(e)) return (e as AxiosError<{detail?:string}>).response?.data?.detail || e.message || fallback;
  if (e instanceof Error) return e.message || fallback;
  return fallback;
};

export function generateReportStreamUrl(): string {
  return `${API_BASE}/api/reports/generate-stream`;
}

export async function detectReportMetadata(
  reportType: string,
  selectedDocIds: string[],
): Promise<{ entity_name: string; period_end: string; confidence: 'high' | 'low' | 'none' }> {
  const r = await API.post('/api/reports/detect', {
    report_type: reportType,
    selected_doc_ids: selectedDocIds,
  });
  return r.data;
}

export async function exportMessage(
  messageId: string,
  format: 'word' | 'pdf' | 'excel',
  filename: string
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_id: messageId, format }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(error.detail || 'Export failed');
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function getConversation(id: string): Promise<{ id: string; mode: string; title: string }> {
  const r = await API.get(`/api/chat/conversations/${id}`);
  return r.data;
}

export async function patchConversationMode(id: string, mode: string): Promise<void> {
  await API.patch(`/api/chat/conversations/${id}`, { mode });
}

export function deepResearchUrl(): string {
  return `${API_BASE}/api/chat/deep-research`;
}

export const councilEndpoint = `${API_BASE}/api/chat/council`;

