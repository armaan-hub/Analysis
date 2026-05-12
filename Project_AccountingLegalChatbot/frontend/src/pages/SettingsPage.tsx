import { useState, useEffect } from 'react';
import { API, API_BASE, getErrMsg } from '../lib/api';
import ApiKeyRow, { type KeyMode } from '../components/ApiKeyRow';
import EmbeddingCard from '../components/EmbeddingCard';

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

interface DetectProviderResponse {
  provider: string;
  key_env_var: string | null;
  key_label: string;
  key_valid: boolean;
}


interface ReindexStatus {
  needs_reindex: boolean;
  documents_pending: number;
  fingerprint: string;
}

interface LocalServerInfo {
  provider: string;
  base_url: string;
  online: boolean;
  models: string[];
  latency_ms: number;
}

interface LocalScanResponse {
  scan_time: string | null;
  cache_age_s: number;
  servers: LocalServerInfo[];
}

const PROVIDER_META: Record<string, { label: string; icon: string; keyRequired: boolean; hasBaseUrl: boolean; hasFastModel: boolean }> = {
  nvidia:  { label: 'NVIDIA NIM',    icon: '🟢', keyRequired: true,  hasBaseUrl: true,  hasFastModel: true  },
  openai:  { label: 'OpenAI',        icon: '⚫', keyRequired: true,  hasBaseUrl: false, hasFastModel: false },
  claude:  { label: 'Anthropic',     icon: '🟠', keyRequired: true,  hasBaseUrl: false, hasFastModel: false },
  mistral: { label: 'Mistral',       icon: '🔵', keyRequired: true,  hasBaseUrl: false, hasFastModel: false },
  groq:    { label: 'Groq',          icon: '🟡', keyRequired: true,  hasBaseUrl: false, hasFastModel: true  },
  opencode: { label: 'OpenCode Zen', icon: '🌐', keyRequired: false, hasBaseUrl: true,  hasFastModel: false },
  ollama:  { label: 'Ollama (local)', icon: '🟣', keyRequired: false, hasBaseUrl: true,  hasFastModel: false },
  local:   { label: 'Local',         icon: '🖥️', keyRequired: false, hasBaseUrl: true,  hasFastModel: false },
};

