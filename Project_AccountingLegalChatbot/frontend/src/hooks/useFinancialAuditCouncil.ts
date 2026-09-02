import { useState, useCallback, useRef } from 'react';
import { financialAuditCouncilEndpoint } from '../lib/api';

export interface AuditSubAgentState {
  name: string;
  role?: string;
  stage: string;
  step: number;
  totalSteps: number;
  content: string;
  status: 'idle' | 'in_progress' | 'completed' | 'error';
  truncated?: boolean;
}

export interface FinancialAuditCouncilRunInput {
  doc1_balance_sheet: string;
  doc2_profit_loss: string;
  doc3_corporate_legal: string;
  doc4_template_notes?: string;
  provider?: string;
}

export const AUDIT_STAGES_INFO = [
  {
    stage: 'legal_extraction',
    name: 'Corporate Legal Extractor',
    role: 'Specialist in UAE Commercial Legal Documents (Trade License & MOA)',
    step: 1,
    icon: '⚖️',
    description: 'Extracts legal entity name (EN/AR), license number, legal structure, shareholding table, and management authority.',
  },
  {
    stage: 'tb_audit',
    name: 'Trial Balance Auditor',
    role: 'Senior Auditor — Balance Sheet & Trial Balance',
    step: 2,
    icon: '📊',
    description: 'Analyzes 2025/2024 Balance Sheet and TB line items, Non-Current/Current Assets, Liabilities, and Equity.',
  },
  {
    stage: 'pl_analysis',
    name: 'Profit & Loss Analyst',
    role: 'Senior Financial Performance & P&L Statement Auditor',
    step: 3,
    icon: '📈',
    description: 'Computes Revenue, Gross Profit, G&A Expenses, Operating Margins, and UAE Corporate Tax compliance.',
  },
  {
    stage: 'mainland_mapping',
    name: 'Comparative Mainland Mapper',
    role: 'Target Template Mapping Specialist (2025-first)',
    step: 4,
    icon: '📑',
    description: 'Maps raw ledgers into strict Comparative Mainland structure, enforcing 2025 first and zero hyphen (-) notation.',
  },
  {
    stage: 'report_synthesis',
    name: 'Audit Report Synthesis Chair',
    role: 'Lead Audit Partner & Report Synthesis Formatter',
    step: 5,
    icon: '🖋️',
    description: 'Synthesizes corporate directory, unqualified audit opinion, SOFP, SOPL, SOCE, CFS, and Notes 1 to 15.',
  },
  {
    stage: 'math_qc',
    name: 'Audit Math Verification Critic',
    role: 'Audit Quality Control & Mathematical Verification Partner',
    step: 6,
    icon: '🔍',
    description: 'Performs line-by-line QC, verifies Assets = Liabilities + Equity, P&L tie-out, column chronology, and discrepancy flags.',
  },
];

export function useFinancialAuditCouncil() {
  const [agents, setAgents] = useState<Record<string, AuditSubAgentState>>({});
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [totalSteps, setTotalSteps] = useState<number>(6);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setAgents({});
    setActiveStage(null);
    setCurrentStep(0);
    setRunning(false);
    setError(null);
    setIsCompleted(false);
  }, []);

  const run = useCallback(async (input: FinancialAuditCouncilRunInput) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    // Initialize blank stage templates
    const initialAgents: Record<string, AuditSubAgentState> = {};
    AUDIT_STAGES_INFO.forEach((s) => {
      initialAgents[s.stage] = {
        name: s.name,
        role: s.role,
        stage: s.stage,
        step: s.step,
        totalSteps: 6,
        content: '',
        status: 'idle',
      };
    });

    setAgents(initialAgents);
    setActiveStage(null);
    setCurrentStep(0);
    setTotalSteps(6);
    setError(null);
    setIsCompleted(false);
    setRunning(true);

    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;

    try {
      const res = await fetch(financialAuditCouncilEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc1_balance_sheet: input.doc1_balance_sheet,
          doc2_profit_loss: input.doc2_profit_loss,
          doc3_corporate_legal: input.doc3_corporate_legal,
          doc4_template_notes: input.doc4_template_notes || '',
          provider: input.provider || undefined,
        }),
        signal: ctrl.signal,
      });

      if (!res.ok) {
        const errorText = await res.text().catch(() => '');
        throw new Error(`Server returned HTTP ${res.status}: ${errorText || res.statusText}`);
      }

      reader = res.body?.getReader();
      if (!reader) throw new Error('No readable response stream received from backend.');

      const dec = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));

            if (evt.type === 'audit_council_agent_start') {
              setActiveStage(evt.stage);
              setCurrentStep(evt.step || 1);
              if (evt.total_steps) setTotalSteps(evt.total_steps);

              setAgents((prev) => ({
                ...prev,
                [evt.stage]: {
                  ...(prev[evt.stage] || {
                    name: evt.agent,
                    role: evt.role,
                    stage: evt.stage,
                    step: evt.step,
                    totalSteps: evt.total_steps || 6,
                    content: '',
                  }),
                  status: 'in_progress',
                },
              }));
            } else if (evt.type === 'audit_council_delta') {
              setAgents((prev) => {
                const current = prev[evt.stage] || {
                  name: evt.agent,
                  stage: evt.stage,
                  step: 1,
                  totalSteps: 6,
                  content: '',
                  status: 'in_progress',
                };
                return {
                  ...prev,
                  [evt.stage]: {
                    ...current,
                    content: current.content + (evt.delta || ''),
                    status: 'in_progress',
                  },
                };
              });
            } else if (evt.type === 'audit_council_agent_complete') {
              setAgents((prev) => {
                const current = prev[evt.stage] || {
                  name: evt.agent,
                  stage: evt.stage,
                  step: evt.step || 1,
                  totalSteps: evt.total_steps || 6,
                  content: '',
                  status: 'completed',
                };
                return {
                  ...prev,
                  [evt.stage]: {
                    ...current,
                    content: evt.content !== undefined ? evt.content : current.content,
                    status: 'completed',
                    truncated: Boolean(evt.truncated),
                  },
                };
              });
            } else if (evt.type === 'audit_council_error') {
              setError(evt.error || 'Subagent encountered an error during review');
              if (evt.stage) {
                setAgents((prev) => ({
                  ...prev,
                  [evt.stage]: {
                    ...(prev[evt.stage] || {
                      name: evt.agent || evt.stage,
                      stage: evt.stage,
                      step: 1,
                      totalSteps: 6,
                      content: '',
                    }),
                    status: 'error',
                  },
                }));
              }
            } else if (evt.type === 'audit_council_done') {
              if (evt.error) {
                setError(evt.error);
              }
              setIsCompleted(true);
              setRunning(false);
            }
          } catch {
            // Ignore JSON parse errors for incomplete frames
          }
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        // User aborted
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      await reader?.cancel().catch(() => {});
      setRunning(false);
    }
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setRunning(false);
  }, []);

  // Derived outputs for easy presentation
  const legalReport = agents['legal_extraction']?.content || '';
  const tbReport = agents['tb_audit']?.content || '';
  const plReport = agents['pl_analysis']?.content || '';
  const mappingReport = agents['mainland_mapping']?.content || '';
  const synthesizedReport = agents['report_synthesis']?.content || '';
  const qcReport = agents['math_qc']?.content || '';

  return {
    agents,
    activeStage,
    currentStep,
    totalSteps,
    running,
    error,
    isCompleted,
    run,
    abort,
    reset,
    // Direct accessors
    legalReport,
    tbReport,
    plReport,
    mappingReport,
    synthesizedReport,
    qcReport,
  };
}
