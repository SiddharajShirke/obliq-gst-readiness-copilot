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
  checklist: Array<{id: string; label: string; status: string}>;
  last_activity_at: string | null;
  token_expires_at: string;
  session_expires_at: string;
  last_outbound_delivery_status: string | null;
};

export type StoredDemoSession = {
  sessionId: string;
  dashboardAccessToken: string;
  created?: WhatsAppDemoCreated;
};

type SessionStorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function storageKey(applicationId: string): string {
  return `obliq_whatsapp_demo:${applicationId}`;
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
