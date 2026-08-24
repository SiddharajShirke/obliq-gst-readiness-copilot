"use client";

import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  ListChecks,
  Sparkles,
  X,
} from "lucide-react";
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
  const statusLabel = {
    action_required: "Action required",
    in_progress: "In progress",
    ready: "Ready",
    complete: "Complete",
  }[instruction.status];
  return <section aria-label={`Guided Demo step ${instruction.step}`} className="mb-6 overflow-hidden rounded-[24px] border border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] text-[var(--obliq-ink)] shadow-sm">
    <div className="flex items-center gap-3 p-4 sm:px-5">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-2xl bg-[var(--obliq-info-ink)] text-sm font-bold text-[var(--obliq-surface)]">{instruction.step}</span>
      <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-[10px] font-bold tracking-[.14em] text-[var(--obliq-info-ink)]">GUIDED DEMO · STEP {instruction.step} OF 6</p><span className="rounded-full border border-[var(--obliq-info-border)] bg-[var(--obliq-surface)]/70 px-2 py-0.5 text-[10px] font-bold text-[var(--obliq-info-ink)]">{statusLabel}</span></div><h2 className="mt-1 truncate text-lg font-bold">{instruction.title}</h2>{instruction.progress && <p className="mt-1 text-xs font-semibold text-[var(--obliq-info-ink)]">{instruction.progress}</p>}</div>
      <button type="button" className="obliq-focus rounded-full p-2 text-[var(--obliq-muted)] hover:bg-[var(--obliq-interactive-hover)]" onClick={() => setMinimized(value => !value)} aria-label={minimized ? "Expand Guided Demo instructions" : "Minimize Guided Demo instructions"}>{minimized ? <ChevronDown size={18}/> : <ChevronUp size={18}/>}</button>
      {onDismiss && <button type="button" className="obliq-focus rounded-full p-2 text-[var(--obliq-muted)] hover:bg-[var(--obliq-interactive-hover)]" onClick={onDismiss} aria-label="Dismiss Guided Demo instructions"><X size={18}/></button>}
    </div>
    {!minimized && <div className="border-t border-[var(--obliq-info-border)] p-4 sm:px-5 sm:py-5">
      <div className="rounded-2xl border border-[var(--obliq-info-border)] bg-[var(--obliq-surface)]/75 p-4">
        <p className="text-[10px] font-bold tracking-[.12em] text-[var(--obliq-info-ink)]">CURRENT OBJECTIVE</p>
        <p className="mt-2 text-sm font-semibold leading-6 text-[var(--obliq-ink)]">{instruction.objective}</p>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
        <div className="rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)]/75 p-4">
          <div className="flex items-center gap-2 text-xs font-bold text-[var(--obliq-info-ink)]"><ListChecks size={16}/>DO THIS NEXT</div>
          <ol className="mt-3 grid gap-2.5">
            {instruction.tasks.map((task, index) => <li key={task} className="flex gap-3 text-sm leading-6 text-[var(--obliq-muted)]"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[var(--obliq-blue-soft)] text-xs font-bold text-[var(--obliq-info-ink)]">{index + 1}</span><span>{task}</span></li>)}
          </ol>
        </div>
        <div className="grid gap-3">
          <div className="flex gap-2 rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)]/75 p-4 text-xs leading-5 text-[var(--obliq-muted)]"><CircleHelp className="mt-0.5 shrink-0 text-[var(--obliq-info-ink)]" size={16}/><span><strong className="text-[var(--obliq-ink)]">Why this matters: </strong>{instruction.why}</span></div>
          <div className="flex gap-2 rounded-2xl border border-[var(--obliq-success-border)] bg-[var(--obliq-success-soft)] p-4 text-xs leading-5 text-[var(--obliq-success-ink)]"><CheckCircle2 className="mt-0.5 shrink-0" size={16}/><span><strong>COMPLETE WHEN: </strong>{instruction.completeWhen}</span></div>
          <div className="flex gap-2 rounded-2xl border border-[var(--obliq-info-border)] bg-[var(--obliq-surface)]/75 p-4 text-xs leading-5 text-[var(--obliq-muted)]"><ArrowRight className="mt-0.5 shrink-0 text-[var(--obliq-info-ink)]" size={16}/><span><strong className="text-[var(--obliq-ink)]">WHAT HAPPENS NEXT: </strong>{instruction.next}</span></div>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-3 border-t border-[var(--obliq-info-border)] pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2 text-xs leading-5 text-[var(--obliq-muted)]"><Sparkles className="mt-0.5 shrink-0 text-[var(--obliq-info-ink)]" size={15}/><span><strong className="text-[var(--obliq-ink)]">Available anytime:</strong> Use the application-scoped RAG Assistant for grounded questions and Audit Trail for recorded workflow actions.</span></div>
        {(primaryAction || secondaryAction) && <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">{secondaryAction && <Button variant="secondary" onClick={secondaryAction.onClick}>{secondaryAction.label}</Button>}{primaryAction && <Button onClick={primaryAction.onClick} disabled={primaryAction.disabled}>{primaryAction.label ?? instruction.actionLabel}</Button>}</div>}
      </div>
    </div>}
  </section>;
}
