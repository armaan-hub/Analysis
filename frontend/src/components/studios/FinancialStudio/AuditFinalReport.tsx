import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, Table2, Save } from 'lucide-react';
import { API, getErrMsg } from '../../../lib/api';
import type { AuditFormat } from './AuditFormatSelector';

interface Props {
  draft: string;
  format: AuditFormat;
  customInstructions?: string;
  priorYearContent?: string;
  onAdvance: () => void;
  onSave?: (content: string) => void;
}

export function AuditFinalReport({ draft, format, customInstructions, priorYearContent, onAdvance, onSave }: Props) {
  const [report, setReport] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const handleDownload = async (fmt: 'docx' | 'xlsx' | 'pdf') => {
    try {
      const resp = await API.post(
        `/api/reports/export-${fmt}`,
        { content: report, filename: `audit_final_${new Date().toISOString().slice(0, 10)}` },
        { responseType: 'blob' }
      );
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_final.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
  };

  const handleSave = () => {
    onSave?.(report);
    setSaved(true);
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError('');
      try {
        const resp = await API.post('/api/reports/format', {
          draft,
          format,
          custom_instructions: customInstructions,
          prior_year_template: priorYearContent ?? '',
        }, { timeout: 0 });
        setReport((resp.data as { report_text: string }).report_text);
      } catch (err) {
        setError(getErrMsg(err, 'Failed to format report.'));
      } finally {
        setLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: '16px', padding: '40px' }}>
      <div className="chat-typing"><span /><span /><span /></div>
      <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
        Reformatting to {format.toUpperCase()} standard — adding all required sections…
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
          Final Audit Report
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => handleDownload('docx')}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}
            title="Download final report as Word"
          >
            <FileText size={13} /> Word
          </button>
          <button
            onClick={() => handleDownload('xlsx')}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}
            title="Download final report as Excel"
          >
            <Table2 size={13} /> Excel
          </button>
          <button
            onClick={() => handleDownload('pdf')}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}
            title="Download final report as PDF"
          >
            <FileText size={13} /> PDF
          </button>
          <button
            onClick={handleSave}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: saved ? 'var(--s-success, #22c55e)' : 'var(--s-text-2)' }}
            title="Save report"
          >
            <Save size={13} /> {saved ? 'Saved ✓' : 'Save'}
          </button>
          <button className="btn-primary" onClick={onAdvance}>
            Proceed to Export →
          </button>
        </div>
      </div>
      <div style={{ overflowY: 'auto', flex: 1, padding: '24px 40px' }}>
        <div className="report-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
