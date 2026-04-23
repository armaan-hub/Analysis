import { useMemo, Suspense, lazy } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChartDataPoint } from './MisChart';

const MisKpiCards = lazy(() =>
  import('./MisKpiCards').then(m => ({ default: m.MisKpiCards }))
);
const MisChart = lazy(() =>
  import('./MisChart').then(m => ({ default: m.MisChart }))
);

interface Props {
  open: boolean;
  title: string;
  reportType: string;
  content: string;
  loading: boolean;
  onClose: () => void;
  onExport: () => void;
}

function parseKpis(content: string) {
  const KPI_KEYS = ['Revenue', 'Expenses', 'Net Profit', 'Gross Margin', 'EBITDA', 'Cash Position'];
  return KPI_KEYS.flatMap(key => {
    const m = content.match(new RegExp(`${key}[:\\s]+(AED[\\s\\d,]+|\\d[\\d,\\.]+)`, 'i'));
    return m ? [{ label: key, value: m[1].trim() }] : [];
  });
}

function parseChartData(content: string): ChartDataPoint[] {
  try {
    const m = content.match(/```(?:json)?\s*(\[[\s\S]*?\])\s*```/);
    if (m) return JSON.parse(m[1]) as ChartDataPoint[];
  } catch {
    // ignore malformed JSON
  }
  return [];
}

export function ArtifactPanel({ open, title, reportType, content, loading, onClose, onExport }: Props) {
  const kpis = useMemo(() => reportType === 'mis' ? parseKpis(content) : [], [content, reportType]);
  const chartData = useMemo(() => reportType === 'mis' ? parseChartData(content) : [], [content, reportType]);

  if (!open) return null;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'hidden',
      background: 'var(--s-bg-1, #fff)', borderLeft: '1px solid var(--s-border, #e2e8f0)',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--s-border)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ fontWeight: 700, fontSize: 14, flex: 1 }}>📊 <span>{title}</span></span>
        <button
          aria-label="export"
          onClick={onExport}
          style={{ background: 'none', border: '1px solid var(--s-border)', borderRadius: 6,
                   padding: '4px 10px', cursor: 'pointer', fontSize: 12 }}
        >Export Markdown</button>
        <button
          aria-label="close"
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--s-text-2)' }}
        >✕</button>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px' }}>
        {loading ? (
          <div style={{ color: 'var(--s-text-2)', textAlign: 'center', marginTop: 40 }}>
            ⏳ Generating report…
          </div>
        ) : (
          <>
            {reportType === 'mis' && kpis.length > 0 && (
              <Suspense fallback={<div className="loading-placeholder">Loading charts…</div>}>
                <MisKpiCards kpis={kpis} />
              </Suspense>
            )}
            {reportType === 'mis' && chartData.length > 0 && (
              <Suspense fallback={<div className="loading-placeholder">Loading charts…</div>}>
                <div style={{ marginBottom: 16 }}>
                  <MisChart data={chartData} type="bar" />
                </div>
              </Suspense>
            )}
            <div style={{
              fontSize: 13, lineHeight: 1.7, color: 'var(--s-text-1)',
              fontFamily: 'var(--s-font-ui, system-ui)',
            }}>
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
