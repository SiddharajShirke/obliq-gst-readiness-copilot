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
  explanation: string;
  why: string;
  actionLabel?: string;
};

export function resolveGuidedDemoStep(input: {
  tab: string;
  workflow: {
    current_stage: string;
    readiness: {ready_for_filing: boolean};
    reconciliation: {run_count: number};
  };
}): GuidedDemoInstruction {
  const stage = input.workflow.current_stage;
  const postValidation = input.workflow.readiness.ready_for_filing
    || stage === "reconciliation_review"
    || stage === "ready_for_filing";
  if (postValidation && input.tab === "reconciliation") {
    return {
      step: 6,
      title: "Review GSTR-2B Reconciliation",
      explanation: "Start the deterministic comparison, then inspect Exact Match, Books Only, GSTR-2B Only, value or invoice-number mismatches, ITC restrictions, RCM and Needs Review.",
      why: "Reconciliation is an independent CA review branch after validation.",
      actionLabel: input.workflow.reconciliation.run_count ? "Review Findings" : "Start Reconciliation",
    };
  }
  if (postValidation) {
    return {
      step: 6,
      title: "Choose the Next Path",
      explanation: "Validation is complete. Reconcile GSTR-2B when required, or generate the GST preparation Export Pack.",
      why: "Ready for Filing and reconciliation are available independently.",
      actionLabel: "Export Pack",
    };
  }
  if (stage === "validation_review") {
    return {
      step: 5,
      title: "Review Validation Findings",
      explanation: "Review the checks created from approved structured GST records and resolve the required findings.",
      why: "Validation completion is the deterministic readiness gate.",
      actionLabel: "Review Findings",
    };
  }
  if (stage === "extraction_review") {
    return {
      step: 4,
      title: "Review Extracted Data",
      explanation: "Compare structured GST records with their original documents, then approve, edit or clarify them.",
      why: "AI extracts; the CA verifies.",
      actionLabel: "Review Extractions",
    };
  }
  if (["documents_requested", "partially_received", "documents_received"].includes(stage)) {
    return {
      step: 3,
      title: "Upload GST Documents",
      explanation: "Open the secure link from the real WhatsApp request and submit the requested synthetic documents.",
      why: "Uploads remain private and update this cloned checklist.",
      actionLabel: "View Checklist",
    };
  }
  return {
    step: 1,
    title: "Request Documents",
    explanation: "Start the real GST workflow by drafting the current six-category document request.",
    why: "The CA reviews the request before connecting and sending through Vonage.",
    actionLabel: "Draft Request",
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
