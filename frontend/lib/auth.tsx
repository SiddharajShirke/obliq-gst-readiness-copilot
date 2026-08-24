"use client";

import {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState} from "react";
import {useRouter} from "next/navigation";
import type {Session} from "@supabase/supabase-js";

import {
  buildRegistrationResult,
  clearLegacyAuthState,
  isMemoryDemoAuthEnabled,
  LEGACY_ACCESS_TOKEN_KEY,
  LEGACY_USER_KEY,
  type RegistrationResult,
} from "./auth-session";
import {
  buildEmailConfirmationOptions,
  getSupabaseBrowserClient,
  isSupabaseAuthConfigured,
  resolveAuthConfirmationUrl,
} from "./supabase";
import {queueWorkspaceBootstrap} from "./workspace-bootstrap";

export type AuthUser = {email: string; name?: string; role?: string};
type DemoRole = "admin" | "preparer" | "reviewer";
export type WorkspaceStatus = "idle" | "preparing" | "ready" | "error";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  workspaceStatus: WorkspaceStatus;
  workspaceError: string | null;
  demoMode: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginDemo: (role?: DemoRole) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<RegistrationResult>;
  resendConfirmation: (email: string) => Promise<void>;
  retryWorkspaceBootstrap: () => void;
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
  const [workspaceStatus, setWorkspaceStatus] = useState<WorkspaceStatus>("idle");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const activeSessionRef = useRef<Session | null>(null);
  const bootstrapUserRef = useRef<string | null>(null);
  const readyUserRef = useRef<string | null>(null);
  const router = useRouter();
  const demoMode = isMemoryDemoAuthEnabled(
    process.env.NEXT_PUBLIC_DEMO_MODE,
    isSupabaseAuthConfigured(),
  );

  const prepareWorkspace = useCallback((session: Session | null, force = false) => {
    activeSessionRef.current = session;
    if (!session) {
      bootstrapUserRef.current = null;
      readyUserRef.current = null;
      setWorkspaceStatus("idle");
      setWorkspaceError(null);
      return;
    }

    const userId = session.user.id;
    if (!force && readyUserRef.current === userId) {
      setWorkspaceStatus("ready");
      return;
    }
    if (bootstrapUserRef.current === userId) return;

    bootstrapUserRef.current = userId;
    setWorkspaceStatus("preparing");
    setWorkspaceError(null);
    queueWorkspaceBootstrap(session.access_token, {
      onReady: () => {
        if (activeSessionRef.current?.user.id !== userId) return;
        bootstrapUserRef.current = null;
        readyUserRef.current = userId;
        setWorkspaceStatus("ready");
      },
      onError: error => {
        if (activeSessionRef.current?.user.id !== userId) return;
        bootstrapUserRef.current = null;
        setWorkspaceStatus("error");
        setWorkspaceError(error.message);
      },
    });
  }, []);

  const retryWorkspaceBootstrap = useCallback(() => {
    if (activeSessionRef.current) prepareWorkspace(activeSessionRef.current, true);
  }, [prepareWorkspace]);

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    const invalidate = () => {
      setUser(null);
      prepareWorkspace(null);
      router.replace("/auth/login");
    };
    window.addEventListener("obliq:auth-invalid", invalidate);

    if (supabase) {
      clearLegacyAuthState(window.localStorage);
      void supabase.auth.getSession()
        .then(({data}) => {
          setUser(sessionUser(data.session));
          prepareWorkspace(data.session);
        })
        .catch(() => {
          setUser(null);
          prepareWorkspace(null);
        })
        .finally(() => setLoading(false));
      const {data: listener} = supabase.auth.onAuthStateChange((_event, session) => {
        setUser(sessionUser(session));
        prepareWorkspace(session);
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
      setWorkspaceStatus(restoredUser ? "ready" : "idle");
      setLoading(false);
    });
    return () => window.removeEventListener("obliq:auth-invalid", invalidate);
  }, [demoMode, prepareWorkspace, router]);

  const login = useCallback(async (email: string, password: string) => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) throw new Error("Supabase Auth is not configured.");
    clearLegacyAuthState(window.localStorage);
    const {data, error} = await supabase.auth.signInWithPassword({email, password});
    if (error || !data.session) throw new Error(error?.message || "Login failed");
    setUser(sessionUser(data.session));
    prepareWorkspace(data.session);
  }, [prepareWorkspace]);

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
    setWorkspaceStatus("ready");
  }, [demoMode]);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) throw new Error("Supabase Auth is not configured in this environment.");
    const {data, error} = await supabase.auth.signUp({
      email,
      password,
      options: buildEmailConfirmationOptions(fullName, window.location.origin),
    });
    if (error) throw new Error(error.message);
    if (data.session) {
      setUser(sessionUser(data.session));
      prepareWorkspace(data.session);
    }
    return buildRegistrationResult(Boolean(data.session));
  }, [prepareWorkspace]);

  const resendConfirmation = useCallback(async (email: string) => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) throw new Error("Supabase Auth is not configured in this environment.");
    const {error} = await supabase.auth.resend({
      type: "signup",
      email,
      options: {
        emailRedirectTo: resolveAuthConfirmationUrl({currentOrigin: window.location.origin}),
      },
    });
    if (error) throw new Error(error.message);
  }, []);

  const logout = useCallback(async () => {
    const supabase = getSupabaseBrowserClient();
    if (supabase) await supabase.auth.signOut();
    clearLegacyAuthState(window.localStorage);
    setUser(null);
    prepareWorkspace(null);
    router.push("/");
  }, [prepareWorkspace, router]);

  const value = useMemo(
    () => ({
      user,
      loading,
      workspaceStatus,
      workspaceError,
      demoMode,
      login,
      loginDemo,
      register,
      resendConfirmation,
      retryWorkspaceBootstrap,
      logout,
    }),
    [
      user,
      loading,
      workspaceStatus,
      workspaceError,
      demoMode,
      login,
      loginDemo,
      register,
      resendConfirmation,
      retryWorkspaceBootstrap,
      logout,
    ],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
