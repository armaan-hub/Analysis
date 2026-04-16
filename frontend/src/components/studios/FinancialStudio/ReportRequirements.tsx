import { useState, useEffect, useRef } from 'react';
import { API, getErrMsg } from '../../../lib/api';
import type { AuditRow } from './AuditGrid';
import type { CompanyInfo } from './CompanyDocuments';

interface SelectOption { value: string; label: string; }

interface FieldDef {
  key: string;
  label: string;
  type?: string;
  options?: SelectOption[];
}

interface ReportQuestion {
  id: string;
  question: string;
  type: 'choice' | 'boolean' | 'text';
  options?: string[];
}

interface Props {
  reportType: string;
  reportFieldDefs: FieldDef[];
  auditRows: AuditRow[];
  onComplete: (fields: Record<string, string>, requirements: Record<string, string>) => void;
  companyInfo?: CompanyInfo;
}

type Phase = 'fields' | 'questions' | 'checklist' | 'done';

const AUDIT_CHECKLIST_ITEMS = [
  { id: 'balance_sheet', label: 'Balance Sheet (Statement of Financial Position)', required: true, standard: 'IAS 1' },
  { id: 'profit_loss', label: 'Statement of Profit & Loss and OCI', required: true, standard: 'IAS 1' },
  { id: 'cash_flows', label: 'Statement of Cash Flows', required: true, standard: 'IAS 7' },
  { id: 'changes_in_equity', label: 'Statement of Changes in Equity', required: true, standard: 'IAS 1' },
  { id: 'notes', label: 'Notes to the Financial Statements (all applicable)', required: true, standard: 'IAS 1.112' },
  { id: 'schedules', label: 'Schedules (Fixed Assets, Depreciation, etc.)', required: true, standard: 'Best practice' },
  { id: 'auditors_report', label: "Independent Auditor's Report with Opinion", required: true, standard: 'ISA 700' },
  { id: 'management_statement', label: 'Management Responsibility Statement', required: true, standard: 'ISA 700' },
  { id: 'key_audit_matters', label: "Auditor's Remarks / Key Audit Matters", required: false, standard: 'ISA 701' },
  { id: 'going_concern', label: 'Going Concern Paragraph (if applicable)', required: false, standard: 'ISA 570' },
  { id: 'related_parties', label: 'Related Party Disclosures (if applicable)', required: false, standard: 'IAS 24' },
] as const;

