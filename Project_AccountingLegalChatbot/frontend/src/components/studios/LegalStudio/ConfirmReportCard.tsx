import { useState, type FormEvent } from 'react';
import { type AuditorFormat } from './AuditorFormatGrid';

interface GenerateParams {
  entityName: string;
  periodEnd: string;
  format: AuditorFormat;
}

interface Props {
  reportType: string;
  reportLabel: string;
  entityName: string;
  periodEnd: string;
  documentsCount: number;
  format: AuditorFormat;
  confidence: 'high' | 'low' | 'none';
  onGenerate: (params: GenerateParams) => void;
  onEdit?: () => void;
}

export function ConfirmReportCard({
  reportLabel, entityName: initialEntity, periodEnd: initialPeriod,
  documentsCount, format: initialFormat, confidence, onGenerate, onEdit,
}: Props) {
  const [editing, setEditing] = useState(confidence === 'none');
  const [entityName, setEntityName] = useState(initialEntity);
  const [periodEnd, setPeriodEnd] = useState(initialPeriod);
  const [format, setFormat] = useState<AuditorFormat>(initialFormat);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onGenerate({ entityName, periodEnd, format });
  };

  return (
    <div style={{
      background: 'var(--s-bg-2, #f7fafc)', border: '1px solid var(--s-border, #e2e8f0)',
      borderRadius: 10, padding: '14px 16px', maxWidth: 420,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>📋 Ready to generate {reportLabel}</div>

      {confidence === 'low' && (
        <div style={{ color: '#dd6b20', fontSize: 12, marginBottom: 8 }}>
          ⚠ Please verify the detected details before generating.
        </div>
      )}

      {!editing ? (
        <>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <strong>Entity:</strong> {entityName || '—'}
          </div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <strong>Period:</strong> {periodEnd || '—'}
          </div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <strong>Documents:</strong> {documentsCount} in scope
          </div>
          <div style={{ fontSize: 13, marginBottom: 12 }}>
            <strong>Format:</strong> {format}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              aria-label="Generate Report"
              onClick={() => onGenerate({ entityName, periodEnd, format })}
              style={{
                background: 'var(--s-brand, #4299e1)', color: '#fff',
                border: 'none', borderRadius: 6, padding: '7px 14px',
                cursor: 'pointer', fontWeight: 600, fontSize: 13,
              }}
            >✅ Generate Report</button>
            <button
              type="button"
              aria-label="Edit Details"
              onClick={() => { setEditing(true); onEdit?.(); }}
              style={{
                background: 'none', border: '1px solid var(--s-border)', borderRadius: 6,
                padding: '7px 14px', cursor: 'pointer', fontSize: 13,
              }}
            >✏️ Edit Details</button>
          </div>
        </>
      ) : (
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
            Entity Name
            <input
              aria-label="entity name"
              value={entityName}
              onChange={e => setEntityName(e.target.value)}
              style={{ display: 'block', width: '100%', padding: '5px 8px', marginTop: 3,
                       border: '1px solid var(--s-border)', borderRadius: 5, fontSize: 13 }}
            />
          </label>
          <label style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
            Period End
            <input
              aria-label="period end"
              value={periodEnd}
              onChange={e => setPeriodEnd(e.target.value)}
              style={{ display: 'block', width: '100%', padding: '5px 8px', marginTop: 3,
                       border: '1px solid var(--s-border)', borderRadius: 5, fontSize: 13 }}
            />
          </label>
          <label style={{ display: 'block', marginBottom: 12, fontSize: 13 }}>
            Format
            <select
              value={format}
              onChange={e => setFormat(e.target.value as AuditorFormat)}
              style={{ display: 'block', width: '100%', padding: '5px 8px', marginTop: 3,
                       border: '1px solid var(--s-border)', borderRadius: 5, fontSize: 13 }}
            >
              {(['standard', 'big4', 'legal', 'compliance', 'custom'] as AuditorFormat[]).map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            aria-label="Generate Report"
            style={{
              background: 'var(--s-brand, #4299e1)', color: '#fff',
              border: 'none', borderRadius: 6, padding: '7px 14px',
              cursor: 'pointer', fontWeight: 600, fontSize: 13,
            }}
          >✅ Generate Report</button>
        </form>
      )}
    </div>
  );
}
