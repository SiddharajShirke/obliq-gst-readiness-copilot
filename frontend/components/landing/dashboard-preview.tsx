import {Check, FileCheck2, MessageCircleMore, ShieldCheck, Sparkles} from "lucide-react";

const stages = ["Request", "Collect", "Extract", "Validate", "Reconcile", "Export"];

export function DashboardPreview() {
  return <div className="landing-reveal landing-delay-4 relative mx-auto mt-12 max-w-[1040px] rounded-[28px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)]/75 p-2 shadow-[var(--obliq-shadow)] backdrop-blur-xl sm:mt-16 sm:rounded-[36px] sm:p-3">
    <div className="overflow-hidden rounded-[27px] border border-[var(--obliq-border)] bg-[var(--obliq-canvas)] text-left">
      <div className="flex items-center justify-between border-b border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-5 py-4">
        <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-[var(--obliq-action)]"/><span className="text-sm font-black tracking-[-.05em]">OBLIQ</span></div>
        <div className="flex items-center gap-2 rounded-full bg-[var(--obliq-blue-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--obliq-info-ink)]"><Sparkles size={14}/> CA-controlled AI</div>
      </div>
      <div className="grid gap-4 p-4 sm:grid-cols-3 sm:p-6">
        {[
          {label: "Secure intake", text: "WhatsApp request + private upload", icon: MessageCircleMore},
          {label: "Structured review", text: "Extracted GST data with CA approval", icon: ShieldCheck},
          {label: "Prepared working", text: "Validation, reconciliation and exports", icon: FileCheck2},
        ].map(({label, text, icon: Icon}) => <div key={label} className="rounded-[19px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4"><Icon size={18} className="text-[var(--obliq-info-ink)]"/><div className="mt-6 font-bold">{label}</div><div className="mt-1 text-xs leading-5 text-[var(--obliq-muted)]">{text}</div></div>)}
      </div>
      <div className="mx-4 mb-4 rounded-[22px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-5 sm:mx-6 sm:mb-6">
        <p className="text-xs font-bold tracking-[.12em] text-[var(--obliq-muted)]">GST READINESS WORKFLOW</p>
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {stages.map((stage, index) => <div key={stage} className="rounded-2xl bg-[var(--obliq-surface-raised)] p-3 text-center"><span className="mx-auto grid h-7 w-7 place-items-center rounded-full bg-[var(--obliq-blue-soft)] text-[var(--obliq-info-ink)]">{index < 3 ? <Check size={14}/> : index + 1}</span><p className="mt-2 text-xs font-semibold">{stage}</p></div>)}
        </div>
      </div>
    </div>
  </div>;
}
