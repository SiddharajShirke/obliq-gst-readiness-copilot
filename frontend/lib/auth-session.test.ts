import {describe, expect, it} from "vitest";

import {
  buildRegistrationResult,
  clearLegacyAuthState,
  isMemoryDemoAuthEnabled,
} from "./auth-session";

class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

describe("Supabase authentication mode", () => {
  it("routes an immediately authenticated registration to the dashboard", () => {
    expect(buildRegistrationResult(true)).toEqual({
      authenticated: true,
      destination: "/dashboard",
      message: "Account created. Your secure OBLIQ workspace is being prepared.",
    });
  });

  it("retains the confirmation fallback when Supabase returns no session", () => {
    expect(buildRegistrationResult(false)).toEqual({
      authenticated: false,
      destination: null,
      message: "Account created. Check your email to confirm the address.",
    });
  });

  it("never enables fake demo tokens when Supabase is configured", () => {
    expect(isMemoryDemoAuthEnabled("true", true)).toBe(false);
    expect(isMemoryDemoAuthEnabled("false", true)).toBe(false);
    expect(isMemoryDemoAuthEnabled("true", false)).toBe(true);
  });

  it("clears only legacy OBLIQ auth cache and preserves the Supabase session", () => {
    const storage = new MemoryStorage();
    storage.setItem("obliq_access_token", "demo-admin-token");
    storage.setItem("obliq_user", JSON.stringify({email: "demo.admin@obliq.local"}));
    storage.setItem("sb-project-auth-token", "managed-by-supabase-js");

    clearLegacyAuthState(storage);

    expect(storage.getItem("obliq_access_token")).toBeNull();
    expect(storage.getItem("obliq_user")).toBeNull();
    expect(storage.getItem("sb-project-auth-token")).toBe("managed-by-supabase-js");
  });
});
