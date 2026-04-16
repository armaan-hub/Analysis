import { useState, useEffect } from 'react';
import { RefreshCw, Sparkles } from 'lucide-react';
import { API, getErrMsg } from '../../../lib/api';

export interface ColumnMapping {
  rawColumn: string;
  systemField: string | null;
  confidence?: number;
}

export interface LlmQuestion {
  column: string;
  question: string;
  options: string[];
}

/** @deprecated Use LlmQuestion */
export type LLMQuestion = LlmQuestion;

function suggestMapping(rawColumn: string, systemFields: string[]): { field: string | null; confidence: number } {
  const col = rawColumn.toLowerCase().replace(/[_/-]/g, ' ');

  // Exact / near-exact matches — 95%+
  const rules: Array<[RegExp, string, number]> = [
    [/cash|bank|petty cash/, 'Cash and Cash Equivalents', 97],
    [/input vat|vat receivable|vat input/, 'Input VAT', 99],
    [/output vat|vat payable|vat output/, 'Output VAT', 99],
    [/standard rated sales|standard sales/, 'Standard Rated Sales', 99],
    [/zero rated sales|zero rate/, 'Zero Rated Sales', 98],
    [/exempt sales|exempt supply/, 'Exempt Sales', 98],
    [/output tax/, 'Output Tax', 99],
    [/input tax/, 'Input Tax', 99],
    [/reverse charge/, 'Reverse Charge', 98],
    [/retained earning|accumulated profit|retained profit/, 'Retained Earnings', 95],
    [/share capital|paid up capital/, 'Share Capital', 95],
    [/share premium/, 'Equity', 90],
    [/equity|capital/, 'Equity', 88],
    [/revenue|sales|turnover|income from operation/, 'Revenue', 94],
    [/other income|misc income|miscellaneous income|non operating income/, 'Revenue', 80],
    [/cost of sales|cogs|cost of goods|direct cost/, 'Cost of Sales', 92],
    [/operating expense|opex|admin expense|general expense|overhead/, 'Operating Expenses', 88],
    [/depreciation|amortis|amortiz/, 'Operating Expenses', 85],
    [/finance cost|interest expense|borrowing cost/, 'Operating Expenses', 84],
    [/trade receivable|account receivable|debtor|receivable/, 'Current Assets', 91],
    [/inventory|stock|wip|work in progress/, 'Current Assets', 88],
    [/prepaid|advance payment|prepayment/, 'Current Assets', 82],
    [/other current asset/, 'Current Assets', 80],
    [/property plant|ppe|fixed asset|tangible asset/, 'Non-Current Assets', 90],
    [/intangible|goodwill|patent|trademark/, 'Non-Current Assets', 88],
    [/investment property/, 'Non-Current Assets', 85],
    [/non.current asset|long.term asset/, 'Non-Current Assets', 88],
    [/trade payable|account payable|creditor|payable/, 'Current Liabilities', 91],
    [/accrual|accrued/, 'Current Liabilities', 85],
    [/short.term loan|current portion|overdraft/, 'Current Liabilities', 84],
    [/other current liabilit/, 'Current Liabilities', 80],
    [/long.term loan|non.current loan|deferred/, 'Non-Current Liabilities', 86],
    [/non.current liabilit|long.term liabilit/, 'Non-Current Liabilities', 88],
    [/ebitda/, 'EBITDA', 99],
    [/gross profit/, 'Gross Profit', 97],
    [/net profit|net income|profit after tax|pat/, 'Net Profit', 95],
    [/budgeted revenue|budget revenue/, 'Budgeted Revenue', 99],
    [/actual revenue/, 'Actual Revenue', 99],
    [/budgeted expense|budget expense/, 'Budgeted Expenses', 99],
    [/actual expense/, 'Actual Expenses', 99],
    [/operating activit/, 'Operating Activities', 99],
    [/investing activit/, 'Investing Activities', 99],
    [/financing activit/, 'Financing Activities', 99],
    [/opening balance|beginning balance/, 'Opening Balance', 99],
    [/closing balance|ending balance/, 'Closing Balance', 99],
    [/regulatory fee/, 'Regulatory Fees', 98],
    [/penalt/, 'Penalties', 97],
    [/tax paid|income tax paid/, 'Tax Paid', 97],
    [/exempt income/, 'Exempt Income', 99],
    [/disallowed expense/, 'Disallowed Expenses', 99],
    [/prior year loss|brought forward loss/, 'Prior Year Losses', 98],
    [/interest income|finance income/, 'Interest Income', 95],
    [/interest expense/, 'Interest Expense', 95],
    [/gross revenue/, 'Gross Revenue', 95],
    [/finance cost/, 'Finance Costs', 95],
    [/tax expense|income tax expense/, 'Tax Expense', 95],
    [/functional currency/, 'Functional Currency', 99],
    [/trade receivable.*operating|operating cash/, 'Operating Cash Flow', 88],
  ];

  for (const [pattern, field, confidence] of rules) {
    if (pattern.test(col) && systemFields.includes(field)) {
      return { field, confidence };
    }
  }
  return { field: null, confidence: 0 };
}

