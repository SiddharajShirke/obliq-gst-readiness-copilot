"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, BriefcaseBusiness, FileCheck2, FileWarning, RotateCcw, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/dashboard/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loading } from "@/components/ui/loading";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Client, GSTApplication } from "@/lib/types";

type Summary={total_clients:number;active_applications:number;missing_documents:number;needs_review:number;ready_for_filing:number};

export default function DashboardPage(){
  const [summary,setSummary]=useState<Summary|null>(null); const [clients,setClients]=useState<Client[]>([]); const [apps,setApps]=useState<GSTApplication[]>([]); const [loading,setLoading]=useState(true); const [resetting,setResetting]=useState(false);
  useEffect(()=>{Promise.all([apiFetch<Summary>("/dashboard/summary"),apiFetch<Client[]>("/clients"),apiFetch<GSTApplication[]>("/applications")]).then(([s,c,a])=>{setSummary(s);setClients(c);setApps(a)}).catch(e=>toast.error(e.message)).finally(()=>setLoading(false))},[]);
  const clientMap=useMemo(()=>Object.fromEntries(clients.map(c=>[c.id,c])),[clients]);
  async function resetDemo(){
    setResetting(true);
    try{
      await apiFetch<{status:string}>("/demo/reset",{method:"POST"});
      toast.success("Demo data restored");
      window.location.reload();
    }catch(error){toast.error(error instanceof Error?error.message:"Unable to reset demo");setResetting(false)}
  }
  if(loading||!summary)return <Loading/>;
  return <>
    <PageHeader eyebrow="CA OPERATIONS" title="GST readiness overview" description="One view of client documents, AI review queues and applications approaching filing readiness." actions={<><Button type="button" variant="secondary" onClick={resetDemo} disabled={resetting}><RotateCcw size={16}/>{resetting?"Resetting…":"Reset demo"}</Button><Link href="/dashboard/clients/new" className="rounded-full bg-[#191515] px-5 py-3 text-sm font-semibold text-white">Add client</Link></>}/>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><StatCard label="Clients" value={summary.total_clients} icon={Users}/><StatCard label="Active periods" value={summary.active_applications} icon={BriefcaseBusiness}/><StatCard label="Missing documents" value={summary.missing_documents} icon={FileWarning}/><StatCard label="Needs review" value={summary.needs_review} icon={AlertTriangle}/><StatCard label="Ready" value={summary.ready_for_filing} icon={FileCheck2}/></div>
    <div className="mt-7 grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
      <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-[#eeeae6] p-5"><div><h2 className="text-lg font-bold">Active GST applications</h2><p className="mt-1 text-xs text-[#77716e]">Open a client workspace to continue the workflow.</p></div><Link href="/dashboard/clients" className="text-sm font-semibold">All clients</Link></div><div className="divide-y divide-[#eeeae6]">{apps.map(app=>{const client=clientMap[app.client_id];return <Link href={`/dashboard/applications/${app.id}`} key={app.id} className="grid gap-3 p-5 transition hover:bg-[#faf9f7] md:grid-cols-[1.2fr_.8fr_.8fr_auto] md:items-center"><div><p className="font-semibold">{client?.business_name||"Client"}</p><p className="mt-1 text-xs text-[#77716e]">{client?.gstin}</p></div><div className="text-sm"><p>{app.period_label}</p><p className="mt-1 text-xs text-[#77716e]">Due {formatDate(app.due_date)}</p></div><Badge value={app.status}/><ArrowRight size={17}/></Link>})}</div></Card>
      <div className="grid gap-6"><Card className="bg-[#a4c5e5] p-6"><p className="text-xs font-bold tracking-[.13em]">GUIDED DEMO</p><h2 className="mt-3 text-2xl font-bold tracking-[-.04em]">Run the complete Raj Traders flow.</h2><p className="mt-3 text-sm leading-6 text-[#403b38]">Approve a document request, act as the client in the mock WhatsApp tab, upload the missing purchase register, and generate readiness.</p><Link href="/dashboard/applications/30000000-0000-0000-0000-000000000001" className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#191515] px-5 py-3 text-sm font-semibold text-white">Start walkthrough <ArrowRight size={16}/></Link></Card>
      <Card className="p-6"><h2 className="font-bold">Prototype boundaries</h2><ul className="mt-4 grid gap-3 text-sm leading-6 text-[#625d5a]"><li>• Does not file a real GST return.</li><li>• AI extraction always needs CA review.</li><li>• ITC differences are review flags, not legal decisions.</li></ul></Card></div>
    </div>
  </>;
}
