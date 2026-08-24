import {ApiError} from "./api";

export type WhatsAppDemoCreated = {
  session_id: string;
  base_client_name: string;
  gst_period: string;
  status: string;
  token_expires_at: string;
  session_expires_at: string;
  sandbox_sender: string;
  sandbox_join_message: string;
  sandbox_join_whatsapp_url: string;
  start_message: string;
  start_whatsapp_url: string;
  dashboard_access_token: string;
};

export type WhatsAppDemoStatus = {
  status: string;
  connection_status: string;
  masked_phone: string | null;
  client_name: string;
  gst_period: string;
  current_step: string | null;
  checklist: Array<{
    id: string;
    label: string;
    status: string;
    upload_status: string;
    processing_status: string | null;
  }>;
  last_activity_at: string | null;
  token_expires_at: string;
  session_expires_at: string;
  last_outbound_delivery_status: string | null;
  collection?: {
    required_count: number;
    received_count: number;
    missing_count: number;
    progress_percent: number;
    workflow_status: string;
  };
};

export type StoredDemoSession = {
  sessionId: string;
  dashboardAccessToken: string;
  created?: WhatsAppDemoCreated;
};

type SessionStorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export type PendingWhatsAppDraft = {
  reminderId: string;
  reminderType: "initial_document_request" | "missing_document_reminder";
  draftMessage: string;
  prepared: boolean;
};

export type GuidedDemoState = {
  active: boolean;
  completed: boolean;
  runId?: string;
  runName?: string;
  clientId?: string;
};

export type GuidedDemoRun = {
  id: string;
  firm_id: string;
  user_id: string;
  demo_client_id: string;
  base_application_id: string;
  demo_session_id: string;
  session_application_id: string;
  run_number: number;
  name: string;
  status: "active" | "completed" | "cancelled";
  started_at: string;
  completed_at: string | null;
  session?: WhatsAppDemoCreated & {session_application_id: string};
};

export function guidedDemoStateFromRun(
  run: Pick<GuidedDemoRun, "id" | "name" | "status" | "demo_client_id">,
): GuidedDemoState {
  return {
    active: run.status === "active",
    completed: run.status === "completed",
    runId: run.id,
    runName: run.name,
    clientId: run.demo_client_id,
  };
}

function storageKey(applicationId: string): string {
  return `obliq_whatsapp_demo:${applicationId}`;
}

function pendingDraftKey(applicationId: string): string {
  return `obliq_whatsapp_pending_draft:${applicationId}`;
}

function guidedDemoKey(applicationId: string): string {
  return `obliq_guided_demo:${applicationId}`;
}

export function saveGuidedDemoState(
  storage: SessionStorageLike,
  applicationId: string,
  state: GuidedDemoState,
): void {
  storage.setItem(guidedDemoKey(applicationId), JSON.stringify(state));
}

export function loadGuidedDemoState(
  storage: SessionStorageLike,
  applicationId: string,
): GuidedDemoState | null {
  const raw = storage.getItem(guidedDemoKey(applicationId));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as GuidedDemoState;
    if (typeof parsed.active !== "boolean" || typeof parsed.completed !== "boolean") return null;
    return parsed;
  } catch {
    storage.removeItem(guidedDemoKey(applicationId));
    return null;
  }
}

export function completeGuidedDemo(
  storage: SessionStorageLike,
  applicationId: string,
): void {
  const current = loadGuidedDemoState(storage, applicationId);
  saveGuidedDemoState(storage, applicationId, {
    ...current,
    active: false,
    completed: true,
  });
}

export async function startFreshGuidedDemo(input: {
  storage: SessionStorageLike;
  applicationId: string;
  cancelSession: (sessionId: string, dashboardAccessToken: string) => Promise<void>;
  createSession: () => Promise<WhatsAppDemoCreated>;
}): Promise<StoredDemoSession> {
  const existing = loadStoredDemoSession(input.storage, input.applicationId);
  if (existing) {
    await input.cancelSession(existing.sessionId, existing.dashboardAccessToken).catch(() => undefined);
  }
  const created = await input.createSession();
  const stored: StoredDemoSession = {
    sessionId: created.session_id,
    dashboardAccessToken: created.dashboard_access_token,
    created,
  };
  removePendingWhatsAppDraft(input.storage, input.applicationId);
  saveStoredDemoSession(input.storage, input.applicationId, stored);
  saveGuidedDemoState(input.storage, input.applicationId, {active: true, completed: false});
  return stored;
}

export type GuidedDemoInstruction = {
  step: number;
  title: string;
  status: "action_required" | "in_progress" | "ready" | "complete";
  objective: string;
  explanation?: string;
  tasks: string[];
  why: string;
  completeWhen: string;
  next: string;
  progress?: string;
  actionKey?: GuidedDemoActionKey;
  actionLabel?: string;
};