const LOCAL_PROVIDER_NAMES: Record<string, string> = {
  ollama: 'Ollama',
  lmstudio: 'LM Studio',
  tgi: 'HuggingFace TGI',
  kobold: 'Kobold.cpp',
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
  const [localScan,    setLocalScan]    = useState<LocalScanResponse | null>(null);
  const [loadingLocal, setLoadingLocal] = useState(true);
  const [refreshingLocal, setRefreshingLocal] = useState(false);
  const [localExpanded, setLocalExpanded] = useState(true);

  const [models,         setModels]         = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [modelsError,    setModelsError]    = useState('');

  const [saving,      setSaving]      = useState(false);
  const [testing,     setTesting]     = useState(false);
  const [statusMsg,   setStatusMsg]   = useState<{ text: string; ok: boolean } | null>(null);

  // URL auto-detect state
  const [detectingProvider, setDetectingProvider] = useState(false);
  const [apiKeyLabel,       setApiKeyLabel]       = useState<string>('');
  const [apiKeyValid,       setApiKeyValid]       = useState<boolean>(false);

  // Embedding provider state (reindex status only — live status shown by EmbeddingCard)
  const [reindexStatus,    setReindexStatus]    = useState<ReindexStatus | null>(null);
  const [reindexing,       setReindexing]       = useState(false);

  // API key visibility modes
  const API_KEY_NAMES = ['NVIDIA_API_KEY', 'NVIDIA_FAST_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GROQ_API_KEY', 'MISTRAL_API_KEY', 'OPENCODE_API_KEY'] as const;
  const [keyModes,    setKeyModes]    = useState<Record<string, KeyMode>>({});
  const [keyLoading,  setKeyLoading]  = useState<Record<string, boolean>>({});

  const flash = (text: string, ok: boolean) => {
    setStatusMsg({ text, ok });
    setTimeout(() => setStatusMsg(null), 4000);
  };

  const fetchEmbeddingInfo = () => {
    API.get('/api/documents/reindex-status').then(r => setReindexStatus(r.data)).catch(() => {});
  };

  const fetchLocalScan = async () => {
    setLoadingLocal(true);
    try {
      const r = await API.get('/api/settings/local-scan');
      setLocalScan(r.data as LocalScanResponse);
    } catch {
      setLocalScan({ scan_time: null, cache_age_s: 0, servers: [] });
    } finally {
      setLoadingLocal(false);
    }
  };

  const refreshLocalScan = async () => {
    setRefreshingLocal(true);
    try {
      await API.post('/api/settings/local-scan/refresh');
      await fetchLocalScan();
      flash('Local scan complete', true);
    } catch (e) {
      flash(getErrMsg(e, 'Scan failed'), false);
    } finally {
      setRefreshingLocal(false);
    }
  };

  const selectLocalServer = (server: LocalServerInfo) => {
    if (!server.online) return;
    setSelectedProvider('local');
    setModels(server.models || []);
    setModelsError('');
    setStatusMsg(null);
    setApiKeyLabel('');
    setApiKeyValid(false);
    setEditKey('');
    setEditFastKey('');
    setEditFastModel('');
    setEditModel(server.models?.[0] || '');
    setEditBaseUrl(server.base_url || '');
    void onBaseUrlBlur(server.base_url || '');
  };

  const triggerReindex = async () => {
    setReindexing(true);
    try {
      const r = await API.post('/api/documents/reindex-all');
      flash(`Re-indexed ${r.data.documents} documents (${r.data.reindexed_chunks} chunks)`, true);
      fetchEmbeddingInfo();
    } catch (e) {
      flash(getErrMsg(e, 'Re-index failed'), false);
    } finally {
      setReindexing(false);
    }
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
    fetchEmbeddingInfo();
    void fetchLocalScan();
    API.get('/api/settings/keys')
      .then(r => setKeyModes(r.data as Record<string, KeyMode>))
      .catch(() => {});
  }, []);

  const toggleKeyMode = async (keyName: string, newMode: KeyMode) => {
    if (keyLoading[keyName]) return;
    const previousMode = keyModes[keyName];
    setKeyModes(prev => ({ ...prev, [keyName]: newMode }));
    setKeyLoading(prev => ({ ...prev, [keyName]: true }));
    try {
      await API.put('/api/settings/keys', { [keyName]: newMode });
    } catch (e) {
      flash(getErrMsg(e, 'Failed to update key visibility'), false);
      setKeyModes(prev => ({ ...prev, [keyName]: previousMode }));
      // Best-effort sync with server state after revert
      API.get('/api/settings/keys')
        .then(r => setKeyModes(r.data as Record<string, KeyMode>))
        .catch(() => {});
    } finally {
      setKeyLoading(prev => ({ ...prev, [keyName]: false }));
    }
  };

  const pickProvider = (p: string) => {
    setSelectedProvider(p);
    setModels([]);
    setModelsError('');
    setStatusMsg(null);
    setApiKeyLabel('');
    setApiKeyValid(false);
    const prov: ProviderConfig = fullSettings?.providers?.[p] || { api_key: '', model: '', base_url: '', fast_api_key: '', fast_model: '' };
    // Never pre-fill key fields with masked values — leave blank so users must type to change
    setEditKey('');
    setEditModel(prov.model || '');
    setEditBaseUrl(prov.base_url || '');
    setEditFastKey('');
    setEditFastModel(prov.fast_model || '');
    // Auto-fetch models for OpenCode Zen (free, no key required)
    if (p === 'opencode') {
      setFetchingModels(true);
      API.get(`/api/settings/providers/opencode/models`)
        .then(r => {
          const rawData = Array.isArray(r.data) ? r.data : [];
          const list: string[] = rawData.map((m: { id: string }) => m.id);
          setModels(list);
          if (list.length === 0) setModelsError('No models returned from OpenCode Zen.');
        })
        .catch(e => setModelsError(getErrMsg(e, 'Failed to fetch models')))
        .finally(() => setFetchingModels(false));
    }
  };

  const fetchModels = async () => {
    setFetchingModels(true);
    setModelsError('');
    setModels([]);
    try {
      const r = await API.get(`/api/settings/providers/${selectedProvider}/models`);
      const rawData = Array.isArray(r.data) ? r.data : [];
      const list: string[] = rawData.map((m: { id: string }) => m.id);
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

  const onBaseUrlBlur = async (url: string) => {
    if (!url.trim()) {
      setApiKeyLabel('');
      setApiKeyValid(false);
      return;
    }
    try {
      setDetectingProvider(true);
      const res = await fetch('/api/settings/detect-provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: url, api_key: editKey || undefined }),
      });
      if (!res.ok) return;
      const data: DetectProviderResponse = await res.json();
      if (data.provider && PROVIDER_META[data.provider]) {
        setSelectedProvider(data.provider);
      }
      setApiKeyLabel(data.key_env_var ?? '');
      setApiKeyValid(data.key_valid);
    } catch {
      // silently ignore — don't disrupt user flow
    } finally {
      setDetectingProvider(false);
    }
  };

  const meta = PROVIDER_META[selectedProvider] ?? { label: selectedProvider, icon: '⚙️', keyRequired: true, hasBaseUrl: false, hasFastModel: false };
  const isActive = fullSettings?.llm_provider === selectedProvider;
  const localServers = localScan?.servers || [];
  const onlineLocalServers = localServers.filter(server => server.online);
  const offlineLocalServers = localServers.filter(server => !server.online);

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
              <div className="settings-section-title" style={{ marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => setLocalExpanded(v => !v)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0, font: 'inherit' }}
                >
                  <span>{localExpanded ? '▼' : '▶'}</span>
                  <span>Local Models</span>
                </button>
                <button
                  type="button"
                  className="btn-icon"
                  style={{ padding: '4px' }}
                  title="Refresh local model scan"
                  onClick={refreshLocalScan}
                  disabled={refreshingLocal}
                >
                  {refreshingLocal ? '…' : '↻'}
                </button>
              </div>

              {localExpanded && (
                <>
                  {loadingLocal ? (
                    <div style={{ padding: '8px 0' }}>
                      <div className="loading-spinner" style={{ width: '18px', height: '18px', borderWidth: '2px', margin: '6px auto' }} />
                    </div>
                  ) : localServers.length === 0 ? (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-2)', lineHeight: 1.4, paddingBottom: '8px' }}>
                      No local models detected. Make sure Ollama or LM Studio is running.
                    </div>
                  ) : (
                    <>
                      {onlineLocalServers.map(server => {
                        const selected = selectedProvider === 'local' && editBaseUrl === server.base_url;
                        return (
                          <div
                            key={`${server.provider}:${server.base_url}`}
                            className={`provider-card ${selected ? 'selected' : ''}`}
                            onClick={() => selectLocalServer(server)}
                          >
                            <span className="provider-card-icon" style={{ fontSize: '0.62rem', border: '1px solid var(--border)', borderRadius: '999px', padding: '2px 6px', letterSpacing: '0.04em' }}>LOCAL</span>
                            <div className="provider-card-info">
                              <div className="provider-card-name" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span>{LOCAL_PROVIDER_NAMES[server.provider] || server.provider}</span>
                                <span style={{ color: 'var(--green)', fontSize: '0.62rem' }}>●</span>
                              </div>
                              <div className="provider-card-model">
                                {server.models.length} model{server.models.length === 1 ? '' : 's'}
                              </div>
                            </div>
                          </div>
                        );
                      })}

                      {offlineLocalServers.map(server => (
                        <div
                          key={`${server.provider}:${server.base_url}`}
                          className="provider-card"
                          style={{ opacity: 0.55, cursor: 'default' }}
                          aria-disabled
                        >
                          <span className="provider-card-icon" style={{ fontSize: '0.62rem', border: '1px solid var(--border)', borderRadius: '999px', padding: '2px 6px', letterSpacing: '0.04em' }}>LOCAL</span>
                          <div className="provider-card-info">
                            <div className="provider-card-name" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span>{LOCAL_PROVIDER_NAMES[server.provider] || server.provider}</span>
                              <span style={{ color: 'var(--text-3)', fontSize: '0.62rem' }}>●</span>
                            </div>
                            <div className="provider-card-model">offline</div>
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </>
              )}

              <div className="settings-section-title" style={{ marginBottom: '10px' }}>Providers</div>
              {Object.entries(PROVIDER_META).filter(([key]) => key !== 'local').map(([key, m]) => {
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
                  <div style={{ fontWeight: 700, fontSize: '1rem' }}>
                    {meta.label}
                    {detectingProvider && <span style={{ fontSize: '0.75rem', color: 'var(--text-2)', marginLeft: '8px' }}>⟳ detecting…</span>}
                  </div>
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
                  {apiKeyValid && (
                    <div style={{ fontSize: '0.72rem', color: 'var(--green)', marginTop: '4px' }}>✓ API key valid</div>
                  )}
                  {apiKeyLabel && (
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-2)', marginTop: '4px' }}>Set via env var: {apiKeyLabel}</div>
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
                    onBlur={e => onBaseUrlBlur(e.target.value)}
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
                    {models.length > 0 ? (
                      <select
                        className="settings-input settings-select"
                        value={editFastModel}
                        onChange={e => setEditFastModel(e.target.value)}
                      >
                        <option value="">— select fast model —</option>
                        {models.map(m => <option key={m} value={m}>{m}</option>)}
                      </select>
                    ) : (
                      <input
                        type="text"
                        className="settings-input"
                        placeholder="e.g. deepseek-ai/deepseek-v3.1-terminus"
                        value={editFastModel}
                        onChange={e => setEditFastModel(e.target.value)}
                      />
                    )}
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

        {/* ── Embedding Provider Card ──────────────────────────────── */}
        {!loading && (
          <div style={{ marginTop: '28px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <span style={{ fontSize: '1.2rem' }}>🔢</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem' }}>Embedding Provider</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-2)' }}>Controls how documents are vectorized for RAG search</div>
              </div>
            </div>

            {reindexStatus?.needs_reindex && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: 'rgba(234,179,8,0.12)', border: '1px solid rgba(234,179,8,0.4)', borderRadius: '8px', padding: '10px 14px', marginBottom: '14px' }}>
                <span style={{ fontSize: '1.1rem' }}>⚠️</span>
                <div style={{ flex: 1, fontSize: '0.82rem', color: 'var(--text-1)' }}>
                  <strong>Re-index needed</strong> — {reindexStatus.documents_pending} document(s) use a different embedding fingerprint.
                </div>
                <button
                  className="btn btn-primary"
                  style={{ whiteSpace: 'nowrap', fontSize: '0.8rem', padding: '6px 14px' }}
                  onClick={triggerReindex}
                  disabled={reindexing}
                >
                  {reindexing ? '⟳ Re-indexing…' : '↺ Re-index All'}
                </button>
              </div>
            )}

            <EmbeddingCard onProviderChange={() => fetchEmbeddingInfo()} />
          </div>
        )}
        {/* ── API Key Visibility Section ─────────────────────────── */}
        {!loading && (
          <div style={{ marginTop: '28px', border: '1px solid var(--border)', borderRadius: '12px', padding: '20px 24px', background: 'var(--surface-2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <span style={{ fontSize: '1.2rem' }}>🔑</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem' }}>API Key Visibility</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-2)' }}>Control how API keys are displayed — cycle between masked, hidden, and visible modes</div>
              </div>
            </div>
            {API_KEY_NAMES.map(keyName => (
              <ApiKeyRow
                key={keyName}
                keyName={keyName}
                mode={(keyModes[keyName] as KeyMode) ?? 'masked'}
                onToggle={toggleKeyMode}
                loading={!!keyLoading[keyName]}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
