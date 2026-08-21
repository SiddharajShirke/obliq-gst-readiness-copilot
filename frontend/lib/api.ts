import {
  clearLegacyAuthState,
  isMemoryDemoAuthEnabled,
  readLegacyDemoToken,
} from "./auth-session";
import {getSupabaseBrowserClient} from "./supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export async function getAccessToken(): Promise<string | null> {
  const supabase = getSupabaseBrowserClient();
  const storage = browserStorage();
  if (supabase) {
    if (storage) clearLegacyAuthState(storage);
    const {data} = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }
  if (!storage) return null;
  return readLegacyDemoToken(
    storage,
    isMemoryDemoAuthEnabled(process.env.NEXT_PUBLIC_DEMO_MODE, false),
  );
}

export function resolveAssetUrl(value: string): string {
  if (!value || value.startsWith("http")) return value;
  const origin = API_BASE.replace(/\/api\/v1\/?$/, "");
  return `${origin}${value.startsWith("/") ? "" : "/"}${value}`;
}

function requestHeaders(options: RequestInit, token: string | null): Headers {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  else headers.delete("Authorization");
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

async function sendRequest(
  path: string,
  options: RequestInit,
  token: string | null,
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: requestHeaders(options, token),
    cache: "no-store",
  });
}

async function invalidateBrowserAuth(): Promise<void> {
  const storage = browserStorage();
  if (storage) clearLegacyAuthState(storage);
  const supabase = getSupabaseBrowserClient();
  if (supabase) await supabase.auth.signOut().catch(() => undefined);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("obliq:auth-invalid"));
  }
}

async function responseDetail(response: Response): Promise<string> {
  let detail = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    detail = body.detail || body.message || detail;
  } catch {
    detail = (await response.text()) || detail;
  }
  return detail;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
): Promise<T> {
  let token = authenticated ? await getAccessToken() : null;
  let response = await sendRequest(path, options, token);

  if (authenticated && response.status === 401) {
    const supabase = getSupabaseBrowserClient();
    if (supabase) {
      const {data, error} = await supabase.auth.refreshSession();
      const refreshed = error ? null : data.session?.access_token ?? null;
      if (refreshed) {
        token = refreshed;
        response = await sendRequest(path, options, token);
      }
    }
    if (response.status === 401) await invalidateBrowserAuth();
  }

  if (!response.ok) {
    throw new ApiError(await responseDetail(response), response.status);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  return (contentType.includes("application/json")
    ? response.json()
    : response.text()) as Promise<T>;
}

export {API_BASE};
