"use client";

import {ChevronDown, ChevronUp, CircleHelp, X} from "lucide-react";
import {useState} from "react";
import {Button} from "@/components/ui/button";
import type {GuidedDemoInstruction} from "@/lib/whatsapp-demo";

export function GuidedDemoStep({instruction, primaryAction, secondaryAction, onDismiss}: {
  instruction: GuidedDemoInstruction;
  primaryAction?: {label?: string; onClick: () => void; disabled?: boolean};
  secondaryAction?: {label: string; onClick: () => void};
  onDismiss?: () => void;
}) {
  const [minimized, setMinimized] = useState(false);
  return <section aria-label={`Guided Demo step ${instruction.step}`} className="mb-6 overflow-hidden rounded-[24px] border border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] text-[var(--obliq-ink)] shadow-sm">
    <div className="flex items-center gap-3 p-4 sm:px-5">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-2xl bg-[var(--obliq-info-ink)] text-sm font-bold text-[var(--obliq-surface)]">{instruction.step}</span>
      <div className="min-w-0 flex-1"><p className="text-[10px] font-bold tracking-[.14em] text-[var(--obliq-info-ink)]">GUIDED DEMO · STEP {instruction.step} OF 6</p><h2 className="mt-1 truncate text-lg font-bold">{instruction.title}</h2></div>
      <button type="button" className="obliq-focus rounded-full p-2 text-[var(--obliq-muted)] hover:bg-[var(--obliq-interactive-hover)]" onClick={() => setMinimized(value => !value)} aria-label={minimized ? "Expand Guided Demo instructions" : "Minimize Guided Demo instructions"}>{minimized ? <ChevronDown size={18}/> : <ChevronUp size={18}/>}</button>
      {onDismiss && <button type="button" className="obliq-focus rounded-full p-2 text-[var(--obliq-muted)] hover:bg-[var(--obliq-interactive-hover)]" onClick={onDismiss} aria-label="Dismiss Guided Demo instructions"><X size={18}/></button>}
    </div>
    {!minimized && <div className="grid gap-4 border-t border-[var(--obliq-info-border)] p-4 sm:grid-cols-[1fr_.8fr_auto] sm:items-center sm:px-5">
      <div><p className="text-xs font-bold text-[var(--obliq-info-ink)]">DO THIS</p><p className="mt-1 text-sm leading-6 text-[var(--obliq-muted)]">{instruction.explanation}</p></div>
      <div className="flex gap-2 rounded-2xl bg-[var(--obliq-surface)]/60 p-3 text-xs leading-5 text-[var(--obliq-muted)]"><CircleHelp className="mt-0.5 shrink-0 text-[var(--obliq-info-ink)]" size={16}/><span><strong className="text-[var(--obliq-ink)]">Why: </strong>{instruction.why}</span></div>
      {(primaryAction || secondaryAction) && <div className="flex flex-wrap gap-2 sm:justify-end">{secondaryAction && <Button variant="secondary" onClick={secondaryAction.onClick}>{secondaryAction.label}</Button>}{primaryAction && <Button onClick={primaryAction.onClick} disabled={primaryAction.disabled}>{primaryAction.label ?? instruction.actionLabel}</Button>}</div>}
    </div>}
  </section>;
}
