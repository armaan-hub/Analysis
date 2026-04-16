import { useEffect, useRef, useState } from 'react';
import { API, API_BASE, type Alert } from '../../../lib/api';
import { AlertCard } from './AlertCard';

type Filter = 'All' | string;

function sortByImpact(alerts: Alert[]): Alert[] {
  const order: Record<string, number> = { critical: 0, warning: 1, info: 2 };
  return [...alerts].sort((a, b) =>
    (order[a.severity] ?? 3) - (order[b.severity] ?? 3)
  );
}

export function RegulatoryStudio() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>('All');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    API.get('/api/monitoring/alerts')
      .then(r => {
        const data: Alert[] = Array.isArray(r.data) ? r.data : [];
        setAlerts(sortByImpact(Array.isArray(data) ? data : []));
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    // WebSocket for real-time alert push
    const wsBase = API_BASE.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsBase}/api/monitoring/ws/alerts`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'alert' && msg.data) {
          setAlerts(prev => sortByImpact([msg.data as Alert, ...prev]));
        }
      } catch { /* ignore parse errors */ }
    };

    return () => {
      ws.close();
    };
  }, []);

  const sources = ['All', ...Array.from(new Set(alerts.map(a => a.source_name))).filter(Boolean)];

  const filtered = filter === 'All'
    ? alerts
    : alerts.filter(a => a.source_name === filter);

  return (
    <div className="regulatory-studio">
      <div className="regulatory-header">
        <h1 className="regulatory-title">Regulatory Command Center</h1>
        <div className="regulatory-filters">
          {sources.map(src => (
            <button
              key={src}
              className={`filter-btn ${filter === src ? 'filter-btn--active' : ''}`}
              onClick={() => setFilter(src)}
            >
              {src}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="regulatory-skeleton">
          {[1, 2, 3, 4].map(i => <div key={i} className="skeleton-card" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="regulatory-empty">
          <div className="regulatory-empty__icon">✓</div>
          <div className="regulatory-empty__title">No regulatory updates</div>
          <div className="regulatory-empty__sub">You're up to date</div>
        </div>
      ) : (
        <div className="regulatory-grid">
          {filtered.map(alert => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </div>
  );
}
