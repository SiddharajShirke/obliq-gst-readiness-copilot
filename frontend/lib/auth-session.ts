export const LEGACY_ACCESS_TOKEN_KEY = "obliq_access_token";
export const LEGACY_USER_KEY = "obliq_user";

export type RegistrationResult = {
  authenticated: boolean;
  destination: "/dashboard" | null;
  message: string;
};

export function buildRegistrationResult(authenticated: boolean): RegistrationResult {
  return authenticated
    ? {
        authenticated: true,
        destination: "/dashboard",
        message: "Account created. Your secure OBLIQ workspace is being prepared.",
      }
    : {
        authenticated: false,
        destination: null,
        message: "Account created. Check your email to confirm the address.",
      };
}

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
