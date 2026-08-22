"use client";

import {Info, X} from "lucide-react";
import type {ReactNode} from "react";
import type {RowExplanation} from "../../lib/record-explanations";
import {Card} from "./card";

export type InsightField = {
  label: string;
  value: ReactNode;
  highlight?: boolean;
};

export function RowInsightModal({
  eyebrow,
  explanation,
  fields,
  onClose,
  children,
}: {
  eyebrow: string;
  explanation: RowExplanation;
  fields: InsightField[];
  onClose: () => void;
  children?: ReactNode;
}) {
  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" onClick={onClose}>
    <Card role="dialog" aria-modal="true" aria-label={explanation.title} className="max-h-[88vh] w-full max-w-2xl overflow-auto p-5 shadow-2xl" onClick={event => event.stopPropagation()}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold tracking-[.12em] text-[#477ca8]">{eyebrow}</p>
          <h3 className="mt-2 text-xl font-bold">{explanation.title}</h3>
        </div>
        <button aria-label="Close details" className="obliq-focus rounded-full p-2 hover:bg-[#f3f1ee]" onClick={onClose}><X size={18}/></button>
      </div>
      <div className="mt-4 rounded-2xl border border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] p-4 text-sm leading-6 text-[var(--obliq-info-ink)]">
        <div className="flex gap-2"><Info className="mt-1 shrink-0" size={16}/><p>{explanation.summary}</p></div>
        <p className="mt-2 border-t border-[var(--obliq-info-border)] pt-2 text-xs"><strong>What the CA should review:</strong> {explanation.review}</p>
      </div>
      <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--obliq-border)]">
        <table className="w-full text-left text-sm">
          <tbody className="divide-y divide-[var(--obliq-border)]">
            {fields.map(field => <tr key={field.label} className={field.highlight ? "bg-[var(--obliq-warning-soft)]" : "bg-[var(--obliq-surface)]"}>
              <th className="w-2/5 px-4 py-3 text-xs font-semibold text-[var(--obliq-muted)]">{field.label}</th>
              <td className="px-4 py-3 font-medium text-[var(--obliq-ink)]">{field.value}</td>
            </tr>)}
          </tbody>
        </table>
      </div>
      {children}
    </Card>
  </div>;
}
