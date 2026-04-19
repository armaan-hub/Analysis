import { useState } from "react";

export type DomainLabel =
  | "vat"
  | "corporate_tax"
  | "peppol"
  | "e_invoicing"
  | "labour"
  | "commercial"
  | "ifrs"
  | "general_law";

const ALL: DomainLabel[] = [
  "vat",
  "corporate_tax",
  "peppol",
  "e_invoicing",
  "labour",
  "commercial",
  "ifrs",
  "general_law",
];

const LABELS: Record<DomainLabel, string> = {
  vat: "VAT",
  corporate_tax: "Corporate Tax",
  peppol: "Peppol",
  e_invoicing: "E-Invoicing",
  labour: "Labour",
  commercial: "Commercial",
  ifrs: "IFRS",
  general_law: "General Law",
};

interface Props {
  value: DomainLabel;
  editable: boolean;
  onChange?: (v: DomainLabel) => void;
}

export function DomainChip({ value, editable, onChange }: Props) {
  const [open, setOpen] = useState(false);
  if (!editable) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-violet-600/30 text-violet-200 text-xs">
        {LABELS[value]}
      </span>
    );
  }
  return (
    <div className="relative inline-block">
      <button
        type="button"
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-600/30 text-violet-200 text-xs hover:bg-violet-600/50"
        onClick={() => setOpen(!open)}
      >
        Domain: {LABELS[value]} ✎
      </button>
      {open && (
        <ul className="absolute z-20 mt-1 rounded-md bg-slate-900 shadow-lg text-xs">
          {ALL.map((d) => (
            <li key={d}>
              <button
                type="button"
                className={`w-full text-left px-3 py-1.5 hover:bg-slate-800 ${
                  d === value ? "bg-slate-800" : ""
                }`}
                onClick={() => {
                  onChange?.(d);
                  setOpen(false);
                }}
              >
                {LABELS[d]}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
