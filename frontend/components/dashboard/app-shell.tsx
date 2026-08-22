"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpen, BriefcaseBusiness, FileClock, LayoutDashboard, LogOut, Menu, MessageCircleMore, Settings, Users, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Loading } from "@/components/ui/loading";
import {ThemeToggle} from "@/components/ui/theme-toggle";

const links = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/clients", label: "Clients", icon: Users },
  { href: "/dashboard?view=gst", label: "GST Work", icon: BriefcaseBusiness },
  { href: "/dashboard/alerts", label: "Alerts", icon: FileClock },
  { href: "/dashboard/knowledge", label: "Knowledge Base", icon: BookOpen },
  { href: "/dashboard/integrations/whatsapp", label: "WhatsApp", icon: MessageCircleMore },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

function SidebarContent({ close }: { close?: () => void }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  return <div className="flex h-full flex-col">
    <div className="flex h-20 items-center justify-between border-b border-[var(--obliq-border)] px-5"><Link href="/dashboard" className="text-xl font-black tracking-[-.06em]">OBLIQ</Link>{close && <button onClick={close} className="obliq-interactive obliq-focus rounded-full p-2"><X size={19}/></button>}</div>
    <nav className="grid gap-1 p-3">{links.map(({href,label,icon:Icon})=>{const active=href==="/dashboard"?pathname==="/dashboard":pathname.startsWith(href.split("?")[0]);return <Link key={label} onClick={close} href={href} aria-current={active?"page":undefined} className={`obliq-focus flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${active?"obliq-nav-selected":"obliq-interactive"}`}><Icon size={18}/>{label}</Link>})}</nav>
    <div className="mt-auto border-t border-[var(--obliq-border)] p-4"><div className="mb-3 rounded-2xl bg-[var(--obliq-surface-raised)] p-3"><p className="truncate text-sm font-semibold">{user?.name || "CA user"}</p><p className="truncate text-xs text-[var(--obliq-muted)]">{user?.email}</p></div><button onClick={logout} className="obliq-focus flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[var(--obliq-muted)] hover:bg-[var(--obliq-danger-soft)] hover:text-[var(--obliq-danger-ink)]"><LogOut size={18}/>Log out</button></div>
  </div>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [open,setOpen]=useState(false);
  useEffect(()=>{if(!loading&&!user) router.replace("/auth/login");},[loading,user,router]);
  if (loading || !user) return <Loading label="Opening your OBLIQ workspace…"/>;
  return <div className="min-h-screen bg-[var(--obliq-canvas)] text-[var(--obliq-ink)] lg:grid lg:grid-cols-[248px_1fr]">
    <aside className="fixed inset-y-0 left-0 hidden w-[248px] border-r border-[var(--obliq-border)] bg-[var(--obliq-surface)] lg:block"><SidebarContent/></aside>
    {open && <div className="fixed inset-0 z-50 bg-black/50 lg:hidden" onClick={()=>setOpen(false)}><aside onClick={(event)=>event.stopPropagation()} className="h-full w-[280px] bg-[var(--obliq-surface)]"><SidebarContent close={()=>setOpen(false)}/></aside></div>}
    <div className="lg:col-start-2"><header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[var(--obliq-border)] bg-[var(--obliq-canvas)] px-4 backdrop-blur-lg lg:px-8"><button onClick={()=>setOpen(true)} className="rounded-full p-2 lg:hidden" aria-label="Open menu"><Menu size={21}/></button><div className="hidden text-sm text-[var(--obliq-muted)] lg:block">Sharma & Associates · GST Readiness Workspace</div><div className="flex items-center gap-2"><ThemeToggle/><span className="hidden rounded-full border border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-4 py-2 text-xs font-semibold sm:inline">Vonage Sandbox</span></div></header><main className="mx-auto max-w-[1500px] p-4 sm:p-6 lg:p-8">{children}</main></div>
  </div>;
}
