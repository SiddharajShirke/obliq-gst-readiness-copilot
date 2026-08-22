import { describe, expect, it } from "vitest";
import {
  buildDemoAccessHeaders,
  buildDemoContextHeaders,
  isMissingDemoSessionError,
  loadPendingWhatsAppDraft,
  loadStoredDemoSession,
  removePendingWhatsAppDraft,
  removeStoredDemoSession,
  savePendingWhatsAppDraft,
  saveStoredDemoSession,
} from "./whatsapp-demo";
import {ApiError} from "./api";

class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

describe("WhatsApp demo browser isolation", () => {
  it("stores each application session in sessionStorage-compatible storage", () => {
    const storage = new MemoryStorage();
    saveStoredDemoSession(storage, "app-a", {
      sessionId: "session-a",
      dashboardAccessToken: "secret-a",
    });
    saveStoredDemoSession(storage, "app-b", {
      sessionId: "session-b",
      dashboardAccessToken: "secret-b",
    });

    expect(loadStoredDemoSession(storage, "app-a")).toEqual({
      sessionId: "session-a",
      dashboardAccessToken: "secret-a",
    });
    expect(loadStoredDemoSession(storage, "app-b")?.sessionId).toBe("session-b");
  });

  it("sends the dashboard secret only through the dedicated header", () => {
    const headers = buildDemoAccessHeaders("dashboard-secret");

    expect(headers).toEqual({"X-OBLIQ-Demo-Access-Token": "dashboard-secret"});
    expect(JSON.stringify(headers)).not.toContain("Authorization");
  });

  it("sends both session isolation headers for collection and request APIs", () => {
    expect(buildDemoContextHeaders({
      sessionId: "session-a",
      dashboardAccessToken: "dashboard-secret",
    })).toEqual({
      "X-OBLIQ-Demo-Session-Id": "session-a",
      "X-OBLIQ-Demo-Access-Token": "dashboard-secret",
    });
    expect(buildDemoContextHeaders(null)).toEqual({});
  });

  it("preserves a request draft while WhatsApp reconnects", () => {
    const storage = new MemoryStorage();
    savePendingWhatsAppDraft(storage, "app-a", {
      reminderId: "reminder-a",
      reminderType: "initial_document_request",
      draftMessage: "Please connect WhatsApp",
      prepared: false,
    });

    expect(loadPendingWhatsAppDraft(storage, "app-a")?.reminderId).toBe("reminder-a");
    removePendingWhatsAppDraft(storage, "app-a");
    expect(loadPendingWhatsAppDraft(storage, "app-a")).toBeNull();
  });

  it("removes only the stale application session and preserves login state", () => {
    const storage = new MemoryStorage();
    storage.setItem("obliq_access_token", "header.payload.signature");
    storage.setItem("obliq_user", "valid-user");
    saveStoredDemoSession(storage, "stale-app", {
      sessionId: "memory-only-session",
      dashboardAccessToken: "dashboard-secret",
    });
    saveStoredDemoSession(storage, "current-app", {
      sessionId: "supabase-session",
      dashboardAccessToken: "another-secret",
    });

    removeStoredDemoSession(storage, "stale-app");

    expect(loadStoredDemoSession(storage, "stale-app")).toBeNull();
    expect(loadStoredDemoSession(storage, "current-app")?.sessionId).toBe("supabase-session");
    expect(storage.getItem("obliq_access_token")).toBe("header.payload.signature");
    expect(storage.getItem("obliq_user")).toBe("valid-user");
  });

  it("treats only an authenticated 404 as a stale demo session", () => {
    expect(isMissingDemoSessionError(new ApiError("Not found", 404))).toBe(true);
    expect(isMissingDemoSessionError(new ApiError("Unauthorized", 401))).toBe(false);
    expect(isMissingDemoSessionError(new Error("Network failure"))).toBe(false);
  });
});
