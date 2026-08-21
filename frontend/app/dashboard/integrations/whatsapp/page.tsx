"use client";

import {useEffect, useState} from "react";
import {toast} from "sonner";
import {PageHeader} from "@/components/dashboard/page-header";
import {Loading} from "@/components/ui/loading";
import {WhatsAppRuntimeStatus, type WhatsAppRuntimeStatusValue} from "@/components/whatsapp/whatsapp-runtime-status";
import {apiFetch} from "@/lib/api";

export default function WhatsAppIntegrationPage() {
  const [status, setStatus] = useState<WhatsAppRuntimeStatusValue | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<WhatsAppRuntimeStatusValue>("/integrations/whatsapp/status")
      .then(setStatus)
      .catch(cause => setError(cause instanceof Error ? cause.message : "Unable to load status"));
  }, []);

  async function copy(value: string) {
    await navigator.clipboard.writeText(value);
    toast.success("Webhook URL copied");
  }

  return <>
    <PageHeader eyebrow="EXTERNAL INTEGRATION" title="Vonage WhatsApp Sandbox" description="Single-judge runtime status for real WhatsApp text delivery. Server secrets remain in the backend environment."/>
    {error && <div className="rounded-2xl bg-red-50 p-5 text-sm text-red-800">{error}</div>}
    {!status && !error && <Loading label="Loading Vonage runtime status…"/>}
    {status && <WhatsAppRuntimeStatus status={status} onCopy={copy}/>}
  </>;
}
