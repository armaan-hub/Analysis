import { useRef } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import { DocumentCard } from './DocumentCard';
import { LearnedProfileTree } from './LearnedProfileTree';
import { VersionSwitcher } from './VersionSwitcher';
import { Plus, Upload } from 'lucide-react';
import { API_BASE_URL } from '../../../../../api-config';

export function SourceDocsSidebar() {
  const { profileId, sourceDocs, refreshDocs, selectedSourceIds, toggleSource } = useFinanceStudio();
  const fileInput = useRef<HTMLInputElement>(null);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !profileId) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', 'trial_balance');
    await fetch(`${API_BASE_URL}/api/audit-profiles/${profileId}/upload-source`, {
      method: 'POST', body: fd,
    });
    e.target.value = '';
    await refreshDocs();
  }

  async function onDelete(docId: string) {
    if (!profileId) return;
    await fetch(`${API_BASE_URL}/api/audit-profiles/${profileId}/source-documents/${docId}`, {
      method: 'DELETE',
    });
    await refreshDocs();
  }

  return (
    <div className="source-docs">
      <button
        className="source-docs__add-btn"
        onClick={() => fileInput.current?.click()}
      >
        <Plus size={16} /> Add sources
      </button>

      <div
        className="dropzone"
        onClick={() => fileInput.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={async e => {
          e.preventDefault();
          const file = e.dataTransfer.files?.[0];
          if (!file || !profileId) return;
          const fd = new FormData();
          fd.append('file', file);
          fd.append('doc_type', 'trial_balance');
          await fetch(`${API_BASE_URL}/api/audit-profiles/${profileId}/upload-source`, {
            method: 'POST', body: fd,
          });
          await refreshDocs();
        }}
      >
        <Upload size={18} />
        Drop file or click to upload
      </div>
      <input ref={fileInput} type="file" hidden onChange={onUpload} />

      <div className="doc-list">
        {sourceDocs.map(d => <DocumentCard key={d.id} doc={d} onDelete={onDelete} selected={selectedSourceIds.includes(d.id)} onToggle={toggleSource} />)}
        {sourceDocs.length === 0 && <div className="muted">No documents yet.</div>}
      </div>

      <LearnedProfileTree />
      <VersionSwitcher />
    </div>
  );
}
