import { useFinanceStudio } from '../FinanceStudioContext';
import type { WorkflowStep } from '../types';

const STEPS: { n: WorkflowStep; label: string }[] = [
  { n: 1, label: 'Upload' },
  { n: 2, label: 'Build Profile' },
  { n: 3, label: 'Validate with AI' },
  { n: 4, label: 'Select Format' },
  { n: 5, label: 'Generate' },
];

export function WorkflowSteps() {
  const { workflowStep, setWorkflowStep } = useFinanceStudio();
  return (
    <ol className="workflow-steps">
      {STEPS.map(s => (
        <li key={s.n}
            className={s.n === workflowStep ? 'active' : s.n < workflowStep ? 'done' : ''}
            onClick={() => setWorkflowStep(s.n)}>
          {s.n}. {s.label}
        </li>
      ))}
    </ol>
  );
}
