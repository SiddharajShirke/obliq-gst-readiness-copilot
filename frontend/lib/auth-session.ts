export const LEGACY_ACCESS_TOKEN_KEY = "obliq_access_token";
export const LEGACY_USER_KEY = "obliq_user";

type StorageLike = Pick<Storage, "getItem" | "removeItem">;

const DEMO_TOKENS = new Set([
  "demo-admin-token",
  "demo-preparer-token",
  "demo-reviewer-token",
]);

export function isMemoryDemoAuthEnabled(
  demoFlag: string | undefined,
  supabaseConfigured: boolean,
): boolean {
  return demoFlag !== "false" && !supabaseConfigured;
}

export function clearLegacyAuthState(storage: StorageLike): void {
  storage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
  storage.removeItem(LEGACY_USER_KEY);
}

export function readLegacyDemoToken(
  storage: StorageLike,
  enabled: boolean,
): string | null {
  if (!enabled) return null;
  const token = storage.getItem(LEGACY_ACCESS_TOKEN_KEY);
  return token && DEMO_TOKENS.has(token) ? token : null;
}
