import { useNavigate } from 'react-router-dom';
import { MessageSquare } from 'lucide-react';
import { fmtDate, type Alert } from '../../../lib/api';

type Impact = 'high' | 'medium' | 'low';

function getImpact(severity: string): Impact {
  if (severity === 'critical') return 'high';
  if (severity === 'warning') return 'medium';
  return 'low';
}

const IMPACT_LABEL: Record<Impact, string> = {
  high: 'HIGH — Action required',
  medium: 'MEDIUM — New requirement',
  low: 'LOW — Minor change',
};

interface Props {
  alert: Alert;
}

export function AlertCard({ alert }: Props) {
  const navigate = useNavigate();
  const impact = getImpact(alert.severity);

  return (
    <div className="alert-card">
      <div className="alert-card__top">
        <span className="alert-source-badge" title={alert.source_name}>
          {alert.source_name}
        </span>
        <span className={`impact-pill impact-pill--${impact}`}>
          {IMPACT_LABEL[impact]}
        </span>
      </div>
      <div className="alert-card__title">{alert.title}</div>
      {alert.summary && (
        <div className="alert-card__summary">{alert.summary}</div>
      )}
      <div className="alert-card__date">{fmtDate(alert.created_at)}</div>
      <button
        className="alert-card__cta"
        onClick={() => navigate(`/?q=${encodeURIComponent(alert.title)}`)}
      >
        <MessageSquare size={13} />
        Open in AI Chat
      </button>
    </div>
  );
}
