import React, { useState, useRef } from 'react';
import { API, getErrMsg } from '../../../lib/api';
import { Upload, FileText, X, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

interface BatchJobStatus {
  job_id: string;
  status: string;
  progress: number;
  pdf_count: number;
  template_id?: string;
  confidence?: number;
  error?: string;
}

interface Props {
  onComplete: () => void;
}

export function BatchUploadForm({ onComplete }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [templateName, setTemplateName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState<BatchJobStatus | null>(null);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const addFiles = (newFiles: FileList | File[]) => {
    const pdfs = Array.from(newFiles).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name));
      const unique = pdfs.filter(f => !existing.has(f.name));
      return [...prev, ...unique];
    });
  };

  const removeFile = (name: string) => setFiles(prev => prev.filter(f => f.name !== name));

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const pollStatus = (jobId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await API.get(`/api/templates/status/${jobId}`);
        const data = res.data as BatchJobStatus;
        setJob(data);
        if (['verified', 'needs_review', 'failed'].includes(data.status)) {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          if (data.status !== 'failed') onComplete();
        }
      } catch {
        clearInterval(pollRef.current!);
      }
    }, 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!files.length || !templateName.trim()) return;
    setError('');
    setUploading(true);
    try {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f));
      const res = await API.post(
        `/api/templates/batch-learn?name=${encodeURIComponent(templateName)}&user_id=default-user`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      const data = res.data as BatchJobStatus;
      setJob(data);
      setFiles([]);
      setTemplateName('');
      pollStatus(data.job_id);
    } catch (e) {
      setError(getErrMsg(e, 'Batch upload failed'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="ts-section">
      <h3 className="ts-section__title">Batch Learn — Multiple Reference PDFs</h3>
      <p className="ts-muted">
        Upload 2–5 PDFs of the same audit format. The system averages them to produce a
        higher-confidence consensus template.
      </p>

      {/* Drop zone */}
      <div
        className={`ts-dropzone${dragOver ? ' ts-dropzone--active' : ''}`}
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload size={28} />
        <span>Drop PDFs here or click to select</span>
        <span className="ts-muted">Multiple files supported</span>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          multiple
          style={{ display: 'none' }}
          onChange={e => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <ul className="ts-file-list">
          {files.map(f => (
            <li key={f.name} className="ts-file-item">
              <FileText size={14} />
              <span>{f.name}</span>
              <span className="ts-muted">({(f.size / 1024).toFixed(0)} KB)</span>
              <button className="ts-btn-icon" onClick={() => removeFile(f.name)}>
                <X size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input
          className="ts-input"
          style={{ flex: 1 }}
          placeholder="Template name (e.g. 'IFRS Standard 2025')"
          value={templateName}
          onChange={e => setTemplateName(e.target.value)}
          disabled={uploading || (!!job?.status && !['failed'].includes(job.status))}
        />
        <button
          type="submit"
          className="ts-btn ts-btn--primary"
          disabled={!files.length || !templateName.trim() || uploading}
        >
          {uploading
            ? <><Loader2 size={14} className="spin" /> Uploading…</>
            : `Learn from ${files.length || 0} PDF${files.length !== 1 ? 's' : ''}`}
        </button>
      </form>

      {/* Job status */}
      {job && (
        <div className={`ts-job-status ts-job-status--${job.status}`}>
          {job.status === 'processing' && <Loader2 size={14} className="spin" />}
          {job.status === 'verified' && <CheckCircle size={14} />}
          {job.status === 'needs_review' && <AlertCircle size={14} />}
          {job.status === 'failed' && <AlertCircle size={14} />}
          <span>
            {job.status === 'processing' && `Processing ${job.pdf_count ?? ''} PDF(s)… ${job.progress}%`}
            {job.status === 'verified' && `✓ Template learned! Confidence: ${((job.confidence ?? 0) * 100).toFixed(0)}%`}
            {job.status === 'needs_review' && `Template needs review. Confidence: ${((job.confidence ?? 0) * 100).toFixed(0)}%`}
            {job.status === 'failed' && `Failed: ${job.error}`}
          </span>
        </div>
      )}

      {error && (
        <div className="ts-alert ts-alert--error">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
