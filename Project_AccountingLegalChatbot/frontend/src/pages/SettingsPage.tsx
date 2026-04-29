import { useState, useEffect } from 'react';
import { API, API_BASE, getErrMsg } from '../lib/api';

interface ProviderConfig {
  api_key: string;
  model: string;
  base_url: string;
  fast_api_key: string;
  fast_model: string;
}

interface FullSettings {
  llm_provider: string;
  llm_model: string;
  temperature: number;
  max_tokens: number;
  top_k_results: number;
  providers: Record<string, ProviderConfig>;
}

const PROVIDER_META: Record<string, { label: string; icon: string; keyRequired: boolean; hasBaseUrl: boolean; hasFastModel: boolean }> = {
  nvidia:  { label: 'NVIDIA NIM',    icon: '🟢', keyRequired: true,  hasBaseUrl: true,  hasFastModel: true  },
  openai:  { label: 'OpenAI',        icon: '⚫', keyRequired: true,  hasBaseUrl: false, hasFastModel: false },
  claude:  { label: 'Anthropic',     icon: '🟠', keyRequired: true,  hasBaseUrl: false, hasFastModel: false },
  mistral: { label: 'Mistral',       icon: '🔵', keyRequired: true,  hasBaseUrl: false, hasFastModel: false },
  groq:    { label: 'Groq',          icon: '🟡', keyRequired: true,  hasBaseUrl: false, hasFastModel: true  },
  ollama:  { label: 'Ollama (local)', icon: '🟣', keyRequired: false, hasBaseUrl: true,  hasFastModel: false },
};

