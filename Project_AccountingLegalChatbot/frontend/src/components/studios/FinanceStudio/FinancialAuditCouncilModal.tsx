import { useState, useEffect } from 'react';
import {
  X,
  Play,
  Square,
  RotateCcw,
  Sparkles,
  Copy,
  Check,
  Download,
  Loader2,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  Building2,
  Scale,
  BarChart3,
  TrendingUp,
  FileCheck,
  Search,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { normalizeMarkdown } from '../../../lib/utils/normalizeMarkdown';
import {
  useFinancialAuditCouncil,
  AUDIT_STAGES_INFO,
} from '../../../hooks/useFinancialAuditCouncil';
import {
  SAMPLE_DOC1_BALANCE_SHEET,
  SAMPLE_DOC2_PROFIT_LOSS,
  SAMPLE_DOC3_CORPORATE_LEGAL,
  SAMPLE_DOC4_TEMPLATE_NOTES,
} from './sampleDossier';
import './FinancialAuditCouncilModal.css';

interface FinancialAuditCouncilModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialDoc1?: string;
  initialDoc2?: string;
  initialDoc3?: string;
  initialDoc4?: string;
}

type TabKey =
  | 'synthesized'
  | 'legal'
  | 'tb'
  | 'pl'
  | 'mapping'
  | 'qc'
  | 'stream';

