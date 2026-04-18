import { useStudio } from '../context/StudioProvider';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface Props {
  conversations?: Conversation[];
  onLoadConversation?: (id: string) => void;
  onNewChat?: () => void;
}

function groupByDate(convos: Conversation[]) {
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterdayStr = new Date(now.getTime() - 86400000).toDateString();
  const weekAgo = new Date(now.getTime() - 7 * 86400000);

  const today = convos.filter(c => new Date(c.updated_at).toDateString() === todayStr);
  const yesterday = convos.filter(c => new Date(c.updated_at).toDateString() === yesterdayStr);
  const lastWeek = convos.filter(c => {
    const d = new Date(c.updated_at);
    return d > weekAgo && d.toDateString() !== todayStr && d.toDateString() !== yesterdayStr;
  });

  return { today, yesterday, lastWeek };
}

export function ContextualSidebar({ conversations = [], onLoadConversation, onNewChat }: Props) {
  const { activeStudio, sidebarOpen, toggleSidebar } = useStudio();
  const groups = groupByDate(conversations);

  return (
    <aside className={`contextual-sidebar ${sidebarOpen ? '' : 'contextual-sidebar--closed'}`}>
      <button className="sidebar-toggle" onClick={toggleSidebar} title={sidebarOpen ? 'Collapse' : 'Expand'}>
        {sidebarOpen ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
      </button>

      {sidebarOpen && (
        <div className="sidebar-content">
          {activeStudio === 'legal' && (
            <>
              <div style={{ padding: '12px 12px 4px' }}>
                <button
                  onClick={onNewChat}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 12px',
                    borderRadius: 'var(--s-r-md)',
                    border: '1px solid var(--s-border)',
                    background: 'transparent',
                    color: 'var(--s-text-2)',
                    fontFamily: 'var(--s-font-ui)',
                    fontSize: '13px',
                    cursor: 'pointer',
                    transition: 'var(--s-ease)',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(107,140,255,0.08)';
                    (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-accent)';
                    (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-accent)';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                    (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-text-2)';
                    (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-border)';
                  }}
                >
                  <span style={{ fontSize: '16px', lineHeight: 1 }}>+</span>
                  New Chat
                </button>
              </div>
              <div className="sidebar-section-title">Chat History</div>
              {groups.today.length > 0 && (
                <div className="sidebar-group">
                  <div className="sidebar-group-label">Today</div>
                  {groups.today.map(c => (
                    <div
                      key={c.id}
                      className="sidebar-item"
                      onClick={() => onLoadConversation?.(c.id)}
                    >
                      {c.title}
                    </div>
                  ))}
                </div>
              )}
              {groups.yesterday.length > 0 && (
                <div className="sidebar-group">
                  <div className="sidebar-group-label">Yesterday</div>
                  {groups.yesterday.map(c => (
                    <div
                      key={c.id}
                      className="sidebar-item"
                      onClick={() => onLoadConversation?.(c.id)}
                    >
                      {c.title}
                    </div>
                  ))}
                </div>
              )}
              {groups.lastWeek.length > 0 && (
                <div className="sidebar-group">
                  <div className="sidebar-group-label">Last Week</div>
                  {groups.lastWeek.map(c => (
                    <div
                      key={c.id}
                      className="sidebar-item"
                      onClick={() => onLoadConversation?.(c.id)}
                    >
                      {c.title}
                    </div>
                  ))}
                </div>
              )}
              {conversations.length === 0 && (
                <div className="sidebar-empty">No conversations yet</div>
              )}
            </>
          )}

          {activeStudio === 'regulatory' && (
            <>
              <div className="sidebar-section-title">Severity</div>
              {['Critical', 'Warning', 'Info'].map(s => (
                <div key={s} className="sidebar-item">{s}</div>
              ))}
            </>
          )}
        </div>
      )}
    </aside>
  );
}
