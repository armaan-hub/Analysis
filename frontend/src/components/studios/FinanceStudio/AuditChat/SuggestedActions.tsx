import { useFinanceStudio } from '../FinanceStudioContext';

const PROMPTS = [
  'Flag anomalies in revenue accounts',
  'Give me an audit risk summary',
  'Drill down on account 4001',
  'Compare to prior year',
];

export function SuggestedActions() {
  const { sendMessage, chatLoading } = useFinanceStudio();
  return (
    <div className="suggested-actions">
      {PROMPTS.map(p => (
        <button key={p} disabled={chatLoading} onClick={() => sendMessage(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}
