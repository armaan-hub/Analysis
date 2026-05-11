import React, { Suspense, useState, useEffect, Component, type ReactNode, type ErrorInfo } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useNavigate, useLocation } from 'react-router-dom';
import { API, type Alert } from './lib/api';
import { StudioProvider } from './context/StudioProvider';
import { ThemeProvider } from './context/ThemeContext';
import { AuditOverlayProvider } from './context/AuditOverlayContext';
import { AuditOverlay } from './components/studios/LegalStudio/AuditOverlay';
import { StudioSwitcher } from './components/StudioSwitcher';
import { ContextualSidebar } from './components/ContextualSidebar';

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(e: Error) { return { error: e }; }
  componentDidCatch(e: Error, info: ErrorInfo) { console.error('App error:', e, info); }
  render() {
    if (this.state.error) {
      const e = this.state.error as Error;
      return (
        <div style={{ padding: '40px', color: '#ef4444', fontFamily: 'monospace', fontSize: '14px', background: '#111', minHeight: '100vh' }}>
          <h2 style={{ color: '#fff', marginBottom: '16px' }}>⚠ App Error — open DevTools Console for full trace</h2>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#fca5a5' }}>{e.message}</pre>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#6b7280', marginTop: '12px', fontSize: '12px' }}>{e.stack}</pre>
          <button onClick={() => this.setState({ error: null })} style={{ marginTop: '20px', padding: '8px 16px', background: '#374151', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

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
            <Route path="/finance" element={<Navigate to="/notebook/new" replace />} />
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
    <ErrorBoundary>
    <ThemeProvider>
    <AuditOverlayProvider>
      <AuditOverlay />
      <Router>
        <StudioProvider>
          <ErrorBoundary>
            <AppInner />
          </ErrorBoundary>
        </StudioProvider>
      </Router>
    </AuditOverlayProvider>
    </ThemeProvider>
    </ErrorBoundary>
  );
}
