import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, Table2 } from 'lucide-react';
import { API, getErrMsg } from '../../../lib/api';
import type { AuditRow } from './AuditGrid';
import type { CompanyInfo } from './CompanyDocuments';

import type { EvidenceResult } from './AuditEvidenceStep';

interface Props {
  auditRows: AuditRow[];
  reportFields: Record<string, string>;
  companyInfo: CompanyInfo | null;
  auditEvidence?: EvidenceResult | null;
  reportMode?: 'standalone' | 'comparative';
  priorYearContent?: string;
  caQuestions?: Array<{ id: string; question: string; account: string; risk: string; answered: boolean }>;
  riskFlags?: Array<{ flag: string; triggered: boolean; detail: string }>;
  onDraftReady: (draft: string) => void;
}

export function AuditDraftViewer({ auditRows, reportFields, companyInfo, reportMode, priorYearContent, caQuestions, riskFlags, onDraftReady }: Props) {
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const handleDownload = async (format: 'docx' | 'xlsx' | 'pdf') => {
    try {
      const resp = await API.post(
        `/api/reports/export-${format}`,
        { content: draft, filename: `audit_draft_${new Date().toISOString().slice(0, 10)}` },
        { responseType: 'blob' }
      );
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_draft.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError('');
      try {
        const resp = await API.post('/api/reports/draft', {
          grouped_rows: auditRows.map(r => ({ account: r.account, mappedTo: r.mappedTo, amount: r.amount })),
          company_info: companyInfo,
          company_name: reportFields.company_name,
          auditor_name: reportFields.auditor_name,
          period_end: reportFields.period_end,
          report_mode: reportMode ?? 'standalone',
          prior_year_content: priorYearContent ?? '',
          ca_questions: caQuestions ?? [],
          risk_flags: riskFlags ?? [],
        }, { timeout: 0 });
        setDraft((resp.data as { report_text: string }).report_text);
      } catch (err) {
        setError(getErrMsg(err, 'Failed to generate draft report.'));
      } finally {
        setLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: '16px', padding: '40px' }}>
      <div className="chat-typing"><span /><span /><span /></div>
      <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
        Generating complete audit draft — large trial balances may take a few minutes…
      </div>
    </div>
  );

  if (error) return (
    <div style={{ padding: '32px 40px', color: 'var(--s-danger)', fontFamily: 'var(--s-font-ui)', fontSize: '13px' }}>{error}</div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      <div style={{ padding: '16px 40px', borderBottom: '1px solid var(--s-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div style={{ fontFamily: 'var(--s-font-display)', fontSize: '16px', fontWeight: 600, color: 'var(--s-text-1)' }}>
          Draft Audit Report
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => handleDownload('docx')}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}
            title="Download draft as Word"
          >
            <FileText size={13} /> Word
          </button>
          <button
            onClick={() => handleDownload('xlsx')}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}
            title="Download draft as Excel"
          >
            <Table2 size={13} /> Excel
          </button>
          <button
            onClick={() => handleDownload('pdf')}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}
            title="Download draft as PDF"
          >
            <FileText size={13} /> PDF
          </button>
          <button className="btn-primary" onClick={() => onDraftReady(draft)}>
            Select Format →
          </button>
        </div>
      </div>
      <div style={{ overflowY: 'auto', flex: 1, padding: '24px 40px' }}>
        <div className="report-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{draft}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