export function FinancialAuditCouncilModal({
  isOpen,
  onClose,
  initialDoc1 = '',
  initialDoc2 = '',
  initialDoc3 = '',
  initialDoc4 = '',
}: FinancialAuditCouncilModalProps) {
  // Input Document Slots
  const [doc1, setDoc1] = useState<string>(initialDoc1);
  const [doc2, setDoc2] = useState<string>(initialDoc2);
  const [doc3, setDoc3] = useState<string>(initialDoc3);
  const [doc4, setDoc4] = useState<string>(initialDoc4);
  const [selectedProvider, setSelectedProvider] = useState<string>('opencode');
  const [activeTab, setActiveTab] = useState<TabKey>('synthesized');
  const [copied, setCopied] = useState<boolean>(false);

  const {
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
    legalReport,
    tbReport,
    plReport,
    mappingReport,
    synthesizedReport,
    qcReport,
  } = useFinancialAuditCouncil();

  // Populate sample data if initial is empty
  useEffect(() => {
    if (!doc1 && !doc2 && !doc3) {
      loadSampleDossier();
    }
  }, []);

  // When synthesis starts or finishes, auto switch to synthesis tab
  useEffect(() => {
    if (activeStage === 'report_synthesis' && activeTab !== 'synthesized') {
      setActiveTab('synthesized');
    }
  }, [activeStage]);

  if (!isOpen) return null;

  function loadSampleDossier() {
    setDoc1(SAMPLE_DOC1_BALANCE_SHEET);
    setDoc2(SAMPLE_DOC2_PROFIT_LOSS);
    setDoc3(SAMPLE_DOC3_CORPORATE_LEGAL);
    setDoc4(SAMPLE_DOC4_TEMPLATE_NOTES);
  }

  function handleStartAudit() {
    run({
      doc1_balance_sheet: doc1,
      doc2_profit_loss: doc2,
      doc3_corporate_legal: doc3,
      doc4_template_notes: doc4,
      provider: selectedProvider,
    });
  }

  function handleCopyCurrentTab() {
    const textToCopy = getTabContent(activeTab);
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownloadMarkdown() {
    const content = synthesizedReport || getTabContent(activeTab);
    if (!content) return;
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Comparative_Mainland_Audit_Report_${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function getTabContent(tab: TabKey): string {
    switch (tab) {
      case 'synthesized':
        return synthesizedReport;
      case 'legal':
        return legalReport;
      case 'tb':
        return tbReport;
      case 'pl':
        return plReport;
      case 'mapping':
        return mappingReport;
      case 'qc':
        return qcReport;
      case 'stream': {
        // Concatenate all active agents stream
        return Object.values(agents)
          .map((a) => `## ${a.name} (${a.stage})\n\n${a.content}`)
          .join('\n\n---\n\n');
      }
      default:
        return '';
    }
  }

  return (
    <div className="fac-overlay" onClick={onClose}>
      <div
        className="fac-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* ── Modal Header ── */}
        <div className="fac-header">
          <div className="fac-header__left">
            <div className="fac-header__icon-badge">
              <Sparkles size={22} color="#60a5fa" />
            </div>
            <div className="fac-header__title-group">
              <div className="fac-header__title">
                Financial Audit Council Orchestrator
                <span className="fac-header__badge">6 Sub-Agents</span>
              </div>
              <div className="fac-header__subtitle">
                UAE Comparative Mainland Statutory Audit & Multi-Document Reconciliation Engine
              </div>
            </div>
          </div>
          <div className="fac-header__actions">
            <button
              className="fac-btn-close"
              onClick={onClose}
              title="Close modal"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── Quick Action Control Bar ── */}
        <div className="fac-controls-bar">
          <div className="fac-controls-bar__left">
            {!running ? (
              <button
                className="fac-btn fac-btn--primary"
                onClick={handleStartAudit}
                disabled={!doc1.trim() && !doc2.trim()}
              >
                <Play size={14} />
                Run Financial Audit Council
              </button>
            ) : (
              <button className="fac-btn fac-btn--danger" onClick={abort}>
                <Square size={14} />
                Stop Council Execution
              </button>
            )}

            <button
              className="fac-btn fac-btn--preset"
              onClick={loadSampleDossier}
              disabled={running}
              title="Load realistic UAE Mainland trial balance, P&L, and Trade License"
            >
              <Building2 size={14} />
              Load UAE Mainland Sample Dossier
            </button>

            <button
              className="fac-btn"
              onClick={reset}
              disabled={running}
              title="Reset all inputs and generated reports"
            >
              <RotateCcw size={14} />
              Reset
            </button>

            <div className="fac-model-picker">
              <span>Model Provider:</span>
              <select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                disabled={running}
              >
                <option value="opencode">OpenCode Zen (laguna-s-2.1-free)</option>
                <option value="nvidia">NVIDIA NIM</option>
                <option value="groq">Groq LLaMA 3.3</option>
                <option value="anthropic">Anthropic Claude</option>
              </select>
            </div>
          </div>
        </div>

        {/* ── 6-Stage Interactive Subagent Timeline Bar ── */}
        <div className="fac-timeline-container">
          <div className="fac-timeline">
            {AUDIT_STAGES_INFO.map((stageInfo) => {
              const agentState = agents[stageInfo.stage];
              const status = agentState?.status || 'idle';
              const isActive = activeStage === stageInfo.stage;

              return (
                <div
                  key={stageInfo.stage}
                  className={`fac-stage-card fac-stage-card--${status} ${
                    isActive ? 'fac-stage-card--active' : ''
                  }`}
                  onClick={() => {
                    if (stageInfo.stage === 'legal_extraction') setActiveTab('legal');
                    else if (stageInfo.stage === 'tb_audit') setActiveTab('tb');
                    else if (stageInfo.stage === 'pl_analysis') setActiveTab('pl');
                    else if (stageInfo.stage === 'mainland_mapping') setActiveTab('mapping');
                    else if (stageInfo.stage === 'report_synthesis') setActiveTab('synthesized');
                    else if (stageInfo.stage === 'math_qc') setActiveTab('qc');
                  }}
                  title={stageInfo.description}
                >
                  <div className="fac-stage-card__header">
                    <span className="fac-stage-card__step-badge">
                      <span className="fac-stage-card__icon">{stageInfo.icon}</span>
                      Step {stageInfo.step}/6
                    </span>
                    <span className="fac-stage-card__status-dot" />
                  </div>
                  <div className="fac-stage-card__name">{stageInfo.name}</div>
                  <div className="fac-stage-card__role">{stageInfo.role}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Main Content Split Body ── */}
        <div className="fac-body">
          {/* Left Panel: 4 Source Document Inputs */}
          <div className="fac-dossier-panel">
            <div className="fac-dossier-panel__header">
              <span className="fac-dossier-panel__title">
                <FileSpreadsheet size={15} color="#93c5fd" />
                Source Dossier Documents
              </span>
            </div>
            <div className="fac-dossier-slots">
              {/* Doc 1: Balance Sheet & TB */}
              <div className="fac-doc-slot">
                <div className="fac-doc-slot__header">
                  <span className="fac-doc-slot__title">
                    <BarChart3 size={13} />
                    Doc 1: Balance Sheet / TB
                  </span>
                  <span className="fac-doc-slot__badge">2025 vs 2024</span>
                </div>
                <textarea
                  value={doc1}
                  onChange={(e) => setDoc1(e.target.value)}
                  placeholder="Paste Balance Sheet or Trial Balance lines (2025/2024)..."
                  disabled={running}
                />
              </div>

              {/* Doc 2: Profit & Loss Statement */}
              <div className="fac-doc-slot">
                <div className="fac-doc-slot__header">
                  <span className="fac-doc-slot__title">
                    <TrendingUp size={13} />
                    Doc 2: Profit & Loss Statement
                  </span>
                  <span className="fac-doc-slot__badge">P&L & CT</span>
                </div>
                <textarea
                  value={doc2}
                  onChange={(e) => setDoc2(e.target.value)}
                  placeholder="Paste Profit & Loss Statement (Revenue, COGS, Opex, CT)..."
                  disabled={running}
                />
              </div>

              {/* Doc 3: Trade License & MOA */}
              <div className="fac-doc-slot">
                <div className="fac-doc-slot__header">
                  <span className="fac-doc-slot__title">
                    <Scale size={13} />
                    Doc 3: Trade License & MOA
                  </span>
                  <span className="fac-doc-slot__badge">Corporate Legal</span>
                </div>
                <textarea
                  value={doc3}
                  onChange={(e) => setDoc3(e.target.value)}
                  placeholder="Paste Trade License, MOA, Shareholding, and Manager Powers..."
                  disabled={running}
                />
              </div>

              {/* Doc 4: Comparative Mainland Template Context */}
              <div className="fac-doc-slot">
                <div className="fac-doc-slot__header">
                  <span className="fac-doc-slot__title">
                    <FileCheck size={13} />
                    Doc 4: Template & Notes Spec
                  </span>
                  <span className="fac-doc-slot__badge">Target Standard</span>
                </div>
                <textarea
                  value={doc4}
                  onChange={(e) => setDoc4(e.target.value)}
                  placeholder="Target Template specifications (Comparative Mainland rules)..."
                  disabled={running}
                />
              </div>
            </div>
          </div>

          {/* Right Panel: Output Tabs & Deliberation Report */}
          <div className="fac-workspace">
            <div className="fac-workspace__tabs">
              <div className="fac-tab-group">
                <button
                  className={`fac-tab ${activeTab === 'synthesized' ? 'fac-tab--active' : ''}`}
                  onClick={() => setActiveTab('synthesized')}
                >
                  <FileCheck size={14} />
                  Comparative Mainland Report
                </button>
                <button
                  className={`fac-tab ${activeTab === 'legal' ? 'fac-tab--active' : ''}`}
                  onClick={() => setActiveTab('legal')}
                >
                  <Scale size={14} />
                  Legal Extraction
                </button>
                <button
                  className={`fac-tab ${activeTab === 'tb' ? 'fac-tab--active' : ''}`}
                  onClick={() => setActiveTab('tb')}
                >
                  <BarChart3 size={14} />
                  Balance Sheet Audit
                </button>
                <button
                  className={`fac-tab ${activeTab === 'pl' ? 'fac-tab--active' : ''}`}
                  onClick={() => setActiveTab('pl')}
                >
                  <TrendingUp size={14} />
                  P&L Analysis
                </button>
                <button
                  className={`fac-tab ${activeTab === 'mapping' ? 'fac-tab--active' : ''}`}
                  onClick={() => setActiveTab('mapping')}
                >
                  <FileSpreadsheet size={14} />
                  Mainland Mapping
                </button>
                <button
                  className={`fac-tab ${activeTab === 'qc' ? 'fac-tab--active' : ''}`}
                  onClick={() => setActiveTab('qc')}
                >
                  <Search size={14} />
                  Math QC & Tie-Out
                </button>
                <button
                  className={`fac-tab ${activeTab === 'stream' ? 'fac-tab--active' : ''}`}
                  onClick={() => setActiveTab('stream')}
                >
                  <Sparkles size={14} />
                  Live Stream
                </button>
              </div>

              <div className="fac-workspace__export-actions">
                <button
                  className="fac-btn"
                  onClick={handleCopyCurrentTab}
                  disabled={!getTabContent(activeTab)}
                  title="Copy current tab text to clipboard"
                >
                  {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
                <button
                  className="fac-btn"
                  onClick={handleDownloadMarkdown}
                  disabled={!synthesizedReport && !getTabContent(activeTab)}
                  title="Download Markdown Report"
                >
                  <Download size={13} />
                  Download .md
                </button>
              </div>
            </div>

            <div className="fac-workspace__content">
              {/* Status Banner */}
              {running && (
                <div className="fac-status-banner fac-status-banner--running">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Loader2 size={16} className="spin" />
                    <span>
                      <strong>Audit Council In Progress:</strong> Step {currentStep}/{totalSteps} —{' '}
                      {activeStage
                        ? AUDIT_STAGES_INFO.find((s) => s.stage === activeStage)?.name ||
                          activeStage
                        : 'Orchestrating council...'}
                    </span>
                  </div>
                  <button className="fac-btn fac-btn--danger" onClick={abort}>
                    Abort
                  </button>
                </div>
              )}

              {isCompleted && !running && (
                <div className="fac-status-banner fac-status-banner--completed">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <CheckCircle2 size={16} />
                    <span>
                      <strong>Audit Council Review Complete:</strong> All 6 sub-agents completed
                      synthesis and mathematical tie-out check.
                    </span>
                  </div>
                  <button
                    className="fac-btn fac-btn--primary"
                    onClick={handleDownloadMarkdown}
                  >
                    <Download size={13} /> Export Report
                  </button>
                </div>
              )}

              {error && (
                <div className="fac-status-banner fac-status-banner--error">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <AlertCircle size={16} />
                    <span>
                      <strong>Council Error:</strong> {error}
                    </span>
                  </div>
                </div>
              )}

              {/* Tab Content Display */}
              {getTabContent(activeTab) ? (
                <div className="fac-markdown-report">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {normalizeMarkdown(getTabContent(activeTab))}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="fac-empty-state">
                  <div className="fac-empty-state__icon">
                    <Sparkles size={32} />
                  </div>
                  <div className="fac-empty-state__title">
                    {running
                      ? 'Synthesizing Subagent Analysis...'
                      : 'No Audit Report Generated Yet'}
                  </div>
                  <div className="fac-empty-state__description">
                    {running
                      ? 'The 6-Subagent Financial Audit Council is actively processing the source dossier documents and verifying line-by-line financial metrics.'
                      : 'Click "Run Financial Audit Council" or load the "UAE Mainland Sample Dossier" to extract legal metadata, audit trial balances, and synthesize the standard Comparative Mainland Audit Report.'}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
