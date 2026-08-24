import {describe, expect, it} from "vitest";

import * as SupabaseConfig from "./supabase";

type AuthRedirectHelpers = {
  resolveAuthConfirmationUrl: (input: {
    configuredSiteUrl?: string;
    currentOrigin?: string;
  }) => string;
  buildEmailConfirmationOptions: (fullName: string, currentOrigin?: string) => {
    data: {full_name: string};
    emailRedirectTo: string;
  };
  parseAuthConfirmationError: (hash: string) => {
    code: string | null;
    description: string | null;
    expired: boolean;
  };
};

function helpers(): AuthRedirectHelpers {
  const candidate = SupabaseConfig as typeof SupabaseConfig & Partial<AuthRedirectHelpers>;
  expect(typeof candidate.resolveAuthConfirmationUrl).toBe("function");
  expect(typeof candidate.buildEmailConfirmationOptions).toBe("function");
  expect(typeof candidate.parseAuthConfirmationError).toBe("function");
  return candidate as typeof SupabaseConfig & AuthRedirectHelpers;
}

describe("Supabase email confirmation redirects", () => {
  it("uses the configured production site and never falls back to localhost", () => {
    expect(helpers().resolveAuthConfirmationUrl({
      configuredSiteUrl: "https://obliq-gst-readiness-copilot.vercel.app/",
      currentOrigin: "http://localhost:3000",
    })).toBe("https://obliq-gst-readiness-copilot.vercel.app/auth/confirm");
  });

  it("uses the browser origin for local and preview environments when no site is configured", () => {
    expect(helpers().resolveAuthConfirmationUrl({
      currentOrigin: "https://preview-obliq.vercel.app",
    })).toBe("https://preview-obliq.vercel.app/auth/confirm");
  });

  it("builds signup options that include the explicit confirmation callback", () => {
    expect(helpers().buildEmailConfirmationOptions(
      "Asha Mehta",
      "https://obliq-gst-readiness-copilot.vercel.app",
    )).toEqual({
      data: {full_name: "Asha Mehta"},
      emailRedirectTo: "https://obliq-gst-readiness-copilot.vercel.app/auth/confirm",
    });
  });

  it("recognizes Supabase expired confirmation errors from the URL fragment", () => {
    expect(helpers().parseAuthConfirmationError(
      "#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired",
    )).toEqual({
      code: "otp_expired",
      description: "Email link is invalid or has expired",
      expired: true,
    });
  });
});
