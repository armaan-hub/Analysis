import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { RefreshCw } from 'lucide-react';
import { API, getErrMsg } from '../../../lib/api';
import type { AuditRow } from './AuditGrid';

interface Props {
  reportType: string;
  auditRows: AuditRow[];
  reportFields: Record<string, string>;
  requirements?: Record<string, string>;
  onAdvance: () => void;
  onDownloadUrl?: (url: string) => void;
}

const STATUS_MESSAGES = [
  'Analyzing mapped data…',
  'Applying regulatory framework…',
  'Generating narrative…',
  'Formatting report…',
  'Almost done…',
];

export function ReportPreview({ reportType, auditRows, reportFields, requirements, onAdvance, onDownloadUrl }: Props) {
  const [reportText, setReportText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusIdx, setStatusIdx] = useState(0);

  const generate = async () => {
    setLoading(true);
    setError('');
    setReportText(null);
    setStatusIdx(0);

    const ticker = setInterval(() => {
      setStatusIdx(i => (i + 1) % STATUS_MESSAGES.length);
    }, 1800);

    try {
      const payload: Record<string, unknown> = {
        ...reportFields,
        mapped_data: auditRows.map(r => ({
          account: r.account,
          mapped_to: r.mappedTo,
          amount: r.amount,
        })),
        ...(requirements && Object.keys(requirements).length > 0 ? { requirements } : {}),
      };
      const r = await API.post(`/api/reports/generate/${reportType}`, payload);
      const data = r.data as { report_text?: string; content?: string; download_url?: string };
      setReportText(data.report_text ?? data.content ?? JSON.stringify(data, null, 2));
      if (data.download_url) onDownloadUrl?.(data.download_url);
    } catch (err) {
      setError(getErrMsg(err, 'Report generation failed. Please try again.'));
    } finally {
      clearInterval(ticker);
      setLoading(false);
    }
  };

  // Auto-generate on mount
  useEffect(() => { generate(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      overflow: 'hidden',
      padding: '24px 32px',
      gap: '16px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--s-font-ui)',
            fontWeight: 600,
            fontSize: '15px',
            color: 'var(--s-text-1)',
          }}>
            AI Report Generation
          </div>
          <div style={{
            fontFamily: 'var(--s-font-ui)',
            fontSize: '12px',
            color: 'var(--s-text-2)',
            marginTop: '2px',
          }}>
            {loading ? STATUS_MESSAGES[statusIdx] : reportText ? 'Review the report below before exporting.' : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn-ghost"
            onClick={generate}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
          >
            <RefreshCw size={14} />
            Regenerate
          </button>
          {reportText && !loading && (
            <button className="btn-primary" onClick={onAdvance}>
              Proceed to Export →
            </button>
          )}
        </div>
      </div>

      {loading && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          gap: '16px',
        }}>
          <div className="loading-spinner" />
          <div style={{
            fontFamily: 'var(--s-font-ui)',
            fontSize: '13px',
            color: 'var(--s-text-2)',
          }}>
            {STATUS_MESSAGES[statusIdx]}
          </div>
        </div>
      )}

      {error && !loading && (
        <div style={{
          padding: '16px',
          borderRadius: 'var(--s-r-md)',
          background: 'rgba(248,113,113,0.08)',
          border: '1px solid var(--s-danger)',
          color: 'var(--s-danger)',
          fontFamily: 'var(--s-font-ui)',
          fontSize: '13px',
        }}>
          {error}
        </div>
      )}

      {reportText && !loading && (
        <div style={{
          flex: 1,
          overflowY: 'auto',
          background: 'var(--s-surface)',
          border: '1px solid var(--s-border)',
          borderRadius: 'var(--s-r-md)',
          padding: '24px',
          fontFamily: 'var(--s-font-ui)',
          fontSize: '13px',
          color: 'var(--s-text-1)',
          lineHeight: 1.7,
        }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportText}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