export type GuidedDemoActionKey =
  | "draft_request"
  | "view_checklist"
  | "view_processing"
  | "review_extractions"
  | "review_validation"
  | "export_pack"
  | "upload_gstr2b"
  | "start_reconciliation"
  | "review_reconciliation"
  | "export_reconciliation";

type GuidedWorkflowSnapshot = {
  current_stage: string;
  readiness: {ready_for_filing: boolean};
  extraction?: {record_count: number; reviewed_count: number; pending_count: number};
  validation?: {finding_count: number; reviewed_count: number; open_count: number};
  reconciliation: {
    run_count: number;
    item_count?: number;
    review_required_count?: number;
    reviewed_count?: number;
    open_count?: number;
    progress_percent?: number;
    export_enabled?: boolean;
  };
};

function reviewedProgress(reviewed: number, total: number, noun: string): string {
  return `${reviewed} of ${total} ${noun} reviewed`;
}

export function resolveGuidedDemoStep(input: {
  tab: string;
  workflow: GuidedWorkflowSnapshot;
  gstr2bStatus?: string | null;
  receivedCount?: number;
  requiredCount?: number;
}): GuidedDemoInstruction {
  const stage = input.workflow.current_stage;
  const postValidation = input.workflow.readiness.ready_for_filing
    || stage === "reconciliation_review"
    || stage === "ready_for_filing";
  if (postValidation && input.tab === "reconciliation") {
    const reconciliation = input.workflow.reconciliation;
    const reviewTotal = reconciliation.review_required_count
      ?? reconciliation.item_count
      ?? 0;
    const reviewed = reconciliation.reviewed_count ?? 0;
    if (reconciliation.export_enabled) {
      return {
        step: 6,
        title: "Export Reconciliation Working",
        status: "complete",
        objective: "Download the completed Books-versus-GSTR-2B working for CA review.",
        tasks: [
          "Confirm the reconciliation review is 100% complete.",
          "Select Export Reconciliation in this workspace.",
          "Open the generated working and verify its exact comparison evidence.",
        ],
        why: "The reconciliation report is independent from the main GST preparation Export Pack.",
        completeWhen: "The reconciliation working downloads successfully.",
        next: "Return to the main workspace or inspect the Audit Trail.",
        progress: "Reconciliation review 100%",
        actionKey: "export_reconciliation",
        actionLabel: "Export Reconciliation",
      };
    }
    if (reconciliation.run_count > 0) {
      return {
        step: 6,
        title: "Review GSTR-2B Findings",
        status: "in_progress",
        objective: "Review every deterministic Books-versus-GSTR-2B exception requiring CA attention.",
        tasks: [
          "Filter the findings by mismatch type when useful.",
          "Open a row and compare the exact Books and GSTR-2B values.",
          "Mark reviewed findings explicitly; raise an alert only when CA follow-up is required.",
          "Use Select All only for the currently visible eligible findings, then confirm the bulk review action.",
        ],
        why: "The matching result is deterministic; AI explanations remain read-only assistance.",
        completeWhen: "Every review-required reconciliation finding is reviewed and progress reaches 100%.",
        next: "Export Reconciliation becomes available without changing Ready for Filing.",
        progress: reviewedProgress(reviewed, reviewTotal, "findings"),
        actionKey: "review_reconciliation",
        actionLabel: "Review Findings",
      };
    }
    if (input.gstr2bStatus === "ready_to_reconcile") {
      return {
        step: 6,
        title: "Start GSTR-2B Reconciliation",
        status: "ready",
        objective: "Run the deterministic comparison against the uploaded GSTR-2B file.",
        tasks: [
          "Confirm the GSTR-2B file is marked Ready to Reconcile.",
          "Select Start Reconciliation once.",
          "Wait for OBLIQ to persist the run and display its result categories.",
        ],
        why: "OBLIQ compares normalized fields using the stored reconciliation rules; an LLM does not decide matches.",
        completeWhen: "A reconciliation run and its categorized findings appear.",
        next: "Inspect Exact Match, mismatch, Books Only, GSTR-2B Only, ITC and RCM results.",
        progress: "GSTR-2B ready",
        actionKey: "start_reconciliation",
        actionLabel: "Start Reconciliation",
      };
    }
    return {
      step: 6,
      title: "Upload GSTR-2B",
      status: "action_required",
      objective: "Provide the CA-side GSTR-2B input for the optional reconciliation branch.",
      tasks: [
        "Select Upload GSTR-2B in the reconciliation controls.",
        "Choose the supplied GSTR-2B PDF, CSV, XLSX or JSON file.",
        "Wait until the file is parsed and marked Ready to Reconcile.",
      ],
      why: "Reconciliation is an independent CA review branch after validation.",
      completeWhen: "The uploaded file is marked Ready to Reconcile.",
      next: "Start the deterministic Books-versus-GSTR-2B comparison.",
      progress: "GSTR-2B not uploaded",
      actionKey: "upload_gstr2b",
      actionLabel: "Upload GSTR-2B",
    };
  }
  if (postValidation) {
    return {
      step: 6,
      title: "Choose the Next Path",
      status: "ready",
      objective: "Generate the main GST preparation pack or open the independent reconciliation branch.",
      tasks: [
        "Generate the Export Pack to complete the Guided Demo.",
        "Optionally open GSTR-2B Reconciliation for the separate Books-versus-GSTR-2B review.",
        "Use Ask OBLIQ or Audit Trail whenever you want to inspect evidence and recorded actions.",
      ],
      why: "Ready for Filing and reconciliation are available independently.",
      completeWhen: "The real GST preparation Export Pack is generated successfully.",
      next: "OBLIQ records Guided Demo completion and retains the completed run on Overview.",
      progress: "Validation 100% · Ready for Filing 100%",
      actionKey: "export_pack",
      actionLabel: "Export Pack",
    };
  }
  if (stage === "validation_review") {
    const validation = input.workflow.validation;
    const total = validation?.finding_count ?? 0;
    const reviewed = validation?.reviewed_count ?? 0;
    return {
      step: 5,
      title: "Review Validation Findings",
      status: "in_progress",
      objective: "Resolve or accept every deterministic validation finding that requires CA review.",
      tasks: [
        "Open a document category, then select one validation finding.",
        "Read what is wrong, the business identity, and the deterministic field evidence.",
        "Use a manual correction or request an AI recommendation; inspect the before/after preview before approving any change.",
        "Raise a categorized alert when follow-up is required, then resolve or accept the finding explicitly.",
        "Use Select All only for visible eligible findings and confirm any bulk review action.",
      ],
      why: "Validation completion is the deterministic readiness gate.",
      completeWhen: "All review-required findings are reviewed and Validation reaches 100%.",
      next: "Ready for Filing and GSTR-2B Reconciliation become available independently.",
      progress: reviewedProgress(reviewed, total, "findings"),
      actionKey: "review_validation",
      actionLabel: "Review Findings",
    };
  }
  if (stage === "extraction_review") {
    const extraction = input.workflow.extraction;
    const total = extraction?.record_count ?? 0;
    const reviewed = extraction?.reviewed_count ?? 0;
    return {
      step: 4,
      title: "Review Extracted Data",
      status: "in_progress",
      objective: "Verify normalized GST data against the original private documents.",
      tasks: [
        "Open a document category or the Combined GST Portfolio.",
        "Select a record and compare its original source with every extracted GST value.",
        "Choose Approve, Edit & Approve, or Reject/Clarify for each eligible record.",
        "For bulk review, select only visible eligible rows and explicitly confirm the action.",
      ],
      why: "AI extracts; the CA verifies.",
      completeWhen: "every eligible record is reviewed and Extraction Review reaches 100%.",
      next: "Approved client records enter deterministic Validation Review.",
      progress: reviewedProgress(reviewed, total, "records"),
      actionKey: "review_extractions",
      actionLabel: "Review Extractions",
    };
  }
  if (stage === "documents_received") {
    const extracted = input.workflow.extraction?.record_count ?? 0;
    return {
      step: 3,
      title: "Documents Submitted — Processing",
      status: "in_progress",
      objective: "Let OBLIQ process the submitted documents while you monitor their live status.",
      tasks: [
        "Confirm the secure upload page accepted and submitted the batch.",
        "Remain on Overview or open Documents & Extraction to monitor processing states.",
        "Wait for normalized records to appear; do not upload the same files again.",
        "If a document fails, inspect its status and retry only that source file.",
      ],
      why: "Parsing, OCR and AI extraction run after secure storage and can take longer on the hosted free tier.",
      completeWhen: "Extracted records appear and the workflow advances to Extraction Review.",
      next: "Open Documents & Extraction and compare every record with its original evidence.",
      progress: `${extracted} ${extracted === 1 ? "record" : "records"} extracted`,
      actionKey: "view_processing",
      actionLabel: "View Processing Status",
    };
  }
  if (["documents_requested", "partially_received"].includes(stage)) {
    const received = input.receivedCount ?? 0;
    const required = input.requiredCount ?? 6;
    return {
      step: 3,
      title: "Upload GST Documents",
      status: "action_required",
      objective: "Collect and submit the six requested synthetic GST document categories.",
      tasks: [
        "Open the secure OBLIQ upload link received in WhatsApp.",
        "Upload files individually, choose a complete browser folder, or upload the supplied ZIP package.",
        "Check that all six required categories show Uploaded.",
        "Select Submit documents for extraction; storage alone does not start processing.",
        "After successful submission, allow the five-second return to Overview.",
      ],
      why: "Uploads remain private and update this cloned checklist.",
      completeWhen: "All required categories are uploaded and the stored batch is submitted for extraction.",
      next: "The upload page returns to Overview while extraction continues in the background.",
      progress: `${received} of ${required} categories received`,
      actionKey: "view_checklist",
      actionLabel: "View Checklist",
    };
  }
  return {
    step: 1,
    title: "Request Documents",
    status: "action_required",
    objective: "Create and send the real six-category GST document request.",
    tasks: [
      "Select Draft Request from the Guided Demo card or Overview checklist.",
      "Connect the Vonage Sandbox when OBLIQ opens the WhatsApp setup step.",
      "Review the generated message and secure upload link.",
      "Select Send Request only after the draft is correct.",
    ],
    why: "The CA reviews the request before connecting and sending through Vonage.",
    completeWhen: "The approved document request is sent and the workflow shows Documents Requested.",
    next: "Open the secure link from WhatsApp and provide the requested synthetic documents.",
    progress: "Request not sent",
    actionKey: "draft_request",
    actionLabel: "Draft Request",
  };
}

