import { useEffect, useState } from 'react';
import { API } from '../../../lib/api';

interface TemplateSection {
  title: string;
  start_page: number;
  level: number;
  content_type: string;
  accounts?: string[];
}

interface FormattingRules {
  currency_symbol: string;
  negative_format: string;
  decimal_places: number;
  font_family: string;
}

interface AccountGroup {
  name: string;
  accounts: string[];
}

interface TemplateData {
  id: string;
  company_name: string;
  source_filename: string;
  confidence: number;
  extraction_method: string;
  document_structure: {
    total_pages: number;
    sections: TemplateSection[];
  };
  formatting_rules: FormattingRules;
  account_grouping: {
    groups: AccountGroup[];
  };
}

interface TemplateReviewStepProps {
  templateId: string;
  onApprove: () => void;
  onReject: () => void;
}

export function TemplateReviewStep({ templateId, onApprove, onReject }: TemplateReviewStepProps) {
  const [template, setTemplate] = useState<TemplateData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    API.get(`/api/reports/template/${templateId}`)
      .then(resp => {
        if (!cancelled) setTemplate(resp.data as TemplateData);
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load template details.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [templateId]);

  const handleAction = async (action: 'approve' | 'reject') => {
    setSubmitting(true);
    try {
      await API.post(`/api/reports/review-template/${templateId}`, { action });
      if (action === 'approve') onApprove();
      else onReject();
    } catch {
      setError(`Failed to ${action} template. Please try again.`);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '20px', fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)',
      }}>
        <span className="chat-typing"><span /><span /><span /></span>
        Loading template details…
      </div>
    );
  }

  if (error && !template) {
    return (
      <div style={{
        padding: '16px', borderRadius: 'var(--s-r-md)',
        border: '1px solid var(--s-border)', background: 'var(--s-surface)',
        fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-danger, #ef4444)',
      }}>
        {error}
      </div>
    );
  }

  if (!template) return null;

  const { document_structure, formatting_rules, account_grouping } = template;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: '16px',
      padding: '20px', borderRadius: 'var(--s-r-md)',
      border: '1px solid var(--s-border)', background: 'var(--s-surface)',
    }}>
      {/* Header */}
      <div>
        <div style={{
          fontFamily: 'var(--s-font-display)', fontSize: '15px',
          fontWeight: 600, color: 'var(--s-text-1)', marginBottom: '2px',
        }}>
          Review Extracted Template
        </div>
        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
          Verify the structure extracted from the prior year report before proceeding.
        </div>
      </div>

      {/* Metadata */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '12px',
        padding: '12px', borderRadius: 'var(--s-r-sm)',
        background: 'var(--s-accent-dim)', border: '1px solid var(--s-border)',
      }}>
        {[
          ['Source', template.source_filename],
          ['Confidence', `${(template.confidence * 100).toFixed(0)}%`],
          ['Method', template.extraction_method],
          ['Pages', `${document_structure.total_pages}`],
        ].map(([label, value]) => (
          <div key={label} style={{ minWidth: '100px' }}>
            <div style={{
              fontFamily: 'var(--s-font-ui)', fontSize: '10px', fontWeight: 600,
              color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              {label}
            </div>
            <div style={{
              fontFamily: 'var(--s-font-ui)', fontSize: '13px',
              fontWeight: 500, color: 'var(--s-text-1)',
            }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Sections */}
      {document_structure.sections.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{
            fontFamily: 'var(--s-font-ui)', fontSize: '11px', fontWeight: 600,
            color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            Sections ({document_structure.sections.length})
          </div>
          <div style={{
            display: 'flex', flexDirection: 'column', gap: '2px',
            maxHeight: '200px', overflowY: 'auto',
            padding: '8px 10px', borderRadius: 'var(--s-r-sm)',
            border: '1px solid var(--s-border)', background: 'var(--s-surface)',
          }}>
            {document_structure.sections.map((s, i) => (
              <div key={i} style={{ paddingLeft: `${(s.level - 1) * 16}px` }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-1)',
                }}>
                  <span>{s.level === 1 ? '▸' : '·'} {s.title}</span>
                  <span style={{
                    fontSize: '10px', color: 'var(--s-text-2)',
                    padding: '1px 5px', borderRadius: '9999px',
                    background: 'var(--s-accent-dim)', border: '1px solid var(--s-border)',
                  }}>
                    {s.content_type}
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--s-text-2)' }}>
                    p.{s.start_page}
                  </span>
                </div>
                {s.accounts && s.accounts.length > 0 && (
                  <div style={{
                    display: 'flex', flexWrap: 'wrap', gap: '4px',
                    marginTop: '4px', marginBottom: '4px', paddingLeft: '14px',
                  }}>
                    {s.accounts.map((a, j) => (
                      <span key={j} style={{
                        fontFamily: 'var(--s-font-ui)', fontSize: '10px',
                        padding: '2px 7px', borderRadius: '9999px',
                        background: 'var(--s-accent-dim)', color: 'var(--s-accent)',
                        border: '1px solid var(--s-border)',
                      }}>
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Account Groupings */}
      {account_grouping?.groups?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{
            fontFamily: 'var(--s-font-ui)', fontSize: '11px', fontWeight: 600,
            color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            Account Groupings
          </div>
          <div style={{
            display: 'flex', flexDirection: 'column', gap: '8px',
            padding: '8px 10px', borderRadius: 'var(--s-r-sm)',
            border: '1px solid var(--s-border)', background: 'var(--s-surface)',
          }}>
            {account_grouping.groups.map((g, i) => (
              <div key={i}>
                <div style={{
                  fontFamily: 'var(--s-font-ui)', fontSize: '12px',
                  fontWeight: 600, color: 'var(--s-text-1)', marginBottom: '4px',
                }}>
                  {g.name}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {g.accounts.map((a, j) => (
                    <span key={j} style={{
                      fontFamily: 'var(--s-font-ui)', fontSize: '10px',
                      padding: '2px 7px', borderRadius: '9999px',
                      background: 'var(--s-accent-dim)', color: 'var(--s-accent)',
                      border: '1px solid var(--s-border)',
                    }}>
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Formatting Rules */}
      {formatting_rules && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{
            fontFamily: 'var(--s-font-ui)', fontSize: '11px', fontWeight: 600,
            color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            Formatting Rules
          </div>
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '8px',
            padding: '8px 10px', borderRadius: 'var(--s-r-sm)',
            border: '1px solid var(--s-border)', background: 'var(--s-surface)',
          }}>
            {[
              ['Currency', formatting_rules.currency_symbol],
              ['Negatives', formatting_rules.negative_format],
              ['Decimals', `${formatting_rules.decimal_places}`],
              ['Font', formatting_rules.font_family],
            ].map(([label, value]) => (
              <div key={label} style={{
                padding: '6px 10px', borderRadius: 'var(--s-r-sm)',
                background: 'var(--s-accent-dim)', border: '1px solid var(--s-border)',
                minWidth: '80px',
              }}>
                <div style={{
                  fontFamily: 'var(--s-font-ui)', fontSize: '10px', fontWeight: 600,
                  color: 'var(--s-text-2)', textTransform: 'uppercase', letterSpacing: '0.06em',
                }}>
                  {label}
                </div>
                <div style={{
                  fontFamily: 'var(--s-font-ui)', fontSize: '12px',
                  fontWeight: 500, color: 'var(--s-text-1)',
                }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div style={{
          fontFamily: 'var(--s-font-ui)', fontSize: '12px',
          color: 'var(--s-danger, #ef4444)',
        }}>
          {error}
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
        <button
          className="btn-primary"
          disabled={submitting}
          onClick={() => handleAction('approve')}
        >
          Approve Template ✓
        </button>
        <button
          className="btn-ghost"
          disabled={submitting}
          onClick={() => handleAction('reject')}
        >
          Reject &amp; Use Standard Format
        </button>
      </div>
    </div>
  );
}
