import React, { useEffect, useState } from 'react';
import { API } from '../../../lib/api';

interface Template {
  id: string;
  name: string;
  format_family: string;
  confidence_score: number;
}

interface Props {
  isOpen: boolean;
  onSelect: (templateId: string, templateName: string) => void;
  onClose: () => void;
}

export function CustomTemplatePicker({ isOpen, onSelect, onClose }: Props) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    API.get<Template[]>('/api/templates/')
      .then(res => setTemplates(res.data))
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--s-bg)',
          border: '1px solid var(--s-border)',
          borderRadius: 'var(--s-r-md)',
          width: 420,
          maxHeight: '70vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--s-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span style={{ fontWeight: 600, fontSize: 15, color: 'var(--s-text-1)' }}>
            Pick a Custom Template
          </span>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--s-text-2)',
              cursor: 'pointer',
              fontSize: 13,
              padding: '4px 10px',
              borderRadius: 'var(--s-r-md)',
            }}
          >
            Cancel
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '12px 20px', overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--s-text-2)', fontSize: 13 }}>
              Loading templates…
            </div>
          ) : templates.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--s-text-2)', fontSize: 13 }}>
              No saved templates. Upload one in Template Learning Studio first.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {templates.map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onSelect(t.id, t.name)}
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid var(--s-border)',
                    borderRadius: 'var(--s-r-md)',
                    padding: '10px 14px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    color: 'var(--s-text-1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'background .15s',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{t.name}</div>
                    <div style={{ fontSize: 12, color: 'var(--s-text-2)', marginTop: 2 }}>
                      {t.format_family}
                    </div>
                  </div>
                  <span style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--s-accent)',
                    whiteSpace: 'nowrap',
                    marginLeft: 12,
                  }}>
                    {Math.round(t.confidence_score * 100)}% match
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
