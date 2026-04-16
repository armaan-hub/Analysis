import { useState, useMemo, useRef, useEffect } from 'react';
import { Paperclip, CheckCircle2 } from 'lucide-react';
import type { AuditRow } from './AuditGrid';
import { API } from '../../../lib/api';

import type { CompanyInfo } from './CompanyDocuments';

export interface EvidenceItem {
  id: string;
  account: string;
  category: string;
  amount: number;
  response: 'confirmed' | 'unavailable' | 'contradicts';
}

type OpinionType = 'unqualified' | 'qualified' | 'disclaimer' | 'adverse';

export interface EvidenceResult {
  items: EvidenceItem[];
  opinion: OpinionType;
  disclaimer: string;
  caQuestions: Array<{ id: string; question: string; account: string; risk: string; answered: boolean }>;
  riskFlags: Array<{ flag: string; triggered: boolean; detail: string }>;
}

interface Props {
  auditRows: AuditRow[];
  companyInfo?: CompanyInfo | null;
  onComplete: (evidence: EvidenceResult) => void;
}

function requiresExternalConfirmation(account: string, category: string): boolean {
  const lc = `${account} ${category}`.toLowerCase();
  return (
    lc.includes('bank') ||
    lc.includes('cash') ||
    category === 'Cash and Cash Equivalents' ||
    lc.includes('od') ||
    lc.includes('overdraft')
  );
}

function isSuspiciousAmount(amount: number, totalAbs: number): boolean {
  if (totalAbs === 0) return false;
  // Flag if a single item is more than 40% of total absolute value
  return Math.abs(amount) > totalAbs * 0.4;
}

