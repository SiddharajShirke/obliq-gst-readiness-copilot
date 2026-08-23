"use client";

import {
  ArrowLeft,
  Check,
  ClipboardCheck,
  Download,
  FileText,
  MessageCircleMore,
  RefreshCw,
  Send,
} from "lucide-react";
import Link from "next/link";
import {useParams, useRouter} from "next/navigation";
import {useCallback, useEffect, useMemo, useState} from "react";
import {toast} from "sonner";
import {AuditTrailPanel} from "@/components/audit/audit-trail-panel";
import {RagAssistantDrawer} from "@/components/assistant/assistant-panel";
import {PageHeader} from "@/components/dashboard/page-header";
import {DocumentPanel} from "@/components/documents/document-panel";
import {FindingsPanel} from "@/components/documents/findings-panel";
import {GuidedDemoStep} from "@/components/guided-demo/guided-demo-step";
import {ReconciliationPanel} from "@/components/reconciliation/reconciliation-panel";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {Textarea} from "@/components/ui/field";
import {Loading} from "@/components/ui/loading";
import {Modal} from "@/components/ui/modal";
import {WorkflowProgress} from "@/components/workflow/workflow-progress";
import {apiFetch, preferredExportUrls} from "@/lib/api";
import {formatDate, formatStatus} from "@/lib/format";
import type {
  AuditEvent,
  DocumentCollectionStatus,
  GSTApplication,
  Reminder,
} from "@/lib/types";
import {
  buildDemoContextHeaders,
  completeGuidedDemo,
  loadGuidedDemoState,
  loadPendingWhatsAppDraft,
  loadStoredDemoSession,
  removePendingWhatsAppDraft,
  resolveGuidedDemoStep,
  savePendingWhatsAppDraft,
} from "@/lib/whatsapp-demo";

type Tab = "overview" | "documents" | "validation" | "reconciliation" | "audit";
type DraftKind = "request" | "reminder";

const tabs: Array<[Tab | "assistant", string]> = [
  ["overview", "Overview"],
  ["documents", "Documents & Extraction"],
  ["validation", "Validation"],
  ["reconciliation", "GSTR-2B Reconciliation"],
  ["assistant", "RAG Assistant"],
  ["audit", "Audit Trail"],
];

