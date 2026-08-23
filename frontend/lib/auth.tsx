"use client";

import {createContext, useCallback, useContext, useEffect, useMemo, useState} from "react";
import {useRouter} from "next/navigation";
import type {Session} from "@supabase/supabase-js";

import {
  clearLegacyAuthState,
  isMemoryDemoAuthEnabled,
  LEGACY_ACCESS_TOKEN_KEY,
  LEGACY_USER_KEY,
} from "./auth-session";
import {
  getSupabaseBrowserClient,
  isSupabaseAuthConfigured,
} from "./supabase";
import {bootstrapAuthenticatedWorkspace} from "./workspace-bootstrap";

export type AuthUser = {email: string; name?: string; role?: string};
type DemoRole = "admin" | "preparer" | "reviewer";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  demoMode: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginDemo: (role?: DemoRole) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<string>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const demoTokens: Record<DemoRole, string> = {
  admin: "demo-admin-token",
  preparer: "demo-preparer-token",
  reviewer: "demo-reviewer-token",
};

function sessionUser(session: Session | null): AuthUser | null {
  if (!session) return null;
  return {
    email: session.user.email || "CA user",
    name: session.user.user_metadata?.full_name,
  };
}

export function AuthProvider({children}: {children: React.ReactNode}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const demoMode = isMemoryDemoAuthEnabled(
    process.env.NEXT_PUBLIC_DEMO_MODE,
    isSupabaseAuthConfigured(),
  );

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    const invalidate = () => {
      setUser(null);
      router.replace("/auth/login");
    };
    window.addEventListener("obliq:auth-invalid", invalidate);

    if (supabase) {
      clearLegacyAuthState(window.localStorage);
      void supabase.auth.getSession()
        .then(async ({data}) => {
          if (data.session) {
            await bootstrapAuthenticatedWorkspace(data.session.access_token);
          }
          setUser(sessionUser(data.session));
        })
        .catch(() => setUser(null))
        .finally(() => setLoading(false));
      const {data: listener} = supabase.auth.onAuthStateChange((_event, session) => {
        void (async () => {
          if (session) {
            await bootstrapAuthenticatedWorkspace(session.access_token);
          }
          setUser(sessionUser(session));
        })().catch(() => setUser(null));
      });
      return () => {
        listener.subscription.unsubscribe();
        window.removeEventListener("obliq:auth-invalid", invalidate);
      };
    }

    let restoredUser: AuthUser | null = null;
    if (demoMode) {
      const storedUser = window.localStorage.getItem(LEGACY_USER_KEY);
      const storedToken = window.localStorage.getItem(LEGACY_ACCESS_TOKEN_KEY);
      if (storedUser && Object.values(demoTokens).includes(storedToken || "")) {
        try {
          restoredUser = JSON.parse(storedUser) as AuthUser;
        } catch {
          clearLegacyAuthState(window.localStorage);
        }
      }
    } else {
      clearLegacyAuthState(window.localStorage);
    }
    queueMicrotask(() => {
      setUser(restoredUser);
      setLoading(false);
    });
    return () => window.removeEventListener("obliq:auth-invalid", invalidate);
  }, [demoMode, router]);

  const login = useCallback(async (email: string, password: string) => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) throw new Error("Supabase Auth is not configured.");
    clearLegacyAuthState(window.localStorage);
    const {data, error} = await supabase.auth.signInWithPassword({email, password});
    if (error || !data.session) throw new Error(error?.message || "Login failed");
    await bootstrapAuthenticatedWorkspace(data.session.access_token);
    setUser(sessionUser(data.session));
  }, []);

  const loginDemo = useCallback(async (role: DemoRole = "admin") => {
    if (!demoMode) {
      throw new Error("Demo-token login is unavailable when Supabase Auth is configured.");
    }
    const authUser = {
      email: role === "admin" ? "demo.admin@obliq.local" : `demo.${role}@obliq.local`,
      name: role === "admin" ? "Ananya Sharma" : role === "preparer" ? "Aman Verma" : "Priya Nair",
      role,
    };
    window.localStorage.setItem(LEGACY_ACCESS_TOKEN_KEY, demoTokens[role]);
    window.localStorage.setItem(LEGACY_USER_KEY, JSON.stringify(authUser));
    setUser(authUser);
  }, [demoMode]);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) throw new Error("Supabase Auth is not configured in this environment.");
    const {data, error} = await supabase.auth.signUp({
      email,
      password,
      options: {data: {full_name: fullName}},
    });
    if (error) throw new Error(error.message);
    if (data.session) {
      await bootstrapAuthenticatedWorkspace(data.session.access_token);
    }
    return data.session
      ? "Account created. Your OBLIQ workspace is ready."
      : "Account created. Check your email to confirm the address.";
  }, []);

  const logout = useCallback(async () => {
    const supabase = getSupabaseBrowserClient();
    if (supabase) await supabase.auth.signOut();
    clearLegacyAuthState(window.localStorage);
    setUser(null);
    router.push("/");
  }, [router]);

  const value = useMemo(
    () => ({user, loading, demoMode, login, loginDemo, register, logout}),
    [user, loading, demoMode, login, loginDemo, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
