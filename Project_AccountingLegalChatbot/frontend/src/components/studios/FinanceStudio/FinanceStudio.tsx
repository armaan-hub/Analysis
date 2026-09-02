import './FinanceStudio.css';
import { FinanceStudioProvider, useFinanceStudio } from './FinanceStudioContext';
import { SourceDocsSidebar } from './SourceDocsSidebar/SourceDocsSidebar';
import { AuditChat } from './AuditChat/AuditChat';
import { ReportPreview } from './ReportPreview/ReportPreview';
import { ExportsPanel } from './ExportsPanel/ExportsPanel';
import { FinancialAuditCouncilModal } from './FinancialAuditCouncilModal';
import { Files, MessageSquare, Eye, LayoutGrid, Sparkles } from 'lucide-react';

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

function FinanceStudioContent() {
  const { isCouncilModalOpen, setIsCouncilModalOpen } = useFinanceStudio();

  return (
    <div className="finance-studio">
      <aside className="finance-studio__left">
        <PanelHeader icon={<Files size={18} />} title="Sources" />
        <SourceDocsSidebar />
      </aside>
      <section className="finance-studio__center">
        <div className="finance-studio__center-chat">
          <PanelHeader icon={<MessageSquare size={18} />} title="Chat">
            <button
              className="fs-header-council-btn"
              onClick={() => setIsCouncilModalOpen(true)}
              title="Launch 6-Subagent Financial Audit Council Orchestrator"
            >
              <Sparkles size={13} />
              Audit Council
            </button>
          </PanelHeader>
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

      <FinancialAuditCouncilModal
        isOpen={isCouncilModalOpen}
        onClose={() => setIsCouncilModalOpen(false)}
      />
    </div>
  );
}

export function FinanceStudio() {
  return (
    <FinanceStudioProvider>
      <FinanceStudioContent />
    </FinanceStudioProvider>
  );
}
