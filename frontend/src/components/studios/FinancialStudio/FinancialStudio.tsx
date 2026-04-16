import React, { useState, useEffect } from 'react';
import * as XLSX from 'xlsx';
import {
  Check, Upload,
} from 'lucide-react';
import { API, API_BASE, getErrMsg } from '../../../lib/api';
import { TrialBalanceMapper } from './TrialBalanceMapper';
import { AuditGrid } from './AuditGrid';
import { ReportPreview } from './ReportPreview';
import { ReportRequirements } from './ReportRequirements';
import type { ColumnMapping, LLMQuestion } from './TrialBalanceMapper';
import type { AuditRow } from './AuditGrid';
import { CompanyDocuments, type CompanyInfo } from './CompanyDocuments';
import { AuditFormatSelector, type AuditFormat } from './AuditFormatSelector';
import { FormatSelector } from './FormatSelector';
import { AuditDraftViewer } from './AuditDraftViewer';
import { AuditFinalReport } from './AuditFinalReport';
import { AuditAnalysisStep } from './AuditAnalysisStep';
import { AuditEvidenceStep, type EvidenceResult } from './AuditEvidenceStep';
import { TemplateReviewStep } from './TemplateReviewStep';
import { REPORT_TYPE_CONFIG, AUDIT_FIELDS } from './report-types';
import type { ReportTypeConfig } from './report-types';

type Step = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

const STEP_LABELS_STD   = ['Select Type', 'Upload File', 'Map Fields', 'Requirements', 'AI Validation', 'AI Generation', 'Export'];
const STEP_LABELS_AUDIT = ['Select Type', 'Upload File', 'Company Docs', 'Requirements', 'Evidence', 'Draft Report', 'Analysis & Discussion', 'Select Format', 'Final Report', 'Export'];

interface FinancialStudioProps {
  initialEditState?: Record<string, unknown>;
  onEditConsumed?: () => void;
}

