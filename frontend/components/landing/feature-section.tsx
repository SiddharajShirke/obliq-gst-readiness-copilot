import {Archive, Bot, FileSearch, MessageSquareText, ScanText, ShieldCheck} from "lucide-react";

const items = [
  {icon: MessageSquareText, title: "Secure Collection", text: "Request GST documents through WhatsApp and private upload links."},
  {icon: ScanText, title: "AI Extraction", text: "Turn supported uploads into structured, reviewable GST records."},
  {icon: ShieldCheck, title: "CA Validation", text: "Review every important finding before readiness advances."},
  {icon: FileSearch, title: "GSTR-2B Reconciliation", text: "Compare books and GSTR-2B with exact deterministic evidence."},
  {icon: Bot, title: "RAG Assistant", text: "Ask grounded questions inside the current GST application."},
  {icon: Archive, title: "Export Pack", text: "Download structured CA working after validation is complete."},
];

export function FeatureSections() {
  return <section id="capabilities" className="obliq-container py-24">
    <div className="mx-auto max-w-2xl text-center"><p className="text-xs font-bold tracking-[.16em] text-[var(--obliq-info-ink)]">CURRENT CAPABILITIES</p><h2 className="mt-4 text-4xl font-bold tracking-[-.045em] sm:text-5xl">One controlled GST workspace.</h2></div>
    <div className="mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{items.map(({icon: Icon, title, text}, index) => <article key={title} className="landing-reveal group rounded-[26px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-6 transition duration-300 hover:-translate-y-1 hover:border-[var(--obliq-blue-strong)] hover:shadow-[var(--obliq-shadow)]" style={{animationDelay: `${index * 80}ms`}}><span className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--obliq-blue-soft)] text-[var(--obliq-info-ink)] transition duration-300 group-hover:scale-110"><Icon size={20}/></span><h3 className="mt-8 text-xl font-bold">{title}</h3><p className="mt-2 text-sm leading-6 text-[var(--obliq-muted)]">{text}</p></article>)}</div>
  </section>;
}

export function AssistantSection() {
  return <section className="bg-[var(--obliq-action)] py-20 text-[var(--obliq-action-ink)]"><div className="obliq-container flex flex-col justify-between gap-8 lg:flex-row lg:items-center"><div><p className="text-xs font-bold tracking-[.16em] opacity-70">APPLICATION-SCOPED ASSISTANCE</p><h2 className="mt-4 max-w-3xl text-4xl font-bold tracking-[-.045em] sm:text-5xl">Grounded answers. Visible sources.</h2></div><div className="max-w-md rounded-[24px] border border-white/15 bg-white/8 p-5"><p className="text-sm leading-6 opacity-85">Structured facts, extracted evidence, reconciliation findings and raised alerts stay scoped to the current client case.</p></div></div></section>;
}
