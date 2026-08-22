"use client";

import {
  ArrowLeft,
  Check,
  Circle,
  ClipboardCheck,
  FileText,
  LockKeyhole,
  MessageCircleMore,
  RefreshCw,
  Send,
} from "lucide-react";
import Link from "next/link";
import {useParams, useRouter} from "next/navigation";
import {useCallback, useEffect, useMemo, useState} from "react";
import {toast} from "sonner";
import {PageHeader} from "@/components/dashboard/page-header";
import {DocumentPanel} from "@/components/documents/document-panel";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {Textarea} from "@/components/ui/field";
import {Loading} from "@/components/ui/loading";
import {LiveWhatsAppDemoLink} from "@/components/whatsapp/live-whatsapp-demo-link";
import {apiFetch} from "@/lib/api";
import {formatDate, formatStatus} from "@/lib/format";
import type {
  AuditEvent,
  DocumentCollectionStatus,
  GSTApplication,
  Reminder,
} from "@/lib/types";
import {
  buildDemoContextHeaders,
  loadPendingWhatsAppDraft,
  loadStoredDemoSession,
  removePendingWhatsAppDraft,
  savePendingWhatsAppDraft,
} from "@/lib/whatsapp-demo";

type Tab = "overview" | "documents" | "validation" | "reconciliation" | "assistant" | "audit";
type DraftKind = "request" | "reminder";

const tabs: Array<[Tab, string]> = [
  ["overview", "Overview"],
  ["documents", "Documents & Extraction"],
  ["validation", "Validation"],
  ["reconciliation", "GSTR-2B Reconciliation"],
  ["assistant", "RAG Assistant"],
  ["audit", "Audit Trail"],
];

const futureStages = ["Extraction Review", "Validation Review", "Reconciliation Review", "Ready for CA Review", "Ready for Filing"];

function unavailable(title: string, description: string) {
  return <Card className="grid min-h-72 place-items-center p-8 text-center">
    <div className="max-w-xl">
      <LockKeyhole className="mx-auto text-[#8a8480]" size={34}/>
      <h2 className="mt-4 text-xl font-bold">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#77716e]">{description}</p>
    </div>
  </Card>;
}

