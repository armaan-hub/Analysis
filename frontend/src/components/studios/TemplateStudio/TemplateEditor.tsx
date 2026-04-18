import { useState } from 'react';
import { API, getErrMsg } from '../../../lib/api';
import { Save, X, AlertCircle, Loader2 } from 'lucide-react';
import './TemplateStudio.css';

/* ── Types ──────────────────────────────────────────────────────── */

interface TemplateForEdit {
  id: string;
  name: string;
  config: Record<string, unknown> | null;
}

interface Props {
  template: TemplateForEdit;
  onSave: () => void;
  onCancel: () => void;
}

/* ── Helpers ────────────────────────────────────────────────────── */

function getNestedString(obj: Record<string, unknown> | null, path: string): string {
  if (!obj) return '';
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current && typeof current === 'object' && part in (current as Record<string, unknown>)) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return '';
    }
  }
  return String(current ?? '');
}

function setNestedValue(obj: Record<string, unknown>, path: string, value: string): Record<string, unknown> {
  const clone = structuredClone(obj);
  const parts = path.split('.');
  let current: Record<string, unknown> = clone;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!(parts[i] in current) || typeof current[parts[i]] !== 'object') {
      current[parts[i]] = {};
    }
    current = current[parts[i]] as Record<string, unknown>;
  }
  const numVal = Number(value);
  current[parts[parts.length - 1]] = isNaN(numVal) || value === '' ? value : numVal;
  return clone;
}

/* ── Component ──────────────────────────────────────────────────── */

export function TemplateEditor({ template, onSave, onCancel }: Props) {
  const [config, setConfig] = useState<Record<string, unknown>>(template.config ?? {});
  const [rawJson, setRawJson] = useState(JSON.stringify(template.config ?? {}, null, 2));
  const [jsonMode, setJsonMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const updateField = (path: string, value: string) => {
    const updated = setNestedValue(config, path, value);
    setConfig(updated);
    setRawJson(JSON.stringify(updated, null, 2));
  };

  const handleJsonChange = (text: string) => {
    setRawJson(text);
    try {
      const parsed = JSON.parse(text) as Record<string, unknown>;
      setConfig(parsed);
      setError('');
    } catch {
      setError('Invalid JSON');
    }
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await API.put(`/api/templates/${template.id}`, { config });
      onSave();
    } catch (e) {
      setError(getErrMsg(e, 'Save failed'));
    } finally {
      setSaving(false);
    }
  };

  /* ── Form fields for common config ────────────────────────────── */

  const formFields: Array<{ label: string; path: string; placeholder: string }> = [
    { label: 'Page Width (pt)', path: 'page_size.width', placeholder: 'e.g. 595' },
    { label: 'Page Height (pt)', path: 'page_size.height', placeholder: 'e.g. 842' },
    { label: 'Margin Top (pt)', path: 'margins.top', placeholder: 'e.g. 72' },
    { label: 'Margin Bottom (pt)', path: 'margins.bottom', placeholder: 'e.g. 72' },
    { label: 'Margin Left (pt)', path: 'margins.left', placeholder: 'e.g. 72' },
    { label: 'Margin Right (pt)', path: 'margins.right', placeholder: 'e.g. 72' },
    { label: 'Primary Font', path: 'fonts.primary', placeholder: 'e.g. Times New Roman' },
    { label: 'Body Font Size', path: 'fonts.body_size', placeholder: 'e.g. 12' },
    { label: 'Heading Font', path: 'fonts.heading', placeholder: 'e.g. Arial Bold' },
    { label: 'Heading Font Size', path: 'fonts.heading_size', placeholder: 'e.g. 16' },
  ];

  return (
    <div className="ts-root">
      {/* Header */}
      <div className="ts-header">
        <h2 className="ts-header__title">Edit Template: {template.name}</h2>
        <div className="ts-header__actions">
          <button
            className={`ts-btn ${jsonMode ? 'ts-btn--primary' : 'ts-btn--secondary'}`}
            onClick={() => setJsonMode(!jsonMode)}
          >
            {jsonMode ? 'Form View' : 'JSON View'}
          </button>
          <button className="ts-btn ts-btn--primary" onClick={save} disabled={saving || !!error}>
            {saving ? <><Loader2 size={14} className="spin" /> Saving…</> : <><Save size={14} /> Save</>}
          </button>
          <button className="ts-btn ts-btn--secondary" onClick={onCancel}>
            <X size={14} /> Cancel
          </button>
        </div>
      </div>

      {error && (
        <div className="ts-alert ts-alert--error">
          <AlertCircle size={16} />
          <span>{error}</span>
          <X size={14} className="ts-alert__close" onClick={() => setError('')} />
        </div>
      )}

      {jsonMode ? (
        <div className="ts-section">
          <h3 className="ts-section__title">Raw JSON Configuration</h3>
          <textarea
            className="ts-json-editor"
            value={rawJson}
            onChange={e => handleJsonChange(e.target.value)}
            spellCheck={false}
          />
        </div>
      ) : (
        <div className="ts-section">
          <h3 className="ts-section__title">Template Configuration</h3>
          <div className="ts-form-grid">
            {formFields.map(f => (
              <div key={f.path} className="ts-form-field">
                <label className="ts-form-field__label">{f.label}</label>
                <input
                  className="ts-input"
                  value={getNestedString(config, f.path)}
                  onChange={e => updateField(f.path, e.target.value)}
                  placeholder={f.placeholder}
                />
              </div>
            ))}
          </div>

          <h3 className="ts-section__title" style={{ marginTop: 24 }}>Full Configuration (read-only)</h3>
          <pre className="ts-json-viewer">{JSON.stringify(config, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
