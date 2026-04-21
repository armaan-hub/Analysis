import { useState, useCallback } from 'react';
import { Download } from 'lucide-react';
import { API } from '../../../lib/api';
import { StudioCards, type ReportType } from './StudioCards';
import { AuditorFormatGrid, type AuditorFormat } from './AuditorFormatGrid';
import { ReportPreview } from './ReportPreview';
import { type ChatMode } from './ModePills';

interface Props {
  sourceIds: string[];
  companyName?: string;
  mode?: ChatMode;
  onReportRequest?: (reportType: string) => void;
  onFormatChange?: (format: AuditorFormat) => void;
  auditorFormat?: AuditorFormat;
}

export function StudioPanel({ sourceIds, companyName = 'Analysis', mode, onReportRequest, onFormatChange, auditorFormat: controlledFormat }: Props) {
  const [localFormat, setLocalFormat] = useState<AuditorFormat>('standard');
  const format = controlledFormat ?? localFormat;

  const handleFormatChange = useCallback((f: AuditorFormat) => {
    if (onFormatChange) {
      onFormatChange(f);
    } else {
      setLocalFormat(f);
    }
  }, [onFormatChange]);
  const [activeReport, setActiveReport] = useState<ReportType | null>(null);
  const [reportContent, setReportContent] = useState('');
  const [generating, setGenerating] = useState(false);

  const handleGenerateReport = useCallback(async (type: ReportType) => {
    // Delegate to chat-redirect flow when callback is provided
    if (onReportRequest) {
      onReportRequest(type);
      return;
    }

    // Fallback: direct generation (legacy path)
    setActiveReport(type);
    setReportContent('');
    setGenerating(true);

    try {
      const backendFormat = format === 'legal' ? 'isa' : format === 'compliance' ? 'fta' : format;
      const backendType = type === 'forecast' ? 'financial_analysis' : type;
      const res = await API.post(`/api/reports/generate/${backendType}`, {
        mapped_data: [],
        requirements: {},
        source_ids: sourceIds,
        auditor_format: backendFormat,
        company_name: companyName,
        ...(type === 'forecast' ? { sub_type: 'forecast' } : {}),
      });
      setReportContent(res.data.report_text ?? res.data.draft ?? 'Report generated.');
    } catch (err) {
      setReportContent('Error generating report. Please try again.');
    } finally {
      setGenerating(false);
    }
  }, [format, sourceIds, companyName, onReportRequest]);

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
      <div className="studio-panel__title">
        {mode === 'analyst' ? 'Financial Reports' : 'Studio'}
      </div>
      <StudioCards onSelect={handleGenerateReport} disabled={generating} mode={mode} />
      <hr className="studio-divider" />
      <AuditorFormatGrid value={format} onChange={handleFormatChange} />
      <button
        type="button"
        className="export-btn"
        disabled={sourceIds.length === 0}
        onClick={() => handleGenerateReport('audit')}
      >
        <Download size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />Export PDF
      </button>
    </aside>
  );
}