export function resolveWhatsAppGuidedDemoStep(status: string): GuidedDemoInstruction {
  if (status === "active") {
    return {
      step: 2,
      title: "WhatsApp Connected",
      status: "complete",
      objective: "Return to the GST workspace and explicitly send the preserved document request.",
      tasks: [
        "Confirm this page shows WhatsApp Connected.",
        "Wait while OBLIQ prepares the preserved request for the connected session.",
        "Review the message and secure upload link in the GST workspace, then select Send Request.",
      ],
      why: "The connected number is now securely bound to this isolated Guided Demo application.",
      completeWhen: "The request is sent through Vonage from the GST workspace.",
      next: "Return to the GST workspace to review and send the preserved document request.",
      progress: "Connection complete",
    };
  }
  return {
    step: 2,
    title: "Connect Vonage WhatsApp",
    status: "action_required",
    objective: "Bind your WhatsApp number to this isolated Guided Demo session.",
    tasks: [
      "Scan the Vonage Sandbox QR and send its pre-filled join message.",
      "Wait until the Sandbox membership is ready.",
      "Scan the unique OBLIQ START QR and send the START message.",
      "Keep this page open until the live status shows WhatsApp Connected.",
    ],
    why: "The Sandbox QR permits messaging; the separate START QR securely binds this reviewer to the cloned GST workflow.",
    completeWhen: "The live session status displays WhatsApp Connected.",
    next: "OBLIQ returns to the preserved document request so the CA can review and send it.",
    progress: "Waiting for connection",
  };
}

