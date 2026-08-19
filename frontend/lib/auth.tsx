"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export type AuthUser = { email: string; name?: string; role?: string };

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  demoMode: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginDemo: (role?: "admin" | "preparer" | "reviewer") => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<string>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const demoTokens = {
  admin: "demo-admin-token",
  preparer: "demo-preparer-token",
  reviewer: "demo-reviewer-token",
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";

  useEffect(() => {
    async function restore() {
      const stored = window.localStorage.getItem("obliq_access_token");
      const storedUser = window.localStorage.getItem("obliq_user");
      if (stored && storedUser) {
        setUser(JSON.parse(storedUser));
        setLoading(false);
        return;
      }
      const supabase = getSupabaseBrowserClient();
      if (supabase) {
        const { data } = await supabase.auth.getSession();
        if (data.session) {
          window.localStorage.setItem("obliq_access_token", data.session.access_token);
          const authUser = { email: data.session.user.email || "CA user" };
          window.localStorage.setItem("obliq_user", JSON.stringify(authUser));
          setUser(authUser);
        }
      }
      setLoading(false);
    }
    restore();
  }, []);

  const persist = useCallback((token: string, authUser: AuthUser) => {
    window.localStorage.setItem("obliq_access_token", token);
    window.localStorage.setItem("obliq_user", JSON.stringify(authUser));
    setUser(authUser);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) throw new Error("Supabase Auth is not configured. Use the demo account instead.");
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error || !data.session) throw new Error(error?.message || "Login failed");
    persist(data.session.access_token, { email: data.user.email || email });
  }, [persist]);

  const loginDemo = useCallback(async (role: "admin" | "preparer" | "reviewer" = "admin") => {
    persist(demoTokens[role], {
      email: role === "admin" ? "demo.admin@obliq.local" : `demo.${role}@obliq.local`,
      name: role === "admin" ? "Ananya Sharma" : role === "preparer" ? "Aman Verma" : "Priya Nair",
      role,
    });
  }, [persist]);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) throw new Error("Supabase Auth is not configured in this environment.");
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName } },
    });
    if (error) throw new Error(error.message);
    return data.session
      ? "Account created. Ask the firm admin to add this user to a firm."
      : "Account created. Check your email to confirm the address.";
  }, []);

  const logout = useCallback(async () => {
    const supabase = getSupabaseBrowserClient();
    if (supabase) await supabase.auth.signOut();
    window.localStorage.removeItem("obliq_access_token");
    window.localStorage.removeItem("obliq_user");
    setUser(null);
    router.push("/");
  }, [router]);

  const value = useMemo(() => ({ user, loading, demoMode, login, loginDemo, register, logout }), [user, loading, demoMode, login, loginDemo, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
