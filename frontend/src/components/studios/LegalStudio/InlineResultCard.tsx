import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from '../../../lib/api';

// ── Types ───────────────────────────────────────────────────────────────────

interface Finding {
  severity: 'low' | 'medium' | 'high';
  document: string;
  finding: string;
}

interface AuditData {
  risk_flags: Finding[];
  anomalies: Finding[];
  compliance_gaps: Finding[];
  summary: string;
}

interface Props {
  reportType: string;
  date: string;
  format?: string;
  content?: string;
  auditData?: AuditData;
  error?: string;
  onRetry?: () => void;
}

// ── Constants ───────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  high:   '#ef4444',
  medium: '#f59e0b',
  low:    '#6b7280',
};

const SECTION_META: { key: keyof Pick<AuditData, 'risk_flags' | 'anomalies' | 'compliance_gaps'>; label: string; color: string }[] = [
  { key: 'risk_flags',      label: 'Risk Flags',      color: 'var(--red, #ef4444)' },
  { key: 'anomalies',       label: 'Anomalies',       color: 'var(--amber, #f59e0b)' },
  { key: 'compliance_gaps', label: 'Compliance Gaps',  color: 'var(--teal, #a78bfa)' },
];

// ── Helpers ─────────────────────────────────────────────────────────────────

async function downloadExport(
  reportType: string,
  date: string,
  format: string | undefined,
  content: string | undefined,
  auditData: AuditData | undefined,
  exportFormat: 'pdf' | 'word' | 'excel',
) {
  const res = await fetch(`${API_BASE}/api/chat/export-deep-research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      report_type: reportType,
      date,
      format,
      content,
      audit_data: auditData,
      export_format: exportFormat,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(err.detail || 'Export failed');
  }

  const blob = await res.blob();
  const ext = exportFormat === 'word' ? 'docx' : exportFormat;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${reportType.replace(/\s+/g, '_')}_${date}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Sub-components ──────────────────────────────────────────────────────────

function FindingsSection({ title, rows, titleColor }: { title: string; rows: Finding[]; titleColor: string }) {
  if (!rows.length) return null;

  return (
    <details open>
      <summary style={{ fontSize: 13, fontWeight: 500, color: titleColor, cursor: 'pointer' }}>
        {title} ({rows.length})
      </summary>
      <ul style={{ listStyle: 'disc', paddingLeft: 20, margin: '4px 0' }}>
        {rows.map((r, i) => (
          <li key={i} style={{ fontSize: 12, color: 'var(--s-text-2)', marginBottom: 4 }}>
            <span style={{
              textTransform: 'uppercase',
              fontSize: 10,
              fontWeight: 600,
              color: SEVERITY_COLORS[r.severity] || '#6b7280',
            }}>
              {r.severity}
            </span>
            {' — '}
            <span style={{ color: 'var(--s-text-2)' }}>{r.document}:</span>{' '}
            {r.finding}
          </li>
        ))}
      </ul>
    </details>
  );
}

function ExportButton({ label, onClick, busy }: { label: string; onClick: () => void; busy: boolean }) {
  return (
    <button
      type="button"
      disabled={busy}
      onClick={onClick}
      style={{
        fontSize: 11,
        padding: '4px 10px',
        borderRadius: 'var(--s-r-sm)',
        border: '1px solid var(--s-border)',
        background: 'rgba(255,255,255,0.05)',
        color: 'var(--s-text-2)',
        cursor: busy ? 'wait' : 'pointer',
        opacity: busy ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

export function InlineResultCard({
  reportType,
  date,
  format,
  content,
  auditData,
  error,
  onRetry,
}: Props) {
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = async (fmt: 'pdf' | 'word' | 'excel') => {
    setExporting(fmt);
    setExportError(null);
    try {
      await downloadExport(reportType, date, format, content, auditData, fmt);
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  // ── Error state ─────────────────────────────────────────────────────────
  if (error) {
    return (
      <div style={{
        borderRadius: 'var(--s-r-sm)',
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.25)',
        padding: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#ef4444' }}>
          ❌ {reportType} — Failed
        </div>
        <div style={{ fontSize: 12, color: '#ef4444', opacity: 0.85 }}>{error}</div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            style={{
              alignSelf: 'flex-start',
              fontSize: 11,
              padding: '4px 12px',
              borderRadius: 'var(--s-r-sm)',
              border: '1px solid rgba(239,68,68,0.4)',
              background: 'rgba(239,68,68,0.12)',
              color: '#ef4444',
              cursor: 'pointer',
            }}
          >
            ↻ Retry
          </button>
        )}
      </div>
    );
  }

  // ── Normal state ────────────────────────────────────────────────────────
  const formattedDate = new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  });

  return (
    <div style={{
      borderRadius: 'var(--s-r-sm)',
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid var(--s-border)',
      padding: 14,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--s-text-1)' }}>
          📄 {reportType}
        </span>
        <span style={{
          fontSize: 10,
          padding: '2px 6px',
          borderRadius: 'var(--s-r-sm)',
          background: 'rgba(255,255,255,0.08)',
          color: 'var(--s-text-2)',
        }}>
          {formattedDate}
        </span>
        {format && (
          <span style={{
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: 'var(--s-r-sm)',
            background: 'var(--s-accent, var(--teal))',
            color: '#000',
            fontWeight: 600,
            textTransform: 'uppercase',
          }}>
            {format}
          </span>
        )}
      </div>

      {/* ── Body: audit findings ───────────────────────────────────────── */}
      {auditData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 13, color: 'var(--s-text-1)' }}>{auditData.summary}</div>
          {SECTION_META.map(({ key, label, color }) => (
            <FindingsSection key={key} title={label} rows={auditData[key]} titleColor={color} />
          ))}
        </div>
      )}

      {/* ── Body: markdown content ─────────────────────────────────────── */}
      {content && !auditData && (
        <div className="report-markdown" style={{ fontSize: 13, color: 'var(--s-text-1)' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}

      {/* ── Footer: export buttons ─────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        <ExportButton label="📥 PDF"   onClick={() => handleExport('pdf')}   busy={exporting === 'pdf'} />
        <ExportButton label="📝 Word"  onClick={() => handleExport('word')}  busy={exporting === 'word'} />
        <ExportButton label="📊 Excel" onClick={() => handleExport('excel')} busy={exporting === 'excel'} />
      </div>

      {exportError && (
        <div style={{ fontSize: 11, color: '#ef4444' }}>Export error: {exportError}</div>
      )}
    </div>
  );
}
