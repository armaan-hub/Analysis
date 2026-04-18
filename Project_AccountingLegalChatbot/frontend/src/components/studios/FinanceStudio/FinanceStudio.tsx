import './FinanceStudio.css';
import { FinanceStudioProvider } from './FinanceStudioContext';
import { SourceDocsSidebar } from './SourceDocsSidebar/SourceDocsSidebar';
import { AuditChat } from './AuditChat/AuditChat';
import { ReportPreview } from './ReportPreview/ReportPreview';
import { ExportsPanel } from './ExportsPanel/ExportsPanel';

export function FinanceStudio() {
  return (
    <FinanceStudioProvider>
      <div className="finance-studio">
        <aside className="finance-studio__left">
          <SourceDocsSidebar />
        </aside>
        <section className="finance-studio__center">
          <AuditChat />
          <ReportPreview />
        </section>
        <aside className="finance-studio__right">
          <ExportsPanel />
        </aside>
      </div>
    </FinanceStudioProvider>
  );
}
