import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import type {
  AuditProfile, ProfileVersion, SourceDoc, ChatMessage,
  GeneratedOutput, OutputType, WorkflowStep,
} from './types';
import * as api from './api';

interface FinanceStudioState {
  profileId: string | null;
  setProfileId: (id: string | null) => void;

  activeProfile: AuditProfile | null;

  versions: ProfileVersion[];
  activeVersionId: string | null;
  switchVersion: (id: string) => Promise<void>;
  branchVersion: (name: string) => Promise<void>;

  sourceDocs: SourceDoc[];
  refreshDocs: () => Promise<void>;

  chatHistory: ChatMessage[];
  sendMessage: (text: string) => Promise<void>;
  clearChat: () => Promise<void>;
  chatLoading: boolean;

  outputs: GeneratedOutput[];
  generateOutput: (type: OutputType) => Promise<void>;
  selectedTemplateId: string | null;
  setSelectedTemplate: (id: string | null) => void;

  workflowStep: WorkflowStep;
  setWorkflowStep: (s: WorkflowStep) => void;
}

const Ctx = createContext<FinanceStudioState | null>(null);

export function FinanceStudioProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = useState<string | null>(null);
  const [activeProfile, setActiveProfile] = useState<AuditProfile | null>(null);
  const [versions, setVersions] = useState<ProfileVersion[]>([]);
  const [sourceDocs, setSourceDocs] = useState<SourceDoc[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [outputs, setOutputs] = useState<GeneratedOutput[]>([]);
  const [selectedTemplateId, setSelectedTemplate] = useState<string | null>(null);
  const [workflowStep, setWorkflowStep] = useState<WorkflowStep>(1);

  const activeVersionId = versions.find(v => v.is_current)?.id ?? null;

  // Load core data whenever profile changes.
  useEffect(() => {
    if (!profileId) return;
    (async () => {
      setActiveProfile(await api.getProfile(profileId));
      setVersions((await api.listVersions(profileId)).versions);
      setSourceDocs(await api.listSourceDocs(profileId));  // plain array
      setChatHistory((await api.chatHistory(profileId)).messages);
      setOutputs((await api.listOutputs(profileId)).outputs);
    })();
  }, [profileId]);

  const refreshDocs = useCallback(async () => {
    if (!profileId) return;
    setSourceDocs(await api.listSourceDocs(profileId));  // plain array
  }, [profileId]);

  const switchVersion = useCallback(async (id: string) => {
    if (!profileId) return;
    await api.activateVersion(profileId, id);
    setVersions((await api.listVersions(profileId)).versions);
  }, [profileId]);

  const branchVersion = useCallback(async (name: string) => {
    if (!profileId) return;
    await api.branchVersion(profileId, name);
    setVersions((await api.listVersions(profileId)).versions);
  }, [profileId]);

  const sendMessage = useCallback(async (text: string) => {
    if (!profileId) return;
    setChatLoading(true);
    try {
      await api.chatSend(profileId, text);
      setChatHistory((await api.chatHistory(profileId)).messages);
    } finally {
      setChatLoading(false);
    }
  }, [profileId]);

  const clearChat = useCallback(async () => {
    if (!profileId) return;
    await api.chatClear(profileId);
    setChatHistory([]);
  }, [profileId]);

  const generateOutput = useCallback(async (type: OutputType) => {
    if (!profileId) return;
    await api.generateOutput(profileId, type, selectedTemplateId);
    setOutputs((await api.listOutputs(profileId)).outputs);
  }, [profileId, selectedTemplateId]);

  return (
    <Ctx.Provider value={{
      profileId, setProfileId, activeProfile,
      versions, activeVersionId, switchVersion, branchVersion,
      sourceDocs, refreshDocs,
      chatHistory, sendMessage, clearChat, chatLoading,
      outputs, generateOutput,
      selectedTemplateId, setSelectedTemplate,
      workflowStep, setWorkflowStep,
    }}>
      {children}
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useFinanceStudio(): FinanceStudioState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useFinanceStudio must be used inside <FinanceStudioProvider>');
  return ctx;
}
