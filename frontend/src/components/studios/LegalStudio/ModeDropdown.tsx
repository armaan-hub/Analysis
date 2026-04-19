/**
 * @deprecated Replaced by ModePills component.
 * Kept for backward compatibility with other studios.
 * New code should import from './ModePills' instead.
 */
import { useState } from "react";

export type ChatMode = "normal" | "deep_research" | "analyst";

const OPTIONS: { value: ChatMode; label: string; icon: string }[] = [
  { value: "normal", label: "Normal", icon: "⚡" },
  { value: "deep_research", label: "Deep Research", icon: "🔍" },
  { value: "analyst", label: "Analyst", icon: "📊" },
];

interface Props {
  value: ChatMode;
  onChange: (v: ChatMode) => void;
}

export function ModeDropdown({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const current = OPTIONS.find((o) => o.value === value) ?? OPTIONS[0];
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-800 text-sm text-white hover:bg-slate-700"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{current.icon}</span>
        <span>{current.label}</span>
        <span>▾</span>
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute z-20 mt-1 min-w-[200px] rounded-md bg-slate-900 shadow-lg"
        >
          {OPTIONS.map((o) => (
            <li key={o.value}>
              <button
                type="button"
                onClick={() => {
                  onChange(o.value);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-800 ${
                  o.value === value ? "bg-slate-800" : ""
                }`}
              >
                {o.icon} {o.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
