import { useFinanceStudio } from '../FinanceStudioContext';
import { Sparkles } from 'lucide-react';

const PROMPTS = [
  'Flag anomalies in revenue accounts',
  'Give me an audit risk summary',
  'Drill down on account 4001',
  'Compare to prior year',
];

export function SuggestedActions() {
  const { sendMessage, chatLoading, setIsCouncilModalOpen } = useFinanceStudio();
  return (
    <div className="suggested-actions">
      <button
        className="suggested-actions__council-btn"
        onClick={() => setIsCouncilModalOpen(true)}
        title="Launch 6-Subagent Financial Audit Council Orchestrator"
      >
        <Sparkles size={12} color="#60a5fa" />
        Run 6-Agent Audit Council
      </button>
      {PROMPTS.map(p => (
        <button key={p} disabled={chatLoading} onClick={() => sendMessage(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}
