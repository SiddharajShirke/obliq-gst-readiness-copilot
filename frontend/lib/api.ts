import {
  clearLegacyAuthState,
  isMemoryDemoAuthEnabled,
  readLegacyDemoToken,
} from "./auth-session";
import {getSupabaseBrowserClient} from "./supabase";

const DEFAULT_API_BASE = "http://localhost:8000/api/v1";

function isUnsafeNetworkHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  if (
    host === "localhost"
    || host.endsWith(".localhost")
    || host.endsWith(".local")
    || host === "host.docker.internal"
    || host === "0.0.0.0"
    || host === "::1"
    || host.startsWith("127.")
    || host.startsWith("10.")
    || host.startsWith("192.168.")
    || host.startsWith("169.254.")
  ) return true;
  const parts = host.split(".").map(Number);
  return parts.length === 4
    && parts.every(part => Number.isInteger(part) && part >= 0 && part <= 255)
    && parts[0] === 172
    && parts[1] >= 16
    && parts[1] <= 31;
}

function isHostedPage(runtimeOrigin?: string): boolean {
  if (!runtimeOrigin) return false;
  try {
    const origin = new URL(runtimeOrigin);
    return !isUnsafeNetworkHost(origin.hostname);
  } catch {
    return false;
  }
}

export function resolveApiBaseUrl(
  configured = process.env.NEXT_PUBLIC_API_BASE_URL,
  runtimeOrigin = typeof window !== "undefined" ? window.location?.origin : undefined,
): string {
  const base = configured?.trim().replace(/\/+$/, "") || DEFAULT_API_BASE;
  const normalized = /\/api\/v1$/i.test(base) ? base : `${base}/api/v1`;
  if (isHostedPage(runtimeOrigin)) {
    try {
      const apiUrl = new URL(normalized);
      if (apiUrl.protocol !== "https:" || isUnsafeNetworkHost(apiUrl.hostname)) {
        throw new Error("unsafe host");
      }
    } catch {
      throw new Error(
        "Production API configuration is missing or points to a local/private server.",
      );
    }
  }
  return normalized;
}

const API_BASE = resolveApiBaseUrl();

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

export function preferredExportUrls(
  files: Record<string, string>,
  archiveKey: string,
): string[] {
  const archiveUrl = files[archiveKey];
  return archiveUrl ? [archiveUrl] : Object.values(files);
}

export {API_BASE};
