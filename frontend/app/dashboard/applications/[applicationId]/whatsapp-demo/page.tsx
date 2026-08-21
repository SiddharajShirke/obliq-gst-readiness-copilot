"use client";

import Link from "next/link";
import {useParams} from "next/navigation";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {ArrowLeft} from "lucide-react";
import {toast} from "sonner";
import {PageHeader} from "@/components/dashboard/page-header";
import {Loading} from "@/components/ui/loading";
import {WhatsAppDemoView} from "@/components/whatsapp/whatsapp-demo-view";
import {apiFetch} from "@/lib/api";
import {
  buildDemoAccessHeaders,
  isMissingDemoSessionError,
  loadStoredDemoSession,
  removeStoredDemoSession,
  saveStoredDemoSession,
  type StoredDemoSession,
  type WhatsAppDemoCreated,
  type WhatsAppDemoStatus,
} from "@/lib/whatsapp-demo";

export default function WhatsAppDemoPage() {
  const {applicationId} = useParams<{applicationId: string}>();
  const initialized = useRef(false);
  const [stored, setStored] = useState<StoredDemoSession | null>(null);
  const [created, setCreated] = useState<WhatsAppDemoCreated | null>(null);
  const [sessionStatus, setSessionStatus] = useState<WhatsAppDemoStatus | null>(null);
  const [now, setNow] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async (session: StoredDemoSession) => {
    const value = await apiFetch<WhatsAppDemoStatus>(
      `/whatsapp-demo-sessions/${session.sessionId}`,
      {headers: buildDemoAccessHeaders(session.dashboardAccessToken)},
    );
    setSessionStatus(value);
  }, []);

  useEffect(() => {
    if (initialized.current || typeof window === "undefined") return;
    initialized.current = true;
    const existing = loadStoredDemoSession(window.sessionStorage, applicationId);
    const start = async () => {
      if (existing?.created) {
        setStored(existing);
        setCreated(existing.created);
        try {
          await poll(existing);
          return;
        } catch (cause) {
          if (!isMissingDemoSessionError(cause)) throw cause;
          removeStoredDemoSession(window.sessionStorage, applicationId);
          setStored(null);
          setCreated(null);
          setSessionStatus(null);
        }
      }
      const response = await apiFetch<WhatsAppDemoCreated>(
        `/applications/${applicationId}/whatsapp-demo-sessions`,
        {method: "POST"},
      );
      const next = {
        sessionId: response.session_id,
        dashboardAccessToken: response.dashboard_access_token,
        created: response,
      };
      saveStoredDemoSession(window.sessionStorage, applicationId, next);
      setStored(next);
      setCreated(response);
      await poll(next);
    };
    start().catch(cause => setError(cause instanceof Error ? cause.message : "Unable to create session"));
  }, [applicationId, poll]);

  useEffect(() => {
    if (!stored) return;
    const timer = window.setInterval(() => poll(stored).catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [poll, stored]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const countdown = useMemo(() => {
    if (!created || now === null) return "--:--";
    const seconds = Math.max(0, Math.floor((new Date(created.token_expires_at).getTime() - now) / 1000));
    return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }, [created, now]);

  async function regenerate() {
    if (!stored || !created) return;
    setBusy(true);
    try {
      const regenerated = await apiFetch<Pick<WhatsAppDemoCreated, "start_message" | "start_whatsapp_url" | "token_expires_at">>(
        `/whatsapp-demo-sessions/${stored.sessionId}/regenerate-start-token`,
        {method: "POST", headers: buildDemoAccessHeaders(stored.dashboardAccessToken)},
      );
      const nextCreated = {...created, ...regenerated};
      const nextStored = {...stored, created: nextCreated};
      saveStoredDemoSession(window.sessionStorage, applicationId, nextStored);
      setStored(nextStored);
      setCreated(nextCreated);
      toast.success("START token regenerated");
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "Unable to regenerate token");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!stored) return;
    setBusy(true);
    try {
      await apiFetch(`/whatsapp-demo-sessions/${stored.sessionId}/cancel`, {
        method: "POST",
        headers: buildDemoAccessHeaders(stored.dashboardAccessToken),
      });
      await poll(stored);
      toast.success("Temporary session cancelled");
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "Unable to cancel session");
    } finally {
      setBusy(false);
    }
  }

  async function copy(value: string) {
    await navigator.clipboard.writeText(value);
    toast.success("Copied to clipboard");
  }

  if (error) return <div className="rounded-2xl bg-red-50 p-6 text-sm text-red-800">{error}</div>;
  if (!created) return <Loading label="Creating isolated WhatsApp session…"/>;
  return <>
    <PageHeader
      eyebrow="VONAGE SANDBOX"
      title={`Live WhatsApp Demo — ${created.base_client_name}`}
      description={`GST Period: ${created.gst_period}`}
      actions={<Link href={`/dashboard/applications/${applicationId}`} className="inline-flex items-center gap-2 rounded-full border border-[#dcd7d2] bg-white px-5 py-3 text-sm font-semibold"><ArrowLeft size={17}/>GST workspace</Link>}
    />
    <WhatsAppDemoView created={created} status={sessionStatus} countdown={countdown} busy={busy} onCopy={copy} onRegenerate={regenerate} onCancel={cancel}/>
  </>;
}
