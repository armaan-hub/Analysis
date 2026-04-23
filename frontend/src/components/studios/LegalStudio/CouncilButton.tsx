interface Props { onClick: () => void; disabled?: boolean; }
export function CouncilButton({ onClick, disabled }: Props) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title="Run this by the council (CA + CPA + CMA + Financial Analyst)"
      style={{
        padding: '6px 12px', borderRadius: 16, border: '1px solid #1a365d',
        background: disabled ? '#e2e8f0' : '#fff', color: disabled ? '#a0aec0' : '#1a365d',
        cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 13,
        opacity: disabled ? 0.7 : 1,
      }}
    >
      🏛️ Run this by the council
    </button>
  );
}
