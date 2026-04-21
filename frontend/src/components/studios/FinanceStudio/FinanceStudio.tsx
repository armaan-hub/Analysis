import './FinanceStudio.css';
import { FinanceStudioProvider } from './FinanceStudioContext';
import { SourceDocsSidebar } from './SourceDocsSidebar/SourceDocsSidebar';
import { AuditChat } from './AuditChat/AuditChat';
import { ReportPreview } from './ReportPreview/ReportPreview';
import { ExportsPanel } from './ExportsPanel/ExportsPanel';
import { Files, MessageSquare, Eye, LayoutGrid } from 'lucide-react';

function PanelHeader({ icon, title, children }: {
  icon: React.ReactNode;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="fs-panel-header">
      <span className="fs-panel-header__icon">{icon}</span>
      <span className="fs-panel-header__title">{title}</span>
      {children}
    </div>
  );
}

export function FinanceStudio() {
  return (
    <FinanceStudioProvider>
      <div className="finance-studio">
        <aside className="finance-studio__left">
          <PanelHeader icon={<Files size={18} />} title="Sources" />
          <SourceDocsSidebar />
        </aside>
        <section className="finance-studio__center">
          <div className="finance-studio__center-chat" style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0', overflowY: 'auto', minHeight: 0 }}>
            <PanelHeader icon={<MessageSquare size={18} />} title="Chat" />
            <AuditChat />
          </div>
          <div className="finance-studio__center-preview">
            <PanelHeader icon={<Eye size={18} />} title="Preview" />
            <ReportPreview />
          </div>
        </section>
        <aside className="finance-studio__right">
          <PanelHeader icon={<LayoutGrid size={18} />} title="Studio" />
          <ExportsPanel />
        </aside>
      </div>
    </FinanceStudioProvider>
  );
}
