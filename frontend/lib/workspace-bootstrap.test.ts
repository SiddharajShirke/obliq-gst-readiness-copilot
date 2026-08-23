import {describe, expect, it, vi} from "vitest";

import {bootstrapAuthenticatedWorkspace} from "./workspace-bootstrap";
import * as workspaceBootstrap from "./workspace-bootstrap";

describe("workspace bootstrap", () => {
  it("uses the authenticated session once and returns the tenant demo workspace", async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      firm_id: "firm-id",
      demo_client_id: "client-id",
      demo_application_id: "application-id",
    }), {status: 200, headers: {"content-type": "application/json"}}));

    const result = await bootstrapAuthenticatedWorkspace("access-token", request);

    expect(request).toHaveBeenCalledWith(expect.stringMatching(/\/onboarding\/bootstrap$/), {
      method: "POST",
      headers: {Authorization: "Bearer access-token"},
    });
    expect(result.demo_client_id).toBe("client-id");
  });

  it("surfaces bootstrap failure instead of exposing a half-created dashboard", async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "Workspace bootstrap failed",
    }), {status: 500, headers: {"content-type": "application/json"}}));

    await expect(bootstrapAuthenticatedWorkspace("access-token", request))
      .rejects.toThrow("Workspace bootstrap failed");
  });

  it("preserves an authenticated session during a temporary backend outage", async () => {
    const attempt = (workspaceBootstrap as typeof workspaceBootstrap & {
      tryBootstrapAuthenticatedWorkspace?: (
        accessToken: string,
        request: typeof fetch,
      ) => Promise<unknown>;
    }).tryBootstrapAuthenticatedWorkspace;
    expect(attempt).toBeTypeOf("function");
    if (!attempt) return;

    const request = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(attempt("access-token", request)).resolves.toBeNull();
  });
});
