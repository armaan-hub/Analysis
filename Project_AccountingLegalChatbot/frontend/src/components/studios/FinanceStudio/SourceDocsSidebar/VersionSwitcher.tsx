import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';

export function VersionSwitcher() {
  const { versions, activeVersionId, switchVersion, branchVersion } = useFinanceStudio();
  const [newBranch, setNewBranch] = useState('');

  return (
    <div className="version-switcher">
      <label>Version</label>
      <select
        value={activeVersionId ?? ''}
        onChange={e => switchVersion(e.target.value)}
      >
        {versions.map(v => (
          <option key={v.id} value={v.id}>
            {v.branch_name}{v.is_current ? ' (current)' : ''}
          </option>
        ))}
      </select>

      <input
        placeholder="new branch name"
        value={newBranch}
        onChange={e => setNewBranch(e.target.value)}
      />
      <button
        disabled={!newBranch.trim()}
        onClick={async () => { await branchVersion(newBranch.trim()); setNewBranch(''); }}
      >
        Branch
      </button>
    </div>
  );
}
