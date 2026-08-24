import { createClient, SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

function validHttpOrigin(value?: string): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim().startsWith("http") ? value.trim() : `https://${value.trim()}`);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    return url.origin;
  } catch {
    return null;
  }
}

export function resolveAuthConfirmationUrl({
  configuredSiteUrl = process.env.NEXT_PUBLIC_SITE_URL,
  currentOrigin,
}: {
  configuredSiteUrl?: string;
  currentOrigin?: string;
} = {}): string {
  const origin = validHttpOrigin(configuredSiteUrl)
    ?? validHttpOrigin(currentOrigin)
    ?? "http://localhost:3000";
  return `${origin}/auth/confirm`;
}

export function buildEmailConfirmationOptions(fullName: string, currentOrigin?: string) {
  return {
    data: {full_name: fullName},
    emailRedirectTo: resolveAuthConfirmationUrl({currentOrigin}),
  };
}

export function parseAuthConfirmationError(hash: string): {
  code: string | null;
  description: string | null;
  expired: boolean;
} {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const code = params.get("error_code");
  const description = params.get("error_description");
  return {
    code,
    description,
    expired: code === "otp_expired" || /expired|invalid/i.test(description ?? ""),
  };
}

export function isSupabaseAuthConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL
    && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );
}

export function getSupabaseBrowserClient(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!isSupabaseAuthConfigured() || !url || !anonKey) return null;
  if (!client) client = createClient(url, anonKey);
  return client;
}
