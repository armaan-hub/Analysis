import { useState, useCallback } from 'react';
import { API } from '../../../lib/api';
import { StudioCards, type ReportType } from './StudioCards';
import { AuditorFormatGrid, type AuditorFormat } from './AuditorFormatGrid';
import { ReportPreview } from './ReportPreview';

interface Props {
  sourceIds: string[];
  companyName?: string;
}

export function StudioPanel({ sourceIds, companyName = 'Analysis' }: Props) {
  const [format, setFormat] = useState<AuditorFormat>('standard');
  const [activeReport, setActiveReport] = useState<ReportType | null>(null);
  const [reportContent, setReportContent] = useState('');
  const [generating, setGenerating] = useState(false);

  const handleGenerateReport = useCallback(async (type: ReportType) => {
    setActiveReport(type);
    setReportContent('');
    setGenerating(true);

    try {
      const backendFormat = format === 'legal' ? 'isa' : format === 'compliance' ? 'fta' : format;
      const res = await API.post(`/api/reports/generate/${type}`, {
        mapped_data: [],
        requirements: {},
        source_ids: sourceIds,
        auditor_format: backendFormat,
        company_name: companyName,
      });
      setReportContent(res.data.report_text ?? res.data.draft ?? 'Report generated.');
    } catch (err) {
      setReportContent('Error generating report. Please try again.');
    } finally {
      setGenerating(false);
    }
  }, [format, sourceIds, companyName]);

  const handleExport = useCallback(async () => {
    if (!reportContent) return;
    try {
      const res = await API.post('/api/reports/format', {
        draft: reportContent,
        format: format === 'legal' ? 'isa' : format === 'compliance' ? 'fta' : format,
      }, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${activeReport}-${format}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      const blob = new Blob([reportContent], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${activeReport}-${format}.md`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [reportContent, activeReport, format]);

  if (activeReport) {
    return (
      <aside className="studio-panel">
        <ReportPreview
          reportType={activeReport}
          format={format}
          content={reportContent}
          loading={generating}
          onBack={() => { setActiveReport(null); setReportContent(''); }}
          onExport={handleExport}
        />
      </aside>
    );
  }

  return (
    <aside className="studio-panel">
      <div className="studio-panel__title">Studio</div>
      <StudioCards onSelect={handleGenerateReport} disabled={generating} />
      <hr className="studio-divider" />
      <AuditorFormatGrid value={format} onChange={setFormat} />
      <button
        type="button"
        className="export-btn"
        disabled={sourceIds.length === 0}
        onClick={() => handleGenerateReport('audit')}
      >
        📥 Export PDF
      </button>
    </aside>
  );
}