export function saveStoredDemoSession(
  storage: SessionStorageLike,
  applicationId: string,
  value: StoredDemoSession,
): void {
  storage.setItem(storageKey(applicationId), JSON.stringify(value));
}

export function loadStoredDemoSession(
  storage: SessionStorageLike,
  applicationId: string,
): StoredDemoSession | null {
  const raw = storage.getItem(storageKey(applicationId));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredDemoSession;
    if (!parsed.sessionId || !parsed.dashboardAccessToken) return null;
    return parsed;
  } catch {
    storage.removeItem(storageKey(applicationId));
    return null;
  }
}

export function removeStoredDemoSession(
  storage: SessionStorageLike,
  applicationId: string,
): void {
  storage.removeItem(storageKey(applicationId));
}

export function isMissingDemoSessionError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function buildDemoAccessHeaders(token: string): Record<string, string> {
  return {"X-OBLIQ-Demo-Access-Token": token};
}

export function buildDemoContextHeaders(
  session: StoredDemoSession | null,
): Record<string, string> {
  if (!session) return {};
  return {
    "X-OBLIQ-Demo-Session-Id": session.sessionId,
    "X-OBLIQ-Demo-Access-Token": session.dashboardAccessToken,
  };
}

export function savePendingWhatsAppDraft(
  storage: SessionStorageLike,
  applicationId: string,
  value: PendingWhatsAppDraft,
): void {
  storage.setItem(pendingDraftKey(applicationId), JSON.stringify(value));
}

export function loadPendingWhatsAppDraft(
  storage: SessionStorageLike,
  applicationId: string,
): PendingWhatsAppDraft | null {
  const raw = storage.getItem(pendingDraftKey(applicationId));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as PendingWhatsAppDraft;
    if (!parsed.reminderId || !parsed.reminderType || !parsed.draftMessage) return null;
    return parsed;
  } catch {
    storage.removeItem(pendingDraftKey(applicationId));
    return null;
  }
}

export function removePendingWhatsAppDraft(
  storage: SessionStorageLike,
  applicationId: string,
): void {
  storage.removeItem(pendingDraftKey(applicationId));
}
