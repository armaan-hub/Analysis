import { useState, useEffect, useRef } from "react";

export type DomainLabel =
  | "legal"
  | "tax"
  | "accounting"
  | "audit"
  | "finance"
  | "general";

const ALL_DOMAINS: { key: DomainLabel; icon: string; label: string }[] = [
  { key: "legal",      icon: "⚖️",  label: "Legal" },
  { key: "tax",        icon: "📋", label: "Tax" },
  { key: "accounting", icon: "📊", label: "Accounting" },
  { key: "audit",      icon: "🔍", label: "Audit" },
  { key: "finance",    icon: "💰", label: "Finance" },
  { key: "general",    icon: "💬", label: "General" },
];

const DOMAIN_MAP = Object.fromEntries(
  ALL_DOMAINS.map((d) => [d.key, d])
) as Record<DomainLabel, (typeof ALL_DOMAINS)[number]>;

interface Props {
  domain: string;
  domainLocked?: boolean;
  onDomainChange?: (newDomain: string, isManual: boolean) => void;
}

export function DomainChip({ domain, domainLocked, onDomainChange }: Props) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const current = DOMAIN_MAP[domain as DomainLabel] ?? ALL_DOMAINS[ALL_DOMAINS.length - 1];

  const chipStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 12px",
    borderRadius: "var(--s-r-sm)",
    border: "1px solid var(--s-border)",
    background: "rgba(255,255,255,0.06)",
    color: "var(--s-text-1)",
    fontSize: 13,
    cursor: "pointer",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    userSelect: "none",
    transition: "border-color 0.2s",
  };

  const dropdownStyle: React.CSSProperties = {
    position: "absolute",
    top: "calc(100% + 6px)",
    left: 0,
    minWidth: 180,
    padding: "6px 0",
    borderRadius: "var(--s-r-sm)",
    border: "1px solid var(--s-border)",
    background: "rgba(20, 20, 30, 0.85)",
    backdropFilter: "blur(18px)",
    WebkitBackdropFilter: "blur(18px)",
    boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
    listStyle: "none",
    margin: 0,
    zIndex: 200,
  };

  const optionStyle = (active: boolean): React.CSSProperties => ({
    display: "flex",
    alignItems: "center",
    gap: 8,
    width: "100%",
    padding: "7px 14px",
    background: active ? "rgba(var(--s-accent-rgb, 99,102,241), 0.18)" : "transparent",
    color: active ? "var(--s-accent)" : "var(--s-text-2)",
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    textAlign: "left" as const,
    borderRadius: 0,
    transition: "background 0.15s",
  });

  return (
    <div ref={wrapperRef} style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        style={chipStyle}
        onClick={() => setOpen((v) => !v)}
        title={domainLocked ? "Domain locked (manual override)" : "Click to change domain"}
      >
        <span>{current.icon}</span>
        <span>{current.label}</span>
        {domainLocked && <span style={{ fontSize: 11, marginLeft: 2 }}>🔒</span>}
        {!domainLocked && <span style={{ fontSize: 11, opacity: 0.5, marginLeft: 2 }}>▾</span>}
      </button>

      {open && (
        <ul style={dropdownStyle}>
          {ALL_DOMAINS.map((d) => (
            <li key={d.key}>
              <button
                type="button"
                style={optionStyle(d.key === domain)}
                onMouseEnter={(e) => {
                  if (d.key !== domain) e.currentTarget.style.background = "rgba(255,255,255,0.07)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = d.key === domain
                    ? "rgba(var(--s-accent-rgb, 99,102,241), 0.18)"
                    : "transparent";
                }}
                onClick={() => {
                  onDomainChange?.(d.key, true);
                  setOpen(false);
                }}
              >
                <span>{d.icon}</span>
                <span>{d.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
