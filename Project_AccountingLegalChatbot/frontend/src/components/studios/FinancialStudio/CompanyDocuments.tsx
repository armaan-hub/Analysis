import { useState } from 'react';
import { Pencil } from 'lucide-react';
import { API, getErrMsg } from '../../../lib/api';

export interface CompanyInfo {
  company_name: string;
  address: string;
  shareholders: string;
  activity: string;
  trade_license_number: string;
  registration_number: string;
  incorporation_date: string;
}

const FIELD_LABELS: Record<keyof CompanyInfo, string> = {
  company_name: 'Company Name',
  address: 'Registered Address',
  shareholders: 'Shareholders',
  activity: 'Business Activity',
  trade_license_number: 'Trade License Number',
  registration_number: 'Registration Number',
  incorporation_date: 'Incorporation Date',
};

const EMPTY_INFO: CompanyInfo = {
  company_name: '',
  address: '',
  shareholders: '',
  activity: '',
  trade_license_number: '',
  registration_number: '',
  incorporation_date: '',
};

interface Props {
  onComplete: (info: CompanyInfo, priorYearContext?: string) => void;
  onSkip: () => void;
}

export function CompanyDocuments({ onComplete, onSkip }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [extracted, setExtracted] = useState<CompanyInfo | null>(null);
  const [editedInfo, setEditedInfo] = useState<CompanyInfo>(EMPTY_INFO);
  const [editingFields, setEditingFields] = useState<Set<string>>(new Set());
  const [overriddenFields, setOverriddenFields] = useState<Set<string>>(new Set());
  const [priorYearFile, setPriorYearFile] = useState<File | null>(null);
  const [priorYearContext, setPriorYearContext] = useState<string>('');
  const [extractingPriorYear, setExtractingPriorYear] = useState(false);
  const [priorYearError, setPriorYearError] = useState<string>('');

  const handleExtract = async () => {
    if (files.length === 0) { onSkip(); return; }
    setLoading(true);
    setError('');
    try {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f));
      const resp = await API.post('/api/reports/extract-company-docs', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const data = { ...EMPTY_INFO, ...(resp.data as Partial<CompanyInfo>) };
      setExtracted(data);
      setEditedInfo(data);
      setEditingFields(new Set());
      setOverriddenFields(new Set());
    } catch (err) {
      setError(getErrMsg(err, 'Failed to extract company information.'));
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (key: string) => {
    setEditingFields(prev => new Set([...prev, key]));
  };

  const handleFieldChange = (key: keyof CompanyInfo, value: string) => {
    setEditedInfo(prev => ({ ...prev, [key]: value }));
    if (extracted && value !== extracted[key]) {
      setOverriddenFields(prev => new Set([...prev, key]));
    } else {
      setOverriddenFields(prev => { const next = new Set(prev); next.delete(key); return next; });
    }
  };

  const handlePriorYearUpload = async (file: File) => {
    setPriorYearFile(file);
    setPriorYearError('');
    setExtractingPriorYear(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/reports/extract-prior-year', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Extraction failed');
      const data = await res.json();
      setPriorYearContext(data.context || '');
    } catch (err) {
      console.error('Prior year extraction failed:', err);
      setPriorYearError('Could not extract prior year data. You can still proceed.');
    } finally {
      setExtractingPriorYear(false);
    }
  };

  /* ── Extracted-fields review phase ── */
  if (extracted) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '32px 40px', gap: '24px', maxWidth: '640px', margin: '0 auto', width: '100%', overflowY: 'auto' }}>
        <div>
          <div style={{ fontFamily: 'var(--s-font-display)', fontSize: '18px', fontWeight: 600, color: 'var(--s-text-1)', marginBottom: '4px' }}>
            Extracted Company Info
          </div>
          <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
            Fields were auto-extracted from your documents. Click the pencil icon to edit any value before continuing.
          </div>
        </div>

        {overriddenFields.size > 0 && (
          <div style={{ padding: '10px 14px', borderRadius: 'var(--s-r-sm)', background: 'rgba(180,83,9,0.08)', border: '1px solid #b45309', color: '#b45309', fontFamily: 'var(--s-font-ui)', fontSize: '13px' }}>
            ⚠ You are overriding an auto-extracted value. Verify this matches your official documents.
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {(Object.keys(FIELD_LABELS) as Array<keyof CompanyInfo>).map(key => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {FIELD_LABELS[key]}
              </label>
              {editingFields.has(key) ? (
                <input
                  type="text"
                  value={editedInfo[key]}
                  onChange={e => handleFieldChange(key, e.target.value)}
                  style={{
                    fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-1)',
                    padding: '8px 10px', borderRadius: 'var(--s-r-sm)',
                    border: `1px solid ${overriddenFields.has(key) ? '#b45309' : 'var(--s-border)'}`,
                    background: 'var(--s-surface)', outline: 'none', width: '100%', boxSizing: 'border-box',
                  }}
                />
              ) : (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <span style={{
                    fontFamily: 'var(--s-font-ui)', fontSize: '13px',
                    color: editedInfo[key] ? 'var(--s-text-1)' : 'var(--s-text-2)',
                    padding: '8px 10px', borderRadius: 'var(--s-r-sm)',
                    border: '1px solid var(--s-border)', background: 'var(--s-surface)',
                    flex: 1, minHeight: '34px', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>
                    {editedInfo[key] || '—'}
                  </span>
                  <button
                    onClick={() => handleEdit(key)}
                    title={`Edit ${FIELD_LABELS[key]}`}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--s-text-2)', padding: '6px', marginTop: '2px', borderRadius: 'var(--s-r-sm)', display: 'flex', alignItems: 'center' }}
                  >
                    <Pencil size={13} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Prior Year Financial Statements (optional) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Prior Year Financial Statements <span style={{ fontWeight: 400, textTransform: 'none' }}>(optional)</span>
          </label>
          <div
            style={{
              padding: '20px',
              borderRadius: 'var(--s-r-md)',
              border: `1px dashed ${priorYearFile ? 'var(--s-accent)' : 'var(--s-border)'}`,
              background: priorYearFile ? 'var(--s-accent-dim)' : 'var(--s-surface)',
              cursor: 'pointer',
              textAlign: 'center',
              minHeight: 72,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'var(--s-font-ui)',
              fontSize: '13px',
              color: 'var(--s-text-2)',
            }}
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file) handlePriorYearUpload(file);
            }}
            onClick={() => document.getElementById('prior-year-input')?.click()}
          >
            <input
              id="prior-year-input"
              type="file"
              accept=".pdf"
              style={{ display: 'none' }}
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) handlePriorYearUpload(file);
              }}
            />
            {extractingPriorYear ? (
              <span>Extracting prior year data…</span>
            ) : priorYearFile ? (
              <span style={{ color: 'var(--s-text-1)' }}>✓ {priorYearFile.name}</span>
            ) : (
              <span>Drop or click to upload prior year PDF</span>
            )}
          </div>
          {priorYearError && (
            <div style={{ padding: '10px 14px', borderRadius: 'var(--s-r-sm)', background: 'rgba(248,113,113,0.08)', border: '1px solid var(--s-danger)', color: 'var(--s-danger)', fontFamily: 'var(--s-font-ui)', fontSize: '13px' }}>
              {priorYearError}
            </div>
          )}
          {priorYearContext && !extractingPriorYear && (
            <div style={{ padding: '10px 14px', borderRadius: 'var(--s-r-sm)', background: 'rgba(34,197,94,0.08)', border: '1px solid #22c55e', color: '#22c55e', fontFamily: 'var(--s-font-ui)', fontSize: '13px' }}>
              Prior year data extracted successfully.
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={() => onComplete(editedInfo, priorYearContext)}>
            Continue →
          </button>
          <button className="btn-ghost" onClick={onSkip}>
            Skip
          </button>
        </div>
      </div>
    );
  }

  /* ── Upload phase ── */
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '32px 40px', gap: '24px', maxWidth: '640px', margin: '0 auto', width: '100%', overflowY: 'auto' }}>
      <div>
        <div style={{ fontFamily: 'var(--s-font-display)', fontSize: '18px', fontWeight: 600, color: 'var(--s-text-1)', marginBottom: '4px' }}>
          Company Documents
        </div>
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
          Upload supporting documents for company verification. The LLM will extract the company name, address, shareholders, and business activity to include in the audit report. This step is optional but recommended.
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Trade License, MOA / AOA, Shareholder Register
        </label>
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.doc,.xlsx,.xls,.jpg,.jpeg,.png,.txt"
          onChange={e => setFiles(Array.from(e.target.files ?? []))}
          style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}
        />
        {files.length > 0 && (
          <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
            {files.length} file(s): {files.map(f => f.name).join(', ')}
          </div>
        )}
      </div>

      {error && (
        <div style={{ padding: '12px', borderRadius: 'var(--s-r-sm)', background: 'rgba(248,113,113,0.08)', border: '1px solid var(--s-danger)', color: 'var(--s-danger)', fontFamily: 'var(--s-font-ui)', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* Prior Year Financial Statements (optional) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Prior Year Financial Statements <span style={{ fontWeight: 400, textTransform: 'none' }}>(optional)</span>
        </label>
        <div
          style={{
            padding: '20px',
            borderRadius: 'var(--s-r-md)',
            border: `1px dashed ${priorYearFile ? 'var(--s-accent)' : 'var(--s-border)'}`,
            background: priorYearFile ? 'var(--s-accent-dim)' : 'var(--s-surface)',
            cursor: 'pointer',
            textAlign: 'center',
            minHeight: 72,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'var(--s-font-ui)',
            fontSize: '13px',
            color: 'var(--s-text-2)',
          }}
          onDragOver={e => e.preventDefault()}
          onDrop={e => {
            e.preventDefault();
            const file = e.dataTransfer.files[0];
            if (file) handlePriorYearUpload(file);
          }}
          onClick={() => document.getElementById('prior-year-input')?.click()}
        >
          <input
            id="prior-year-input"
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={e => {
              const file = e.target.files?.[0];
              if (file) handlePriorYearUpload(file);
            }}
          />
          {extractingPriorYear ? (
            <span>Extracting prior year data…</span>
          ) : priorYearFile ? (
            <span style={{ color: 'var(--s-text-1)' }}>✓ {priorYearFile.name}</span>
          ) : (
            <span>Drop or click to upload prior year PDF</span>
          )}
        </div>
        {priorYearError && (
          <div style={{ padding: '10px 14px', borderRadius: 'var(--s-r-sm)', background: 'rgba(248,113,113,0.08)', border: '1px solid var(--s-danger)', color: 'var(--s-danger)', fontFamily: 'var(--s-font-ui)', fontSize: '13px' }}>
            {priorYearError}
          </div>
        )}
        {priorYearContext && !extractingPriorYear && (
          <div style={{ padding: '10px 14px', borderRadius: 'var(--s-r-sm)', background: 'rgba(34,197,94,0.08)', border: '1px solid #22c55e', color: '#22c55e', fontFamily: 'var(--s-font-ui)', fontSize: '13px' }}>
            Prior year data extracted successfully.
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <button className="btn-primary" onClick={handleExtract} disabled={loading}>
          {loading ? 'Extracting…' : files.length > 0 ? 'Upload & Continue →' : 'Skip →'}
        </button>
        {files.length > 0 && (
          <button className="btn-ghost" onClick={onSkip} disabled={loading}>
            Skip without uploading
          </button>
        )}
      </div>
    </div>
  );
}
