"use client";

import Link from "next/link";
import {useParams, useRouter} from "next/navigation";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {ArrowLeft} from "lucide-react";
import {toast} from "sonner";
import {PageHeader} from "@/components/dashboard/page-header";
import {GuidedDemoStep} from "@/components/guided-demo/guided-demo-step";
import {Loading} from "@/components/ui/loading";
import {WhatsAppDemoView} from "@/components/whatsapp/whatsapp-demo-view";
import {apiFetch} from "@/lib/api";
import {
  buildDemoAccessHeaders,
  buildDemoContextHeaders,
  isMissingDemoSessionError,
  loadGuidedDemoState,
  loadPendingWhatsAppDraft,
  loadStoredDemoSession,
  removeStoredDemoSession,
  resolveWhatsAppGuidedDemoStep,
  saveStoredDemoSession,
  savePendingWhatsAppDraft,
  type StoredDemoSession,
  type WhatsAppDemoCreated,
  type WhatsAppDemoStatus,
} from "@/lib/whatsapp-demo";

export default function WhatsAppDemoPage() {
  const {applicationId} = useParams<{applicationId: string}>();
  const router = useRouter();
  const initialized = useRef(false);
  const preparingDraft = useRef(false);
  const [stored, setStored] = useState<StoredDemoSession | null>(null);
  const [created, setCreated] = useState<WhatsAppDemoCreated | null>(null);
  const [sessionStatus, setSessionStatus] = useState<WhatsAppDemoStatus | null>(null);
  const [now, setNow] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guidedActive, setGuidedActive] = useState(false);

  const poll = useCallback(async (session: StoredDemoSession) => {
    const value = await apiFetch<WhatsAppDemoStatus>(
      `/whatsapp-demo-sessions/${session.sessionId}`,
      {headers: buildDemoAccessHeaders(session.dashboardAccessToken)},
    );
    setSessionStatus(value);
  }, []);

  const createSession = useCallback(async () => {
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
    return next;
  }, [applicationId, poll]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const timer = window.setTimeout(() => {
      const guided = loadGuidedDemoState(window.sessionStorage, applicationId);
      setGuidedActive(guided?.active === true && guided.completed === false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [applicationId]);

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
      await createSession();
    };
    start().catch(cause => setError(cause instanceof Error ? cause.message : "Unable to create session"));
  }, [applicationId, createSession, poll]);

  useEffect(() => {
    if (!stored) return;
    const timer = window.setInterval(() => poll(stored).catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [poll, stored]);

  useEffect(() => {
    if (
      !stored
      || sessionStatus?.status !== "active"
      || preparingDraft.current
      || typeof window === "undefined"
    ) return;
    const pending = loadPendingWhatsAppDraft(window.sessionStorage, applicationId);
    if (!pending || pending.prepared) return;
    preparingDraft.current = true;
    apiFetch<{
      draft_message: string;
      reminder_needed: boolean;
      message?: string;
    }>(`/reminders/${pending.reminderId}/prepare`, {
      method: "POST",
      headers: buildDemoContextHeaders(stored),
    }).then(prepared => {
      if (!prepared.reminder_needed) {
        window.sessionStorage.removeItem(`obliq_whatsapp_pending_draft:${applicationId}`);
        toast.success(prepared.message ?? "No reminder is needed");
      } else {
        savePendingWhatsAppDraft(window.sessionStorage, applicationId, {
          ...pending,
          draftMessage: prepared.draft_message,
          prepared: true,
        });
      }
      router.push(`/dashboard/applications/${applicationId}`);
    }).catch(cause => {
      preparingDraft.current = false;
      toast.error(cause instanceof Error ? cause.message : "Unable to prepare request");
    });
  }, [applicationId, router, sessionStatus?.status, stored]);

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

  async function reconnect() {
    if (!stored || !created) return;
    setBusy(true);
    try {
      const regenerated = await apiFetch<Pick<
        WhatsAppDemoCreated,
        "session_id" | "status" | "start_message" | "start_whatsapp_url" | "token_expires_at" | "session_expires_at"
      >>(`/whatsapp-demo-sessions/${stored.sessionId}/reconnect`, {
        method: "POST",
        headers: buildDemoAccessHeaders(stored.dashboardAccessToken),
      });
      const nextCreated = {...created, ...regenerated};
      const nextStored = {...stored, created: nextCreated};
      saveStoredDemoSession(window.sessionStorage, applicationId, nextStored);
      setStored(nextStored);
      setCreated(nextCreated);
      setSessionStatus(null);
      await poll(nextStored);
      toast.success("New single-use START token generated for the retained session");
    } catch (cause) {
      if (isMissingDemoSessionError(cause)) {
        removeStoredDemoSession(window.sessionStorage, applicationId);
        setStored(null);
        setCreated(null);
        setSessionStatus(null);
        await createSession();
        toast.success("Retained data was unavailable, so a new isolated session was created");
      } else {
        toast.error(cause instanceof Error ? cause.message : "Unable to reconnect WhatsApp");
      }
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
      actions={<Link href={`/dashboard/applications/${applicationId}`} className="obliq-focus inline-flex items-center gap-2 rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-5 py-3 text-sm font-semibold"><ArrowLeft size={17}/>GST workspace</Link>}
    />
    {guidedActive && <GuidedDemoStep instruction={resolveWhatsAppGuidedDemoStep(sessionStatus?.status ?? created.status)} />}
    <WhatsAppDemoView created={created} status={sessionStatus} countdown={countdown} busy={busy} onCopy={copy} onRegenerate={regenerate} onCancel={cancel} onReconnect={reconnect}/>
  </>;
}
