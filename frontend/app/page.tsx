import Link from "next/link";
import { ArrowRight, Bot, Database, FileCheck2, MessageCircleMore, ShieldCheck } from "lucide-react";
import { LandingNavbar } from "@/components/landing/navbar";
import { DashboardPreview } from "@/components/landing/dashboard-preview";
import { AssistantSection, FeatureSections } from "@/components/landing/feature-section";

export default function HomePage() {
  return <main className="overflow-hidden">
    <LandingNavbar />
    <section className="relative min-h-[920px] overflow-hidden bg-[#a4c5e5] pb-24 pt-40 text-center">
      <div className="absolute -left-32 top-28 h-80 w-80 rounded-full bg-white/45 blur-3xl animate-pulse-soft"/><div className="absolute -right-24 top-8 h-96 w-96 rounded-full bg-[#f0e2d5]/65 blur-3xl animate-pulse-soft"/>
      <div className="obliq-container relative">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-xs font-bold tracking-[.09em]"><Bot size={15}/> AI-POWERED GST WORKFLOW FOR INDIAN CA FIRMS</div>
        <h1 className="mx-auto mt-7 max-w-[960px] text-5xl font-bold leading-[.98] tracking-[-.06em] sm:text-7xl lg:text-[88px]">Turn scattered GST documents into a review-ready filing pack.</h1>
        <p className="mx-auto mt-7 max-w-2xl text-base leading-7 text-[#3f3a38] sm:text-lg">Collect documents through WhatsApp, extract invoice data, detect missing records, reconcile GSTR-2B, and prepare every client for CA review from one secure workspace.</p>
        <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row"><Link href="/auth/login?demo=1" className="inline-flex items-center justify-center gap-2 rounded-full bg-[#191515] px-7 py-4 text-sm font-semibold text-white">Open live demo <ArrowRight size={17}/></Link><a href="#workflow" className="rounded-full border border-black/15 bg-white/45 px-7 py-4 text-sm font-semibold">See the workflow</a></div>
        <DashboardPreview />
      </div>
    </section>
    <section className="obliq-container py-24 text-center"><p className="text-xs font-bold tracking-[.16em] text-[#477ca8]">BUILT AROUND ONE REAL OUTCOME</p><h2 className="mx-auto mt-4 max-w-3xl text-4xl font-bold leading-[1.08] tracking-[-.045em] sm:text-6xl">From incomplete client documents to structured GST readiness.</h2><div className="mt-12 grid gap-4 text-left md:grid-cols-4">{[{icon:MessageCircleMore,title:"Collect",text:"WhatsApp requests and secure links"},{icon:Database,title:"Extract",text:"Structured invoice and register data"},{icon:FileCheck2,title:"Reconcile",text:"Rules plus GSTR-2B matching"},{icon:ShieldCheck,title:"Review",text:"CA approval and complete audit history"}].map(({icon:Icon,title,text})=><div key={title} className="rounded-[25px] border border-[#e5e2de] bg-white p-6"><Icon className="text-[#477ca8]"/><h3 className="mt-8 text-xl font-bold">{title}</h3><p className="mt-2 text-sm leading-6 text-[#625d5a]">{text}</p></div>)}</div></section>
    <FeatureSections />
    <AssistantSection />
    <section id="safety" className="obliq-container py-28"><div className="rounded-[36px] bg-[#f0e2d5] p-8 sm:p-14"><div className="grid items-center gap-10 lg:grid-cols-[1.2fr_.8fr]"><div><p className="text-xs font-bold tracking-[.16em]">HUMAN CONTROL BY DESIGN</p><h2 className="mt-4 max-w-3xl text-4xl font-bold tracking-[-.045em] sm:text-6xl">AI prepares the work. The CA makes the decision.</h2><p className="mt-5 max-w-2xl leading-7 text-[#625d5a]">Every outbound reminder and extracted field stays reviewable. OBLIQ does not file returns, pay GST, or decide final ITC eligibility.</p></div><Link href="/auth/login?demo=1" className="inline-flex items-center justify-center gap-2 rounded-full bg-[#191515] px-7 py-4 text-sm font-semibold text-white lg:justify-self-end">Run guided demo <ArrowRight size={17}/></Link></div></div></section>
    <footer className="border-t border-[#e5e2de] bg-white py-8"><div className="obliq-container flex flex-col justify-between gap-4 text-sm text-[#625d5a] sm:flex-row"><strong className="text-[#191515]">OBLIQ GST Readiness Copilot</strong><span>Prototype · Synthetic data only · Professional review required</span></div></footer>
  </main>;
}
