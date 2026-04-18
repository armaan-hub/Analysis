import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import * as api from '../api';

export function VersionCompare() {
  const { profileId, versions } = useFinanceStudio();
  const [v1, setV1] = useState<string>('');
  const [v2, setV2] = useState<string>('');
  const [diff, setDiff] = useState<Awaited<ReturnType<typeof api.compareVersions>> | null>(null);

  async function run() {
    if (!profileId || !v1 || !v2) return;
    setDiff(await api.compareVersions(profileId, v1, v2));
  }

  const empty = diff && !Object.keys(diff.changed).length
                       && !Object.keys(diff.added).length
                       && !Object.keys(diff.removed).length;

  return (
    <div className="version-compare">
      <h4>Compare versions</h4>
      <div className="version-compare__row">
        <select value={v1} onChange={e => setV1(e.target.value)}>
          <option value="">— v1 —</option>
          {versions.map(v => <option key={v.id} value={v.id}>{v.branch_name}</option>)}
        </select>
        <select value={v2} onChange={e => setV2(e.target.value)}>
          <option value="">— v2 —</option>
          {versions.map(v => <option key={v.id} value={v.id}>{v.branch_name}</option>)}
        </select>
        <button disabled={!v1 || !v2 || v1 === v2} onClick={run}>Compare</button>
      </div>

      {empty && <div className="muted">No differences found between these versions.</div>}
      {diff && !empty && (
        <pre className="version-compare__diff">{JSON.stringify(diff, null, 2)}</pre>
      )}
    </div>
  );
}
