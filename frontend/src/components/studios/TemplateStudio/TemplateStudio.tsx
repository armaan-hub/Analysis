import React, { useState, useEffect, useCallback, useRef } from 'react';
import { API, getErrMsg } from '../../../lib/api';
import {
  Layout, Upload, FileText, Trash2, Globe, RefreshCw,
  CheckCircle, AlertCircle, X, Loader2, Eye, Send, Search, Layers,
} from 'lucide-react';
import { TemplateEditor } from './TemplateEditor';
import { BatchUploadForm } from './BatchUploadForm';
import './TemplateStudio.css';

/* ── Types ──────────────────────────────────────────────────────── */

interface TemplateSummary {
  id: string;
  name: string;
  status: string;
  confidence: number | null;
  source_pdf_name: string | null;
  page_count: number | null;
  is_global?: boolean;
  created_at: string | null;
}

interface TemplateDetail extends TemplateSummary {
  config: Record<string, unknown> | null;
  verification_report: Record<string, unknown> | null;
}

interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  template_id?: string;
  confidence?: number;
  error?: string;
}

const USER_ID = 'default-user';

/* ── Main Component ─────────────────────────────────────────────── */

export function TemplateStudio() {
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [library, setLibrary] = useState<TemplateSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Upload form
  const [templateName, setTemplateName] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Learning job polling
  const [activeJob, setActiveJob] = useState<JobStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Detail modal
  const [selectedDetail, setSelectedDetail] = useState<TemplateDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Editor
  const [editingTemplate, setEditingTemplate] = useState<TemplateDetail | null>(null);

  // Tabs & search
  const [activeTab, setActiveTab] = useState<'my' | 'library' | 'batch'>('my');
  const [searchQuery, setSearchQuery] = useState('');

  /* ── Data Fetching ───────────────────────────────────────────── */

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await API.get('/api/templates/list', { params: { user_id: USER_ID } });
      setTemplates(data.templates ?? []);
    } catch (e) {
      setError(getErrMsg(e, 'Failed to load templates'));
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchLibrary = useCallback(async () => {
    try {
      const { data } = await API.get('/api/templates/library');
      setLibrary(data.templates ?? []);
    } catch (e) {
      setError(getErrMsg(e, 'Failed to load template library'));
    }
  }, []);

  useEffect(() => { fetchTemplates(); fetchLibrary(); }, [fetchTemplates, fetchLibrary]);

  /* ── Upload & Learn ──────────────────────────────────────────── */

  const uploadAndLearn = async (file: File) => {
    setUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const { data: uploadRes } = await API.post('/api/templates/upload-reference', form, {
        params: { name: templateName.trim() || undefined, user_id: USER_ID },
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const jobId: string = uploadRes.job_id;
      await API.post(`/api/templates/learn/${jobId}`);

      setActiveJob({ job_id: jobId, status: 'processing', progress: 0 });
      startPolling(jobId);
      setTemplateName('');
    } catch (e) {
      setError(getErrMsg(e, 'Upload failed'));
    } finally {
      setUploading(false);
    }
  };

  const startPolling = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await API.get<JobStatus>(`/api/templates/status/${jobId}`);
        setActiveJob(data);
        if (data.progress >= 100 || data.status === 'failed' || data.status === 'verified' || data.status === 'needs_review') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          fetchTemplates();
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }, 2000);
  };

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  /* ── Actions ─────────────────────────────────────────────────── */

  const viewDetail = async (id: string) => {
    setDetailLoading(true);
    try {
      const { data } = await API.get<TemplateDetail>(`/api/templates/${id}`);
      setSelectedDetail(data);
    } catch (e) {
      setError(getErrMsg(e, 'Failed to load template'));
    } finally {
      setDetailLoading(false);
    }
  };

  const publishTemplate = async (id: string) => {
    try {
      await API.post(`/api/templates/publish/${id}`, null, { params: { user_id: USER_ID } });
      fetchTemplates();
      fetchLibrary();
    } catch (e) {
      setError(getErrMsg(e, 'Publish failed'));
    }
  };

  const deleteTemplate = async (id: string) => {
    if (!confirm('Delete this template?')) return;
    try {
      await API.delete(`/api/templates/${id}`, { params: { user_id: USER_ID } });
      setTemplates(prev => prev.filter(t => t.id !== id));
      if (selectedDetail?.id === id) setSelectedDetail(null);
    } catch (e) {
      setError(getErrMsg(e, 'Delete failed'));
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) uploadAndLearn(file);
  };

  const handleEditorSave = () => {
    setEditingTemplate(null);
    fetchTemplates();
  };

  /* ── Filter ──────────────────────────────────────────────────── */

  const filteredTemplates = templates.filter(t =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredLibrary = library.filter(t =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  /* ── Sub-components ──────────────────────────────────────────── */

  const StatusBadge = ({ status }: { status: string }) => {
    const colors: Record<string, string> = {
      pending: '#888', processing: '#5bc0de', verified: '#5cb85c',
      needs_review: '#f0ad4e', published: '#6c5ce7', failed: '#d9534f',
    };
    return (
      <span className="ts-badge" style={{
        background: `${colors[status] || '#888'}22`, color: colors[status] || '#888',
      }}>
        {status.replace('_', ' ')}
      </span>
    );
  };

  const ConfidenceMeter = ({ value }: { value: number | null }) => {
    const v = value ?? 0;
    return (
      <div className="ts-confidence">
        <div className="ts-confidence__track">
          <div
            className="ts-confidence__fill"
            style={{
              width: `${v * 100}%`,
              background: v > 0.7 ? '#5cb85c' : v > 0.4 ? '#f0ad4e' : '#d9534f',
            }}
          />
        </div>
        <span className="ts-confidence__label">{(v * 100).toFixed(0)}%</span>
      </div>
    );
  };

  /* ── Editor View ─────────────────────────────────────────────── */

  if (editingTemplate) {
    return (
      <TemplateEditor
        template={editingTemplate}
        onSave={handleEditorSave}
        onCancel={() => setEditingTemplate(null)}
      />
    );
  }

  /* ── Render ──────────────────────────────────────────────────── */

  return (
    <div className="ts-root">
      {/* Header */}
      <div className="ts-header">
        <Layout size={20} />
        <h2 className="ts-header__title">Template Learning Studio</h2>
        <button className="ts-btn ts-btn--icon" onClick={() => { fetchTemplates(); fetchLibrary(); }} title="Refresh">
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="ts-alert ts-alert--error">
          <AlertCircle size={16} />
          <span>{error}</span>
          <X size={14} className="ts-alert__close" onClick={() => setError('')} />
        </div>
      )}

      {/* Upload Section */}
      <div className="ts-section">
        <h3 className="ts-section__title">Upload Reference PDF</h3>
        <div
          className="ts-upload-zone"
          onDragOver={e => e.preventDefault()}
          onDrop={handleFileDrop}
        >
          <Upload size={32} strokeWidth={1.5} className="ts-upload-zone__icon" />
          <p className="ts-upload-zone__main">Drag & drop a reference PDF or click to browse</p>
          <p className="ts-upload-zone__sub">The system will learn page layout, fonts, margins, and structure</p>
          <div className="ts-upload-zone__controls">
            <input
              type="text"
              placeholder="Template name (optional)"
              value={templateName}
              onChange={e => setTemplateName(e.target.value)}
              className="ts-input"
              style={{ width: 220 }}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              style={{ display: 'none' }}
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) uploadAndLearn(file);
                e.target.value = '';
              }}
            />
            <button
              className="ts-btn ts-btn--primary"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? <><Loader2 size={14} className="spin" /> Uploading...</> : 'Browse Files'}
            </button>
          </div>
        </div>
      </div>

      {/* Active Learning Job */}
      {activeJob && activeJob.progress < 100 && (
        <div className="ts-section">
          <h3 className="ts-section__title">Learning in Progress</h3>
          <div className="ts-progress-card">
            <div className="ts-progress-card__info">
              <Loader2 size={16} className="spin" />
              <span>Analyzing template… {activeJob.status}</span>
            </div>
            <div className="ts-progress-bar">
              <div className="ts-progress-bar__fill" style={{ width: `${activeJob.progress}%` }} />
            </div>
            <span className="ts-progress-card__pct">{activeJob.progress}%</span>
          </div>
        </div>
      )}

      {/* Job complete banner */}
      {activeJob && activeJob.progress >= 100 && (
        <div className={`ts-alert ${activeJob.status === 'failed' ? 'ts-alert--error' : 'ts-alert--success'}`}>
          {activeJob.status === 'failed'
            ? <><AlertCircle size={16} /> Learning failed: {activeJob.error}</>
            : <><CheckCircle size={16} /> Template learned successfully (confidence: {((activeJob.confidence ?? 0) * 100).toFixed(0)}%)</>
          }
          <X size={14} className="ts-alert__close" onClick={() => setActiveJob(null)} />
        </div>
      )}

      {/* Tabs */}
      <div className="ts-tabs">
        <button
          className={`ts-tabs__btn ${activeTab === 'my' ? 'ts-tabs__btn--active' : ''}`}
          onClick={() => setActiveTab('my')}
        >
          <FileText size={14} /> My Templates ({templates.length})
        </button>
        <button
          className={`ts-tabs__btn ${activeTab === 'library' ? 'ts-tabs__btn--active' : ''}`}
          onClick={() => setActiveTab('library')}
        >
          <Globe size={14} /> Global Library ({library.length})
        </button>
        <button
          className={`ts-tabs__btn ${activeTab === 'batch' ? 'ts-tabs__btn--active' : ''}`}
          onClick={() => setActiveTab('batch')}
        >
          <Layers size={14} /> Batch Learn
        </button>
        <div className="ts-tabs__search">
          <Search size={14} />
          <input
            type="text"
            placeholder="Search templates…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="ts-input ts-input--sm"
          />
        </div>
      </div>

      {/* Batch Upload */}
      {activeTab === 'batch' && <BatchUploadForm onComplete={fetchTemplates} />}

      {/* Template Table */}
      {activeTab !== 'batch' && (
      <div className="ts-section">
        {loading ? (
          <div className="ts-empty"><Loader2 size={24} className="spin" /></div>
        ) : activeTab === 'my' ? (
          filteredTemplates.length === 0 ? (
            <div className="ts-empty">
              <Layout size={40} strokeWidth={1} />
              <p>No templates yet. Upload a reference PDF to get started.</p>
            </div>
          ) : (
            <table className="ts-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTemplates.map(t => (
                  <tr key={t.id}>
                    <td className="ts-table__name">{t.name}</td>
                    <td className="ts-table__muted">{t.source_pdf_name || '—'}</td>
                    <td><StatusBadge status={t.status} /></td>
                    <td><ConfidenceMeter value={t.confidence} /></td>
                    <td className="ts-table__muted">
                      {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td>
                      <div className="ts-actions">
                        <button className="ts-btn ts-btn--ghost" onClick={() => viewDetail(t.id)} title="View">
                          <Eye size={14} />
                        </button>
                        {(t.status === 'verified' || t.status === 'needs_review') && (
                          <button
                            className="ts-btn ts-btn--ghost"
                            onClick={async () => {
                              const { data } = await API.get<TemplateDetail>(`/api/templates/${t.id}`);
                              setEditingTemplate(data);
                            }}
                            title="Edit Config"
                          >
                            <FileText size={14} />
                          </button>
                        )}
                        {(t.status === 'verified') && !t.is_global && (
                          <button className="ts-btn ts-btn--ghost" onClick={() => publishTemplate(t.id)} title="Publish">
                            <Send size={14} />
                          </button>
                        )}
                        <button className="ts-btn ts-btn--ghost ts-btn--danger" onClick={() => deleteTemplate(t.id)} title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          filteredLibrary.length === 0 ? (
            <div className="ts-empty">
              <Globe size={40} strokeWidth={1} />
              <p>No templates in the global library yet.</p>
            </div>
          ) : (
            <table className="ts-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredLibrary.map(t => (
                  <tr key={t.id}>
                    <td className="ts-table__name">{t.name}</td>
                    <td className="ts-table__muted">{t.source_pdf_name || '—'}</td>
                    <td><StatusBadge status={t.status} /></td>
                    <td><ConfidenceMeter value={t.confidence} /></td>
                    <td className="ts-table__muted">
                      {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td>
                      <button className="ts-btn ts-btn--ghost" onClick={() => viewDetail(t.id)} title="View">
                        <Eye size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
      )}

      {/* Detail Modal */}
      {(selectedDetail || detailLoading) && (
        <div className="ts-modal-overlay" onClick={() => setSelectedDetail(null)}>
          <div className="ts-modal" onClick={e => e.stopPropagation()}>
            <div className="ts-modal__header">
              <h3>{selectedDetail?.name ?? 'Loading…'}</h3>
              <button className="ts-btn ts-btn--ghost" onClick={() => setSelectedDetail(null)}>
                <X size={18} />
              </button>
            </div>
            {detailLoading ? (
              <div className="ts-empty"><Loader2 size={24} className="spin" /></div>
            ) : selectedDetail && (
              <div className="ts-modal__body">
                <div className="ts-detail-grid">
                  <div className="ts-detail-item">
                    <label>Status</label>
                    <StatusBadge status={selectedDetail.status} />
                  </div>
                  <div className="ts-detail-item">
                    <label>Confidence</label>
                    <ConfidenceMeter value={selectedDetail.confidence} />
                  </div>
                  <div className="ts-detail-item">
                    <label>Source PDF</label>
                    <span>{selectedDetail.source_pdf_name || '—'}</span>
                  </div>
                  <div className="ts-detail-item">
                    <label>Pages</label>
                    <span>{selectedDetail.page_count ?? '—'}</span>
                  </div>
                  <div className="ts-detail-item">
                    <label>Global</label>
                    <span>{selectedDetail.is_global ? 'Yes' : 'No'}</span>
                  </div>
                </div>
                <h4 className="ts-modal__subtitle">Configuration</h4>
                <pre className="ts-json-viewer">
                  {JSON.stringify(selectedDetail.config, null, 2)}
                </pre>
                {selectedDetail.verification_report && (
                  <>
                    <h4 className="ts-modal__subtitle">Verification Report</h4>
                    <pre className="ts-json-viewer">
                      {JSON.stringify(selectedDetail.verification_report, null, 2)}
                    </pre>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
