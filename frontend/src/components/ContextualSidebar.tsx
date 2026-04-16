import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Trash2, Pencil } from 'lucide-react';
import { useStudio } from '../context/StudioProvider';
import { API } from '../lib/api';
import { NewReportPanel } from './studios/FinancialStudio/NewReportPanel';

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface SavedReport {
  id: string;
  company_name: string;
  format: string;
  report_type?: string;
  period_end_date: string | null;
  status: 'draft' | 'final';
  updated_at: string;
  draft_content?: string;
  final_content?: string;
  wizard_state_json?: Record<string, unknown> | null;
  rows?: Record<string, unknown>[];
}

interface Props {
  conversations?: Conversation[];
  onLoadConversation?: (id: string) => void;
  onNewChat?: () => void;
  onEditReport?: (state: Record<string, unknown>) => void;
}

function groupByDate(convos: Conversation[]) {
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterdayStr = new Date(now.getTime() - 86400000).toDateString();
  const weekAgo = new Date(now.getTime() - 7 * 86400000);

  const today = convos.filter(c => new Date(c.updated_at).toDateString() === todayStr);
  const yesterday = convos.filter(c => new Date(c.updated_at).toDateString() === yesterdayStr);
  const lastWeek = convos.filter(c => {
    const d = new Date(c.updated_at);
    return d > weekAgo && d.toDateString() !== todayStr && d.toDateString() !== yesterdayStr;
  });

  return { today, yesterday, lastWeek };
}