export default function SettingsPage() {
  const [fullSettings, setFullSettings] = useState<FullSettings | null>(null);
  const [loading, setLoading]           = useState(true);
  const [selectedProvider, setSelectedProvider] = useState<string>('nvidia');

  const [editKey,      setEditKey]      = useState('');
  const [editModel,    setEditModel]    = useState('');
  const [editBaseUrl,  setEditBaseUrl]  = useState('');
  const [editFastKey,  setEditFastKey]  = useState('');
  const [editFastModel,setEditFastModel]= useState('');
  const [showKey,      setShowKey]      = useState(false);
  const [showFastKey,  setShowFastKey]  = useState(false);
  // Tracks which providers already have a key configured (so we don't overwrite with masked values)
  const [hasKey,       setHasKey]       = useState<Record<string, boolean>>({});
  const [hasFastKey,   setHasFastKey]   = useState<Record<string, boolean>>({});

  const [models,         setModels]         = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [modelsError,    setModelsError]    = useState('');

  const [saving,      setSaving]      = useState(false);
  const [testing,     setTesting]     = useState(false);
  const [statusMsg,   setStatusMsg]   = useState<{ text: string; ok: boolean } | null>(null);

  const flash = (text: string, ok: boolean) => {
    setStatusMsg({ text, ok });
    setTimeout(() => setStatusMsg(null), 4000);
  };

  useEffect(() => {
    API.get('/api/settings/current')
      .then(r => {
        setFullSettings(r.data);
        const active = r.data.llm_provider || 'nvidia';
        setSelectedProvider(active);
        const prov = r.data.providers?.[active] || {};
        // Never pre-fill with masked values — track "key configured" state separately
        setEditKey('');
        setEditModel(prov.model || '');
        setEditBaseUrl(prov.base_url || '');
        setEditFastKey('');
        setEditFastModel(prov.fast_model || '');
        // Record which providers already have keys set (based on non-empty masked value)
        const keyFlags: Record<string, boolean> = {};
        const fastKeyFlags: Record<string, boolean> = {};
        Object.entries((r.data.providers || {}) as Record<string, { api_key: string; fast_api_key: string }>).forEach(([p, cfg]) => {
          keyFlags[p] = !!cfg.api_key;
          fastKeyFlags[p] = !!cfg.fast_api_key;
        });
        setHasKey(keyFlags);
        setHasFastKey(fastKeyFlags);
      })
      .catch(() => flash('Failed to load settings', false))
      .finally(() => setLoading(false));
  }, []);

  const pickProvider = (p: string) => {
    setSelectedProvider(p);
    setModels([]);
    setModelsError('');
    setStatusMsg(null);
    const prov: ProviderConfig = fullSettings?.providers?.[p] || { api_key: '', model: '', base_url: '', fast_api_key: '', fast_model: '' };
    // Never pre-fill key fields with masked values — leave blank so users must type to change
    setEditKey('');
    setEditModel(prov.model || '');
    setEditBaseUrl(prov.base_url || '');
    setEditFastKey('');
    setEditFastModel(prov.fast_model || '');
  };

  const fetchModels = async () => {
    setFetchingModels(true);
    setModelsError('');
    setModels([]);
    try {
      const r = await API.get(`/api/settings/providers/${selectedProvider}/models`);
      const list: string[] = (r.data as Array<{ id: string }>).map(m => m.id);
      setModels(list);
      if (list.length === 0) setModelsError('No models returned from provider.');
    } catch (e) {
      setModelsError(getErrMsg(e, 'Failed to fetch models'));
    } finally {
      setFetchingModels(false);
    }
  };

  const save = async (activate: boolean) => {
    setSaving(true);
    try {
      await API.put('/api/settings/provider', {
        provider:      selectedProvider,
        api_key:       editKey       || undefined,
        model:         editModel     || undefined,
        base_url:      editBaseUrl   || undefined,
        fast_api_key:  editFastKey   || undefined,
        fast_model:    editFastModel || undefined,
        activate,
      });
      const r = await API.get('/api/settings/current');
      setFullSettings(r.data);
      // Update "key configured" flags after a successful save
      if (editKey) setHasKey(prev => ({ ...prev, [selectedProvider]: true }));
      if (editFastKey) setHasFastKey(prev => ({ ...prev, [selectedProvider]: true }));
      setEditKey('');
      setEditFastKey('');
      flash(activate ? `Activated ${selectedProvider} — model: ${editModel}` : 'Saved', true);
    } catch (e) {
      flash(getErrMsg(e, 'Failed to save'), false);
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      await API.put('/api/settings/provider', {
        provider:     selectedProvider,
        api_key:      editKey      || undefined,
        model:        editModel    || undefined,
        base_url:     editBaseUrl  || undefined,
        fast_api_key: editFastKey  || undefined,
        fast_model:   editFastModel|| undefined,
        activate: false,
      });
      // Update key flags and clear fields if a new key was submitted
      if (editKey) { setHasKey(prev => ({ ...prev, [selectedProvider]: true })); setEditKey(''); }
      if (editFastKey) { setHasFastKey(prev => ({ ...prev, [selectedProvider]: true })); setEditFastKey(''); }
      const r = await API.post('/api/settings/providers/test', { provider: selectedProvider });
      const d = r.data as { success: boolean; message: string; model: string };
      flash(d.success ? `Connection OK — ${d.model}: ${d.message}` : `Failed: ${d.message}`, d.success);
    } catch (e) {
      flash(getErrMsg(e, 'Test failed'), false);
    } finally {
      setTesting(false);
    }
  };

  const meta = PROVIDER_META[selectedProvider] ?? { label: selectedProvider, icon: '⚙️', keyRequired: true, hasBaseUrl: false, hasFastModel: false };
  const isActive = fullSettings?.llm_provider === selectedProvider;

  return (
    <div className="main">
      <div className="page-header">
        <div>
          <h1 className="page-title">API <span>Settings</span></h1>
          <div className="page-sub">Configure LLM providers — changes persist to .env and take effect immediately</div>
        </div>
        {statusMsg && (
          <div className="settings-status-banner" style={{ background: statusMsg.ok ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)', color: statusMsg.ok ? 'var(--green)' : 'var(--red)' }}>
            {statusMsg.ok ? '✓' : '✗'} {statusMsg.text}
          </div>
        )}
      </div>
      <div className="page-body">
        {loading ? <div className="loading-spinner" /> : (
          <div className="api-settings-layout">

            <div className="provider-card-list">
              <div className="settings-section-title" style={{ marginBottom: '10px' }}>Providers</div>
              {Object.entries(PROVIDER_META).map(([key, m]) => {
                const isAct = fullSettings?.llm_provider === key;
                return (
                  <div
                    key={key}
                    className={`provider-card ${selectedProvider === key ? 'selected' : ''}`}
                    onClick={() => pickProvider(key)}
                  >
                    <span className="provider-card-icon">{m.icon}</span>
                    <div className="provider-card-info">
                      <div className="provider-card-name">{m.label}</div>
                      <div className="provider-card-model">
                        {fullSettings?.providers?.[key]?.model || '—'}
                      </div>
                    </div>
                    {isAct && <span className="provider-active-badge">ACTIVE</span>}
                  </div>
                );
              })}

              <div className="settings-section-title" style={{ marginTop: '24px', marginBottom: '8px' }}>System Info</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-2)', lineHeight: 2 }}>
                <div>API Docs: <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" style={{ color: 'var(--primary)' }}>{API_BASE}/docs</a></div>
                <div>Health: <a href={`${API_BASE}/health`} target="_blank" rel="noreferrer" style={{ color: 'var(--green)' }}>/health</a></div>
              </div>
            </div>

            <div className="provider-config-panel">
              <div className="provider-config-header">
                <span style={{ fontSize: '1.4rem' }}>{meta.icon}</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1rem' }}>{meta.label}</div>
                  {isActive && <div style={{ fontSize: '0.75rem', color: 'var(--green)' }}>Currently active provider</div>}
                </div>
              </div>

              {/* ── Deep / Main model ─────────────────────────────────── */}
              {meta.keyRequired && (
                <div className="settings-field">
                  <label className="settings-label">API Key {meta.hasFastModel && <span style={{ fontSize: '0.7rem', color: 'var(--text-2)' }}>(Deep Research / Main)</span>}</label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type={showKey ? 'text' : 'password'}
                      className="settings-input"
                      placeholder={hasKey[selectedProvider] ? 'Key configured — enter new key to replace' : 'Enter API key…'}
                      value={editKey}
                      onChange={e => setEditKey(e.target.value)}
                    />
                    <button className="btn btn-secondary" style={{ whiteSpace: 'nowrap' }} onClick={() => setShowKey(v => !v)}>
                      {showKey ? 'Hide' : 'Show'}
                    </button>
                  </div>
                  {hasKey[selectedProvider] && !editKey && (
                    <div style={{ fontSize: '0.72rem', color: 'var(--green)', marginTop: '4px' }}>✓ API key is configured</div>
                  )}
                </div>
              )}

              {meta.hasBaseUrl && (
                <div className="settings-field">
                  <label className="settings-label">Base URL</label>
                  <input
                    type="text"
                    className="settings-input"
                    placeholder="https://..."
                    value={editBaseUrl}
                    onChange={e => setEditBaseUrl(e.target.value)}
                  />
                </div>
              )}

              <div className="settings-field">
                <label className="settings-label">Model {meta.hasFastModel && <span style={{ fontSize: '0.7rem', color: 'var(--text-2)' }}>(Deep Research / Analyst)</span>}</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {models.length > 0 ? (
                    <select
                      className="settings-input settings-select"
                      value={editModel}
                      onChange={e => setEditModel(e.target.value)}
                    >
                      {models.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  ) : (
                    <input
                      type="text"
                      className="settings-input"
                      placeholder="e.g. deepseek-ai/deepseek-v3.2"
                      value={editModel}
                      onChange={e => setEditModel(e.target.value)}
                    />
                  )}
                  <button
                    className="btn btn-secondary"
                    style={{ whiteSpace: 'nowrap' }}
                    onClick={fetchModels}
                    disabled={fetchingModels}
                    title="Connect to provider API and fetch available models"
                  >
                    {fetchingModels ? '⟳ Fetching…' : '⬇ Fetch Models'}
                  </button>
                </div>
                {modelsError && <div style={{ fontSize: '0.75rem', color: 'var(--red)', marginTop: '4px' }}>{modelsError}</div>}
                {models.length > 0 && <div style={{ fontSize: '0.75rem', color: 'var(--text-2)', marginTop: '4px' }}>{models.length} models available from provider API</div>}
              </div>

              {/* ── Fast Mode section ─────────────────────────────────── */}
              {meta.hasFastModel && (
                <div style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '12px 14px', marginTop: '8px' }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--primary)', marginBottom: '10px' }}>⚡ Fast Mode Configuration</div>

                  {meta.keyRequired && (
                    <div className="settings-field">
                      <label className="settings-label" style={{ fontSize: '0.78rem' }}>Fast Mode API Key <span style={{ fontSize: '0.7rem', color: 'var(--text-2)' }}>(leave blank to reuse main key)</span></label>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <input
                          type={showFastKey ? 'text' : 'password'}
                          className="settings-input"
                          placeholder={hasFastKey[selectedProvider] ? 'Key configured — enter new key to replace' : 'Enter fast mode API key…'}
                          value={editFastKey}
                          onChange={e => setEditFastKey(e.target.value)}
                        />
                        <button className="btn btn-secondary" style={{ whiteSpace: 'nowrap' }} onClick={() => setShowFastKey(v => !v)}>
                          {showFastKey ? 'Hide' : 'Show'}
                        </button>
                      </div>
                      {hasFastKey[selectedProvider] && !editFastKey && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--green)', marginTop: '4px' }}>✓ Fast mode key is configured</div>
                      )}
                    </div>
                  )}

                  <div className="settings-field" style={{ marginBottom: 0 }}>
                    <label className="settings-label" style={{ fontSize: '0.78rem' }}>Fast Mode Model</label>
                    <input
                      type="text"
                      className="settings-input"
                      placeholder="e.g. deepseek-ai/deepseek-v3.1-terminus"
                      value={editFastModel}
                      onChange={e => setEditFastModel(e.target.value)}
                    />
                  </div>
                </div>
              )}

              <div className="provider-config-actions">
                <button className="btn btn-secondary" onClick={testConnection} disabled={testing || saving}>
                  {testing ? '⟳ Testing…' : '⚡ Test Connection'}
                </button>
                <button className="btn btn-secondary" onClick={() => save(false)} disabled={saving || testing}>
                  {saving ? '⟳ Saving…' : '💾 Save'}
                </button>
                <button className="btn btn-primary" onClick={() => save(true)} disabled={saving || testing}>
                  {'▶ Save & Activate'}
                </button>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}


