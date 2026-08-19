const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("obliq_access_token");
}

export function resolveAssetUrl(value: string): string {
  if (!value || value.startsWith("http")) return value;
  const origin = API_BASE.replace(/\/api\/v1\/?$/, "");
  return `${origin}${value.startsWith("/") ? "" : "/"}${value}`;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (authenticated) {
    const token = getStoredToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || body.message || detail;
    } catch {
      detail = (await response.text()) || detail;
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  return (contentType.includes("application/json") ? response.json() : response.text()) as Promise<T>;
}

export { API_BASE };
