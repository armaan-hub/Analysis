import { useEffect, useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import { API_BASE_URL } from '../../../../../api-config';

interface Template { id: string; name: string; confidence?: number; is_prebuilt?: boolean; }

export function FormatPicker() {
  const { selectedTemplateId, setSelectedTemplate } = useFinanceStudio();
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    (async () => {
      const [custom, prebuilt] = await Promise.all([
        fetch(`${API_BASE_URL}/api/templates/list`).then(r => r.json()),
        fetch(`${API_BASE_URL}/api/templates/prebuilt`).then(r => r.json()),
      ]);
      const all: Template[] = [
        ...(prebuilt.templates || []).map((t: Template) => ({ ...t, is_prebuilt: true })),
        ...(custom.templates || []),
      ];
      setTemplates(all);
    })();
  }, []);

  const selected = templates.find(t => t.id === selectedTemplateId);
  const lowConfidence = selected && !selected.is_prebuilt && (selected.confidence ?? 1) < 0.7;

  return (
    <div className="format-picker">
      <label>Auditor format</label>
      <select
        value={selectedTemplateId ?? ''}
        onChange={e => setSelectedTemplate(e.target.value || null)}
      >
        <option value="">— Select —</option>
        <optgroup label="Prebuilt">
          {templates.filter(t => t.is_prebuilt).map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </optgroup>
        <optgroup label="Custom (learned)">
          {templates.filter(t => !t.is_prebuilt).map(t => (
            <option key={t.id} value={t.id}>
              {t.name}{t.confidence != null ? ` (${Math.round(t.confidence * 100)}%)` : ''}
            </option>
          ))}
        </optgroup>
      </select>
      {lowConfidence && (
        <div className="format-picker__warn">
          ⚠ Low confidence — review before generating.
        </div>
      )}
    </div>
  );
}