export default function ApplicationWorkspace() {
  const {applicationId} = useParams<{applicationId: string}>();
  const router = useRouter();
  const [application, setApplication] = useState<GSTApplication | null>(null);
  const [collection, setCollection] = useState<DocumentCollectionStatus | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Reminder | null>(null);
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(false);
  const [guidedActive, setGuidedActive] = useState(false);
  const [guidedRunId, setGuidedRunId] = useState<string | null>(null);
  const [guidedDismissed, setGuidedDismissed] = useState(false);
  const [showExportGuide, setShowExportGuide] = useState(false);
  const [guidedComplete, setGuidedComplete] = useState(false);

  const resolveStoredSession = useCallback(() => {
    if (typeof window === "undefined") return null;
    return loadStoredDemoSession(window.sessionStorage, applicationId);
  }, [applicationId]);

  const load = useCallback(async () => {
    const session = typeof window === "undefined"
      ? null
      : loadStoredDemoSession(window.sessionStorage, applicationId);
    const headers = buildDemoContextHeaders(session);
    const [nextApplication, nextCollection] = await Promise.all([
      apiFetch<GSTApplication>(`/applications/${applicationId}`),
      apiFetch<DocumentCollectionStatus>(`/applications/${applicationId}/document-collection-status`, {headers}),
    ]);
    const events = await apiFetch<AuditEvent[]>(`/applications/${nextCollection.effective_application_id}/audit`, {headers});
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
    const timer = window.setTimeout(() => {
      const guided = loadGuidedDemoState(window.sessionStorage, applicationId);
      setGuidedActive(guided?.active === true && guided.completed === false);
      setGuidedRunId(guided?.runId ?? null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [applicationId]);

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

  async function exportPack() {
    setBusy(true);
    try {
      const files = await apiFetch<Record<string, string>>(
        `/applications/${collection?.effective_application_id ?? applicationId}/export`,
        {method: "POST"},
      );
      for (const url of preferredExportUrls(files, "export_pack_zip")) {
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        anchor.download = "OBLIQ_GST_Preparation_Export_Pack.zip";
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      }
      toast.success("GST preparation export pack generated");
      if (guidedActive && typeof window !== "undefined") {
        if (guidedRunId) {
          await apiFetch(`/guided-demo-runs/${guidedRunId}/complete`, {method: "POST"});
        }
        completeGuidedDemo(window.sessionStorage, applicationId);
        setGuidedActive(false);
        setGuidedComplete(true);
      }
      setShowExportGuide(false);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to export GST preparation pack");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !application || !collection) return <Loading label="Opening GST workspace…"/>;

  const complete = collection.workflow_status === "documents_complete";
  const displayApplicationId = collection.effective_application_id;
  const clientName = application.client?.business_name ?? "Client";
  const workflow = collection.workflow;
  const extractionStarted = workflow.extraction.record_count > 0;
  const reconciliationStarted = workflow.reconciliation.run_count > 0;
  const guidedInstruction = resolveGuidedDemoStep({tab, workflow});
  const guidedPrimaryAction = (() => {
    if (guidedInstruction.step === 1) return {label: "Draft Request", onClick: () => void createDraft("request"), disabled: busy || complete};
    if (guidedInstruction.step === 3) return {label: "View Checklist", onClick: () => setTab("overview")};
    if (guidedInstruction.step === 4) return {label: "Review Extractions", onClick: () => setTab("documents")};
    if (guidedInstruction.step === 5) return {label: "Review Findings", onClick: () => setTab("validation")};
    if (guidedInstruction.step === 6 && workflow.readiness.ready_for_filing) return {label: "Export Pack", onClick: () => setShowExportGuide(true), disabled: busy};
    if (guidedInstruction.step === 6) return {label: guidedInstruction.actionLabel, onClick: () => setTab("reconciliation")};
    return undefined;
  })();

  return <>
    <PageHeader
      eyebrow="GST DOCUMENT COLLECTION"
      title={`${clientName} · ${application.period_label}`}
      description={`${application.client?.gstin ?? ""} · Due ${formatDate(application.due_date)} · ${formatStatus(application.filing_frequency)} filing`}
      actions={<>
        <Link href={`/dashboard/clients/${application.client_id}`} className="obliq-focus inline-flex items-center gap-2 rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-5 py-3 text-sm font-semibold">
          <ArrowLeft size={17}/>Client
        </Link>
        <Button variant="secondary" disabled={busy || !workflow.readiness.main_export_enabled} onClick={() => setShowExportGuide(true)} title={workflow.readiness.main_export_enabled ? "Review and download the GST preparation pack" : "Complete Validation Review before exporting the GST preparation pack"}><Download size={16}/>Export Pack</Button>
      </>}
    />

    {guidedActive && !guidedDismissed && !guidedComplete && <GuidedDemoStep
      instruction={guidedInstruction}
      primaryAction={guidedPrimaryAction}
      secondaryAction={guidedInstruction.step === 6 && workflow.readiness.ready_for_filing ? {label: "Review GSTR-2B", onClick: () => setTab("reconciliation")} : undefined}
      onDismiss={() => setGuidedDismissed(true)}
    />}

    <WorkflowProgress workflow={workflow} receivedCount={collection.received_count} requiredCount={collection.required_count}/>

    <div className="mb-6 flex gap-1 overflow-x-auto rounded-2xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-1">
      {tabs.map(([value, label]) => <button key={value} onClick={() => value === "assistant" ? setAssistantOpen(true) : setTab(value)} className={`obliq-focus whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-semibold transition ${value !== "assistant" && tab === value ? "obliq-selected" : "obliq-interactive"}`}>{label}</button>)}
    </div>

    {tab === "overview" && <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
      <Card className="p-5">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div><h2 className="font-bold">Document checklist</h2><p className="mt-1 text-xs text-[var(--obliq-muted)]">This live checklist drives requests, reminders, progress, and WhatsApp STATUS.</p></div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => createDraft("request")} disabled={busy || complete}><MessageCircleMore size={16}/>Draft Request</Button>
            <Button variant="secondary" onClick={() => createDraft("reminder")} disabled={busy}><RefreshCw size={16}/>Draft Reminder</Button>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {collection.requirements.map(item => <div key={item.id} className="flex items-center justify-between rounded-2xl border border-[var(--obliq-border)] p-4">
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
            ].map(([label, value]) => <div key={label} className="rounded-2xl bg-[var(--obliq-surface-raised)] p-4"><p className="text-2xl font-bold">{value}</p><p className="mt-1 text-xs text-[var(--obliq-muted)]">{label}</p></div>)}
          </div>
          <div className="mt-4 rounded-2xl border border-[var(--obliq-border)] p-4"><p className="text-xs text-[var(--obliq-muted)]">Current Status</p><p className="mt-2 font-bold">{collectionStatus}</p></div>
        </Card>
        <Card className="p-5">
          <h2 className="font-bold">GST Preparation Readiness</h2>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {[
              ["Extraction Review", `${workflow.steps.find(step => step.key === "extraction_review")?.progress_percent ?? 0}%`],
              ["Validation Review", `${workflow.validation.progress_percent}%`],
              ["Ready for Filing", workflow.readiness.ready_for_filing ? "✓ 100%" : "Pending"],
              ["GSTR-2B Review", `${workflow.reconciliation.progress_percent}%`],
            ].map(([label, value]) => <div key={label} className="rounded-2xl bg-[var(--obliq-surface-raised)] p-4"><p className="text-xl font-bold">{value}</p><p className="mt-1 text-xs text-[var(--obliq-muted)]">{label}</p></div>)}
          </div>
          <ul className="mt-4 grid gap-3 text-sm text-[var(--obliq-muted)]">
            <li className="flex gap-2"><ClipboardCheck size={17}/> Validation completion deterministically activates Ready for Filing and Export Pack.</li>
            <li className="flex gap-2"><ClipboardCheck size={17}/> Reconciliation remains an independent optional review working.</li>
            <li className="flex gap-2"><ClipboardCheck size={17}/> OBLIQ does not file or submit data to the GST Portal.</li>
          </ul>
        </Card>
      </div>
    </div>}

    {tab === "documents" && <DocumentPanel applicationId={displayApplicationId} checklist={collection.requirements} onChanged={load}/>}
    {tab === "validation" && <FindingsPanel applicationId={displayApplicationId} onChanged={load}/>}
    {tab === "reconciliation" && <ReconciliationPanel applicationId={displayApplicationId} onChanged={load}/>}
    {tab === "audit" && <AuditTrailPanel events={audit}/>}

    <RagAssistantDrawer
      applicationId={displayApplicationId}
      clientName={clientName}
      period={application.period_label}
      missingCount={collection.missing_count}
      hasExtraction={extractionStarted}
      hasReconciliation={reconciliationStarted}
      open={assistantOpen}
      onOpenChange={setAssistantOpen}
    />

    {draft && <div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" onClick={() => void cancelDraft()}>
      <Card className="w-full max-w-2xl p-6 shadow-2xl" onClick={event => event.stopPropagation()}>
        <p className="text-xs font-bold tracking-[.13em] text-[#477ca8]">HUMAN APPROVAL REQUIRED</p>
        <h2 className="mt-3 text-2xl font-bold">{draft.reminder_type === "initial_document_request" ? "Document Request Draft" : "Reminder Draft"}</h2>
        <p className="mt-2 text-sm text-[var(--obliq-muted)]">Review the live checklist message and secure upload link before sending through Vonage.</p>
        {editing
          ? <Textarea className="mt-5 h-64 w-full" value={message} onChange={event => setMessage(event.target.value)}/>
          : <pre className="mt-5 max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl bg-[var(--obliq-surface-raised)] p-4 text-sm leading-6">{message}</pre>}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => void cancelDraft()}>Cancel</Button>
          <Button variant="secondary" onClick={() => setEditing(value => !value)}>{editing ? "Preview" : "Edit"}</Button>
          <Button onClick={sendDraft} disabled={busy}><Send size={16}/>{busy ? "Sending…" : draft.reminder_type === "initial_document_request" ? "Send Request" : "Send Reminder"}</Button>
        </div>
      </Card>
    </div>}

    {showExportGuide && <Modal titleId="export-guide-title" onClose={() => setShowExportGuide(false)} className="max-w-xl">
        <p className="text-xs font-bold tracking-[.13em] text-[var(--obliq-success-ink)]">READY FOR FILING</p>
        <h2 id="export-guide-title" className="mt-3 text-2xl font-bold">Your GST preparation work is ready.</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--obliq-muted)]">Generate the Export Pack to download collected-document references, normalized GST data, validation information and available workflow results.</p>
        <p className="mt-3 rounded-2xl bg-[var(--obliq-warning-soft)] p-3 text-xs text-[var(--obliq-warning-ink)]">This is a preparatory CA working pack, not a filed GST return.</p>
        <div className="mt-6 flex justify-end gap-2"><Button variant="ghost" onClick={() => setShowExportGuide(false)}>Cancel</Button><Button onClick={() => void exportPack()} disabled={busy}><Download size={16}/>{busy ? "Generating…" : "Export Pack"}</Button></div>
    </Modal>}

    {guidedComplete && <Modal titleId="guided-complete-title" onClose={() => setGuidedComplete(false)} className="max-w-lg text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[var(--obliq-success-soft)] text-[var(--obliq-success-ink)]"><Check size={24}/></span>
        <h2 id="guided-complete-title" className="mt-4 text-2xl font-bold">Guided Demo Complete</h2>
        <p className="mt-2 text-sm text-[var(--obliq-muted)]">You completed the real OBLIQ GST readiness workflow and generated its Export Pack.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button variant="secondary" onClick={() => router.push("/dashboard")}>Return to Overview</Button>
          <Button onClick={() => router.push(`/dashboard/clients/${application.client_id}`)}>Open Client Profile</Button>
        </div>
    </Modal>}
  </>;
}
