"use client";

import {ArrowRight, BriefcaseBusiness} from "lucide-react";
import Link from "next/link";
import {useEffect, useMemo, useState} from "react";
import {toast} from "sonner";
import {PageHeader} from "@/components/dashboard/page-header";
import {Badge} from "@/components/ui/badge";
import {Card} from "@/components/ui/card";
import {Loading} from "@/components/ui/loading";
import {apiFetch} from "@/lib/api";
import {formatDate} from "@/lib/format";
import type {Client, GSTApplication} from "@/lib/types";

export default function GSTWorkPage() {
  const [applications, setApplications] = useState<GSTApplication[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([apiFetch<GSTApplication[]>("/applications"), apiFetch<Client[]>("/clients")])
      .then(([nextApplications, nextClients]) => {
        setApplications(nextApplications);
        setClients(nextClients);
      })
      .catch(error => toast.error(error instanceof Error ? error.message : "Unable to load GST work"))
      .finally(() => setLoading(false));
  }, []);

  const clientMap = useMemo(() => Object.fromEntries(clients.map(client => [client.id, client])), [clients]);
  if (loading) return <Loading label="Loading GST work…"/>;

  return <>
    <PageHeader eyebrow="GST WORK" title="Client GST workspaces" description="Continue document collection, review, reconciliation and export for each GST period."/>
    <Card className="overflow-hidden">
      <div className="flex items-center gap-3 border-b border-[var(--obliq-border)] p-5"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-[var(--obliq-blue-soft)] text-[var(--obliq-info-ink)]"><BriefcaseBusiness size={19}/></span><div><h2 className="font-bold">Active applications</h2><p className="text-xs text-[var(--obliq-muted)]">{applications.length} GST workspaces</p></div></div>
      <div className="divide-y divide-[var(--obliq-border)]">{applications.map(application => {
        const client = clientMap[application.client_id];
        return <Link href={`/dashboard/applications/${application.id}`} key={application.id} className="obliq-interactive grid gap-3 p-5 md:grid-cols-[1.2fr_.8fr_.8fr_auto] md:items-center">
          <div><p className="font-semibold">{client?.business_name ?? "Client"}</p><p className="mt-1 text-xs text-[var(--obliq-muted)]">{client?.gstin}</p></div>
          <div><p className="text-sm">{application.period_label}</p><p className="mt-1 text-xs text-[var(--obliq-muted)]">Due {formatDate(application.due_date)}</p></div>
          <div><Badge value={application.display_status ?? application.status}/>{application.workflow_percent != null && <p className="mt-1 text-xs text-[var(--obliq-muted)]">{application.workflow_percent}% workflow</p>}</div><ArrowRight size={17}/>
        </Link>;
      })}{!applications.length && <p className="p-10 text-center text-sm text-[var(--obliq-muted)]">No GST workspaces are available.</p>}</div>
    </Card>
  </>;
}