export function ReportRequirements({ reportType, reportFieldDefs, auditRows, onComplete, companyInfo }: Props) {
  const [phase, setPhase] = useState<Phase>('fields');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [customFile, setCustomFile] = useState<string>('');
  const [questions, setQuestions] = useState<ReportQuestion[]>([]);
  const [qIndex, setQIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [textInput, setTextInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});
  const [customSection, setCustomSection] = useState<string>('');
  const [autoFilledKeys, setAutoFilledKeys] = useState<Set<string>>(() => new Set());
  const inputRef = useRef<HTMLInputElement>(null);

  // Pre-fill company_name from companyInfo, and period_end with today's date, when those fields exist
  useEffect(() => {
    if (companyInfo?.company_name && reportFieldDefs.some(f => f.key === 'company_name')) {
      setFields(prev => ({ ...prev, company_name: companyInfo.company_name }));
      setAutoFilledKeys(prev => { const s = new Set(prev); s.add('company_name'); return s; });
    }
    // CompanyInfo doesn't expose a fiscal period end, so default to today's date as a convenient starting point
    if (reportFieldDefs.some(f => f.key === 'period_end')) {
      const today = new Date().toISOString().split('T')[0];
      setFields(prev => prev['period_end'] ? prev : { ...prev, period_end: today });
      setAutoFilledKeys(prev => { const s = new Set(prev); s.add('period_end'); return s; });
    }
  }, [companyInfo, reportFieldDefs]);

  // Visible fields: exclude 'file' types from the static form; show custom_format_file
  // only when auditor_format === 'custom'
  const visibleFieldDefs = reportFieldDefs.filter(f => {
    if (f.type === 'file') return f.key === 'custom_format_file' && fields['auditor_format'] === 'custom';
    return true;
  });

  const fetchQuestions = async () => {
    setLoading(true);
    setError('');
    try {
      const mappedData = auditRows.map(r => ({ mapped_to: r.mappedTo, amount: r.amount }));
      const resp = await API.post(`/api/reports/questions/${reportType}`, { mapped_data: mappedData });
      const data = resp.data as { questions?: ReportQuestion[] };
      setQuestions(data.questions ?? []);
      setPhase('questions');
    } catch (err) {
      setError(getErrMsg(err, 'Failed to load requirements questions.'));
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (key: string, value: string) => {
    setFields(prev => ({ ...prev, [key]: value }));
    setAutoFilledKeys(prev => { const s = new Set(prev); s.delete(key); return s; });
  };

  const handleFieldsSubmit = () => {
    if (reportType === 'audit') {
      const initial: Record<string, boolean> = {};
      AUDIT_CHECKLIST_ITEMS.forEach(item => { initial[item.id] = true; });
      setCheckedItems(initial);
      setPhase('checklist');
    } else {
      fetchQuestions();
    }
  };

  const handleChecklistConfirm = () => {
    const finalFields: Record<string, string> = { ...fields };
    if (customFile) finalFields['custom_format_instructions'] = customFile;
    const enabledIds = AUDIT_CHECKLIST_ITEMS
      .filter(item => item.required || checkedItems[item.id])
      .map(item => item.id)
      .join(',');
    const finalReqs: Record<string, string> = { audit_components: enabledIds };
    if (customSection.trim()) finalReqs['custom_sections'] = customSection.trim();
    onComplete(finalFields, finalReqs);
  };

  const handleAnswer = (questionId: string, answer: string) => {
    const newAnswers = { ...answers, [questionId]: answer };
    setAnswers(newAnswers);
    if (qIndex + 1 < questions.length) {
      setQIndex(i => i + 1);
      setTextInput('');
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setPhase('done');
    }
  };

  const handleTextSubmit = () => {
    const q = questions[qIndex];
    if (!textInput.trim()) return;
    handleAnswer(q.id, textInput.trim());
  };

  const handleSkipQuestions = () => {
    setPhase('done');
  };

  useEffect(() => {
    if (phase === 'done') {
      const finalFields: Record<string, string> = { ...fields };
      if (customFile) finalFields['custom_format_instructions'] = customFile;
      const finalReqs: Record<string, string> = {};
      questions.forEach(q => {
        if (answers[q.id]) finalReqs[q.question] = answers[q.id];
      });
      onComplete(finalFields, finalReqs);
    }
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentQuestion = questions[qIndex];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      padding: '32px 40px',
      gap: '24px',
      overflowY: 'auto',
      maxWidth: '640px',
      margin: '0 auto',
      width: '100%',
    }}>
      <div>
        <div style={{
          fontFamily: 'var(--s-font-display)',
          fontSize: '18px',
          fontWeight: 600,
          color: 'var(--s-text-1)',
          marginBottom: '4px',
        }}>
          {phase === 'fields' ? 'Report Details' : phase === 'checklist' ? 'Audit Components' : 'Requirements'}
        </div>
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
          {phase === 'fields'
            ? 'Fill in the report metadata before we generate your questions.'
            : phase === 'checklist'
            ? 'Confirm the components to include in your audit report. Required items cannot be removed.'
            : `Question ${Math.min(qIndex + 1, questions.length)} of ${questions.length}`}
        </div>
      </div>

      {/* Phase 1: Static report fields */}
      {phase === 'fields' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {visibleFieldDefs.map(f => (
            <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{
                fontFamily: 'var(--s-font-ui)',
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--s-text-2)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}>
                {f.label}
                {autoFilledKeys.has(f.key) && (
                  <span style={{ marginLeft: '6px', fontSize: '10px', color: 'var(--s-accent)', background: 'var(--s-accent-dim)', border: '1px solid var(--s-accent)', borderRadius: '999px', padding: '1px 6px', fontFamily: 'var(--s-font-ui)', fontWeight: 600 }}>
                    ✦ auto-filled
                  </span>
                )}
              </label>

              {f.type === 'select' && f.options ? (
                <select
                  value={fields[f.key] ?? f.options[0].value}
                  onChange={e => handleFieldChange(f.key, e.target.value)}
                  style={{
                    background: 'var(--s-surface)',
                    border: '1px solid var(--s-border)',
                    borderRadius: 'var(--s-r-sm)',
                    color: 'var(--s-text-1)',
                    fontFamily: 'var(--s-font-ui)',
                    fontSize: '13px',
                    padding: '8px 12px',
                    outline: 'none',
                  }}
                >
                  {f.options.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              ) : f.type === 'file' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <input
                    type="file"
                    accept=".txt,.docx,.doc,.xlsx,.xls,.pdf"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      try {
                        const form = new FormData();
                        form.append('file', file);
                        const resp = await API.post('/api/reports/extract-template', form, {
                          headers: { 'Content-Type': 'multipart/form-data' },
                        });
                        const text = (resp.data as { text: string }).text;
                        if (f.key === 'custom_format_file') setCustomFile(text);
                        setFields(prev => ({ ...prev, [f.key]: text }));
                      } catch {
                        // ignore extraction error — user can retry
                      }
                    }}
                    style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}
                  />
                  <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}>
                    Accepted: .txt, .docx, .xlsx, .pdf
                  </span>
                </div>
              ) : (
                <input
                  type={f.type === 'date' ? 'date' : 'text'}
                  value={fields[f.key] ?? ''}
                  onChange={e => handleFieldChange(f.key, e.target.value)}
                  placeholder={f.label}
                  style={{
                    background: 'var(--s-surface)',
                    border: '1px solid var(--s-border)',
                    borderRadius: 'var(--s-r-sm)',
                    color: 'var(--s-text-1)',
                    fontFamily: 'var(--s-font-ui)',
                    fontSize: '13px',
                    padding: '8px 12px',
                    outline: 'none',
                  }}
                />
              )}
            </div>
          ))}

          {error && (
            <div style={{
              padding: '12px',
              borderRadius: 'var(--s-r-sm)',
              background: 'rgba(248,113,113,0.08)',
              border: '1px solid var(--s-danger)',
              color: 'var(--s-danger)',
              fontFamily: 'var(--s-font-ui)',
              fontSize: '13px',
            }}>
              {error}
            </div>
          )}

          <button
            className="btn-primary"
            onClick={handleFieldsSubmit}
            disabled={loading}
            style={{ alignSelf: 'flex-start', marginTop: '8px' }}
          >
            {loading ? 'Loading questions…' : 'Continue →'}
          </button>
        </div>
      )}

      {/* Phase: Audit Checklist */}
      {phase === 'checklist' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {AUDIT_CHECKLIST_ITEMS.map(item => (
              <div
                key={item.id}
                title={item.required
                  ? `Required by ${item.standard} — cannot be excluded from a compliant audit report.`
                  : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 12px',
                  borderRadius: 'var(--s-r-sm)',
                  background: 'var(--s-surface)',
                  border: '1px solid var(--s-border)',
                }}
              >
                <input
                  type="checkbox"
                  checked={item.required ? true : (checkedItems[item.id] ?? true)}
                  disabled={item.required}
                  onChange={item.required ? undefined : (e) =>
                    setCheckedItems(prev => ({ ...prev, [item.id]: e.target.checked }))
                  }
                  style={{ cursor: item.required ? 'not-allowed' : 'pointer', flexShrink: 0 }}
                />
                <span style={{
                  flex: 1,
                  fontFamily: 'var(--s-font-ui)',
                  fontSize: '13px',
                  color: item.required ? 'var(--s-text-2)' : 'var(--s-text-1)',
                  opacity: item.required ? 0.75 : 1,
                }}>
                  {item.label}
                </span>
                <span style={{
                  fontFamily: 'var(--s-font-ui)',
                  fontSize: '10px',
                  fontWeight: 600,
                  color: 'var(--s-accent)',
                  background: 'var(--s-accent-dim)',
                  border: '1px solid var(--s-accent)',
                  borderRadius: 'var(--s-r-sm)',
                  padding: '2px 6px',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}>
                  {item.standard}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{
              fontFamily: 'var(--s-font-ui)',
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--s-text-2)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}>
              Add custom section (optional)
            </label>
            <input
              type="text"
              value={customSection}
              onChange={e => setCustomSection(e.target.value)}
              placeholder="e.g. FTA Regulatory Compliance Schedule"
              style={{
                background: 'var(--s-surface)',
                border: '1px solid var(--s-border)',
                borderRadius: 'var(--s-r-sm)',
                color: 'var(--s-text-1)',
                fontFamily: 'var(--s-font-ui)',
                fontSize: '13px',
                padding: '8px 12px',
                outline: 'none',
              }}
            />
          </div>

          <button
            className="btn-primary"
            onClick={handleChecklistConfirm}
            style={{ alignSelf: 'flex-start', marginTop: '8px' }}
          >
            Generate Audit Report →
          </button>
        </div>
      )}

      {/* Phase 2: Chat-style Q&A */}
      {phase === 'questions' && currentQuestion && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Progress bar */}
          <div style={{
            height: '3px',
            background: 'var(--s-border)',
            borderRadius: '2px',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${((qIndex) / questions.length) * 100}%`,
              background: 'var(--s-accent)',
              borderRadius: '2px',
              transition: 'width 0.3s ease',
            }} />
          </div>

          {/* Answered questions (history) */}
          {questions.slice(0, qIndex).map((q) => (
            <div key={q.id} style={{ opacity: 0.55 }}>
              <div style={{
                fontFamily: 'var(--s-font-ui)',
                fontSize: '13px',
                color: 'var(--s-text-2)',
                marginBottom: '4px',
              }}>
                {q.question}
              </div>
              <div style={{
                display: 'inline-block',
                padding: '4px 10px',
                borderRadius: 'var(--s-r-sm)',
                background: 'var(--s-accent-dim)',
                border: '1px solid var(--s-accent)',
                fontFamily: 'var(--s-font-ui)',
                fontSize: '13px',
                color: 'var(--s-accent)',
              }}>
                {answers[q.id]}
              </div>
            </div>
          ))}

          {/* Current question */}
          <div>
            <div style={{
              fontFamily: 'var(--s-font-ui)',
              fontSize: '15px',
              fontWeight: 600,
              color: 'var(--s-text-1)',
              marginBottom: '12px',
            }}>
              {currentQuestion.question}
            </div>

            {(currentQuestion.type === 'choice' || currentQuestion.type === 'boolean') && currentQuestion.options ? (
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {currentQuestion.options.map(opt => (
                  <button
                    key={opt}
                    className="btn-ghost"
                    style={{ fontSize: '13px' }}
                    onClick={() => handleAnswer(currentQuestion.id, opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  ref={inputRef}
                  type="text"
                  value={textInput}
                  onChange={e => setTextInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleTextSubmit(); }}
                  placeholder="Type your answer…"
                  autoFocus
                  style={{
                    flex: 1,
                    background: 'var(--s-surface)',
                    border: '1px solid var(--s-border)',
                    borderRadius: 'var(--s-r-sm)',
                    color: 'var(--s-text-1)',
                    fontFamily: 'var(--s-font-ui)',
                    fontSize: '13px',
                    padding: '8px 12px',
                    outline: 'none',
                  }}
                />
                <button className="btn-primary" onClick={handleTextSubmit} disabled={!textInput.trim()}>
                  →
                </button>
              </div>
            )}
          </div>

          <button
            className="btn-ghost"
            onClick={handleSkipQuestions}
            style={{ alignSelf: 'flex-start', fontSize: '12px', color: 'var(--s-text-2)' }}
          >
            Skip remaining questions
          </button>
        </div>
      )}
    </div>
  );
}
