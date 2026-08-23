import {Check, Circle, GitBranch} from "lucide-react";
import type {WorkflowProgress as WorkflowProgressValue, WorkflowStep} from "@/lib/types";

function StepCard({step}: {step: WorkflowStep}) {
  const completed = step.state === "completed";
  const current = step.state === "current";
  return <div aria-current={current ? "step" : undefined} className={`relative rounded-2xl border p-3 transition-all duration-500 motion-reduce:transition-none ${completed ? "border-[var(--obliq-success-border)] bg-[var(--obliq-success-soft)]" : current ? "obliq-progress-current border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)]" : "border-[var(--obliq-border)] bg-[var(--obliq-surface-raised)]"}`}>
    <div className="flex items-center gap-2"><span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border ${completed ? "border-[var(--obliq-success-border)] bg-[var(--obliq-success-ink)] text-[var(--obliq-surface)]" : current ? "border-[var(--obliq-info-border)] bg-[var(--obliq-blue-soft)] text-[var(--obliq-info-ink)]" : "border-[var(--obliq-border)] text-[var(--obliq-muted)]"}`}>{completed ? <Check size={14}/> : <Circle size={10} fill={current ? "currentColor" : "none"}/>}</span><div className="min-w-0"><p className="truncate text-xs font-bold">{step.label}</p><p className="text-[10px] capitalize text-[var(--obliq-muted)]">{step.state}{step.progress_percent > 0 && step.progress_percent < 100 ? ` · ${step.progress_percent}%` : ""}</p></div></div>
  </div>;
}

export function WorkflowProgress({workflow, receivedCount, requiredCount}: {workflow: WorkflowProgressValue; receivedCount: number; requiredCount: number}) {
  const required = workflow.steps.slice(0, 4);
  const reconciliation = workflow.steps.find(step => step.key === "reconciliation_review");
  const readiness = workflow.steps.find(step => step.key === "ready_for_filing");
  return <section aria-label="GST workflow progress" className="mb-6 overflow-hidden rounded-[24px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)]">
    <div className="grid gap-5 bg-[var(--obliq-blue-soft)] p-5 sm:grid-cols-[1fr_auto] sm:items-center">
      <div><div className="flex flex-wrap items-center gap-3"><span className="rounded-full border border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] px-3 py-1 text-xs font-bold text-[var(--obliq-info-ink)]">{workflow.current_stage.replaceAll("_", " ")}</span><span className="text-xs font-semibold text-[var(--obliq-muted)]">{workflow.extraction.reviewed_count}/{workflow.extraction.record_count} records reviewed · {workflow.validation.open_count} validation findings open</span></div><div className="mt-4 h-2 max-w-2xl overflow-hidden rounded-full bg-[var(--obliq-surface)]"><div className="obliq-progress-fill h-full rounded-full bg-[var(--obliq-info-ink)] transition-[width] duration-700 ease-out motion-reduce:transition-none" style={{width: `${workflow.progress_percent}%`}}/></div><p className="mt-2 text-xs font-semibold text-[var(--obliq-muted)]">Document collection: {receivedCount}/{requiredCount}</p></div>
      <div className="sm:text-right"><strong className="text-3xl text-[var(--obliq-ink)]">{workflow.progress_percent}%</strong><p className="text-xs text-[var(--obliq-muted)]">readiness progress</p></div>
    </div>
    <div className="p-4 sm:p-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{required.map(step => <StepCard key={step.key} step={step}/>)}</div>
      <div className="mt-4 rounded-2xl border border-dashed border-[var(--obliq-border)] p-3"><div className="mb-3 flex items-center gap-2 text-xs font-semibold text-[var(--obliq-muted)]"><GitBranch size={15}/>After Validation, both paths are available independently.</div><div className="grid gap-3 sm:grid-cols-2">{reconciliation && <StepCard step={reconciliation}/>} {readiness && <StepCard step={readiness}/>}</div></div>
    </div>
  </section>;
}