interface Props {
  columns: string[];
  systemFields: string[];
  reportType: string;
  onConfirm: (mappings: ColumnMapping[]) => void;
  disabled?: boolean;
  /** Initial LLM suggestions from the upload step (applied on first load). */
  llmSuggestions?: Record<string, string>;
  /** Initial Q&A questions from the upload step. */
  llmQuestions?: LlmQuestion[];
}

export function TrialBalanceMapper({ columns, systemFields, reportType, onConfirm, disabled, llmSuggestions = {}, llmQuestions: initialLlmQuestions = [] }: Props) {
  const [mappings, setMappings] = useState<ColumnMapping[]>([]);
  const [dragSource, setDragSource] = useState<string | null>(null);
  const [llmApplying, setLlmApplying] = useState(false);
  const [llmQuestions, setLlmQuestions] = useState<LlmQuestion[]>(initialLlmQuestions);
  const [llmError, setLlmError] = useState('');
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({});

  const buildMappings = (cols: string[], extraSuggestions: Record<string, string> = {}) =>
    cols.map(col => {
      const { field, confidence } = suggestMapping(col, systemFields);
      if (field) return { rawColumn: col, systemField: field, confidence };
      const llmField = extraSuggestions[col];
      if (llmField && systemFields.includes(llmField)) {
        return { rawColumn: col, systemField: llmField, confidence: 80 };
      }
      return { rawColumn: col, systemField: null, confidence: undefined };
    });

  useEffect(() => {
    setMappings(buildMappings(columns, llmSuggestions));
  }, [columns, systemFields]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAutoApply = async () => {
    setLlmApplying(true);
    setLlmError('');
    setLlmQuestions([]);
    try {
      const unmappedCols = mappings.filter(m => !m.systemField).map(m => m.rawColumn);
      if (unmappedCols.length === 0) return;

      const resp = await API.post('/api/reports/suggest-mappings', {
        columns: unmappedCols,
        report_type: reportType,
        system_fields: systemFields,
      });
      const data = resp.data as {
        mappings: Array<{
          column: string;
          field: string | null;
          confidence: number;
          question?: string;
          options?: string[];
        }>;
      };

      const questions: LlmQuestion[] = [];
      const newMappings = [...mappings];

      for (const item of data.mappings) {
        if (item.field && item.confidence >= 60) {
          const idx = newMappings.findIndex(m => m.rawColumn === item.column);
          if (idx !== -1) {
            newMappings[idx] = { rawColumn: item.column, systemField: item.field, confidence: item.confidence };
          }
        } else if (item.question && item.options) {
          questions.push({ column: item.column, question: item.question, options: item.options });
        }
      }

      setMappings(newMappings);
      setLlmQuestions(questions);
    } catch (err) {
      setLlmError(getErrMsg(err, 'Auto-mapping failed. Please map manually.'));
    } finally {
      setLlmApplying(false);
    }
  };

  const handleQuestionAnswer = (column: string, answer: string) => {
    setQuestionAnswers(prev => ({ ...prev, [column]: answer }));
    const systemField = systemFields.find(f => f === answer) ?? null;
    if (systemField) {
      setMappings(prev =>
        prev.map(m => m.rawColumn === column ? { ...m, systemField, confidence: undefined } : m)
      );
    }
    setLlmQuestions(prev => prev.filter(q => q.column !== column));
  };

  const handleDrop = (systemField: string) => {
    if (!dragSource) return;
    setMappings(prev =>
      prev.map(m => m.rawColumn === dragSource ? { ...m, systemField, confidence: undefined } : m)
    );
    setDragSource(null);
  };

  const handleUnmap = (rawColumn: string) => {
    setMappings(prev =>
      prev.map(m => m.rawColumn === rawColumn ? { ...m, systemField: null, confidence: undefined } : m)
    );
  };

  const unmapped = mappings.filter(m => !m.systemField && !llmQuestions.find(q => q.column === m.rawColumn));
  const hasSomeMapped = mappings.some(m => m.systemField);

  return (
    <div className="mapper">
      <div className="mapper__header">
        <div>
          <h2 className="mapper__title">Map Columns</h2>
          <p className="mapper__sub">
            AI suggestions are pre-applied. Drag unmapped columns onto system fields to map manually.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            className="btn-ghost"
            onClick={() => setMappings(buildMappings(columns, llmSuggestions))}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
            title="Reset to initial suggestions"
            disabled={llmApplying}
          >
            <RefreshCw size={14} />
            Reset
          </button>
          <button
            className="btn-ghost"
            onClick={handleAutoApply}
            disabled={llmApplying || mappings.every(m => m.systemField !== null)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
            title="Use AI to map remaining unmapped columns"
          >
            <Sparkles size={14} />
            {llmApplying ? 'Mapping…' : 'Auto-Apply AI'}
          </button>
        </div>
      </div>

      {/* Error banner */}
      {llmError && (
        <div style={{
          padding: '8px 12px',
          borderRadius: 'var(--s-r-sm)',
          background: 'rgba(248,113,113,0.08)',
          border: '1px solid var(--s-danger)',
          color: 'var(--s-danger)',
          fontFamily: 'var(--s-font-ui)',
          fontSize: '12px',
          marginBottom: '8px',
        }}>
          {llmError}
        </div>
      )}

      {/* LLM Q&A panel for ambiguous columns */}
      {llmQuestions.length > 0 && (
        <div style={{
          background: 'var(--s-elevated)',
          border: '1px solid var(--s-border)',
          borderRadius: 'var(--s-r-md)',
          padding: '16px',
          marginBottom: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
            The AI needs a little help with {llmQuestions.length} column{llmQuestions.length > 1 ? 's' : ''}:
          </div>
          {llmQuestions.map(q => (
            <div key={q.column} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-1)' }}>
                Column <strong>"{q.column}"</strong>: {q.question}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {q.options.map(opt => (
                  <button
                    key={opt}
                    onClick={() => handleQuestionAnswer(q.column, opt)}
                    style={{
                      padding: '4px 12px',
                      borderRadius: 'var(--s-r-sm)',
                      border: `1px solid ${questionAnswers[q.column] === opt ? 'var(--s-accent)' : 'var(--s-border)'}`,
                      background: questionAnswers[q.column] === opt ? 'var(--s-accent-dim)' : 'transparent',
                      color: questionAnswers[q.column] === opt ? 'var(--s-accent)' : 'var(--s-text-2)',
                      fontFamily: 'var(--s-font-ui)',
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mapper__columns">
        <div className="mapper__panel">
          <div className="mapper__panel-title">Raw Columns ({unmapped.length})</div>
          {unmapped.length === 0 ? (
            <div className="mapper__empty">All columns mapped ✓</div>
          ) : (
            unmapped.map(m => (
              <div
                key={m.rawColumn}
                className="mapper__chip"
                draggable
                onDragStart={() => setDragSource(m.rawColumn)}
              >
                {m.rawColumn}
              </div>
            ))
          )}
        </div>

        <div className="mapper__panel">
          <div className="mapper__panel-title">System Fields</div>
          {systemFields.map(field => {
            const mapping = mappings.find(m => m.systemField === field);
            const isAmber = mapping?.confidence !== undefined && mapping.confidence < 85;
            return (
              <div
                key={field}
                className={`mapper__field ${mapping ? 'mapper__field--mapped' : ''}`}
                onDragOver={e => e.preventDefault()}
                onDrop={() => handleDrop(field)}
              >
                <span className="mapper__field-label">{field}</span>
                {mapping && (
                  <div className="mapper__field-mapping">
                    <span className="mapper__field-raw">{mapping.rawColumn}</span>
                    {mapping.confidence !== undefined && (
                      <span
                        className="mapper__confidence"
                        style={{ color: isAmber ? 'var(--s-warning)' : undefined }}
                        title={isAmber ? 'Low confidence — please review' : undefined}
                      >
                        {mapping.confidence}%
                      </span>
                    )}
                    <button
                      className="mapper__unmap"
                      onClick={() => handleUnmap(mapping.rawColumn)}
                      title="Remove mapping"
                    >
                      ×
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mapper__footer">
        <button
          className="btn-primary"
          onClick={() => onConfirm(mappings)}
          disabled={disabled || !hasSomeMapped}
        >
          {disabled ? 'Validating…' : 'Confirm Mapping & Validate'}
        </button>
      </div>
    </div>
  );
}
