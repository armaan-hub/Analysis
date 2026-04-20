import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Grid3X3, List, Search } from 'lucide-react';
import { API } from '../lib/api';
import { NotebookCard, CreateNotebookCard, type Notebook } from '../components/common/NotebookCard';

interface HomePageProps {
  onNewChat?: () => void;
}

export default function HomePage({ onNewChat }: HomePageProps) {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    API.get('/api/chat/conversations')
      .then(r => {
        const convos = r.data ?? [];
        setNotebooks(convos.map((c: any) => ({
          id: c.id,
          title: c.title || 'Untitled Notebook',
          updated_at: c.updated_at || new Date().toISOString(),
          source_count: c.source_count,
          domain: c.domain,
        })));
      })
      .catch(() => {});
  }, []);

  const handleOpen = (id: string) => navigate(`/notebook/${id}`);

  const handleCreate = () => {
    if (onNewChat) onNewChat();
    else navigate('/notebook/new');
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
        await Promise.all([...selectedIds].map(id => API.delete(`/api/legal-studio/notebook/${id}`)));
        setNotebooks(prev => prev.filter(n => !selectedIds.has(n.id)));
        exitSelectionMode();
      } catch { /* ignore */ }
      setDeleteTarget(null);
    } else if (deleteTarget) {
      try {
        await API.delete(`/api/legal-studio/notebook/${deleteTarget}`);
        setNotebooks(prev => prev.filter(n => n.id !== deleteTarget));
      } catch { /* ignore */ }
      setDeleteTarget(null);
    }
  };

  const filtered = notebooks.filter(n =>
    n.title.toLowerCase().includes(search.toLowerCase()),
  );

  const deleteNotebook = deleteTarget === '__bulk__'
    ? null
    : filtered.find(n => n.id === deleteTarget) ?? notebooks.find(n => n.id === deleteTarget);

  /* ── inline styles ───────────────────────────────────────── */
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
        <h1 className="home-page__title">📚 Legal Studio</h1>
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
            onClick={id => !selectionMode && handleOpen(id)}
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
