"use client";

import Link from "next/link";
import {Menu, X} from "lucide-react";
import {useState} from "react";
import {ThemeToggle} from "@/components/ui/theme-toggle";

const items = [
  ["#workflow", "Workflow"],
  ["#capabilities", "Capabilities"],
  ["#control", "CA Control"],
];

export function LandingNavbar() {
  const [open, setOpen] = useState(false);
  return <header className="fixed inset-x-0 top-4 z-50 px-4">
    <nav className="mx-auto flex max-w-[1120px] items-center justify-between rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface)]/90 px-5 py-3 shadow-[var(--obliq-shadow)] backdrop-blur-xl">
      <Link href="/" className="text-xl font-black tracking-[-.06em]">OBLIQ</Link>
      <div className="hidden items-center gap-7 text-sm font-medium text-[var(--obliq-muted)] md:flex">
        {items.map(([href, label]) => <a key={href} href={href} className="transition hover:text-[var(--obliq-ink)]">{label}</a>)}
      </div>
      <div className="hidden items-center gap-2 md:flex">
        <ThemeToggle compact/>
        <Link href="/auth/login" className="obliq-focus rounded-full bg-[var(--obliq-action)] px-5 py-2.5 text-sm font-semibold text-[var(--obliq-action-ink)] transition hover:bg-[var(--obliq-action-hover)]">Sign in</Link>
      </div>
      <button type="button" className="obliq-focus rounded-full p-2 md:hidden" aria-label="Toggle navigation" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? <X size={20}/> : <Menu size={20}/>}</button>
    </nav>
    {open && <div className="mx-auto mt-2 grid max-w-[1120px] gap-2 rounded-[24px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-4 shadow-xl md:hidden">
      {items.map(([href, label]) => <a key={href} href={href} onClick={() => setOpen(false)} className="obliq-interactive rounded-xl px-3 py-2">{label}</a>)}
      <div className="mt-2 flex items-center gap-2"><ThemeToggle compact/><Link href="/auth/login" className="flex-1 rounded-full bg-[var(--obliq-action)] px-5 py-3 text-center text-sm font-semibold text-[var(--obliq-action-ink)]">Sign in</Link></div>
    </div>}
  </header>;
}
