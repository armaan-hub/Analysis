import { useFinanceStudio } from '../FinanceStudioContext';
import { PreviewPage } from './PreviewPage';
import { API_BASE_URL } from '../../../../api-config';

export function ReportPreview() {
  const { outputs } = useFinanceStudio();
  const readyReport = outputs.find(o => o.output_type === 'audit_report' && o.status === 'ready');

  if (!readyReport) {
    return (
      <div className="report-preview report-preview--empty">
        <div className="report-preview__body">
          <PreviewPage pageNumber={1}>
            <h3>No report generated yet.</h3>
            <p className="muted">Generate an Audit Report from the Studio panel to preview it here.</p>
          </PreviewPage>
        </div>
      </div>
    );
  }

  return (
    <div className="report-preview">
      <iframe
        src={`${API_BASE_URL}${readyReport.download_url}`}
        title="Audit Report Preview"
        className="report-preview__iframe"
      />
    </div>
  );
}
