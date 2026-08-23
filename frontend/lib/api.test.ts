import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

const {getSupabaseBrowserClient} = vi.hoisted(() => ({
  getSupabaseBrowserClient: vi.fn(),
}));

vi.mock("./supabase", () => ({getSupabaseBrowserClient}));

import {apiFetch} from "./api";
import * as apiModule from "./api";

class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

function okJson(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: {"Content-Type": "application/json"},
  });
}

describe("apiFetch Supabase bearer handling", () => {
  let storage: MemoryStorage;

  beforeEach(() => {
    storage = new MemoryStorage();
    vi.stubGlobal("window", {
      localStorage: storage,
      dispatchEvent: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("uses the current Supabase access token instead of a stale demo token", async () => {
    storage.setItem("obliq_access_token", "demo-admin-token");
    getSupabaseBrowserClient.mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: {session: {access_token: "header.payload.signature"}},
        }),
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/clients");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer header.payload.signature");
  });

  it("omits Authorization when Supabase has no authenticated session", async () => {
    getSupabaseBrowserClient.mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({data: {session: null}}),
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/clients");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.has("Authorization")).toBe(false);
  });

  it("refreshes once after 401 and retries with the refreshed JWT", async () => {
    getSupabaseBrowserClient.mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: {session: {access_token: "old.payload.signature"}},
        }),
        refreshSession: vi.fn().mockResolvedValue({
          data: {session: {access_token: "new.payload.signature"}},
          error: null,
        }),
      },
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({detail: "Unauthorized"}), {
        status: 401,
        headers: {"Content-Type": "application/json"},
      }))
      .mockResolvedValueOnce(okJson({ok: true}));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch<{ok: boolean}>("/clients")).resolves.toEqual({ok: true});
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const retryHeaders = fetchMock.mock.calls[1][1].headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer new.payload.signature");
  });

  it("clears stale legacy auth after an unrecoverable 401", async () => {
    storage.setItem("obliq_access_token", "demo-admin-token");
    storage.setItem("obliq_user", "{}");
    getSupabaseBrowserClient.mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({data: {session: null}}),
        refreshSession: vi.fn().mockResolvedValue({data: {session: null}, error: null}),
        signOut: vi.fn().mockResolvedValue({error: null}),
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({detail: "Unauthorized"}), {
        status: 401,
        headers: {"Content-Type": "application/json"},
      }),
    ));

    await expect(apiFetch("/clients")).rejects.toMatchObject({status: 401});
    expect(storage.getItem("obliq_access_token")).toBeNull();
    expect(storage.getItem("obliq_user")).toBeNull();
  });
});

describe("export download selection", () => {
  it("prefers one archive URL over browser-blocked multi-file downloads", () => {
    expect(apiModule).toHaveProperty("preferredExportUrls");
    const select = (apiModule as typeof apiModule & {
      preferredExportUrls: (files: Record<string, string>, packKey: string) => string[];
    }).preferredExportUrls;
    expect(select({report: "report-url", export_pack_zip: "pack-url"}, "export_pack_zip"))
      .toEqual(["pack-url"]);
    expect(select({report: "report-url"}, "export_pack_zip")).toEqual(["report-url"]);
  });
});
