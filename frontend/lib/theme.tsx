"use client";

import {createContext, useContext, useEffect, useState} from "react";

export type ThemePreference = "light" | "dark" | "system";
type AppliedTheme = "light" | "dark";
type ThemeContextValue = {theme: ThemePreference; appliedTheme: AppliedTheme; setTheme: (theme: ThemePreference) => void};

const ThemeContext = createContext<ThemeContextValue>({theme: "system", appliedTheme: "light", setTheme: () => undefined});

export function resolveAppliedTheme(theme: ThemePreference, systemDark: boolean): AppliedTheme {
  return theme === "system" ? (systemDark ? "dark" : "light") : theme;
}

function applyTheme(theme: ThemePreference): AppliedTheme {
  const applied = resolveAppliedTheme(theme, window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", applied === "dark");
  document.documentElement.dataset.theme = applied;
  document.documentElement.style.colorScheme = applied;
  return applied;
}

export function ThemeProvider({children}: {children: React.ReactNode}) {
  const [theme, setThemeState] = useState<ThemePreference>("system");
  const [appliedTheme, setAppliedTheme] = useState<AppliedTheme>("light");
  useEffect(() => {
    const stored = window.localStorage.getItem("obliq-theme");
    const initial: ThemePreference = stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const frame = window.requestAnimationFrame(() => {
      setThemeState(initial);
      setAppliedTheme(applyTheme(initial));
    });
    const listener = () => {
      if ((window.localStorage.getItem("obliq-theme") || "system") === "system") {
        setAppliedTheme(applyTheme("system"));
      }
    };
    media.addEventListener("change", listener);
    return () => {
      window.cancelAnimationFrame(frame);
      media.removeEventListener("change", listener);
    };
  }, []);
  function setTheme(next: ThemePreference) {
    window.localStorage.setItem("obliq-theme", next);
    setThemeState(next);
    setAppliedTheme(applyTheme(next));
  }
  return <ThemeContext.Provider value={{theme, appliedTheme, setTheme}}>{children}</ThemeContext.Provider>;
}

export function useTheme() { return useContext(ThemeContext); }

export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('obliq-theme')||'system';var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);document.documentElement.dataset.theme=d?'dark':'light';document.documentElement.style.colorScheme=d?'dark':'light'}catch(e){}})()`;
