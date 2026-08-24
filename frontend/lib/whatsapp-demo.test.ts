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
import * as WhatsAppDemo from "./whatsapp-demo";
import {ApiError} from "./api";

class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

describe("WhatsApp demo browser isolation", () => {
  it("keeps guided instructions scoped to one real cloned application", () => {
    const storage = new MemoryStorage();
    const api = WhatsAppDemo as typeof WhatsAppDemo & {
      saveGuidedDemoState: (storage: MemoryStorage, applicationId: string, state: {active: boolean; completed: boolean}) => void;
      loadGuidedDemoState: (storage: MemoryStorage, applicationId: string) => {active: boolean; completed: boolean} | null;
      completeGuidedDemo: (storage: MemoryStorage, applicationId: string) => void;
    };

    expect(typeof api.saveGuidedDemoState).toBe("function");
    api.saveGuidedDemoState(storage, "app-a", {active: true, completed: false});
    expect(api.loadGuidedDemoState(storage, "app-a")).toEqual({active: true, completed: false});
    expect(api.loadGuidedDemoState(storage, "app-b")).toBeNull();
    api.completeGuidedDemo(storage, "app-a");
    expect(api.loadGuidedDemoState(storage, "app-a")).toEqual({active: false, completed: true});
  });

  it("persists the numbered backend run needed for explicit completion", () => {
    const storage = new MemoryStorage();
    WhatsAppDemo.saveGuidedDemoState(storage, "base-app", {
      active: true,
      completed: false,
      runId: "run-2",
      runName: "Guided Demo 2",
      clientId: "raj-client",
    });

    expect(WhatsAppDemo.loadGuidedDemoState(storage, "base-app")).toEqual({
      active: true,
      completed: false,
      runId: "run-2",
      runName: "Guided Demo 2",
      clientId: "raj-client",
    });
  });

  it("maps a persistent backend run to the browser guidance state", () => {
    const api = WhatsAppDemo as typeof WhatsAppDemo & {
      guidedDemoStateFromRun: (run: {
        id: string;
        name: string;
        status: string;
        demo_client_id: string;
      }) => WhatsAppDemo.GuidedDemoState;
    };

    expect(typeof api.guidedDemoStateFromRun).toBe("function");
    expect(api.guidedDemoStateFromRun({
      id: "run-3",
      name: "Guided Demo 3",
      status: "active",
      demo_client_id: "raj-client",
    })).toEqual({
      active: true,
      completed: false,
      runId: "run-3",
      runName: "Guided Demo 3",
      clientId: "raj-client",
    });
  });

  it("replaces a retained browser session with a newly cloned guided workspace", async () => {
    const storage = new MemoryStorage();
    saveStoredDemoSession(storage, "app-a", {
      sessionId: "old-session",
      dashboardAccessToken: "old-secret",
    });
    savePendingWhatsAppDraft(storage, "app-a", {
      reminderId: "stale-reminder",
      reminderType: "initial_document_request",
      draftMessage: "Old cloned-session draft",
      prepared: true,
    });
    const events: string[] = [];
    const api = WhatsAppDemo as typeof WhatsAppDemo & {
      startFreshGuidedDemo: (input: {
        storage: MemoryStorage;
        applicationId: string;
        cancelSession: (sessionId: string, token: string) => Promise<void>;
        createSession: () => Promise<WhatsAppDemo.WhatsAppDemoCreated>;
      }) => Promise<WhatsAppDemo.StoredDemoSession>;
    };

    expect(typeof api.startFreshGuidedDemo).toBe("function");
    const result = await api.startFreshGuidedDemo({
      storage,
      applicationId: "app-a",
      cancelSession: async (sessionId, token) => { events.push(`cancel:${sessionId}:${token}`); },
      createSession: async () => {
        events.push("create");
        return {
          session_id: "fresh-session",
          base_client_name: "Raj Traders",
          gst_period: "April 2026",
          status: "waiting_for_start",
          token_expires_at: "2026-08-23T18:00:00Z",
          session_expires_at: "2026-08-23T20:00:00Z",
          sandbox_sender: "14155238886",
          sandbox_join_message: "join repel finch",
          sandbox_join_whatsapp_url: "https://wa.me/14155238886",
          start_message: "START OBLIQ DEMO ABCD2345",
          start_whatsapp_url: "https://wa.me/14155238886",
          dashboard_access_token: "fresh-secret",
        };
      },
    });

    expect(events).toEqual(["cancel:old-session:old-secret", "create"]);
    expect(result.sessionId).toBe("fresh-session");
    expect(loadStoredDemoSession(storage, "app-a")?.sessionId).toBe("fresh-session");
    expect(loadPendingWhatsAppDraft(storage, "app-a")).toBeNull();
    expect(api.loadGuidedDemoState(storage, "app-a")).toEqual({active: true, completed: false});
  });

  it("derives guidance from real workflow data instead of browser-authored completion", () => {
    type DetailedInstruction = {
      step: number;
      title: string;
      actionKey?: string;
      actionLabel?: string;
      tasks: string[];
      completeWhen: string;
      next: string;
      progress?: string;
    };
    const resolve = WhatsAppDemo.resolveGuidedDemoStep as unknown as (input: {
      tab: string;
      gstr2bStatus?: string | null;
      workflow: {
        current_stage: string;
        readiness: {ready_for_filing: boolean};
        extraction?: {record_count: number; reviewed_count: number; pending_count: number};
        validation?: {finding_count: number; reviewed_count: number; open_count: number};
        reconciliation: {
          run_count: number;
          item_count?: number;
          reviewed_count?: number;
          open_count?: number;
          progress_percent?: number;
          export_enabled?: boolean;
        };
      };
    }) => DetailedInstruction;

    expect(typeof resolve).toBe("function");
    expect(resolve({
      tab: "overview",
      workflow: {current_stage: "not_started", readiness: {ready_for_filing: false}, reconciliation: {run_count: 0}},
    })).toMatchObject({
      step: 1,
      title: "Request Documents",
      actionKey: "draft_request",
      actionLabel: "Draft Request",
      completeWhen: expect.stringContaining("sent"),
    });
    expect(resolve({
      tab: "overview",
      workflow: {
        current_stage: "documents_received",
        readiness: {ready_for_filing: false},
        extraction: {record_count: 0, reviewed_count: 0, pending_count: 0},
        reconciliation: {run_count: 0},
      },
    })).toMatchObject({
      step: 3,
      title: "Documents Submitted — Processing",
      actionKey: "view_processing",
      progress: "0 records extracted",
      next: expect.stringContaining("Documents & Extraction"),
    });
    const extraction = resolve({
      tab: "documents",
      workflow: {
        current_stage: "extraction_review",
        readiness: {ready_for_filing: false},
        extraction: {record_count: 24, reviewed_count: 12, pending_count: 12},
        reconciliation: {run_count: 0},
      },
    });
    expect(extraction).toMatchObject({
      step: 4,
      title: "Review Extracted Data",
      actionKey: "review_extractions",
      progress: "12 of 24 records reviewed",
      completeWhen: expect.stringContaining("every eligible record"),
    });
    expect(extraction.tasks.join(" ")).toContain("category");
    expect(extraction.tasks.join(" ")).toContain("Approve, Edit & Approve, or Reject/Clarify");

    const validation = resolve({
      tab: "validation",
      workflow: {
        current_stage: "validation_review",
        readiness: {ready_for_filing: false},
        validation: {finding_count: 41, reviewed_count: 30, open_count: 11},
        reconciliation: {run_count: 0},
      },
    });
    expect(validation).toMatchObject({
      step: 5,
      title: "Review Validation Findings",
      actionKey: "review_validation",
      progress: "30 of 41 findings reviewed",
      completeWhen: expect.stringContaining("100%"),
    });
    expect(validation.tasks.join(" ")).toContain("AI recommendation");
    expect(validation.tasks.join(" ")).toContain("alert");

    expect(resolve({
      tab: "reconciliation",
      gstr2bStatus: "not_uploaded",
      workflow: {current_stage: "reconciliation_review", readiness: {ready_for_filing: true}, reconciliation: {run_count: 0}},
    })).toMatchObject({step: 6, actionKey: "upload_gstr2b", actionLabel: "Upload GSTR-2B"});
    expect(resolve({
      tab: "reconciliation",
      gstr2bStatus: "ready_to_reconcile",
      workflow: {current_stage: "reconciliation_review", readiness: {ready_for_filing: true}, reconciliation: {run_count: 0}},
    })).toMatchObject({step: 6, actionKey: "start_reconciliation", actionLabel: "Start Reconciliation"});
    expect(resolve({
      tab: "reconciliation",
      gstr2bStatus: "ready_to_reconcile",
      workflow: {
        current_stage: "reconciliation_review",
        readiness: {ready_for_filing: true},
        reconciliation: {run_count: 1, item_count: 11, reviewed_count: 4, open_count: 7, progress_percent: 36, export_enabled: false},
      },
    })).toMatchObject({step: 6, actionKey: "review_reconciliation", actionLabel: "Review Findings", progress: "4 of 11 findings reviewed"});
    expect(resolve({
      tab: "reconciliation",
      gstr2bStatus: "ready_to_reconcile",
      workflow: {
        current_stage: "ready_for_filing",
        readiness: {ready_for_filing: true},
        reconciliation: {run_count: 1, item_count: 11, reviewed_count: 11, open_count: 0, progress_percent: 100, export_enabled: true},
      },
    })).toMatchObject({step: 6, actionKey: "export_reconciliation", actionLabel: "Export Reconciliation"});

    expect(resolve({
      tab: "overview",
      workflow: {current_stage: "reconciliation_review", readiness: {ready_for_filing: true}, reconciliation: {run_count: 0}},
    })).toMatchObject({
      step: 6,
      title: "Choose the Next Path",
      actionKey: "export_pack",
      actionLabel: "Export Pack",
    });
  });

  it("explains both Vonage QR steps and the connected handoff", () => {
    type DetailedInstruction = {
      step: number;
      title: string;
      tasks: string[];
      completeWhen: string;
      next: string;
      progress?: string;
    };
    const resolve = (WhatsAppDemo as typeof WhatsAppDemo & {
      resolveWhatsAppGuidedDemoStep: (status: string) => DetailedInstruction;
    }).resolveWhatsAppGuidedDemoStep;

    expect(typeof resolve).toBe("function");
    expect(resolve("waiting_for_start")).toMatchObject({
      step: 2,
      title: "Connect Vonage WhatsApp",
      completeWhen: expect.stringContaining("WhatsApp Connected"),
      next: expect.stringContaining("document request"),
    });
    expect(resolve("waiting_for_start").tasks.join(" ")).toContain("Sandbox QR");
    expect(resolve("waiting_for_start").tasks.join(" ")).toContain("OBLIQ START QR");
    expect(resolve("active")).toMatchObject({
      step: 2,
      title: "WhatsApp Connected",
      progress: "Connection complete",
      next: expect.stringContaining("review and send"),
    });
  });
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
