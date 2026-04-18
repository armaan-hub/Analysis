import { useFinanceStudio } from '../FinanceStudioContext';
import type { OutputType } from '../types';

interface Props { outputType: OutputType; label: string; }

export function ExportCard({ outputType, label }: Props) {
  const { outputs, generateOutput, selectedTemplateId } = useFinanceStudio();
  const latest = outputs
    .filter(o => o.output_type === outputType)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];

  const disabled = !selectedTemplateId || latest?.status === 'processing' || latest?.status === 'pending';

  return (
    <div className="export-card" data-testid={`export-${outputType}`}>
      <div className="export-card__label">{label}</div>
      <div className="export-card__status">{latest?.status ?? 'not started'}</div>
      {latest?.status === 'failed' && (
        <div className="export-card__error">{latest.error_message ?? 'failed'}</div>
      )}
      <div className="export-card__actions">
        <button disabled={disabled} onClick={() => generateOutput(outputType)}>
          {latest?.status === 'ready' ? 'Regenerate' : 'Generate'}
        </button>
        {latest?.status === 'ready' && latest.download_url && (
          <a href={`http://localhost:8000${latest.download_url}`}>Download</a>
        )}
      </div>
    </div>
  );
}
