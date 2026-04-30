import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Grid3X3, List, Search } from 'lucide-react';
import { API } from '../lib/api';
import { NotebookCard, CreateNotebookCard, type Notebook } from '../components/common/NotebookCard';

interface HomePageProps {
  onNewChat?: () => void;
}

type ModeFilter = 'all' | 'fast' | 'deep_research' | 'analyst';

const MODE_META: Record<string, { label: string; icon: string; colour: string }> = {
  fast:          { label: 'Fast',          icon: '⚡', colour: '#f59e0b' },
  deep_research: { label: 'Deep Research', icon: '🔬', colour: '#6366f1' },
  analyst:       { label: 'Analyst',       icon: '📊', colour: '#10b981' },
};

export default function HomePage({ onNewChat }: HomePageProps) {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeModes, setActiveModes] = useState<Set<ModeFilter>>(new Set(['all']));
  const navigate = useNavigate();

  useEffect(() => {
    API.get('/api/chat/conversations')
      .then(r => {
        const convos = r.data ?? [];
        setNotebooks(convos
          .map((c: { id: string; title: string; updated_at: string; mode?: string; source_count?: number; domain?: string }) => ({
            id: c.id,
            title: c.title || 'Untitled Notebook',
            updated_at: c.updated_at || new Date().toISOString(),
            source_count: c.source_count,
            domain: c.domain,
            mode: c.mode,
          })));
      })
      .catch((err) => console.error('Failed to load conversations:', err));
  }, []);

  const handleOpen = (id: string) => navigate(`/notebook/${id}`);

  const handleCreate = () => {
    if (onNewChat) onNewChat();
    else navigate('/notebook/new');
  };

  const toggleMode = (mode: ModeFilter) => {
    if (mode === 'all') {
      setActiveModes(new Set(['all']));
      return;
    }
    setActiveModes(prev => {
      const next = new Set(prev);
      next.delete('all');
      if (next.has(mode)) {
        next.delete(mode);
      } else {
        next.add(mode);
      }
      return next.size === 0 ? new Set<ModeFilter>(['all']) : next;
    });
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const exitSelectionMode = () => {
    setSelectionMode(false);
    setSelectedIds(new Set());
  };

  const handleDeleteConfirm = async () => {
    if (deleteTarget === '__bulk__') {
      try {
        await Promise.all([...selectedIds].map(id => API.delete(`/api/chat/conversations/${id}`)));
        setNotebooks(prev => prev.filter(n => !selectedIds.has(n.id)));
        exitSelectionMode();
      } catch (err) { console.error('Operation failed:', err); }
      setDeleteTarget(null);
    } else if (deleteTarget) {
      try {
        await API.delete(`/api/chat/conversations/${deleteTarget}`);
        setNotebooks(prev => prev.filter(n => n.id !== deleteTarget));
      } catch (err) { console.error('Operation failed:', err); }
      setDeleteTarget(null);
    }
  };

  const filtered = notebooks
    .filter(n => n.title.toLowerCase().includes(search.toLowerCase()))
    .filter(n =>
      activeModes.has('all') ||
      (n.mode != null && activeModes.has(n.mode))
    );

  const deleteNotebook = deleteTarget === '__bulk__'
    ? null
    : filtered.find(n => n.id === deleteTarget) ?? notebooks.find(n => n.id === deleteTarget);

  /* ── inline styles ───────────────────────────────────────── */
  const filterBarStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '8px',
    flexWrap: 'wrap', marginBottom: '16px',
  };

  const filterLabelStyle: React.CSSProperties = {
    fontSize: '11px', fontWeight: 600, color: 'var(--s-text-2)',
    textTransform: 'uppercase', letterSpacing: '0.06em', marginRight: '4px',
  };

  const filterTagStyle = (mode: ModeFilter): React.CSSProperties => {
    const isAll   = mode === 'all';
    const active  = activeModes.has(mode);
    const colour  = isAll ? 'var(--primary)' : (MODE_META[mode]?.colour ?? 'var(--primary)');
    return {
      display: 'inline-flex', alignItems: 'center', gap: '6px',
      padding: '5px 14px', borderRadius: '8px',
      fontSize: '12px', fontWeight: 600, cursor: 'pointer',
      transition: 'all 150ms ease',
      background:   active ? `${colour}26` : 'transparent',
      border:       active ? `1.5px solid ${colour}99` : `1.5px dashed var(--border)`,
      color:        active ? colour : 'var(--text-3)',
    };
  };

  const toolbarStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '12px',
    flexWrap: 'wrap', marginBottom: '20px',
  };

  const searchBoxStyle: React.CSSProperties = {
    flex: '1 1 220px', display: 'flex', alignItems: 'center', gap: '8px',
    background: 'rgba(255,255,255,0.06)', border: '1px solid var(--s-border)',
    borderRadius: 'var(--s-r-lg, 12px)', padding: '8px 14px',
  };

  const inputStyle: React.CSSProperties = {
    flex: 1, background: 'transparent', border: 'none', outline: 'none',
    color: 'var(--s-text)', fontSize: '14px',
  };

  const toggleBtnBase: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: '36px', height: '36px', borderRadius: 'var(--s-r-md, 8px)',
    border: '1px solid var(--s-border)', cursor: 'pointer',
    transition: 'background 150ms ease, color 150ms ease',
  };

  const activeToggle: React.CSSProperties = {
    ...toggleBtnBase,
    background: 'var(--s-accent, #6366f1)', color: '#fff', borderColor: 'transparent',
  };

  const inactiveToggle: React.CSSProperties = {
    ...toggleBtnBase,
    background: 'rgba(255,255,255,0.06)', color: 'var(--s-text-2)',
  };

  const toolbarBtnStyle: React.CSSProperties = {
    padding: '8px 16px', borderRadius: 'var(--s-r-md, 8px)',
    border: '1px solid var(--s-border)', cursor: 'pointer',
    fontSize: '14px', fontWeight: 500,
    background: 'rgba(255,255,255,0.06)', color: 'var(--s-text)',
    transition: 'background 150ms ease, color 150ms ease',
  };

  const toolbarBtnActiveStyle: React.CSSProperties = {
    ...toolbarBtnStyle,
    background: 'var(--s-accent, #6366f1)', color: '#fff', borderColor: 'transparent',
  };

  const toolbarBtnDangerStyle: React.CSSProperties = {
    ...toolbarBtnStyle,
    background: '#ef4444', color: '#fff', borderColor: 'transparent',
  };

  const overlayStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 9999,
    background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  };

  const modalStyle: React.CSSProperties = {
    background: 'var(--s-bg, #1e1e2e)', border: '1px solid var(--s-border)',
    borderRadius: 'var(--s-r-lg, 12px)', padding: '28px 32px',
    maxWidth: '420px', width: '90%', textAlign: 'center',
    color: 'var(--s-text)',
  };

  const modalBtnBase: React.CSSProperties = {
    padding: '8px 20px', borderRadius: 'var(--s-r-md, 8px)',
    border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '14px',
  };

  return (
    <div className="home-page">
      <div className="home-page__header">
        <h1 className="home-page__title">📚 Compliance and Analysis Studio</h1>
      </div>

      {/* Mode filter bar */}
      <div style={filterBarStyle}>
        <span style={filterLabelStyle}>Filter</span>

        <button
          type="button"
          aria-pressed={activeModes.has('all')}
          style={filterTagStyle('all')}
          onClick={() => toggleMode('all')}
        >
          All Modes
        </button>

        {(['fast', 'deep_research', 'analyst'] as ModeFilter[]).map(mode => {
          const meta = MODE_META[mode];
          return (
            <button
              key={mode}
              type="button"
              aria-label={meta.label}
              aria-pressed={activeModes.has(mode)}
              style={filterTagStyle(mode)}
              onClick={() => toggleMode(mode)}
            >
              <span
                aria-hidden="true"
                style={{
                  width: '7px', height: '7px', borderRadius: '50%',
                  background: meta.colour, flexShrink: 0,
                  boxShadow: activeModes.has(mode) ? `0 0 5px ${meta.colour}` : 'none',
                }}
              />
              {meta.icon} {meta.label}
            </button>
          );
        })}
      </div>

      {/* Toolbar: search + view toggle */}
      <div style={toolbarStyle}>
        <div style={searchBoxStyle}>
          <Search size={16} style={{ color: 'var(--s-text-2)', flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Search notebooks…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={inputStyle}
          />
        </div>

        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            type="button"
            aria-label="Grid view"
            style={viewMode === 'grid' ? activeToggle : inactiveToggle}
            onClick={() => setViewMode('grid')}
          >
            <Grid3X3 size={18} />
          </button>
          <button
            type="button"
            aria-label="List view"
            style={viewMode === 'list' ? activeToggle : inactiveToggle}
            onClick={() => setViewMode('list')}
          >
            <List size={18} />
          </button>
        </div>

        {/* Selection mode toggle */}
        <button
          type="button"
          style={selectionMode ? toolbarBtnActiveStyle : toolbarBtnStyle}
          onClick={() => selectionMode ? exitSelectionMode() : setSelectionMode(true)}
        >
          {selectionMode ? 'Cancel' : 'Select'}
        </button>

        {/* Bulk delete */}
        {selectionMode && selectedIds.size > 0 && (
          <button
            type="button"
            style={toolbarBtnDangerStyle}
            onClick={() => setDeleteTarget('__bulk__')}
          >
            Delete ({selectedIds.size})
          </button>
        )}
      </div>

      <div className="home-page__section-label">Recent Notebooks</div>

      <div className={viewMode === 'list' ? 'notebook-list' : 'notebook-grid'}>
        <CreateNotebookCard onClick={handleCreate} view={viewMode} />
        {filtered.map(nb => (
          <NotebookCard
            key={nb.id}
            notebook={nb}
            onClick={id => selectionMode ? handleToggleSelect(id) : handleOpen(id)}
            onDelete={id => setDeleteTarget(id)}
            view={viewMode}
            selectionMode={selectionMode}
            selected={selectedIds.has(nb.id)}
            onToggleSelect={handleToggleSelect}
          />
        ))}
      </div>

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div style={overlayStyle} onClick={() => setDeleteTarget(null)}>
          <div style={modalStyle} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 12px' }}>Delete Notebook{deleteTarget === '__bulk__' ? 's' : ''}</h3>
            <p style={{ margin: '0 0 24px', color: 'var(--s-text-2)', lineHeight: 1.5 }}>
              {deleteTarget === '__bulk__'
                ? `Delete ${selectedIds.size} notebook${selectedIds.size > 1 ? 's' : ''}? This cannot be undone.`
                : <>Delete notebook <strong>{deleteNotebook?.title ?? 'this notebook'}</strong>? This cannot be undone.</>
              }
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button
                type="button"
                style={{ ...modalBtnBase, background: 'rgba(255,255,255,0.08)', color: 'var(--s-text)' }}
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                style={{ ...modalBtnBase, background: '#ef4444', color: '#fff' }}
                onClick={handleDeleteConfirm}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
