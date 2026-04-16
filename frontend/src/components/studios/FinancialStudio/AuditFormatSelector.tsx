import { useState } from 'react';
import { API } from '../../../lib/api';

export type AuditFormat = 'big4' | 'isa' | 'fta' | 'internal' | 'custom';

const FORMATS: Array<{ value: AuditFormat; label: string; description: string }> = [
  { value: 'big4',     label: 'Big 4 Standard',      description: 'ISA 700/701 with Key Audit Matters, Management Letter, and Big 4 disclosures' },
  { value: 'isa',      label: 'ISA 700',              description: 'ISA 700/701/705/706 full structure with all mandatory audit sections' },
  { value: 'fta',      label: 'UAE FTA Audit',        description: 'FTA compliance opinion with VAT, Corporate Tax, and AML/CFT findings' },
  { value: 'internal', label: 'Internal Audit (IIA)', description: 'Risk-rated findings, root cause analysis, and Management Action Plan' },
  { value: 'custom',   label: 'Custom Format',        description: "Paste your firm's template — LLM will follow its structure" },
];

interface Props {
  onSelect: (format: AuditFormat, customInstructions?: string) => void;
}

export function AuditFormatSelector({ onSelect }: Props) {
  const [selected, setSelected] = useState<AuditFormat>('big4');
  const [customText, setCustomText] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [extractedSections, setExtractedSections] = useState<Array<{heading: string; level: number}>>([]);

  const handleTemplateFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setExtracting(true);
    try {
      const form1 = new FormData();
      form1.append('file', file);
      const form2 = new FormData();
      form2.append('file', file);

      const [textResp, formatResp] = await Promise.all([
        API.post('/api/reports/extract-template', form1, { headers: { 'Content-Type': 'multipart/form-data' } }),
        API.post('/api/reports/extract-format', form2, { headers: { 'Content-Type': 'multipart/form-data' } }),
      ]);

      setCustomText((textResp.data as { text: string }).text);
      const formatData = formatResp.data as { sections: Array<{heading: string; level: number}>; section_count: number };
      setExtractedSections(formatData.sections ?? []);
    } catch {
      // silent — user can type manually
    } finally {
      setExtracting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '32px 40px', gap: '24px', maxWidth: '640px', margin: '0 auto', width: '100%', overflowY: 'auto' }}>
      <div>
        <div style={{ fontFamily: 'var(--s-font-display)', fontSize: '18px', fontWeight: 600, color: 'var(--s-text-1)', marginBottom: '4px' }}>
          Select Audit Format
        </div>
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
          The LLM will reformat your draft report to match the selected standard, adding all required sections, notes, and schedules.
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {FORMATS.map(f => (
          <button
            key={f.value}
            onClick={() => setSelected(f.value)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '4px',
              padding: '14px 16px', borderRadius: 'var(--s-r-sm)', textAlign: 'left', cursor: 'pointer',
              border: `1px solid ${selected === f.value ? 'var(--s-accent)' : 'var(--s-border)'}`,
              background: selected === f.value ? 'var(--s-accent-dim)' : 'var(--s-surface)',
            }}
          >
            <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', fontWeight: 600, color: selected === f.value ? 'var(--s-accent)' : 'var(--s-text-1)' }}>
              {f.label}
            </span>
            <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
              {f.description}
            </span>
          </button>
        ))}
      </div>

      {selected === 'custom' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <label style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Custom Format Instructions
          </label>

          {/* File upload section - above textarea */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '12px', color: 'var(--s-text-2)', fontFamily: 'var(--s-font-ui)' }}>
              Upload template file (PDF, DOCX, XLSX) — structure extracted automatically
            </span>
            <input
              type="file"
              accept=".pdf,.docx,.xlsx"
              onChange={handleTemplateFileUpload}
              disabled={extracting}
              style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}
            />
            {extracting && (
              <span style={{ fontSize: '12px', color: 'var(--s-text-2)', fontFamily: 'var(--s-font-ui)' }}>
                Extracting template structure…
              </span>
            )}
          </div>

          {extractedSections.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '11px', fontWeight: 600, color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Detected Sections ({extractedSections.length})
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxHeight: '140px', overflowY: 'auto', padding: '6px 8px', borderRadius: 'var(--s-r-sm)', background: 'var(--s-surface)', border: '1px solid var(--s-border)' }}>
                {extractedSections.map((s, i) => (
                  <div key={i} style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-1)', paddingLeft: `${(s.level - 1) * 12}px` }}>
                    {s.level === 1 ? '▸' : '·'} {s.heading}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Textarea */}
          <textarea
            value={customText}
            onChange={e => setCustomText(e.target.value)}
            placeholder="Template structure extracted here, or paste manually…"
            rows={6}
            style={{ background: 'var(--s-surface)', border: '1px solid var(--s-border)', borderRadius: 'var(--s-r-sm)', color: 'var(--s-text-1)', fontFamily: 'var(--s-font-ui)', fontSize: '13px', padding: '8px 12px', outline: 'none', resize: 'vertical' }}
          />
        </div>
      )}

      <button
        className="btn-primary"
        onClick={() => onSelect(selected, selected === 'custom' ? customText : undefined)}
        style={{ alignSelf: 'flex-start' }}
      >
        Generate Final Report →
      </button>
    </div>
  );
}
