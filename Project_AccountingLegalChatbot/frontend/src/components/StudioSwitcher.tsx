import { type ReactNode, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { MessageSquare, BarChart2, Bell, Settings, Sun, Moon, BookOpen, Layout } from 'lucide-react';
import { useStudio, type Studio } from '../context/StudioProvider';
import { useTheme } from '../context/ThemeContext';

interface NavItem {
  icon: ReactNode;
  label: string;
  path: string;
  studio: Studio;
}

interface Props {
  alertCount?: number;
}

export function StudioSwitcher({ alertCount = 0 }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const { setActiveStudio } = useStudio();
  const { theme, toggleTheme } = useTheme();

  const items: NavItem[] = [
    { icon: <MessageSquare size={20} />, label: 'Legal Intelligence', path: '/', studio: 'legal' },
    { icon: <BarChart2 size={20} />, label: 'Financial Reporting', path: '/reports', studio: 'financial' },
    { icon: <BookOpen size={20} />, label: 'Audit Profiles', path: '/profiles', studio: 'profiles' },
    { icon: <Layout size={20} />, label: 'Template Learning', path: '/templates', studio: 'templates' },
    { icon: <Bell size={20} />, label: 'Regulatory Center', path: '/monitoring', studio: 'regulatory' },
    { icon: <Settings size={20} />, label: 'Settings', path: '/settings', studio: 'settings' },
  ];

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  useEffect(() => {
    const match = items.find(i => isActive(i.path));
    if (match) setActiveStudio(match.studio);
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <aside className="studio-switcher">
      <div className="switcher-logo">LA</div>
      <nav className="switcher-nav">
        {items.map(item => (
          <button
            key={item.path}
            className={`switcher-btn ${isActive(item.path) ? 'switcher-btn--active' : ''}`}
            onClick={() => { navigate(item.path); setActiveStudio(item.studio); }}
            title={item.label}
          >
            {item.icon}
            {item.studio === 'regulatory' && alertCount > 0 && (
              <span className="switcher-badge" />
            )}
          </button>
        ))}
        <button
          className="switcher-btn"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          style={{ marginTop: 'auto' }}
        >
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </nav>
    </aside>
  );
}