export function ContextualSidebar({ conversations = [], onLoadConversation, onNewChat, onEditReport }: Props) {
  const { activeStudio, sidebarOpen, toggleSidebar } = useStudio();
  const navigate = useNavigate();
  const groups = groupByDate(conversations);

  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);
  const [viewReport, setViewReport] = useState<SavedReport | null>(null);
  const [editReport, setEditReport] = useState<SavedReport | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [noWizardState, setNoWizardState] = useState(false);

  useEffect(() => {
    if (activeStudio !== 'financial') return;
    API.get('/api/reports/saved')
      .then(r => setSavedReports(r.data as SavedReport[]))
      .catch(() => {});
  }, [activeStudio]);

  const handleView = async (id: string) => {
    try {
      const resp = await API.get(`/api/reports/saved/${id}`);
      setViewReport(resp.data as SavedReport);
    } catch { /* silent */ }
  };

  const handleDownloadReport = async (r: SavedReport, format: 'docx' | 'pdf' | 'xlsx') => {
    const content = r.final_content || r.draft_content || '';
    if (!content) return;
    setDownloading(`${r.id}:${format}`);
    try {
      const body: Record<string, unknown> = {
        content,
        filename: `${r.company_name ?? 'report'}_audit_${r.period_end_date ?? ''}`,
        report_type: r.report_type ?? 'general',
        company_name: r.company_name ?? '',
        period_end: r.period_end_date ?? '',
        rows: r.rows ?? [],
      };
      const resp = await API.post(
        `/api/reports/export-${format}`,
        body,
        { responseType: 'blob' }
      );
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(r.company_name || 'audit_report').replace(/\s+/g, '_')}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
    finally { setDownloading(null); }
  };

  const handleEdit = async (id: string) => {
    try {
      const res = await API.get(`/api/reports/saved/${id}/wizard-state`);
      const data = res.data as {
        wizard_state: Record<string, unknown> | null;
        has_wizard_state: boolean;
        draft_content: string | null;
        company_name: string;
        report_type: string;
      };
      if (onEditReport) {
        if (data.has_wizard_state && data.wizard_state) {
          onEditReport({ ...data.wizard_state, draft_content: data.draft_content ?? undefined });
        } else {
          // Fallback for old reports without wizard state — open draft step with content only
          onEditReport({ selectedConfigKey: data.report_type, draft_content: data.draft_content ?? undefined });
        }
        navigate('/reports');
      } else {
        // Last resort: text modal when no wizard integration is available
        const fullResp = await API.get(`/api/reports/saved/${id}`);
        const r = fullResp.data as SavedReport;
        setEditReport(r);
        setEditContent(r.final_content || r.draft_content || '');
        setNoWizardState(true);
      }
    } catch { /* silent */ }
  };

  const handleEditSave = async () => {
    if (!editReport) return;
    setEditSaving(true);
    try {
      const isFinal = !!editReport.final_content;
      await API.put(`/api/reports/saved/${editReport.id}`, {
        company_name: editReport.company_name,
        status: editReport.status,
        draft_content: isFinal ? editReport.draft_content : editContent,
        final_content: isFinal ? editContent : undefined,
      });
      setSavedReports(prev => prev.map(r =>
        r.id === editReport.id
          ? { ...r, final_content: isFinal ? editContent : r.final_content, draft_content: !isFinal ? editContent : r.draft_content }
          : r
      ));
      setEditReport(null);
      setNoWizardState(false);
    } catch { /* silent */ }
    finally { setEditSaving(false); }
  };

  const handleDelete = async (id: string) => {
    setDeleteConfirmId(id);
  };

  const confirmDelete = async () => {
    if (!deleteConfirmId) return;
    await API.delete(`/api/reports/saved/${deleteConfirmId}`).catch(() => {});
    setSavedReports(prev => prev.filter(r => r.id !== deleteConfirmId));
    setDeleteConfirmId(null);
  };

  return (
    <aside className={`contextual-sidebar ${sidebarOpen ? '' : 'contextual-sidebar--closed'}`}>
      <button className="sidebar-toggle" onClick={toggleSidebar} title={sidebarOpen ? 'Collapse' : 'Expand'}>
        {sidebarOpen ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
      </button>

      {sidebarOpen && (
        <div className="sidebar-content">
          {activeStudio === 'legal' && (
            <>
              <div style={{ padding: '12px 12px 4px' }}>
                <button
                  onClick={onNewChat}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 12px',
                    borderRadius: 'var(--s-r-md)',
                    border: '1px solid var(--s-border)',
                    background: 'transparent',
                    color: 'var(--s-text-2)',
                    fontFamily: 'var(--s-font-ui)',
                    fontSize: '13px',
                    cursor: 'pointer',
                    transition: 'var(--s-ease)',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(107,140,255,0.08)';
                    (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-accent)';
                    (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-accent)';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                    (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-text-2)';
                    (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-border)';
                  }}
                >
                  <span style={{ fontSize: '16px', lineHeight: 1 }}>+</span>
                  New Chat
                </button>
              </div>
              <div className="sidebar-section-title">Chat History</div>
              {groups.today.length > 0 && (
                <div className="sidebar-group">
                  <div className="sidebar-group-label">Today</div>
                  {groups.today.map(c => (
                    <div
                      key={c.id}
                      className="sidebar-item"
                      onClick={() => onLoadConversation?.(c.id)}
                    >
                      {c.title}
                    </div>
                  ))}
                </div>
              )}
              {groups.yesterday.length > 0 && (
                <div className="sidebar-group">
                  <div className="sidebar-group-label">Yesterday</div>
                  {groups.yesterday.map(c => (
                    <div
                      key={c.id}
                      className="sidebar-item"
                      onClick={() => onLoadConversation?.(c.id)}
                    >
                      {c.title}
                    </div>
                  ))}
                </div>
              )}
              {groups.lastWeek.length > 0 && (
                <div className="sidebar-group">
                  <div className="sidebar-group-label">Last Week</div>
                  {groups.lastWeek.map(c => (
                    <div
                      key={c.id}
                      className="sidebar-item"
                      onClick={() => onLoadConversation?.(c.id)}
                    >
                      {c.title}
                    </div>
                  ))}
                </div>
              )}
              {conversations.length === 0 && (
                <div className="sidebar-empty">No conversations yet</div>
              )}
            </>
          )}

          {activeStudio === 'financial' && (
            <>
              <NewReportPanel onSelect={(key) => {
                navigate('/reports');
                window.dispatchEvent(new CustomEvent('studio:new-report', { detail: key }));
              }} />
              <div className="sidebar-section-title" style={{ marginTop: '8px' }}>Saved Reports</div>
              {savedReports.length === 0 ? (
                <div className="sidebar-empty">No saved reports</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '0 8px' }}>
                  {savedReports.map(r => (
                    <div key={r.id} style={{ display: 'flex', flexDirection: 'column', gap: '6px', padding: '8px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'var(--s-surface)' }}>
                      {/* Header row */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '6px' }}>
                        <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', fontWeight: 600, color: 'var(--s-text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                          {r.company_name || 'Audit Report'}
                        </div>
                        <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '10px', padding: '1px 6px', borderRadius: '999px', background: r.status === 'final' ? 'rgba(22,163,74,0.12)' : 'rgba(180,83,9,0.12)', color: r.status === 'final' ? '#16a34a' : '#b45309', fontWeight: 600, flexShrink: 0 }}>
                          {r.status}
                        </span>
                      </div>
                      <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}>
                        {r.format.toUpperCase()} · {r.period_end_date ?? '—'} · {new Date(r.updated_at).toLocaleDateString('en-AE')}
                      </div>
                      {/* Action buttons */}
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
                        <button
                          onClick={() => handleView(r.id)}
                          style={{ display: 'flex', alignItems: 'center', gap: '3px', padding: '3px 7px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-accent)' }}
                        >View</button>
                        <button
                          onClick={() => handleEdit(r.id)}
                          style={{ display: 'flex', alignItems: 'center', gap: '3px', padding: '3px 7px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                          title="Edit report content"
                        ><Pencil size={10} /> Edit</button>
                        {(['docx', 'pdf', 'xlsx'] as const).map(fmt => (
                          <button
                            key={fmt}
                            onClick={() => handleDownloadReport(r, fmt)}
                            disabled={downloading === `${r.id}:${fmt}`}
                            style={{ display: 'flex', alignItems: 'center', gap: '3px', padding: '3px 7px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--s-font-ui)', fontSize: '11px', color: 'var(--s-text-2)' }}
                          >{downloading === `${r.id}:${fmt}` ? '…' : fmt.toUpperCase()}</button>
                        ))}
                        <button
                          onClick={() => handleDelete(r.id)}
                          style={{ display: 'flex', alignItems: 'center', gap: '3px', padding: '3px 7px', borderRadius: 'var(--s-r-sm)', border: '1px solid var(--s-border)', background: 'transparent', cursor: 'pointer', color: 'var(--s-danger)', marginLeft: 'auto' }}
                        ><Trash2 size={11} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {activeStudio === 'regulatory' && (
            <>
              <div className="sidebar-section-title">Severity</div>
              {['Critical', 'Warning', 'Info'].map(s => (
                <div key={s} className="sidebar-item">{s}</div>
              ))}
            </>
          )}
        </div>
      )}

      {/* View report modal */}
      {viewReport && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto' }}
          onClick={e => { if (e.target === e.currentTarget) setViewReport(null); }}
        >
          <div style={{ background: 'var(--s-bg)', borderRadius: 'var(--s-r-md)', border: '1px solid var(--s-border)', width: '100%', maxWidth: '900px', display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px', borderBottom: '1px solid var(--s-border)' }}>
              <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '14px', fontWeight: 600, color: 'var(--s-text-1)' }}>
                {viewReport.company_name || 'Audit Report'} — {viewReport.status === 'final' ? 'Final' : 'Draft'}
              </div>
              <button onClick={() => setViewReport(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--s-text-2)', padding: '4px', fontFamily: 'var(--s-font-ui)', fontSize: '18px' }}>✕</button>
            </div>
            <div style={{ padding: '24px', overflowY: 'auto', maxHeight: '70vh' }} className="report-markdown">
              <pre style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-1)', whiteSpace: 'pre-wrap', lineHeight: 1.6, margin: 0 }}>
                {viewReport.final_content || viewReport.draft_content || 'No content available.'}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Edit report modal */}
      {editReport && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 1001, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto' }}
          onClick={e => { if (e.target === e.currentTarget) { setEditReport(null); setNoWizardState(false); } }}
        >
          <div style={{ background: 'var(--s-bg)', borderRadius: 'var(--s-r-md)', border: '1px solid var(--s-border)', width: '100%', maxWidth: '900px', display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px', borderBottom: '1px solid var(--s-border)' }}>
              <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '14px', fontWeight: 600, color: 'var(--s-text-1)' }}>
                Edit — {editReport.company_name || 'Audit Report'} ({editReport.status})
              </div>
              <button onClick={() => { setEditReport(null); setNoWizardState(false); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--s-text-2)', padding: '4px', fontFamily: 'var(--s-font-ui)', fontSize: '18px' }}>✕</button>
            </div>
            {noWizardState && (
              <div style={{ margin: '0 24px', padding: '8px 12px', borderRadius: 'var(--s-r-sm)', background: 'rgba(180,83,9,0.08)', border: '1px solid #b45309', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '14px' }}>⚠️</span>
                <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: '#b45309' }}>
                  Wizard state unavailable for this report — editing in text mode only.
                </span>
              </div>
            )}
            <div style={{ padding: '16px 24px', flex: 1 }}>
              <textarea
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
                style={{ width: '100%', minHeight: '500px', background: 'var(--s-surface)', border: '1px solid var(--s-border)', borderRadius: 'var(--s-r-sm)', color: 'var(--s-text-1)', fontFamily: 'var(--s-font-ui)', fontSize: '13px', padding: '12px', outline: 'none', resize: 'vertical', boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', padding: '12px 24px', borderTop: '1px solid var(--s-border)' }}>
              <button onClick={() => { setEditReport(null); setNoWizardState(false); }} className="btn-ghost" style={{ fontSize: '13px' }}>Cancel</button>
              <button onClick={handleEditSave} className="btn-primary" style={{ fontSize: '13px' }} disabled={editSaving}>
                {editSaving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      {deleteConfirmId && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 1001, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}
          onClick={e => { if (e.target === e.currentTarget) setDeleteConfirmId(null); }}
        >
          <div style={{ background: 'var(--s-bg)', borderRadius: 'var(--s-r-md)', border: '1px solid var(--s-border)', padding: '24px', maxWidth: '360px', width: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '14px', fontWeight: 600, color: 'var(--s-text-1)' }}>Delete Report?</div>
            <div style={{ fontFamily: 'var(--s-font-ui)', fontSize: '13px', color: 'var(--s-text-2)' }}>
              This will permanently delete the saved report. This action cannot be undone.
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setDeleteConfirmId(null)} className="btn-ghost" style={{ fontSize: '13px' }}>Cancel</button>
              <button onClick={confirmDelete} className="btn-primary" style={{ fontSize: '13px', background: 'var(--s-danger)', borderColor: 'var(--s-danger)' }}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
