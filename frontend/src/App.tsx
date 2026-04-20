import React, { Suspense, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useNavigate, useLocation } from 'react-router-dom';
import { API, type Alert } from './lib/api';
import { StudioProvider } from './context/StudioProvider';
import { ThemeProvider } from './context/ThemeContext';
import { StudioSwitcher } from './components/StudioSwitcher';
import { ContextualSidebar } from './components/ContextualSidebar';

const LegalStudio = React.lazy(() =>
  import('./components/studios/LegalStudio/LegalStudio').then(m => ({ default: m.LegalStudio }))
);
const RegulatoryStudio = React.lazy(() =>
  import('./components/studios/RegulatoryStudio/RegulatoryStudio').then(m => ({ default: m.RegulatoryStudio }))
);
const SettingsPage = React.lazy(() => import('./pages/SettingsPage'));
const TemplateStudio = React.lazy(() =>
  import('./components/studios/TemplateStudio/TemplateStudio').then(m => ({ default: m.TemplateStudio }))
);
const HomePage = React.lazy(() => import('./pages/HomePage'));

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

function PageLoader() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flex: 1,
      background: 'var(--s-bg)',
    }}>
      <div className="loading-spinner" />
    </div>
  );
}

function NotebookPage({ onConversationsChange }: {
  onConversationsChange: (c: Conversation[]) => void;
}) {
  const { id } = useParams<{ id: string }>();
  const convId = id === 'new' ? undefined : id;

  return (
    <LegalStudio
      key={convId ?? 'new'}
      onConversationsChange={onConversationsChange}
      initialConversationId={convId}
    />
  );
}

function AppInner() {
  const [alertCount, setAlertCount] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [newKey, setNewKey] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();

  const isLegalRoute = location.pathname === '/' || location.pathname.startsWith('/notebook');

  const handleLoadConversation = (id: string) => {
    navigate(`/notebook/${id}`);
  };

  const handleNewChat = () => {
    setNewKey(prev => prev + 1);
    navigate('/notebook/new');
  };

  useEffect(() => {
    API.get('/api/monitoring/alerts')
      .then(r => {
        const data: Alert[] = Array.isArray(r.data) ? r.data : [];
        setAlertCount(Array.isArray(data) ? data.filter(a => a.severity === 'critical').length : 0);
      })
      .catch(() => {});
  }, []);

  return (
    <div className={`app-shell ${isLegalRoute ? 'app-shell--legal' : ''}`}>
      <StudioSwitcher alertCount={alertCount} />
      <ContextualSidebar conversations={conversations} onLoadConversation={handleLoadConversation} onNewChat={handleNewChat} />
      <main className="studio-main">
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<HomePage onNewChat={handleNewChat} />} />
            <Route
              path="/notebook/new"
              element={
                <LegalStudio
                  key={`new-${newKey}`}
                  onConversationsChange={setConversations}
                />
              }
            />
            <Route
              path="/notebook/:id"
              element={
                <NotebookPage
                  onConversationsChange={setConversations}
                />
              }
            />
            <Route path="/finance" element={<Navigate to="/" replace />} />
            <Route path="/monitoring" element={<RegulatoryStudio />} />
            <Route path="/templates" element={<TemplateStudio />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
    <Router>
      <StudioProvider>
        <AppInner />
      </StudioProvider>
    </Router>
    </ThemeProvider>
  );
}
