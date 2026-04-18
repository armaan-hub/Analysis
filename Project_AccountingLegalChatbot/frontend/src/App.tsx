import React, { Suspense, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { API, type Alert } from './lib/api';
import { StudioProvider } from './context/StudioProvider';
import { ThemeProvider } from './context/ThemeContext';
import { StudioSwitcher } from './components/StudioSwitcher';
import { ContextualSidebar } from './components/ContextualSidebar';

const LegalStudio = React.lazy(() =>
  import('./components/studios/LegalStudio/LegalStudio').then(m => ({ default: m.LegalStudio }))
);
const FinanceStudio = React.lazy(() =>
  import('./components/studios/FinanceStudio/FinanceStudio').then(m => ({ default: m.FinanceStudio }))
);
const RegulatoryStudio = React.lazy(() =>
  import('./components/studios/RegulatoryStudio/RegulatoryStudio').then(m => ({ default: m.RegulatoryStudio }))
);
const SettingsPage = React.lazy(() => import('./pages/SettingsPage'));
const TemplateStudio = React.lazy(() =>
  import('./components/studios/TemplateStudio/TemplateStudio').then(m => ({ default: m.TemplateStudio }))
);

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

export default function App() {
  const [alertCount, setAlertCount] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);

  const handleNewChat = () => {
    setChatKey(k => k + 1);
    setActiveConvId(null);
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
    <ThemeProvider>
    <Router>
      <StudioProvider>
        <div className="app-shell">
          <StudioSwitcher alertCount={alertCount} />
          <ContextualSidebar conversations={conversations} onLoadConversation={setActiveConvId} onNewChat={handleNewChat} />
          <main className="studio-main">
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route
                  path="/"
                  element={
                    <LegalStudio
                      key={activeConvId ?? `new-${chatKey}`}
                      onConversationsChange={setConversations}
                      initialConversationId={activeConvId ?? undefined}
                    />
                  }
                />
                <Route path="/finance" element={<FinanceStudio />} />
                <Route path="/monitoring" element={<RegulatoryStudio />} />
                <Route path="/templates" element={<TemplateStudio />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </StudioProvider>
    </Router>
    </ThemeProvider>
  );
}
