import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/api';
import { NotebookCard, CreateNotebookCard, type Notebook } from '../components/common/NotebookCard';

export default function HomePage() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
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
        })));
      })
      .catch(() => {});
  }, []);

  const handleOpen = (id: string) => {
    navigate(`/notebook/${id}`);
  };

  const handleCreate = () => {
    navigate('/notebook/new');
  };

  return (
    <div className="home-page">
      <div className="home-page__header">
        <h1 className="home-page__title">📚 Legal Studio</h1>
        <button
          type="button"
          className="home-page__new-btn"
          onClick={handleCreate}
        >
          + New Notebook
        </button>
      </div>

      <div className="home-page__section-label">Recent Notebooks</div>

      <div className="notebook-grid">
        {notebooks.map(nb => (
          <NotebookCard key={nb.id} notebook={nb} onClick={handleOpen} />
        ))}
        <CreateNotebookCard onClick={handleCreate} />
      </div>
    </div>
  );
}
