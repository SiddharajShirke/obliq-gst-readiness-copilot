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

function storageKey(applicationId: string): string {
  return `obliq_whatsapp_demo:${applicationId}`;
}

function pendingDraftKey(applicationId: string): string {
  return `obliq_whatsapp_pending_draft:${applicationId}`;
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
