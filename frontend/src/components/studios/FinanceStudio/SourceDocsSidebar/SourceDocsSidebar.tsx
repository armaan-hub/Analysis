import { useRef } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import { DocumentCard } from './DocumentCard';
import { LearnedProfileTree } from './LearnedProfileTree';
import { VersionSwitcher } from './VersionSwitcher';

export function SourceDocsSidebar() {
  const { profileId, sourceDocs, refreshDocs } = useFinanceStudio();
  const fileInput = useRef<HTMLInputElement>(null);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !profileId) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', 'trial_balance');
    await fetch(`http://localhost:8000/api/audit-profiles/${profileId}/upload-source`, {
      method: 'POST', body: fd,
    });
    e.target.value = '';
    await refreshDocs();
  }

  async function onDelete(docId: string) {
    if (!profileId) return;
    await fetch(`http://localhost:8000/api/audit-profiles/${profileId}/source-documents/${docId}`, {
      method: 'DELETE',
    });
    await refreshDocs();
  }

  return (
    <div className="source-docs">
      <VersionSwitcher />

      <h4>Source Documents</h4>
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
          await fetch(`http://localhost:8000/api/audit-profiles/${profileId}/upload-source`, {
            method: 'POST', body: fd,
          });
          await refreshDocs();
        }}
      >
        Drop file or click to upload
      </div>
      <input ref={fileInput} type="file" hidden onChange={onUpload} />

      <div className="doc-list">
        {sourceDocs.map(d => <DocumentCard key={d.id} doc={d} onDelete={onDelete} />)}
        {sourceDocs.length === 0 && <div className="muted">No documents yet.</div>}
      </div>

      <LearnedProfileTree />
    </div>
  );
}
