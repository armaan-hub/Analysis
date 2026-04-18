import { useState, useEffect } from 'react';
import { API } from '../../../lib/api';

interface PrebuiltFormat {
  id: string;
  name: string;
  format_family: string;
  format_variant: string;
  description: string;
}

type FamilyFilter = 'all' | 'IFRS' | 'GAAP' | 'local-tax' | 'custom';

export function PrebuiltFormatsTab({ onApplied }: { onApplied: () => void }) {
  const [formats, setFormats] = useState<PrebuiltFormat[]>([]);
  const [filter, setFilter] = useState<FamilyFilter>('all');
  const [applying, setApplying] = useState<string | null>(null);
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const url = filter === 'all'
      ? '/api/templates/prebuilt'
      : `/api/templates/prebuilt?format_family=${filter}`;
    API.get(url)
      .then(r => {
        const data = r.data;
        setFormats(data.formats ?? data);
      })
      .catch(() => setError('Failed to load prebuilt formats'));
  }, [filter]);

  async function applyFormat(fmt: PrebuiltFormat) {
    setApplying(fmt.id);
    try {
      await API.post(
        `/api/templates/prebuilt/${fmt.id}/apply?user_id=default-user&name=${encodeURIComponent(fmt.name)}`
      );
      setApplied(prev => new Set([...prev, fmt.id]));
      onApplied();
    } catch {
      setError(`Failed to apply ${fmt.name}`);
    } finally {
      setApplying(null);
    }
  }

  return (
    <div className="ts-prebuilt-tab">
      <div className="ts-prebuilt-filters">
        {(['all', 'IFRS', 'GAAP', 'local-tax', 'custom'] as FamilyFilter[]).map(f => (
          <button
            key={f}
            className={`ts-filter-btn${filter === f ? ' ts-filter-btn--active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'All' : f}
          </button>
        ))}
      </div>
      {error && <p className="ts-error">{error}</p>}
      <div className="ts-prebuilt-grid">
        {formats.map(fmt => (
          <div key={fmt.id} className="ts-prebuilt-card">
            <div className="ts-prebuilt-card-body">
              <h4 className="ts-prebuilt-name">{fmt.name}</h4>
              <p className="ts-muted ts-prebuilt-variant">{fmt.format_variant}</p>
              <p className="ts-prebuilt-desc">{fmt.description}</p>
            </div>
            <div className="ts-prebuilt-card-footer">
              {applied.has(fmt.id) ? (
                <span className="ts-applied-badge">✓ Added to My Templates</span>
              ) : (
                <button
                  className="ts-btn ts-btn--primary"
                  disabled={applying === fmt.id}
                  onClick={() => applyFormat(fmt)}
                >
                  {applying === fmt.id ? 'Applying…' : 'Apply'}
                </button>
              )}
            </div>
          </div>
        ))}
        {formats.length === 0 && !error && (
          <p className="ts-muted">No formats found for this filter.</p>
        )}
      </div>
    </div>
  );
}