export default function ApplicationWorkspace() {
  const {applicationId} = useParams<{applicationId: string}>();
  const router = useRouter();
  const [application, setApplication] = useState<GSTApplication | null>(null);
  const [collection, setCollection] = useState<DocumentCollectionStatus | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Reminder | null>(null);
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(false);

  const resolveStoredSession = useCallback(() => {
    if (typeof window === "undefined") return null;
    return loadStoredDemoSession(window.sessionStorage, applicationId);
  }, [applicationId]);

  const load = useCallback(async () => {
    const session = typeof window === "undefined"
      ? null
      : loadStoredDemoSession(window.sessionStorage, applicationId);
    const headers = buildDemoContextHeaders(session);
    const [nextApplication, nextCollection, events] = await Promise.all([
      apiFetch<GSTApplication>(`/applications/${applicationId}`),
      apiFetch<DocumentCollectionStatus>(`/applications/${applicationId}/document-collection-status`, {headers}),
      apiFetch<AuditEvent[]>(`/applications/${applicationId}/audit`, {headers}),
    ]);
    setApplication(nextApplication);
    setCollection(nextCollection);
    setAudit(events);
  }, [applicationId]);

  useEffect(() => {
    const initial = window.setTimeout(() => {
      void load()
        .catch(error => toast.error(error instanceof Error ? error.message : "Unable to open workspace"))
        .finally(() => setLoading(false));
    }, 0);
    const timer = window.setInterval(() => void load().catch(() => undefined), 2500);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [load]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const pending = loadPendingWhatsAppDraft(window.sessionStorage, applicationId);
    if (!pending?.prepared) return;
    const timer = window.setTimeout(() => {
      setDraft({
        id: pending.reminderId,
        draft_message: pending.draftMessage,
        reminder_type: pending.reminderType,
        status: "awaiting_approval",
        requires_connection: false,
      });
      setMessage(pending.draftMessage);
      setEditing(false);
      removePendingWhatsAppDraft(window.sessionStorage, applicationId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [applicationId]);

  const collectionStatus = useMemo(() => {
    if (!collection) return "Not Started";
    return {
      not_started: "Not Started",
      documents_requested: "Documents Requested",
      partially_received: "Partially Received",
      documents_complete: "Document Collection Complete",
    }[collection.workflow_status];
  }, [collection]);

  async function createDraft(kind: DraftKind) {
    setBusy(true);
    try {
      const session = resolveStoredSession();
      const path = kind === "request"
        ? `/applications/${applicationId}/document-request/draft`
        : `/applications/${applicationId}/reminders/draft`;
      const result = await apiFetch<Reminder>(path, {
        method: "POST",
        headers: buildDemoContextHeaders(session),
      });
      if (result.reminder_needed === false) {
        toast.success(result.message ?? "All required document categories have been received. No reminder is needed.");
        return;
      }
      const reminderType = result.reminder_type
        ?? (kind === "request" ? "initial_document_request" : "missing_document_reminder");
      if (result.requires_connection) {
        savePendingWhatsAppDraft(window.sessionStorage, applicationId, {
          reminderId: result.id,
          reminderType,
          draftMessage: result.draft_message,
          prepared: false,
        });
        toast.info("Connect or reconnect WhatsApp to review and send this draft");
        router.push(`/dashboard/applications/${applicationId}/whatsapp-demo`);
        return;
      }
      setDraft({...result, reminder_type: reminderType});
      setMessage(result.draft_message);
      setEditing(false);
      toast.success(kind === "request" ? "Document request drafted" : "Reminder drafted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to draft message");
    } finally {
      setBusy(false);
    }
  }

  async function sendDraft() {
    if (!draft) return;
    setBusy(true);
    try {
      const session = resolveStoredSession();
      const initial = draft.reminder_type === "initial_document_request";
      const path = initial
        ? `/applications/${applicationId}/document-request/approve-send`
        : `/reminders/${draft.id}/approve-send`;
      await apiFetch(path, {
        method: "POST",
        headers: buildDemoContextHeaders(session),
        body: JSON.stringify({reminder_id: draft.id, message}),
      });
      toast.success(initial ? "Document request sent through Vonage" : "Reminder sent through Vonage");
      setDraft(null);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Message could not be sent");
    } finally {
      setBusy(false);
    }
  }

  async function cancelDraft() {
    if (!draft) return;
    try {
      await apiFetch(`/reminders/${draft.id}/cancel`, {method: "POST"});
    } catch {
      // The local preview can still be dismissed if its server draft was already cancelled.
    }
    setDraft(null);
  }

  if (loading || !application || !collection) return <Loading label="Opening GST workspace…"/>;

  const requested = collection.workflow_status !== "not_started";
  const complete = collection.workflow_status === "documents_complete";
  const partial = collection.workflow_status === "partially_received";
  const displayApplicationId = collection.effective_application_id;
  const clientName = application.client?.business_name ?? "Client";

  return <>
    <PageHeader
      eyebrow="GST DOCUMENT COLLECTION"
      title={`${clientName} · ${application.period_label}`}
      description={`${application.client?.gstin ?? ""} · Due ${formatDate(application.due_date)} · ${formatStatus(application.filing_frequency)} filing`}
      actions={<>
        <Link href={`/dashboard/clients/${application.client_id}`} className="inline-flex items-center gap-2 rounded-full border border-[#dcd7d2] bg-white px-5 py-3 text-sm font-semibold">
          <ArrowLeft size={17}/>Client
        </Link>
        <LiveWhatsAppDemoLink applicationId={applicationId}/>
        <Button variant="secondary" disabled title="Available after document processing and review">Export pack</Button>
        <Button disabled title="Available after document processing and review">Approve readiness</Button>
      </>}
    />

    <Card className="mb-6 overflow-hidden">
      <div className="grid gap-5 bg-[#a4c5e5] p-5 sm:grid-cols-[1fr_auto] sm:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge value={collection.workflow_status}/>
            <span className="text-xs font-semibold">{collection.received_count} / {collection.required_count} document categories received</span>
          </div>
          <div className="mt-4 h-2 max-w-xl overflow-hidden rounded-full bg-white/60">
            <div className="h-full rounded-full bg-[#191515] transition-all" style={{width: `${collection.progress_percent}%`}}/>
          </div>
        </div>
        <div className="text-right"><strong className="text-3xl">{collection.progress_percent}%</strong><p className="text-xs">collection progress</p></div>
      </div>
      <div className="overflow-x-auto border-t border-[#eeeae6] bg-white p-4">
        <div className="flex min-w-[920px] items-center">
          <Stage label="Documents Requested" completed={requested} current={!requested}/>
          <Stage label="Partially Received" completed={complete} current={partial}/>
          <Stage label="Documents Received" completed={complete} current={complete}/>
          {futureStages.map(label => <Stage key={label} label={label} disabled/>)}
        </div>
      </div>
    </Card>

    <div className="mb-6 flex gap-1 overflow-x-auto rounded-2xl border border-[#e5e2de] bg-white p-1">
      {tabs.map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-semibold transition ${tab === value ? "bg-[#191515] text-white" : "text-[#6b6562] hover:bg-[#f5f3f0]"}`}>{label}</button>)}
    </div>

    {tab === "overview" && <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
      <Card className="p-5">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div><h2 className="font-bold">Document checklist</h2><p className="mt-1 text-xs text-[#77716e]">This live checklist drives requests, reminders, progress, and WhatsApp STATUS.</p></div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => createDraft("request")} disabled={busy || complete}><MessageCircleMore size={16}/>Draft Request</Button>
            <Button variant="secondary" onClick={() => createDraft("reminder")} disabled={busy}><RefreshCw size={16}/>Draft Reminder</Button>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {collection.requirements.map(item => <div key={item.id} className="flex items-center justify-between rounded-2xl border border-[#e5e2de] p-4">
            <div className="flex items-center gap-3">
              <span className={`grid h-8 w-8 place-items-center rounded-full ${item.status === "received" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                {item.status === "received" ? <Check size={15}/> : <FileText size={15}/>}
              </span>
              <strong className="text-sm">{item.label}</strong>
            </div>
            <Badge value={item.status}/>
          </div>)}
        </div>
      </Card>
      <div className="grid content-start gap-6">
        <Card className="p-5">
          <h2 className="font-bold">Document Collection</h2>
          <div className="mt-5 grid grid-cols-2 gap-3">
            {[
              ["Required", collection.required_count],
              ["Received", collection.received_count],
              ["Pending", collection.missing_count],
              ["Progress", `${collection.progress_percent}%`],
            ].map(([label, value]) => <div key={label} className="rounded-2xl bg-[#f8f7f5] p-4"><p className="text-2xl font-bold">{value}</p><p className="mt-1 text-xs text-[#77716e]">{label}</p></div>)}
          </div>
          <div className="mt-4 rounded-2xl border border-[#e5e2de] p-4"><p className="text-xs text-[#77716e]">Current Status</p><p className="mt-2 font-bold">{collectionStatus}</p></div>
        </Card>
        <Card className="p-5">
          <h2 className="font-bold">Phase 2 boundary</h2>
          <ul className="mt-4 grid gap-3 text-sm text-[#625d5a]">
            <li className="flex gap-2"><ClipboardCheck size={17}/> Messages require CA review before sending.</li>
            <li className="flex gap-2"><ClipboardCheck size={17}/> Uploaded originals stay private in Supabase Storage.</li>
            <li className="flex gap-2"><ClipboardCheck size={17}/> Processing and filing readiness remain unavailable.</li>
          </ul>
        </Card>
      </div>
    </div>}

    {tab === "documents" && <DocumentPanel applicationId={displayApplicationId} checklist={collection.requirements} onChanged={load}/>}
    {tab === "validation" && unavailable("Validation unavailable", "Validation becomes available after document processing in a later phase.")}
    {tab === "reconciliation" && unavailable("Reconciliation unavailable", "GSTR-2B reconciliation becomes available after document extraction and validation.")}
    {tab === "assistant" && unavailable("RAG Assistant unavailable for uploaded documents", "Document RAG is intentionally deferred to Phase 4. No uploaded document content is indexed or queried in Phase 2.")}
    {tab === "audit" && <Card className="overflow-hidden">
      <div className="border-b border-[#eeeae6] p-5"><h2 className="font-bold">Audit trail</h2><p className="mt-1 text-xs text-[#77716e]">Real collection, request, upload, reminder, and session events.</p></div>
      <div className="divide-y divide-[#eeeae6]">
        {audit.map(event => <div key={event.id} className="grid gap-3 p-5 sm:grid-cols-[auto_1fr_auto]">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#e8f1fa]"><FileText size={16}/></span>
          <div><p className="text-sm font-semibold">{formatStatus(event.action.replaceAll(".", "_"))}</p><p className="mt-1 text-xs text-[#77716e]">{event.entity_type} · {event.entity_id}</p></div>
          <time className="text-xs text-[#77716e]">{formatDate(event.created_at)}</time>
        </div>)}
        {!audit.length && <div className="p-10 text-center text-sm text-[#77716e]">No audit events yet.</div>}
      </div>
    </Card>}

    {draft && <div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" onClick={() => void cancelDraft()}>
      <Card className="w-full max-w-2xl p-6 shadow-2xl" onClick={event => event.stopPropagation()}>
        <p className="text-xs font-bold tracking-[.13em] text-[#477ca8]">HUMAN APPROVAL REQUIRED</p>
        <h2 className="mt-3 text-2xl font-bold">{draft.reminder_type === "initial_document_request" ? "Document Request Draft" : "Reminder Draft"}</h2>
        <p className="mt-2 text-sm text-[#6b6562]">Review the live checklist message and secure upload link before sending through Vonage.</p>
        {editing
          ? <Textarea className="mt-5 h-64 w-full" value={message} onChange={event => setMessage(event.target.value)}/>
          : <pre className="mt-5 max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl bg-[#f8f7f5] p-4 text-sm leading-6">{message}</pre>}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => void cancelDraft()}>Cancel</Button>
          <Button variant="secondary" onClick={() => setEditing(value => !value)}>{editing ? "Preview" : "Edit"}</Button>
          <Button onClick={sendDraft} disabled={busy}><Send size={16}/>{busy ? "Sending…" : draft.reminder_type === "initial_document_request" ? "Send Request" : "Send Reminder"}</Button>
        </div>
      </Card>
    </div>}
  </>;
}

function Stage({label, completed = false, current = false, disabled = false}: {label: string; completed?: boolean; current?: boolean; disabled?: boolean}) {
  return <div className="flex flex-1 items-center">
    <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border text-xs font-bold ${completed ? "border-[#191515] bg-[#191515] text-white" : current ? "border-[#477ca8] bg-[#e8f1fa] text-[#315d82]" : "border-[#d9d4cf] bg-white text-[#8a8480]"}`}>
      {completed ? <Check size={14}/> : <Circle size={10} fill={current ? "currentColor" : "none"}/>}
    </span>
    <span className={`ml-2 text-[11px] font-semibold ${disabled ? "text-[#aaa4a0]" : "text-[#191515]"}`}>{label}</span>
    <span className="mx-3 h-px flex-1 bg-[#ded9d4]"/>
  </div>;
}