export function AuditEvidenceStep({ auditRows, companyInfo, onComplete }: Props) {
  const totalAbs = auditRows.reduce((s, r) => s + Math.abs(r.amount), 0);

  const [caQuestions, setCaQuestions] = useState<Array<{id: string; question: string; account: string; risk: string}>>([]);
  const [caAnswers, setCaAnswers] = useState<Record<string, boolean>>({});
  const [riskFlags, setRiskFlags] = useState<Array<{ flag: string; triggered: boolean; detail: string }>>([]);

  useEffect(() => {
    API.post('/api/reports/audit/ca-questions', {
      tb_data: auditRows.map(r => ({ account: r.account, mappedTo: r.mappedTo, amount: r.amount })),
      trial_balance_rows: auditRows.map(r => ({ account: r.account, mappedTo: r.mappedTo, amount: r.amount })),
      company_info: companyInfo ?? {},
    })
      .then(res => {
        setCaQuestions(res.data.questions ?? []);
        setRiskFlags(res.data.risk_flags ?? []);
      })
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Track attached bank confirmation files per row id
  const [attachments, setAttachments] = useState<Record<string, File>>({});
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const handleAttach = (id: string, file: File) => {
    setAttachments(prev => ({ ...prev, [id]: file }));
    // Auto-confirm the row once a document is attached
    setItems(prev => prev.map(i => i.id === id ? { ...i, response: 'confirmed' } : i));
  };

  const [items, setItems] = useState<EvidenceItem[]>(() =>
    auditRows.map(r => {
      const needsConfirmation =
        requiresExternalConfirmation(r.account, r.mappedTo) ||
        isSuspiciousAmount(r.amount, totalAbs);
      return {
        id: r.id,
        account: r.account,
        category: r.mappedTo,
        amount: r.amount,
        response: needsConfirmation ? ('unavailable' as const) : ('confirmed' as const),
      };
    })
  );

  const opinion = useMemo<OpinionType>(() => {
    if (items.every(i => i.response === 'confirmed')) return 'unqualified';
    if (items.some(i => i.response === 'contradicts')) return 'adverse';
    const unavailable = items.filter(i => i.response === 'unavailable');
    const totalAbs = items.reduce((s, i) => s + Math.abs(i.amount), 0);
    const pervasive =
      unavailable.length >= 3 ||
      unavailable.some(i => totalAbs > 0 && Math.abs(i.amount) > totalAbs * 0.3);
    return pervasive ? 'disclaimer' : 'qualified';
  }, [items]);

  const disclaimer = useMemo<string>(() => {
    if (opinion === 'unqualified')
      return 'In our opinion, the financial statements present fairly, in all material respects, the financial position of the entity in accordance with IFRS (ISA 700.35).';
    if (opinion === 'adverse')
      return 'In our opinion, because of the significance of the matters described in the Basis for Adverse Opinion paragraph, the financial statements do not present fairly the financial position of the entity (ISA 705.8).';
    if (opinion === 'disclaimer')
      return 'We do not express an opinion on the financial statements. Because of the significance of the matters described in the Basis for Disclaimer of Opinion paragraph, we were unable to obtain sufficient appropriate audit evidence (ISA 705.9).';
    const unavailableAccounts = items
      .filter(i => i.response === 'unavailable')
      .map(i => i.account)
      .join(', ');
    return `Except for the possible effects of the matters described in the Basis for Qualified Opinion paragraph (${unavailableAccounts}), the financial statements present fairly, in all material respects, the financial position (ISA 705.7).`;
  }, [opinion, items]);

  const opinionConfig: Record<OpinionType, { color: string; label: string }> = {
    unqualified: { color: '#16a34a', label: 'Unqualified Opinion — ISA 700' },
    qualified:   { color: '#b45309', label: 'Qualified Opinion — ISA 705.7 Except For' },
    disclaimer:  { color: '#ea580c', label: 'Disclaimer of Opinion — ISA 705.9' },
    adverse:     { color: 'var(--s-danger)', label: 'Adverse Opinion — ISA 705.8' },
  };

  const { color, label } = opinionConfig[opinion];

  const setResponse = (id: string, response: EvidenceItem['response']) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, response } : i));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', fontFamily: 'var(--s-font-ui)' }}>
      {/* Header */}
      <div style={{ padding: '16px 40px', borderBottom: '1px solid var(--s-border)', flexShrink: 0 }}>
        <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--s-text-1)' }}>Audit Evidence</div>
        <div style={{ fontSize: '12px', color: 'var(--s-text-2)', marginTop: '4px' }}>
          Review each TB line and record your evidence finding. The opinion indicator updates in real time per ISA 700/705.
        </div>
      </div>

      {caQuestions.length > 0 && (
        <div style={{ padding: '16px 40px', borderBottom: '1px solid var(--s-border)', flexShrink: 0 }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--s-text-1)', marginBottom: '10px' }}>
            CA Clarification Questions
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {caQuestions.map(q => (
              <label key={q.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', cursor: 'pointer', padding: '8px 10px', borderRadius: 'var(--s-r-sm)', background: 'var(--s-surface)', border: `1px solid ${q.risk === 'high' ? 'var(--s-danger)' : 'var(--s-border)'}` }}>
                <input
                  type="checkbox"
                  checked={caAnswers[q.id] ?? false}
                  onChange={e => setCaAnswers(prev => ({ ...prev, [q.id]: e.target.checked }))}
                  style={{ marginTop: '2px', accentColor: q.risk === 'high' ? 'var(--s-danger)' : 'var(--s-accent)', flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--s-text-1)', lineHeight: 1.4 }}>{q.question}</div>
                  <div style={{ fontSize: '10px', color: q.risk === 'high' ? 'var(--s-danger)' : '#b45309', marginTop: '2px', fontWeight: 600 }}>
                    {q.risk.toUpperCase()} RISK — {q.account}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </div>
      )}

      <div style={{ overflowY: 'auto', flex: 1, padding: '24px 40px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Legend */}
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)', display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '8px 12px', borderRadius: '6px', background: 'var(--s-surface)', border: '1px solid var(--s-border)' }}>
          <span style={{ color: '#b45309', fontWeight: 600 }}>● Unavailable (pre-flagged)</span>
          <span>— Bank/cash accounts require a bank confirmation letter (ISA 505). Large balances (&gt;40% of TB) are flagged for additional scrutiny. Change to "Confirmed" once evidence is obtained.</span>
        </div>

        {/* Opinion indicator — sticky inside scroll container */}
        <div style={{
          position: 'sticky', top: 0, zIndex: 10,
          background: 'var(--s-surface)',
          border: `1px solid ${color}`,
          borderRadius: '8px',
          padding: '12px 16px',
        }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color }}>
            {label}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--s-text-2)', marginTop: '4px', lineHeight: 1.5 }}>
            {disclaimer}
          </div>
        </div>

        {/* Evidence table */}
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: 'var(--s-text-1)' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--s-border)' }}>
              {['Account', 'Category', 'Amount (AED)', 'Evidence Response'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(item => {
              const flaggedBank = requiresExternalConfirmation(item.account, item.category);
              const flaggedAmount = isSuspiciousAmount(item.amount, totalAbs);
              const flagReason = flaggedBank
                ? 'Bank/cash — confirmation letter required (ISA 505)'
                : flaggedAmount
                ? 'Large balance — additional scrutiny required'
                : '';
              return (
              <tr key={item.id} style={{ borderBottom: '1px solid var(--s-border)', background: flagReason ? 'rgba(180,83,9,0.04)' : undefined }}>
                <td style={{ padding: '10px 12px' }}>
                  <div>{item.account}</div>
                  {flagReason && <div style={{ fontSize: '10px', color: '#b45309', marginTop: '2px' }}>⚑ {flagReason}</div>}
                </td>
                <td style={{ padding: '10px 12px', color: 'var(--s-text-2)' }}>{item.category}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {item.amount.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                      {(
                        [
                          { value: 'confirmed',   label: 'Confirmed ✓',  accent: 'var(--s-accent)' },
                          { value: 'unavailable', label: 'Unavailable',   accent: '#b45309' },
                          { value: 'contradicts', label: 'Contradicts TB', accent: 'var(--s-danger)' },
                        ] as const
                      ).map(opt => (
                        <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '12px' }}>
                          <input
                            type="radio"
                            name={`resp-${item.id}`}
                            value={opt.value}
                            checked={item.response === opt.value}
                            onChange={() => setResponse(item.id, opt.value)}
                            style={{ accentColor: opt.accent, cursor: 'pointer' }}
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                    {/* Bank confirmation letter attachment — shown for bank/cash flagged rows */}
                    {flaggedBank && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <input
                          ref={el => { fileInputRefs.current[item.id] = el; }}
                          type="file"
                          accept=".pdf,.jpg,.jpeg,.png,.docx"
                          style={{ display: 'none' }}
                          onChange={e => {
                            const f = e.target.files?.[0];
                            if (f) handleAttach(item.id, f);
                            e.target.value = '';
                          }}
                        />
                        {attachments[item.id] ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#16a34a' }}>
                            <CheckCircle2 size={13} />
                            <span>{attachments[item.id].name}</span>
                            <button
                              onClick={() => fileInputRefs.current[item.id]?.click()}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '11px', color: 'var(--s-text-2)', textDecoration: 'underline', padding: 0 }}
                            >Replace</button>
                          </div>
                        ) : (
                          <button
                            onClick={() => fileInputRefs.current[item.id]?.click()}
                            style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '3px 8px', borderRadius: 'var(--s-r-sm)', border: '1px dashed #b45309', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: '#b45309' }}
                          >
                            <Paperclip size={11} /> Attach Bank Statement (ISA 505)
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>

        {/* Continue */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '8px' }}>
          <button className="btn-primary" onClick={() => {
            const questionsWithAnswers = caQuestions.map(q => ({
              ...q,
              answered: caAnswers[q.id] ?? false,
            }));
            onComplete({ items, opinion, disclaimer, caQuestions: questionsWithAnswers, riskFlags });
          }}>
            Continue →
          </button>
        </div>
      </div>
    </div>
  );
}
