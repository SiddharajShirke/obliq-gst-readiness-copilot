"use client";

import {
  AlertTriangle,
  ArrowRight,
  BriefcaseBusiness,
  FileCheck2,
  FileWarning,
  Users,
} from "lucide-react";
import Link from "next/link";
import {useEffect, useMemo, useState} from "react";
import {toast} from "sonner";
import {PageHeader} from "@/components/dashboard/page-header";
import {StatCard} from "@/components/dashboard/stat-card";
import {GuidedDemoLauncher} from "@/components/guided-demo/guided-demo-launcher";
import {Badge} from "@/components/ui/badge";
import {Card} from "@/components/ui/card";
import {Loading} from "@/components/ui/loading";
import {apiFetch} from "@/lib/api";
import {formatDate} from "@/lib/format";
import type {Client, GSTApplication} from "@/lib/types";
import type {GuidedDemoRun} from "@/lib/whatsapp-demo";

type Summary = {
  total_clients: number;
  active_applications: number;
  missing_documents: number;
  needs_review: number;
  ready_for_filing: number;
};

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [apps, setApps] = useState<GSTApplication[]>([]);
  const [runs, setRuns] = useState<GuidedDemoRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<Summary>("/dashboard/summary"),
      apiFetch<Client[]>("/clients"),
      apiFetch<GSTApplication[]>("/applications"),
      apiFetch<GuidedDemoRun[]>("/guided-demo-runs"),
    ]).then(([nextSummary, nextClients, nextApps, nextRuns]) => {
      setSummary(nextSummary);
      setClients(nextClients);
      setApps(nextApps);
      setRuns(nextRuns);
    }).catch(error => toast.error(error.message)).finally(() => setLoading(false));
  }, []);

  const clientMap = useMemo(
    () => Object.fromEntries(clients.map(client => [client.id, client])),
    [clients],
  );
  const guidedClient = useMemo(
    () => clients.find(client => client.demo_scenario === "guided_demo_template"),
    [clients],
  );
  const latestRun = runs[0];

  if (loading || !summary) return <Loading/>;
  return <>
    <PageHeader
      eyebrow="CA OPERATIONS"
      title="GST readiness overview"
      description="One view of client documents, review queues and filing preparation."
      actions={<Link
        href="/dashboard/clients/new"
        className="obliq-focus rounded-full bg-[var(--obliq-action)] px-5 py-3 text-sm font-semibold text-[var(--obliq-action-ink)] transition hover:bg-[var(--obliq-action-hover)]"
      >Add client</Link>}
    />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <StatCard label="Clients" value={summary.total_clients} icon={Users}/>
      <StatCard label="Active periods" value={summary.active_applications} icon={BriefcaseBusiness}/>
      <StatCard label="Missing documents" value={summary.missing_documents} icon={FileWarning}/>
      <StatCard label="Needs review" value={summary.needs_review} icon={AlertTriangle}/>
      <StatCard label="Ready" value={summary.ready_for_filing} icon={FileCheck2}/>
    </div>
    <div className="mt-7 grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--obliq-border)] p-5">
          <div><h2 className="text-lg font-bold">Active GST applications</h2><p className="mt-1 text-xs text-[var(--obliq-muted)]">Open a client workspace to continue the workflow.</p></div>
          <Link href="/dashboard/clients" className="text-sm font-semibold">All clients</Link>
        </div>
        <div className="divide-y divide-[var(--obliq-border)]">
          {apps.map(app => {
            const client = clientMap[app.client_id];
            return <Link href={`/dashboard/applications/${app.id}`} key={app.id} className="obliq-interactive grid gap-3 p-5 transition md:grid-cols-[1.2fr_.8fr_.8fr_auto] md:items-center">
              <div><p className="font-semibold">{client?.business_name || "Client"}</p><p className="mt-1 text-xs text-[var(--obliq-muted)]">{client?.gstin}</p></div>
              <div className="text-sm"><p>{app.period_label}</p><p className="mt-1 text-xs text-[var(--obliq-muted)]">Due {formatDate(app.due_date)}</p></div>
              <Badge value={app.display_status ?? app.status}/><ArrowRight size={17}/>
            </Link>;
          })}
        </div>
      </Card>
      <div className="grid gap-6">
        <Card className="border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] p-6">
          <div className="flex items-center justify-between gap-3"><p className="text-xs font-bold tracking-[.13em] text-[var(--obliq-info-ink)]">GUIDED DEMO</p>{latestRun && <Badge value={latestRun.status}/>}</div>
          <h2 className="mt-3 text-2xl font-bold tracking-[-.04em]">{latestRun?.name ?? "Experience OBLIQ end to end."}</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--obliq-muted)]">{latestRun?.status === "completed" ? "Completed workflow retained. Open the demo client or start another isolated run." : "Use the real Phase 1–4 workflow from request through export."}</p>
          <div className="mt-6 flex flex-wrap gap-2">
            {latestRun?.status === "completed" && guidedClient && <Link href={`/dashboard/clients/${guidedClient.id}`} className="obliq-focus inline-flex items-center gap-2 rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-5 py-3 text-sm font-semibold">Open Client Profile<ArrowRight size={16}/></Link>}
            {latestRun?.status === "active"
              ? <Link href={`/dashboard/applications/${latestRun.base_application_id}?guided=1`} className="obliq-focus inline-flex items-center gap-2 rounded-full bg-[var(--obliq-action)] px-5 py-3 text-sm font-semibold text-[var(--obliq-action-ink)]">Continue {latestRun.name}<ArrowRight size={16}/></Link>
              : <GuidedDemoLauncher label={latestRun?.status === "completed" ? "Restart" : "Guided Demo"}/>}
          </div>
        </Card>
        <Card className="p-6"><h2 className="font-bold">CA-controlled preparation</h2><ul className="mt-4 grid gap-3 text-sm leading-6 text-[var(--obliq-muted)]"><li>• OBLIQ prepares; it does not file a GST return.</li><li>• AI-extracted values stay subject to CA review.</li><li>• Reconciliation flags support professional review.</li></ul></Card>
      </div>
    </div>
  </>;
}
