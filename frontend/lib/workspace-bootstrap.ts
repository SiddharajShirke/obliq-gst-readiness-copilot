import {API_BASE} from "./api";

export type WorkspaceBootstrap = {
  firm_id: string;
  demo_client_id: string;
  demo_application_id: string;
};

export async function bootstrapAuthenticatedWorkspace(
  accessToken: string,
  request: typeof fetch = fetch,
): Promise<WorkspaceBootstrap> {
  const response = await request(`${API_BASE}/onboarding/bootstrap`, {
    method: "POST",
    headers: {Authorization: `Bearer ${accessToken}`},
  });
  if (!response.ok) {
    let detail = `Workspace setup failed (${response.status})`;
    try {
      const body = await response.json() as {detail?: string};
      detail = body.detail || detail;
    } catch {
      // Preserve the safe status-based message when the server did not return JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<WorkspaceBootstrap>;
}
