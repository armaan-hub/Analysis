export type ChatMode = 'fast' | 'deep_research' | 'analyst';

const MODE_OPTIONS: { value: ChatMode; label: string; icon: string }[] = [
  { value: 'fast', label: 'Fast', icon: '⚡' },
  { value: 'deep_research', label: 'Deep Research', icon: '🔬' },
  { value: 'analyst', label: 'Analyst', icon: '📊' },
];

const PLACEHOLDERS: Record<ChatMode, string> = {
  fast: 'Ask about your sources…',
  deep_research: 'What would you like to research?',
  analyst: 'What should I analyze?',
};

interface Props {
  value: ChatMode;
  onChange: (mode: ChatMode) => void;
}

export function ModePills({ value, onChange }: Props) {
  return (
    <div className="mode-pills">
      {MODE_OPTIONS.map(opt => (
        <button
          key={opt.value}
          type="button"
          className={`mode-pill${opt.value === value ? ' mode-pill--active' : ''}`}
          onClick={() => onChange(opt.value)}
          aria-pressed={opt.value === value}
        >
          <span>{opt.icon}</span> {opt.label}
        </button>
      ))}
    </div>
  );
}

export { PLACEHOLDERS as MODE_PLACEHOLDERS };
