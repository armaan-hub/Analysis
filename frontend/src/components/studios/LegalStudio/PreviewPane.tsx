/**
 * @deprecated Replaced by StudioPanel > ReportPreview.
 * Kept for backward compatibility.
 */
import { useEffect, useState } from 'react';
import { API_BASE } from '../../../lib/api';

interface Props {
  docId: string | null;
  onClose: () => void;
}

export function PreviewPane({ docId, onClose }: Props) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) {
      setUrl(null);
      return;
    }
    setUrl(`${API_BASE}/api/documents/${docId}/file`);
  }, [docId]);

  if (!docId) return null;

  return (
    <aside style={{
      width: 480,
      borderLeft: '1px solid var(--s-border)',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--s-bg-2, #111)',
    }}>
      <div style={{
        padding: 8,
        borderBottom: '1px solid var(--s-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{ fontSize: 13, color: 'var(--s-text-1, #fff)', fontFamily: 'var(--s-font-ui)' }}>
          Preview
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close preview"
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--s-text-2)',
            cursor: 'pointer',
            fontSize: 16,
          }}
          title="Close preview"
        >
          ✕
        </button>
      </div>
      <iframe
        src={url ?? ''}
        style={{ flex: 1, border: 'none' }}
        title="Document preview"
      />
    </aside>
  );
}
