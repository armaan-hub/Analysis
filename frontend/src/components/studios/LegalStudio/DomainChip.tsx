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
      <span className="domain-chip">
        {LABELS[value]}
      </span>
    );
  }
  return (
    <div className="domain-chip-wrapper">
      <button
        type="button"
        className="domain-chip domain-chip--editable"
        onClick={() => setOpen(!open)}
      >
        Domain: {LABELS[value]} ✎
      </button>
      {open && (
        <ul className="domain-chip-dropdown">
          {ALL.map((d) => (
            <li key={d}>
              <button
                type="button"
                data-active={d === value ? "true" : undefined}
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