export function FinancialStudio({ initialEditState, onEditConsumed }: FinancialStudioProps = {}) {
  const [activeStep, setActiveStep] = useState<Step>(0);
  const [selectedConfig, setSelectedConfig] = useState<ReportTypeConfig | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [auditRows, setAuditRows] = useState<AuditRow[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [reportFields, setReportFields] = useState<Record<string, string>>({});
  const [requirements, setRequirements] = useState<Record<string, string>>({});
  const [llmSuggestions, setLlmSuggestions] = useState<Record<string, string>>({});
  const [llmQuestions, setLlmQuestions] = useState<LLMQuestion[]>([]);

  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [auditDraft, setAuditDraft] = useState('');
  const [auditFormat, setAuditFormat] = useState<AuditFormat>('big4');
  const [auditFormatCustom, setAuditFormatCustom] = useState<string | undefined>();
  const [auditEvidence, setAuditEvidence] = useState<EvidenceResult | null>(null);
  const [reportMode, setReportMode] = useState<'standalone' | 'comparative'>('standalone');
  const [priorYearFile, setPriorYearFile] = useState<File | null>(null);
  const [priorYearContent, setPriorYearContent] = useState<string>('');
  const [auditCaQuestions, setAuditCaQuestions] = useState<Array<{ id: string; question: string; account: string; risk: string; answered: boolean }>>([]);
  const [auditRiskFlags, setAuditRiskFlags] = useState<Array<{ flag: string; triggered: boolean; detail: string }>>([]);
  const [priorYearContext, setPriorYearContext] = useState<string>('');
  const [, setAnalysisHistory] = useState<Array<{role: string; content: string}>>([]);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [templateConfidence, setTemplateConfidence] = useState(0);
  const [templateExtracting, setTemplateExtracting] = useState(false);
  const [templateReviewed, setTemplateReviewed] = useState(false);
  const isAudit = selectedConfig?.key === 'audit';
  const stepLabels = isAudit ? STEP_LABELS_AUDIT : STEP_LABELS_STD;

  const [isDirty, setIsDirty] = useState(false);
  // Internal sidebar removed — ContextualSidebar's NewReportPanel handles report type selection

  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  useEffect(() => {
    if (!initialEditState) return;
    const key = initialEditState.selectedConfigKey as string | undefined;
    const cfg = key ? REPORT_TYPE_CONFIG.find(c => c.key === key) ?? null : null;
    if (cfg) setSelectedConfig(cfg);
    if (initialEditState.auditRows) setAuditRows(initialEditState.auditRows as AuditRow[]);
    if (initialEditState.reportFields) setReportFields(initialEditState.reportFields as Record<string, string>);
    if (initialEditState.requirements) setRequirements(initialEditState.requirements as Record<string, string>);
    if (initialEditState.companyInfo) setCompanyInfo(initialEditState.companyInfo as CompanyInfo);
    if (initialEditState.auditFormat) setAuditFormat(initialEditState.auditFormat as AuditFormat);
    if (initialEditState.reportMode) setReportMode(initialEditState.reportMode as 'standalone' | 'comparative');
    if (initialEditState.draft_content) setAuditDraft(initialEditState.draft_content as string);
    // Navigate to the right step: if there's a draft → step 7 (Analysis), otherwise step 4
    const targetStep: Step = initialEditState.draft_content ? 7 : 4;
    setActiveStep(targetStep);
    onEditConsumed?.();
  }, [initialEditState]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Comparative mode: prior year file must be selected before uploading current year
    if (selectedConfig?.key === 'audit' && reportMode === 'comparative' && !priorYearFile) {
      setUploadError('Please select the prior year file (bottom slot) before uploading the current year trial balance.');
      e.target.value = '';
      return;
    }

    setUploading(true);
    setUploadError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (selectedConfig?.key) formData.append('report_type', selectedConfig.key);
      if (selectedConfig?.key === 'audit' && reportMode === 'comparative') {
        formData.append('report_mode', 'comparative');
        if (priorYearFile) formData.append('prior_year_file', priorYearFile);
      }
      const resp = await API.post('/api/reports/upload-trial-balance', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 0,  // no timeout — audit grouping can take minutes
      });
      const serverData = resp.data as {
        columns?: string[];
        suggestions?: Record<string, string | null>;
        llm_suggestions?: Record<string, string>;
        llm_questions?: LLMQuestion[];
        grouped_rows?: Array<{ account: string; mappedTo: string; amount: number }>;
        prior_year_content?: string;
      };
      if (serverData.prior_year_content) setPriorYearContent(serverData.prior_year_content);

      if (selectedConfig?.key === 'audit' && serverData.grouped_rows?.length) {
        // Audit path: LLM pre-grouped all rows — go straight to Company Docs
        const rows: AuditRow[] = serverData.grouped_rows.map((r, i) => ({
          id: String(i),
          account: r.account,
          mappedTo: r.mappedTo,
          amount: r.amount,
          status: 'valid' as AuditRow['status'],
        }));
        setAuditRows(rows);
        setReportFields(prev => ({ ...prev, report_mode: reportMode }));
        setIsDirty(true);
        setActiveStep(3); // Company Docs (step 3 in audit flow)
      } else {
        // Non-audit path: show Map Fields with column suggestions
        const serverCols = serverData.columns ?? [];
        let cols = serverCols;
        if (cols.length === 0) {
          const buf = await file.arrayBuffer();
          const wb = XLSX.read(buf, { type: 'array' });
          const ws = wb.Sheets[wb.SheetNames[0]];
          const rows = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1 });
          const firstRow = Array.isArray(rows[0]) ? (rows[0] as unknown[]) : [];
          cols = firstRow.filter(Boolean).map(String);
        }
        setColumns(cols.length > 0 ? cols : ['Column 1', 'Column 2', 'Column 3']);
        setLlmSuggestions(serverData.llm_suggestions ?? {});
        setLlmQuestions(serverData.llm_questions ?? []);
        setIsDirty(true);
        setActiveStep(3); // Map Fields (step 3 in non-audit flow)
      }
    } catch (err) {
      setUploadError(getErrMsg(err, 'Upload failed. Check the file format and try again.'));
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleMappingConfirm = (mappings: ColumnMapping[]) => {
    const mapped = mappings.filter(m => m.systemField);
    const REQUIRED_FIELDS = new Set(['Revenue', 'Current Assets', 'Current Liabilities']);
    const mappedFields = new Set(mapped.map(m => m.systemField));

    const newRows: AuditRow[] = mapped.map((m, i) => {
      const lowConfidence = (m.confidence ?? 100) < 60;
      return {
        id: String(i),
        account: m.rawColumn,
        mappedTo: m.systemField ?? '',
        amount: 0,
        status: (lowConfidence ? 'warning' : 'valid') as AuditRow['status'],
        flagMessage: lowConfidence
          ? `Low mapping confidence (${m.confidence ?? 0}%)`
          : undefined,
      };
    });

    [...REQUIRED_FIELDS].filter(f => !mappedFields.has(f)).forEach((field, i) => {
      newRows.push({
        id: String(mapped.length + i),
        account: '(unmapped)',
        mappedTo: field,
        amount: 0,
        status: 'error',
        flagMessage: `Required field "${field}" has no mapped column`,
      });
    });

    setAuditRows(newRows);
    setActiveStep(4); // → Requirements step
  };

  const handleBack = () => {
    if (activeStep > 0) setActiveStep((activeStep - 1) as Step);
  };

  const handleSaveDraft = async () => {
    await API.post('/api/reports/saved', {
      company_name: reportFields.company_name || companyInfo?.company_name || 'Audit Report',
      report_type: selectedConfig?.key || 'audit',
      format: auditFormat,
      period_end_date: reportFields.period_end,
      status: 'draft',
      draft_content: auditDraft,
      wizard_state_json: {
        selectedConfigKey: selectedConfig?.key,
        auditRows,
        reportFields,
        requirements,
        companyInfo,
        auditFormat,
        reportMode,
      },
    }).catch(() => {});
    setIsDirty(false);
  };

  return (
    <div className="financial-studio" style={{ display: 'flex', height: '100%' }}>
      {/* Sidebar removed — ContextualSidebar's NewReportPanel handles report type selection */}
      {/* Main content (stepper + workspace) */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
      {/* Stepper */}
      {activeStep > 0 && (
      <div className="financial-stepper">
        {stepLabels.map((label, i) => {
          const stepNum = (i + 1) as Step;
          const status =
            stepNum < activeStep ? 'done'
            : stepNum === activeStep ? 'active'
            : 'pending';
          return (
            <React.Fragment key={label}>
              <div
                className={`stepper-step stepper-step--${status}`}
                onClick={() => status === 'done' ? setActiveStep(stepNum) : undefined}
                style={{ cursor: status === 'done' ? 'pointer' : 'default' }}
                title={status === 'done' ? `Go back to ${label}` : undefined}
              >
                <div className="stepper-dot">
                  {status === 'done' ? <Check size={12} /> : stepNum}
                </div>
                <span className="stepper-label">{label}</span>
              </div>
              {i < stepLabels.length - 1 && (
                <div className={`stepper-line ${status === 'done' ? 'stepper-line--done' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
      )}

      {activeStep > 0 && (
        <div style={{ padding: '8px 32px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            onClick={handleBack}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: 'var(--s-r-sm)',
              color: 'var(--s-text-2)',
              fontFamily: 'var(--s-font-ui)',
              fontSize: '13px',
              transition: 'var(--s-ease)',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-accent)';
              (e.currentTarget as HTMLButtonElement).style.background = 'var(--s-accent-dim)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-text-2)';
              (e.currentTarget as HTMLButtonElement).style.background = 'none';
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6"/>
            </svg>
            {stepLabels[activeStep - 2] ?? 'Previous'}
          </button>
        </div>
      )}
      {/* Workspace */}
      <div className="financial-workspace">
        {/* Step 0: Landing */}
        {activeStep === 0 && (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '16px',
            padding: '40px',
          }}>
            <div style={{
              fontSize: '32px',
              opacity: 0.3,
            }}>📊</div>
            <div style={{
              fontFamily: 'var(--s-font-display)',
              fontSize: '20px',
              fontWeight: 600,
              color: 'var(--s-text-1)',
            }}>Financial Reports</div>
            <div style={{
              fontFamily: 'var(--s-font-ui)',
              fontSize: '14px',
              color: 'var(--s-text-2)',
              textAlign: 'center',
              maxWidth: '400px',
            }}>
              Generate audit reports, VAT returns, financial statements and more from your trial balance data.
            </div>
            <button
              className="btn-primary"
              onClick={() => setActiveStep(1)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 24px',
                fontSize: '14px',
                marginTop: '8px',
              }}
            >
              <span style={{ fontSize: '18px', lineHeight: 1 }}>+</span>
              New Report
            </button>
          </div>
        )}

        {/* Step 1: Select Report Type */}
        {activeStep === 1 && (
          <div style={{ padding: '24px 32px', overflowY: 'auto', flex: 1 }}>
            {Object.entries(
              REPORT_TYPE_CONFIG.reduce<Record<string, ReportTypeConfig[]>>((acc, cfg) => {
                (acc[cfg.category] ??= []).push(cfg);
                return acc;
              }, {})
            ).map(([category, configs]) => (
              <div key={category} style={{ marginBottom: '28px' }}>
                <div style={{
                  fontFamily: 'var(--s-font-ui)',
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--s-text-2)',
                  marginBottom: '12px',
                }}>
                  {category}
                </div>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                  gap: '12px',
                }}>
                  {configs.map(cfg => {
                    const IconComp = cfg.icon;
                    const isSelected = selectedConfig?.key === cfg.key;
                    return (
                      <button
                        key={cfg.key}
                        onClick={() => { setSelectedConfig(cfg); setActiveStep(2); }}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'flex-start',
                          gap: '8px',
                          padding: '16px',
                          borderRadius: 'var(--s-r-md)',
                          border: `1px solid ${isSelected ? 'var(--s-accent)' : 'var(--s-border)'}`,
                          background: isSelected ? 'var(--s-accent-dim)' : 'var(--s-surface)',
                          color: 'var(--s-text-1)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          transition: 'var(--s-ease)',
                        }}
                        onMouseEnter={e => {
                          if (!isSelected) {
                            (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-accent)';
                            (e.currentTarget as HTMLButtonElement).style.background = 'var(--s-accent-dim)';
                          }
                        }}
                        onMouseLeave={e => {
                          if (!isSelected) {
                            (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-border)';
                            (e.currentTarget as HTMLButtonElement).style.background = 'var(--s-surface)';
                          }
                        }}
                      >
                        <IconComp size={20} />
                        <div style={{
                          fontFamily: 'var(--s-font-ui)',
                          fontWeight: 600,
                          fontSize: '13px',
                          color: 'var(--s-text-1)',
                        }}>
                          {cfg.label}
                        </div>
                        <div style={{
                          fontFamily: 'var(--s-font-ui)',
                          fontSize: '12px',
                          color: 'var(--s-text-2)',
                          lineHeight: 1.4,
                        }}>
                          {cfg.description}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Step 2: Upload File — non-audit */}
        {activeStep === 2 && !isAudit && (
          <div className="upload-zone">
            <label className="upload-label">
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
                disabled={uploading}
              />
              <div className="upload-icon">
                <Upload size={20} />
              </div>
              <div className="upload-title">
                {selectedConfig?.uploadLabel ?? 'Upload File'}
              </div>
              <div className="upload-sub">
                {uploading
                  ? 'Uploading…'
                  : 'Excel (.xlsx, .xls) or CSV — drag or click to browse'}
              </div>
              {uploadError && (
                <div style={{ color: 'var(--s-danger)', fontSize: '13px', fontFamily: 'var(--s-font-ui)' }}>
                  {uploadError}
                </div>
              )}
            </label>
          </div>
        )}

        {/* Step 2: Upload File — audit */}
        {activeStep === 2 && isAudit && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px', padding: '32px', overflowY: 'auto', flex: 1 }}>
            {/* Audit mode selector */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              padding: '20px',
              borderRadius: 'var(--s-r-md)',
              border: '1px solid var(--s-border)',
              background: 'var(--s-surface)',
              width: '100%',
              maxWidth: '560px',
            }}>
              <div style={{ fontFamily: 'var(--s-font-ui)', fontWeight: 600, fontSize: '13px', color: 'var(--s-text-1)', marginBottom: '4px' }}>
                Audit Mode
              </div>
              {(['standalone', 'comparative'] as const).map(mode => (
                <label key={mode} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="reportMode"
                    value={mode}
                    checked={reportMode === mode}
                    onChange={() => { setReportMode(mode); setPriorYearFile(null); }}
                    style={{ accentColor: 'var(--s-accent)', marginTop: '2px' }}
                  />
                  <div>
                    <div style={{ fontFamily: 'var(--s-font-ui)', fontWeight: 600, fontSize: '13px', color: 'var(--s-text-1)' }}>
                      {mode === 'standalone' ? 'Standalone' : 'Comparative'}
                    </div>
                    <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)', marginTop: '2px' }}>
                      {mode === 'standalone'
                        ? 'Single period audit, one trial balance'
                        : 'Two-period audit, prior year figures required per IAS 1.38'}
                    </div>
                  </div>
                </label>
              ))}
            </div>

            {/* Standalone: single upload slot */}
            {reportMode === 'standalone' && (
              <div className="upload-zone" style={{ width: '100%', maxWidth: '560px' }}>
                <label className="upload-label">
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv,.pdf"
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                    disabled={uploading}
                  />
                  <div className="upload-icon">
                    <Upload size={20} />
                  </div>
                  <div className="upload-title">
                    {selectedConfig?.uploadLabel ?? 'Upload Trial Balance'}
                  </div>
                  <div className="upload-sub">
                    {uploading
                      ? 'Processing trial balance — LLM is grouping all accounts, please wait…'
                      : 'Excel (.xlsx, .xls), CSV, or PDF financial statements — drag or click to browse'}
                  </div>
                  {uploadError && (
                    <div style={{ color: 'var(--s-danger)', fontSize: '13px', fontFamily: 'var(--s-font-ui)' }}>
                      {uploadError}
                    </div>
                  )}
                </label>
              </div>
            )}

            {/* Comparative: current year + prior year slots */}
            {reportMode === 'comparative' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '100%', maxWidth: '560px' }}>
                {/* Slot 1: Current Year Trial Balance — triggers upload */}
                <div className="upload-zone">
                  <label className="upload-label">
                    <input
                      type="file"
                      accept=".xlsx,.xls,.csv,.pdf"
                      onChange={handleFileUpload}
                      style={{ display: 'none' }}
                      disabled={uploading}
                    />
                    <div className="upload-icon">
                      <Upload size={20} />
                    </div>
                    <div className="upload-title">Current Year Trial Balance</div>
                    <div className="upload-sub">
                      {uploading
                        ? 'Processing trial balance — LLM is grouping all accounts, please wait…'
                        : 'Excel (.xlsx, .xls), CSV, or PDF financial statements — drag or click to browse'}
                    </div>
                  </label>
                </div>

                {/* Slot 2: Prior Year — stores to state, sent alongside main upload */}
                <label style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '24px',
                  borderRadius: 'var(--s-r-md)',
                  border: `1px dashed ${priorYearFile ? 'var(--s-accent)' : 'var(--s-border)'}`,
                  background: priorYearFile ? 'var(--s-accent-dim)' : 'var(--s-surface)',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}>
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv,.pdf"
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      setPriorYearFile(f);
                      e.target.value = '';

                      // If PDF, extract template
                      if (f.name.toLowerCase().endsWith('.pdf')) {
                        setTemplateExtracting(true);
                        try {
                          const form = new FormData();
                          form.append('file', f);
                          const resp = await API.post('/api/reports/extract-audit-template', form, {
                            headers: { 'Content-Type': 'multipart/form-data' },
                          });
                          const data = resp.data as { template_id: string; confidence: number };
                          setTemplateId(data.template_id);
                          setTemplateConfidence(data.confidence);
                        } catch (err) {
                          console.error('Template extraction failed:', err);
                        } finally {
                          setTemplateExtracting(false);
                        }
                      }
                    }}
                    style={{ display: 'none' }}
                    disabled={uploading}
                  />
                  <div style={{ color: 'var(--s-accent)' }}>
                    <Upload size={20} />
                  </div>
                  <div style={{ fontFamily: 'var(--s-font-ui)', fontWeight: 600, fontSize: '13px', color: 'var(--s-text-1)' }}>
                    Prior Year — Trial Balance (Excel/CSV) or Signed Audit Report (PDF)
                  </div>
                  <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
                    {priorYearFile
                      ? `Selected: ${priorYearFile.name}`
                      : 'Excel (.xlsx, .xls), CSV, or PDF — drag or click to browse'}
                  </div>
                </label>

                {templateExtracting && (
                  <div style={{ fontSize: '12px', color: 'var(--s-accent)', fontFamily: 'var(--s-font-ui)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="chat-typing"><span /><span /><span /></span>
                    Extracting template from prior year audit…
                  </div>
                )}
                {templateId && !templateExtracting && (
                  <div style={{ fontSize: '12px', color: 'var(--s-success, #22c55e)', fontFamily: 'var(--s-font-ui)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    ✓ Template extracted (confidence: {(templateConfidence * 100).toFixed(0)}%)
                  </div>
                )}

                {templateId && !templateExtracting && !templateReviewed && (
                  <TemplateReviewStep
                    templateId={templateId}
                    onApprove={() => setTemplateReviewed(true)}
                    onReject={() => { setTemplateId(null); setTemplateReviewed(false); }}
                  />
                )}

                {uploadError && (
                  <div style={{ color: 'var(--s-danger)', fontSize: '13px', fontFamily: 'var(--s-font-ui)' }}>
                    {uploadError}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Map Fields (non-audit) OR Company Documents (audit) */}
        {activeStep === 3 && !isAudit && (
          <TrialBalanceMapper
            columns={columns}
            systemFields={selectedConfig?.mapperFields ?? AUDIT_FIELDS}
            reportType={selectedConfig?.key ?? 'custom'}
            onConfirm={handleMappingConfirm}
            llmSuggestions={llmSuggestions}
            llmQuestions={llmQuestions}
          />
        )}
        {activeStep === 3 && isAudit && (
          <CompanyDocuments
            onComplete={(info, priorYearCtx) => { setCompanyInfo(info); if (priorYearCtx) setPriorYearContext(priorYearCtx); setActiveStep(4); }}
            onSkip={() => setActiveStep(4)}
          />
        )}

        {/* Step 4: Requirements */}
        {activeStep === 4 && selectedConfig && (
          <ReportRequirements
            reportType={selectedConfig.key}
            reportFieldDefs={selectedConfig.reportFields}
            auditRows={auditRows}
            companyInfo={companyInfo ?? undefined}
            onComplete={(fields, reqs) => {
              setReportFields(fields);
              setRequirements(reqs);
              setActiveStep(5);
            }}
          />
        )}

        {/* Step 5: AI Validation (non-audit) OR Evidence (audit) */}
        {activeStep === 5 && !isAudit && (
          <AuditGrid
            rows={auditRows}
            onRowsChange={setAuditRows}
            onAdvance={() => setActiveStep(6)}
          />
        )}
        {activeStep === 5 && isAudit && (
          <AuditEvidenceStep
            auditRows={auditRows}
            companyInfo={companyInfo}
            onComplete={(evidence) => {
              setAuditEvidence(evidence);
              setAuditCaQuestions(evidence.caQuestions);
              setAuditRiskFlags(evidence.riskFlags);
              setActiveStep(6);
            }}
          />
        )}

        {/* Step 6: AI Generation (non-audit) OR Draft Report Pass 1 (audit) */}
        {activeStep === 6 && !isAudit && selectedConfig && (
          <ReportPreview
            reportType={selectedConfig.key}
            auditRows={auditRows}
            reportFields={reportFields}
            requirements={requirements}
            onAdvance={() => setActiveStep(7)}
            onDownloadUrl={setDownloadUrl}
          />
        )}
        {activeStep === 6 && isAudit && (
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
            <AuditDraftViewer
              auditRows={auditRows}
              reportFields={reportFields}
              companyInfo={companyInfo}
              auditEvidence={auditEvidence}
              reportMode={reportMode}
              priorYearContent={priorYearContent}
              caQuestions={auditCaQuestions}
              riskFlags={auditRiskFlags}
              onDraftReady={async (draft) => {
                setAuditDraft(draft);
                setIsDirty(true);
                setActiveStep(7);
              }}
            />
            {auditDraft && (
              <div style={{ padding: '12px 32px', borderTop: '1px solid var(--s-border)', flexShrink: 0 }}>
                <button className="btn-ghost" onClick={handleSaveDraft} style={{ fontSize: '13px' }}>
                  💾 Save Draft
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step 7: Analysis & Discussion (audit only) */}
        {activeStep === 7 && isAudit && (
          <AuditAnalysisStep
            draftContent={auditDraft}
            trialBalanceSummary={''}
            priorYearContext={priorYearContext}
            companyName={companyInfo?.company_name ?? ''}
            periodEnd={reportFields.period_end ?? ''}
            onBack={() => setActiveStep(6)}
            onComplete={(history) => {
              setAnalysisHistory(history);
              setActiveStep(8);
            }}
          />
        )}

        {/* Step 8: Export (non-audit) OR Select Format (audit) */}
        {activeStep === 7 && !isAudit && (
          <div className="export-ready">
            <div className="export-icon"><Check size={24} /></div>
            <div className="export-title">Report Generated</div>
            <div className="export-sub">
              {downloadUrl
                ? 'Your report is ready. Click below to download the file.'
                : 'The AI report was previewed in the previous step. Go back to regenerate if needed.'}
            </div>
            {downloadUrl && (
              <a href={`${API_BASE}${downloadUrl}`} download className="btn-primary" style={{ textDecoration: 'none' }}>
                Download Report
              </a>
            )}
            <button className="btn-ghost" onClick={() => setActiveStep(6)}>← Back to Report Preview</button>
          </div>
        )}
        {activeStep === 8 && isAudit && (
          templateId ? (
            <FormatSelector
              templateId={templateId}
              templateConfidence={templateConfidence}
              onSelectFormat={(format) => {
                setAuditFormat(format as AuditFormat);
                setActiveStep(9);
              }}
              selectedFormat={auditFormat}
            />
          ) : (
            <AuditFormatSelector
              onSelect={(fmt, custom) => {
                setAuditFormat(fmt);
                setAuditFormatCustom(custom);
                setActiveStep(9);
              }}
            />
          )
        )}

        {/* Step 9: Final Report Pass 2 (audit only) */}
        {activeStep === 9 && isAudit && (
          <AuditFinalReport
            draft={auditDraft}
            format={auditFormat}
            customInstructions={auditFormatCustom}
            priorYearContent={priorYearContent}
            onAdvance={() => setActiveStep(10)}
            onSave={async (finalContent) => {
              await API.post('/api/reports/saved', {
                company_name: reportFields.company_name || companyInfo?.company_name || 'Audit Report',
                report_type: 'audit',
                format: auditFormat,
                period_end_date: reportFields.period_end,
                status: 'final',
                draft_content: auditDraft,
                final_content: finalContent,
                wizard_state_json: {
                  selectedConfigKey: selectedConfig?.key,
                  auditRows,
                  reportFields,
                  requirements,
                  companyInfo,
                  auditFormat,
                  reportMode,
                },
              }).catch(() => {});
              setIsDirty(false);
            }}
          />
        )}

        {/* Step 10: Export (audit only) */}
        {activeStep === 10 && isAudit && (
          <div className="export-ready">
            <div className="export-icon"><Check size={24} /></div>
            <div className="export-title">Audit Report Ready</div>
            <div className="export-sub">
              Your final audit report is displayed in the previous step. Use your browser's print function or copy the Markdown to export.
            </div>
            <button className="btn-ghost" onClick={() => setActiveStep(9)}>← Back to Final Report</button>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
