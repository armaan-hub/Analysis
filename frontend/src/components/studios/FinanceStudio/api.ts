import type {
  AuditProfile, ProfileVersion, SourceDoc, ChatMessage,
  GeneratedOutput, OutputType,
} from './types';
import { API_BASE_URL } from '../../../api-config';

const BASE = API_BASE_URL;

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

// Profiles (existing endpoints, re-exposed here for locality)
export const getProfile = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}`).then(json<AuditProfile>);

// Returns plain array (not wrapped)
export const listSourceDocs = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/source-documents`).then(json<SourceDoc[]>);

// Versions (new)
export const listVersions = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/versions`).then(json<{ versions: ProfileVersion[] }>);

export const branchVersion = (id: string, name: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/branch`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ branch_name: name }),
  }).then(json<{ version_id: string }>);

export const activateVersion = (id: string, vid: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/versions/${vid}/activate`, { method: 'PATCH' }).then(json);

export const compareVersions = (id: string, v1: string, v2: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/versions/${v1}/compare/${v2}`).then(json<{
    changed: Record<string, { before: unknown; after: unknown }>;
    added: Record<string, unknown>;
    removed: Record<string, unknown>;
  }>);

// Chat (new)
export const chatHistory = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/chat/history`).then(json<{ messages: ChatMessage[] }>);

export const chatSend = (id: string, message: string, sourceIds?: string[]) =>
  fetch(`${BASE}/api/audit-profiles/${id}/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, source_ids: sourceIds ?? null }),
  }).then(json<{ content: string; citations: unknown[] }>);

export const chatClear = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/chat/history`, { method: 'DELETE' }).then(json);

// Generation (new)
export const generateOutput = (id: string, type: OutputType, templateId: string | null) =>
  fetch(`${BASE}/api/audit-profiles/${id}/generate/${type}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_id: templateId, options: {} }),
  }).then(json<{ job_id: string; status: string }>);

export const listOutputs = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/outputs`).then(json<{ outputs: GeneratedOutput[] }>);
