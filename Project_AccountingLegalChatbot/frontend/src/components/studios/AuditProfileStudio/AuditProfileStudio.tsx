import React, { useState, useEffect, useCallback, useRef } from 'react';
import { API, getErrMsg } from '../../../lib/api';
import {
  BookOpen, Upload, FileText, CheckCircle, AlertCircle,
  Plus, Trash2, RefreshCw, ChevronRight, X, Loader2
} from 'lucide-react';

/* ── Types ──────────────────────────────────────────────────────── */

interface AuditProfile {
  id: string;
  engagement_name: string;
  client_name: string;
  period_end: string;
  status: string;
  profile_json: Record<string, unknown> | null;
  source_files: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}

interface SourceDoc {
  id: string;
  document_type: string;
  original_filename: string;
  confidence: number;
  status: string;
  extracted_data: Record<string, unknown> | null;
  uploaded_at: string;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  trial_balance: '📊 Trial Balance',
  prior_audit: '📄 Prior Year Audit',
  template: '📋 Report Template',
  chart_of_accounts: '📒 Chart of Accounts',
  custom: '📎 Custom Document',
};

const DOC_TYPES = Object.keys(DOC_TYPE_LABELS);

/* ── Main Component ─────────────────────────────────────────────── */

export function AuditProfileStudio() {
  const [profiles, setProfiles] = useState<AuditProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<AuditProfile | null>(null);
  const [sourceDocs, setSourceDocs] = useState<SourceDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Create profile form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newClient, setNewClient] = useState('');
  const [newPeriod, setNewPeriod] = useState('');

  // Upload state
  const [uploadType, setUploadType] = useState('trial_balance');
  const [uploading, setUploading] = useState(false);
  const [building, setBuilding] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Report generation state
  const [generating, setGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState<Record<string, unknown> | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [lastTbFile, setLastTbFile] = useState<File | null>(null);
  const tbInputRef = useRef<HTMLInputElement>(null);

  // Tab state for profile detail view
  const [detailTab, setDetailTab] = useState<'overview' | 'mapping' | 'format' | 'generate'>('overview');

  /* ── Data fetching ──────────────────────────────────────────── */

  const fetchProfiles = useCallback(async () => {
    try {
      const { data } = await API.get('/api/audit-profiles');
      setProfiles(data);
    } catch (e) {
      setError(getErrMsg(e, 'Failed to load profiles'));
    }
  }, []);

  const fetchSourceDocs = useCallback(async (profileId: string) => {
    try {
      const { data } = await API.get(`/api/audit-profiles/${profileId}/source-documents`);
      setSourceDocs(data);
    } catch (e) {
      setError(getErrMsg(e, 'Failed to load source documents'));
    }
  }, []);

  useEffect(() => { fetchProfiles(); }, [fetchProfiles]);

  useEffect(() => {
    if (selectedProfile) fetchSourceDocs(selectedProfile.id);
    else setSourceDocs([]);
  }, [selectedProfile, fetchSourceDocs]);

  /* ── Actions ────────────────────────────────────────────────── */

  const createProfile = async () => {
    if (!newName.trim()) return;
    setLoading(true);
    try {
      const { data } = await API.post('/api/audit-profiles', {
        engagement_name: newName.trim(),
        client_name: newClient.trim(),
        period_end: newPeriod.trim(),
      });
      setProfiles(prev => [data, ...prev]);
      setSelectedProfile(data);
      setShowCreate(false);
      setNewName(''); setNewClient(''); setNewPeriod('');
    } catch (e) {
      setError(getErrMsg(e, 'Failed to create profile'));
    } finally {
      setLoading(false);
    }
  };

  const deleteProfile = async (id: string) => {
    if (!confirm('Delete this profile and all its source documents?')) return;
    try {
      await API.delete(`/api/audit-profiles/${id}`);
      setProfiles(prev => prev.filter(p => p.id !== id));
      if (selectedProfile?.id === id) setSelectedProfile(null);
    } catch (e) {
      setError(getErrMsg(e, 'Failed to delete profile'));
    }
  };

  const uploadFile = async (file: File) => {
    if (!selectedProfile) return;
    setUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('document_type', uploadType);
      await API.post(`/api/audit-profiles/${selectedProfile.id}/upload-source`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      await fetchSourceDocs(selectedProfile.id);
      await refreshProfile();
    } catch (e) {
      setError(getErrMsg(e, 'Upload failed'));
    } finally {
      setUploading(false);
    }
  };

  const buildProfile = async () => {
    if (!selectedProfile) return;
    setBuilding(true);
    setError('');
    try {
      const { data } = await API.post(`/api/audit-profiles/${selectedProfile.id}/build-profile`);
      setSelectedProfile(data);
      setProfiles(prev => prev.map(p => p.id === data.id ? data : p));
    } catch (e) {
      setError(getErrMsg(e, 'Profile building failed'));
    } finally {
      setBuilding(false);
    }
  };

  const refreshProfile = async () => {
    if (!selectedProfile) return;
    try {
      const { data } = await API.get(`/api/audit-profiles/${selectedProfile.id}`);
      setSelectedProfile(data);
      setProfiles(prev => prev.map(p => p.id === data.id ? data : p));
    } catch { /* ignore */ }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  };

  const generateReportFromFile = async (file: File) => {
    if (!selectedProfile) return;
    setGenerating(true);
    setError('');
    setGeneratedReport(null);
    setLastTbFile(file);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('company_name', selectedProfile.client_name || '');
      form.append('period_end', selectedProfile.period_end || '');
      const { data } = await API.post(
        `/api/audit-profiles/${selectedProfile.id}/generate-report`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      setGeneratedReport(data.report);
    } catch (e) {
      setError(getErrMsg(e, 'Report generation failed'));
    } finally {
      setGenerating(false);
    }
  };

  const exportReport = async (fmt: 'pdf' | 'docx' | 'xlsx') => {
    if (!selectedProfile || !lastTbFile) return;
    setExporting(fmt);
    try {
      const form = new FormData();
      form.append('file', lastTbFile);
      form.append('company_name', selectedProfile.client_name || '');
      form.append('period_end', selectedProfile.period_end || '');
      const { data } = await API.post(
        `/api/audit-profiles/${selectedProfile.id}/export-report/${fmt}`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob' }
      );
      const blob = new Blob([data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_report_${selectedProfile.client_name || 'report'}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(getErrMsg(e, `Export to ${fmt.toUpperCase()} failed`));
    } finally {
      setExporting(null);
    }
  };

  /* ── Status badge ───────────────────────────────────────────── */

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, string> = {
      draft: '#888', learning: '#f0ad4e', ready: '#5cb85c',
      processing: '#5bc0de', extracted: '#5cb85c', error: '#d9534f',
    };
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        background: `${colors[status] || '#888'}22`, color: colors[status] || '#888',
      }}>
        {status}
      </span>
    );
  };

  const ConfidenceMeter = ({ value }: { value: number }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        width: 60, height: 6, borderRadius: 3,
        background: 'var(--s-border, #333)',
      }}>
        <div style={{
          width: `${value * 100}%`, height: '100%', borderRadius: 3,
          background: value > 0.7 ? '#5cb85c' : value > 0.4 ? '#f0ad4e' : '#d9534f',
        }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--s-muted, #888)' }}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );

  /* ── Render ─────────────────────────────────────────────────── */

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left Panel: Profile List */}
      <div style={{
        width: 300, borderRight: '1px solid var(--s-border, #333)',
        display: 'flex', flexDirection: 'column', background: 'var(--s-bg, #1a1a2e)',
      }}>
        <div style={{
          padding: '16px', borderBottom: '1px solid var(--s-border, #333)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <BookOpen size={18} />
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Audit Profiles</h3>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              marginLeft: 'auto', background: 'var(--accent, #6c5ce7)', border: 'none',
              color: '#fff', borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
              fontSize: 12, display: 'flex', alignItems: 'center', gap: 4,
            }}
          >
            <Plus size={14} /> New
          </button>
        </div>

        {/* Create form */}
        {showCreate && (
          <div style={{ padding: 12, borderBottom: '1px solid var(--s-border, #333)', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <input
              placeholder="Engagement name *"
              value={newName} onChange={e => setNewName(e.target.value)}
              style={inputStyle}
            />
            <input
              placeholder="Client name"
              value={newClient} onChange={e => setNewClient(e.target.value)}
              style={inputStyle}
            />
            <input
              placeholder="Period end (e.g., 2025-12-31)"
              value={newPeriod} onChange={e => setNewPeriod(e.target.value)}
              style={inputStyle}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={createProfile} disabled={loading || !newName.trim()} style={btnPrimary}>
                {loading ? <Loader2 size={14} className="spin" /> : 'Create'}
              </button>
              <button onClick={() => setShowCreate(false)} style={btnSecondary}>Cancel</button>
            </div>
          </div>
        )}

        {/* Profile list */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {profiles.length === 0 && (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--s-muted, #888)', fontSize: 13 }}>
              No profiles yet. Create one to get started.
            </div>
          )}
          {profiles.map(p => (
            <div
              key={p.id}
              onClick={() => setSelectedProfile(p)}
              style={{
                padding: '12px 16px', cursor: 'pointer',
                borderBottom: '1px solid var(--s-border, #222)',
                background: selectedProfile?.id === p.id ? 'var(--s-active, #2a2a4e)' : 'transparent',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{p.engagement_name}</span>
                <StatusBadge status={p.status} />
              </div>
              <div style={{ fontSize: 11, color: 'var(--s-muted, #888)', marginTop: 4 }}>
                {p.client_name || 'No client'} · {p.period_end || 'No period'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--s-muted, #666)', marginTop: 2 }}>
                {p.source_files?.length || 0} source files
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right Panel: Profile Details + Upload */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {error && (
          <div style={{
            padding: '10px 16px', marginBottom: 16, borderRadius: 8,
            background: '#d9534f22', color: '#d9534f', fontSize: 13,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <AlertCircle size={16} />
            {error}
            <X size={14} style={{ marginLeft: 'auto', cursor: 'pointer' }} onClick={() => setError('')} />
          </div>
        )}

        {!selectedProfile ? (
          <div style={{ textAlign: 'center', paddingTop: 80, color: 'var(--s-muted, #888)' }}>
            <BookOpen size={48} strokeWidth={1} />
            <h3 style={{ marginTop: 16, fontWeight: 500 }}>Select or create an audit profile</h3>
            <p style={{ fontSize: 13 }}>
              Upload source documents (prior audits, trial balances, templates) and the system will learn
              your formatting preferences, account groupings, and report structure.
            </p>
          </div>
        ) : (
          <>
            {/* Profile header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
                {selectedProfile.engagement_name}
              </h2>
              <StatusBadge status={selectedProfile.status} />
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                <button onClick={buildProfile} disabled={building || sourceDocs.length === 0} style={btnPrimary}>
                  {building ? <><Loader2 size={14} className="spin" /> Building...</> : <><RefreshCw size={14} /> Build Profile</>}
                </button>
                <button onClick={() => deleteProfile(selectedProfile.id)} style={btnDanger}>
                  <Trash2 size={14} />
                </button>
              </div>
            </div>

            {/* Tab Navigation */}
            <div style={{
              display: 'flex', gap: 0, marginBottom: 24,
              borderBottom: '2px solid var(--s-border, #333)',
            }}>
              {([
                { key: 'overview', label: '📋 Overview' },
                { key: 'mapping', label: '🔗 Account Mapping' },
                { key: 'format', label: '📐 Format' },
                { key: 'generate', label: '📊 Generate' },
              ] as const).map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setDetailTab(tab.key)}
                  style={{
                    padding: '10px 20px', border: 'none', cursor: 'pointer',
                    background: detailTab === tab.key ? 'var(--s-active, #2a2a4e)' : 'transparent',
                    color: detailTab === tab.key ? 'var(--accent, #6c5ce7)' : 'var(--s-muted, #888)',
                    fontSize: 13, fontWeight: detailTab === tab.key ? 600 : 400,
                    borderBottom: detailTab === tab.key ? '2px solid var(--accent, #6c5ce7)' : '2px solid transparent',
                    marginBottom: -2,
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab: Overview */}
            {detailTab === 'overview' && (<>

            {/* Upload zone */}
            <div style={{
              border: '2px dashed var(--s-border, #444)', borderRadius: 12,
              padding: 24, textAlign: 'center', marginBottom: 24,
              background: 'var(--s-bg, #1a1a2e)',
            }}
              onDragOver={e => e.preventDefault()}
              onDrop={handleFileDrop}
            >
              <Upload size={32} strokeWidth={1.5} style={{ color: 'var(--accent, #6c5ce7)' }} />
              <p style={{ margin: '12px 0 8px', fontSize: 14, fontWeight: 500 }}>
                Upload Source Document
              </p>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--s-muted, #888)' }}>
                Drag & drop or click to browse. Supports PDF, Excel, Word.
              </p>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 16, flexWrap: 'wrap' }}>
                <select
                  value={uploadType} onChange={e => setUploadType(e.target.value)}
                  style={{ ...inputStyle, width: 'auto' }}
                >
                  {DOC_TYPES.map(t => (
                    <option key={t} value={t}>{DOC_TYPE_LABELS[t]}</option>
                  ))}
                </select>
                <input
                  ref={fileInputRef} type="file" style={{ display: 'none' }}
                  accept=".pdf,.xlsx,.xls,.docx,.doc"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) uploadFile(file);
                    e.target.value = '';
                  }}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  style={btnPrimary}
                >
                  {uploading ? <><Loader2 size={14} className="spin" /> Uploading...</> : 'Browse Files'}
                </button>
              </div>
            </div>

            {/* Source Documents */}
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
              Source Documents ({sourceDocs.length})
            </h3>
            {sourceDocs.length === 0 ? (
              <p style={{ color: 'var(--s-muted, #888)', fontSize: 13 }}>
                No documents uploaded yet. Upload trial balances, prior audits, and templates above.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sourceDocs.map(doc => (
                  <div key={doc.id} style={{
                    padding: '12px 16px', borderRadius: 8,
                    border: '1px solid var(--s-border, #333)',
                    background: 'var(--s-bg, #1a1a2e)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <FileText size={16} />
                      <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>
                        {doc.original_filename}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--s-muted, #888)' }}>
                        {DOC_TYPE_LABELS[doc.document_type] || doc.document_type}
                      </span>
                      <StatusBadge status={doc.status} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 8 }}>
                      <ConfidenceMeter value={doc.confidence} />
                      {doc.extracted_data && (
                        <span style={{ fontSize: 11, color: 'var(--s-muted, #888)' }}>
                          {(doc.extracted_data as Record<string, unknown>).tables
                            ? `${(((doc.extracted_data as Record<string, unknown>).tables) as unknown[]).length} tables`
                            : ''}
                          {' · '}
                          {((doc.extracted_data as Record<string, unknown>).text as string || '').length > 0
                            ? `${Math.round(((doc.extracted_data as Record<string, unknown>).text as string).length / 1000)}K chars`
                            : 'no text'}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Profile JSON preview */}
            {selectedProfile.profile_json && Object.keys(selectedProfile.profile_json).length > 0 && (
              <div style={{ marginTop: 24 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
                  <CheckCircle size={16} style={{ color: '#5cb85c', marginRight: 4 }} />
                  Learned Profile
                </h3>
                <ProfilePreview profile={selectedProfile.profile_json} />
              </div>
            )}

            {/* Report Generation — now in Generate tab */}
            </>)}

            {/* Tab: Account Mapping */}
            {detailTab === 'mapping' && (
              <AccountMappingEditor
                profileId={selectedProfile.id}
                profileJson={selectedProfile.profile_json}
                onSave={async () => { await fetchProfiles(); if (selectedProfile) { const { data } = await API.get(`/api/audit-profiles/${selectedProfile.id}`); setSelectedProfile(data); } }}
                setError={setError}
              />
            )}

            {/* Tab: Format Customizer */}
            {detailTab === 'format' && (
              <FormatCustomizer
                profileId={selectedProfile.id}
                profileJson={selectedProfile.profile_json}
                onSave={async () => { await fetchProfiles(); if (selectedProfile) { const { data } = await API.get(`/api/audit-profiles/${selectedProfile.id}`); setSelectedProfile(data); } }}
                setError={setError}
              />
            )}

            {/* Tab: Generate Report */}
            {detailTab === 'generate' && (
              <>
            {selectedProfile.status === 'ready' ? (
              <div>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
                  📊 Generate Audit Report
                </h3>
                <div style={{
                  padding: 20, borderRadius: 12,
                  border: '1px solid var(--s-border, #444)',
                  background: 'var(--s-bg, #1a1a2e)',
                }}>
                  <p style={{ fontSize: 13, color: 'var(--s-muted, #888)', margin: '0 0 12px' }}>
                    Upload a trial balance file and the system will generate a structured audit report
                    using the learned mappings, format template, and requirements.
                  </p>
                  <input
                    ref={tbInputRef} type="file" style={{ display: 'none' }}
                    accept=".xlsx,.xls,.pdf"
                    onChange={e => {
                      const file = e.target.files?.[0];
                      if (file) generateReportFromFile(file);
                      e.target.value = '';
                    }}
                  />
                  <button
                    onClick={() => tbInputRef.current?.click()}
                    disabled={generating}
                    style={{ ...btnPrimary, padding: '10px 20px', fontSize: 14 }}
                  >
                    {generating
                      ? <><Loader2 size={16} className="spin" /> Generating Report...</>
                      : '📊 Upload Trial Balance & Generate Report'}
                  </button>
                </div>

                {generatedReport && (
                  <div style={{ marginTop: 16 }}>
                    <ReportPreview report={generatedReport} />
                    {/* Export Buttons */}
                    <div style={{
                      marginTop: 16, display: 'flex', gap: 12, flexWrap: 'wrap',
                      padding: 16, borderRadius: 10,
                      border: '1px solid var(--s-border, #333)',
                      background: 'var(--s-bg, #1a1a2e)',
                    }}>
                      <span style={{ fontSize: 13, fontWeight: 600, width: '100%', marginBottom: 4 }}>
                        📥 Export Report
                      </span>
                      {(['pdf', 'docx', 'xlsx'] as const).map(fmt => (
                        <button
                          key={fmt}
                          onClick={() => exportReport(fmt)}
                          disabled={!!exporting}
                          style={{
                            ...btnPrimary, padding: '10px 20px',
                            background: fmt === 'pdf' ? '#d9534f' : fmt === 'docx' ? '#337ab7' : '#5cb85c',
                          }}
                        >
                          {exporting === fmt
                            ? <><Loader2 size={14} className="spin" /> Exporting...</>
                            : `📄 Download ${fmt.toUpperCase()}`}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--s-muted, #888)' }}>
                <p style={{ fontSize: 14 }}>Profile must be in &quot;ready&quot; status to generate reports.</p>
                <p style={{ fontSize: 12 }}>Upload source documents and build the profile first.</p>
              </div>
            )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ── Profile Preview Component ──────────────────────────────────── */

function ProfilePreview({ profile }: { profile: Record<string, unknown> }) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const sections = [
    { key: 'financial_data', label: '💰 Financial Data', icon: '💰' },
    { key: 'format_template', label: '📐 Format Template', icon: '📐' },
    { key: 'account_mapping', label: '🗂️ Account Mappings', icon: '🗂️' },
    { key: 'statement_groupings', label: '📊 Statement Groupings', icon: '📊' },
    { key: 'custom_requirements', label: '⚙️ Requirements', icon: '⚙️' },
    { key: 'source_summary', label: '📎 Sources', icon: '📎' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {sections.map(s => {
        const data = profile[s.key];
        if (!data) return null;
        const isExpanded = expandedSection === s.key;
        const itemCount = typeof data === 'object'
          ? (Array.isArray(data) ? data.length : Object.keys(data as object).length)
          : 0;

        return (
          <div key={s.key} style={{
            border: '1px solid var(--s-border, #333)', borderRadius: 8,
            overflow: 'hidden',
          }}>
            <div
              onClick={() => setExpandedSection(isExpanded ? null : s.key)}
              style={{
                padding: '10px 14px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 8,
                background: 'var(--s-bg, #1a1a2e)',
              }}
            >
              <ChevronRight size={14} style={{
                transform: isExpanded ? 'rotate(90deg)' : 'none',
                transition: 'transform 0.2s',
              }} />
              <span style={{ fontSize: 13, fontWeight: 500 }}>{s.label}</span>
              <span style={{ fontSize: 11, color: 'var(--s-muted, #888)', marginLeft: 'auto' }}>
                {itemCount} items
              </span>
            </div>
            {isExpanded && (
              <pre style={{
                margin: 0, padding: '12px 14px', fontSize: 11,
                background: 'var(--s-code-bg, #111)', overflow: 'auto',
                maxHeight: 300, lineHeight: 1.4,
                color: 'var(--s-text, #ccc)',
              }}>
                {JSON.stringify(data, null, 2)}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Report Preview Component ──────────────────────────────────── */

function ReportPreview({ report }: { report: Record<string, unknown> }) {
  const metadata = (report.metadata || {}) as Record<string, unknown>;
  const opinion = (report.auditor_opinion || {}) as Record<string, unknown>;
  const fs = (report.financial_statements || {}) as Record<string, unknown>;
  const notes = (report.notes || {}) as Record<string, unknown>;

  const renderStatement = (stmt: Record<string, unknown> | null, key: string) => {
    if (!stmt) return null;
    const sections = (stmt.sections || []) as Array<Record<string, unknown>>;
    const total = stmt.total as Record<string, unknown> | null;

    return (
      <div key={key} style={{ marginBottom: 20 }}>
        <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{stmt.title as string}</h4>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--s-border, #444)' }}>
              <th style={{ textAlign: 'left', padding: '6px 8px' }}>Account</th>
              <th style={{ textAlign: 'right', padding: '6px 8px' }}>Current Year</th>
              <th style={{ textAlign: 'right', padding: '6px 8px' }}>Prior Year</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((section, si) => {
              const items = (section.line_items || []) as Array<Record<string, unknown>>;
              const subtotal = section.subtotal as Record<string, unknown> | null;
              return (
                <React.Fragment key={si}>
                  <tr><td colSpan={3} style={{ padding: '8px 8px 2px', fontWeight: 600, color: 'var(--accent, #6c5ce7)' }}>{section.title as string}</td></tr>
                  {items.map((item, ii) => (
                    <tr key={ii} style={{ borderBottom: '1px solid var(--s-border, #222)' }}>
                      <td style={{ padding: '4px 8px 4px 24px' }}>{item.account_name as string}</td>
                      <td style={{ textAlign: 'right', padding: '4px 8px' }}>{fmtNum(item.current_year as number)}</td>
                      <td style={{ textAlign: 'right', padding: '4px 8px', color: 'var(--s-muted, #888)' }}>{fmtNum(item.prior_year as number)}</td>
                    </tr>
                  ))}
                  {subtotal && (
                    <tr style={{ borderBottom: '1px solid var(--s-border, #444)', fontWeight: 600 }}>
                      <td style={{ padding: '4px 8px 4px 16px' }}>{subtotal.account_name as string}</td>
                      <td style={{ textAlign: 'right', padding: '4px 8px' }}>{fmtNum(subtotal.current_year as number)}</td>
                      <td style={{ textAlign: 'right', padding: '4px 8px' }}>{fmtNum(subtotal.prior_year as number)}</td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            {total && (
              <tr style={{ borderTop: '2px solid var(--s-border, #444)', fontWeight: 700 }}>
                <td style={{ padding: '6px 8px' }}>{total.account_name as string}</td>
                <td style={{ textAlign: 'right', padding: '6px 8px' }}>{fmtNum(total.current_year as number)}</td>
                <td style={{ textAlign: 'right', padding: '6px 8px' }}>{fmtNum(total.prior_year as number)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div style={{
      border: '1px solid var(--s-border, #333)', borderRadius: 12,
      padding: 20, background: 'var(--s-bg, #1a1a2e)',
    }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
        📋 Generated Audit Report
      </h3>

      {/* Metadata */}
      <div style={{ fontSize: 12, color: 'var(--s-muted, #888)', marginBottom: 16 }}>
        {metadata.company_name as string} · Period: {metadata.period_end as string} · {metadata.currency as string}
      </div>

      {/* Auditor Opinion */}
      {opinion.opinion_text && (
        <div style={{ marginBottom: 20, padding: 12, borderRadius: 8, background: 'var(--s-code-bg, #111)' }}>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            Independent Auditor&apos;s Report ({opinion.opinion_type as string})
          </h4>
          <p style={{ fontSize: 12, lineHeight: 1.6, margin: 0 }}>{opinion.opinion_text as string}</p>
        </div>
      )}

      {/* Financial Statements */}
      {renderStatement(fs.statement_of_financial_position as Record<string, unknown> | null, 'sofp')}
      {renderStatement(fs.statement_of_profit_or_loss as Record<string, unknown> | null, 'sopl')}

      {/* Notes Summary */}
      {notes.accounting_policies && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Notes to Financial Statements</h4>
          <pre style={{
            fontSize: 11, lineHeight: 1.5, whiteSpace: 'pre-wrap',
            padding: 12, borderRadius: 8, background: 'var(--s-code-bg, #111)',
            maxHeight: 200, overflow: 'auto',
          }}>
            {notes.accounting_policies as string}
          </pre>
        </div>
      )}
    </div>
  );
}

function fmtNum(n: number): string {
  if (!n && n !== 0) return '-';
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/* ── Account Mapping Editor ─────────────────────────────────────── */

const IFRS_GROUPS = [
  'Revenue', 'Cost of Sales', 'Staff Costs', 'Administrative Expenses',
  'Other Operating Expenses', 'Finance Costs', 'Finance Income', 'Tax Expense',
  'Property, Plant and Equipment', 'Intangible Assets', 'Right-of-Use Assets',
  'Investment Property', 'Trade and Other Receivables', 'Prepayments',
  'Cash and Cash Equivalents', 'Inventories', 'Other Current Assets',
  'Share Capital', 'Retained Earnings', 'Other Reserves',
  'Trade and Other Payables', 'Borrowings', 'Lease Liabilities',
  'Provisions', 'Other Non-Current Liabilities', 'Other Current Liabilities',
  'Depreciation', 'Amortisation',
];

function AccountMappingEditor({ profileId, profileJson, onSave, setError }: {
  profileId: string;
  profileJson: Record<string, unknown> | null;
  onSave: () => Promise<void>;
  setError: (e: string) => void;
}) {
  const mapping = ((profileJson || {}).account_mapping || {}) as Record<string, string>;
  const [localMapping, setLocalMapping] = useState<Record<string, string>>({ ...mapping });
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('');

  const accounts = Object.keys(localMapping).sort();
  const filtered = filter
    ? accounts.filter(a => a.toLowerCase().includes(filter.toLowerCase()) || (localMapping[a] || '').toLowerCase().includes(filter.toLowerCase()))
    : accounts;

  const saveMapping = async () => {
    setSaving(true);
    try {
      await API.put(`/api/audit-profiles/${profileId}/account-mapping`, { mapping: localMapping });
      await onSave();
    } catch (e) {
      setError(getErrMsg(e, 'Failed to save mapping'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>🔗 Account Mapping</h3>
        <input
          placeholder="Filter accounts..."
          value={filter} onChange={e => setFilter(e.target.value)}
          style={{ ...inputStyle, width: 200, marginLeft: 'auto' }}
        />
        <button onClick={saveMapping} disabled={saving} style={btnPrimary}>
          {saving ? <><Loader2 size={14} className="spin" /> Saving...</> : 'Save Mapping'}
        </button>
      </div>

      {accounts.length === 0 ? (
        <p style={{ color: 'var(--s-muted, #888)', fontSize: 13 }}>
          No account mappings yet. Build the profile from uploaded source documents first.
        </p>
      ) : (
        <div style={{
          border: '1px solid var(--s-border, #333)', borderRadius: 8, overflow: 'hidden',
          maxHeight: 500, overflowY: 'auto',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--s-bg, #1a1a2e)', position: 'sticky', top: 0 }}>
                <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid var(--s-border, #444)' }}>Account Name</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid var(--s-border, #444)' }}>IFRS Group</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(account => (
                <tr key={account} style={{ borderBottom: '1px solid var(--s-border, #222)' }}>
                  <td style={{ padding: '6px 12px', fontSize: 12 }}>{account}</td>
                  <td style={{ padding: '4px 12px' }}>
                    <select
                      value={localMapping[account] || ''}
                      onChange={e => setLocalMapping(prev => ({ ...prev, [account]: e.target.value }))}
                      style={{ ...inputStyle, padding: '4px 8px', fontSize: 11 }}
                    >
                      <option value="">— Unassigned —</option>
                      {IFRS_GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ fontSize: 11, color: 'var(--s-muted, #666)', marginTop: 8 }}>
        {accounts.length} accounts mapped · {filtered.length} shown
      </p>
    </div>
  );
}

/* ── Format Customizer ─────────────────────────────────────────── */

function FormatCustomizer({ profileId, profileJson, onSave, setError }: {
  profileId: string;
  profileJson: Record<string, unknown> | null;
  onSave: () => Promise<void>;
  setError: (e: string) => void;
}) {
  const template = ((profileJson || {}).format_template || {}) as Record<string, unknown>;
  const [columns, setColumns] = useState<string>(
    JSON.stringify(template.columns || ['Account', 'Notes', 'Current Year', 'Prior Year'])
  );
  const [currency, setCurrency] = useState((template.currency_symbol as string) || 'AED');
  const [fontFamily, setFontFamily] = useState((template.font_family as string) || 'Times New Roman');
  const [fontSize, setFontSize] = useState(String(template.font_size || 10));
  const [pageSize, setPageSize] = useState((template.page_size as string) || 'A4');
  const [saving, setSaving] = useState(false);

  const saveFormat = async () => {
    setSaving(true);
    try {
      let parsedCols;
      try { parsedCols = JSON.parse(columns); } catch { parsedCols = ['Account', 'Notes', 'Current Year', 'Prior Year']; }
      const formatData = {
        columns: parsedCols,
        currency_symbol: currency,
        font_family: fontFamily,
        font_size: parseInt(fontSize) || 10,
        page_size: pageSize,
      };
      await API.put(`/api/audit-profiles/${profileId}/format-template`, { format_template: formatData });
      await onSave();
    } catch (e) {
      setError(getErrMsg(e, 'Failed to save format'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>📐 Format Template</h3>
        <button onClick={saveFormat} disabled={saving} style={{ ...btnPrimary, marginLeft: 'auto' }}>
          {saving ? <><Loader2 size={14} className="spin" /> Saving...</> : 'Save Format'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div>
          <label style={labelStyle}>Currency Symbol</label>
          <select value={currency} onChange={e => setCurrency(e.target.value)} style={inputStyle}>
            {['AED', 'USD', 'EUR', 'GBP', 'SAR', 'INR'].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Page Size</label>
          <select value={pageSize} onChange={e => setPageSize(e.target.value)} style={inputStyle}>
            {['A4', 'Letter', 'Legal'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Font Family</label>
          <select value={fontFamily} onChange={e => setFontFamily(e.target.value)} style={inputStyle}>
            {['Times New Roman', 'Arial', 'Helvetica', 'Calibri', 'Garamond'].map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Font Size</label>
          <input type="number" value={fontSize} onChange={e => setFontSize(e.target.value)} min={8} max={16} style={inputStyle} />
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <label style={labelStyle}>Columns (JSON array)</label>
          <input value={columns} onChange={e => setColumns(e.target.value)} style={inputStyle} />
        </div>
      </div>

      <div style={{ marginTop: 20, padding: 16, borderRadius: 8, background: 'var(--s-code-bg, #111)' }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Preview</h4>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr>
              {(() => { try { return JSON.parse(columns); } catch { return ['Account', 'Notes', 'CY', 'PY']; } })().map((col: string) => (
                <th key={col} style={{ padding: '6px 8px', borderBottom: '2px solid var(--s-border, #444)', textAlign: 'left', fontFamily }}>
                  {col} {col.includes('Year') ? `(${currency})` : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr><td style={{ padding: '4px 8px', fontFamily, fontWeight: 600 }}>Non-Current Assets</td><td></td><td></td><td></td></tr>
            <tr><td style={{ padding: '4px 8px 4px 20px', fontFamily }}>Property, Plant and Equipment</td><td style={{ fontFamily }}>5</td><td style={{ textAlign: 'right', fontFamily }}>1,234,567.00</td><td style={{ textAlign: 'right', fontFamily, color: '#888' }}>1,100,000.00</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 11, fontWeight: 600,
  color: 'var(--s-muted, #888)', marginBottom: 4,
};

/* ── Shared styles ──────────────────────────────────────────────── */

const inputStyle: React.CSSProperties = {
  padding: '8px 12px', borderRadius: 6, border: '1px solid var(--s-border, #444)',
  background: 'var(--s-input-bg, #222)', color: 'var(--s-text, #eee)',
  fontSize: 13, outline: 'none', width: '100%',
};

const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 6, border: 'none',
  background: 'var(--accent, #6c5ce7)', color: '#fff',
  fontSize: 12, fontWeight: 600, cursor: 'pointer',
  display: 'flex', alignItems: 'center', gap: 6,
};

const btnSecondary: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 6, border: '1px solid var(--s-border, #444)',
  background: 'transparent', color: 'var(--s-text, #ccc)',
  fontSize: 12, cursor: 'pointer',
};

const btnDanger: React.CSSProperties = {
  padding: '8px 10px', borderRadius: 6, border: 'none',
  background: '#d9534f22', color: '#d9534f',
  fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center',
};
