"use client";

import {Monitor, Moon, Sun} from "lucide-react";
import {useTheme, type ThemePreference} from "../../lib/theme";

const order: ThemePreference[] = ["light", "dark", "system"];
const labels: Record<ThemePreference, string> = {light: "Light", dark: "Dark", system: "System"};

export function ThemeToggle({compact = false}: {compact?: boolean}) {
  const {theme, setTheme} = useTheme();
  const next = order[(order.indexOf(theme) + 1) % order.length];
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return <button type="button" aria-label={`Change color theme. Current: ${labels[theme]}. Next: ${labels[next]}`} title={`Theme: ${labels[theme]}`} onClick={() => setTheme(next)} className="obliq-focus inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-3 py-2 text-xs font-semibold text-[var(--obliq-ink)] transition hover:bg-[var(--obliq-surface-raised)] dark:hover:bg-[var(--obliq-interactive-hover)]"><Icon size={16}/>{!compact && <>Theme: {labels[theme]}</>}</button>;
}
