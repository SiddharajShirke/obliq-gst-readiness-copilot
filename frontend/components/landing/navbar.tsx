"use client";

import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useState } from "react";

export function LandingNavbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="fixed inset-x-0 top-4 z-50 px-4">
      <nav className="mx-auto flex max-w-[1120px] items-center justify-between rounded-full border border-black/5 bg-white/88 px-5 py-3 shadow-[0_14px_45px_rgba(25,21,21,.09)] backdrop-blur-xl">
        <Link href="/" className="text-xl font-black tracking-[-.06em]">OBLIQ</Link>
        <div className="hidden items-center gap-7 text-sm font-medium text-[#625d5a] md:flex">
          <a href="#workflow" className="transition hover:text-black">Workflow</a>
          <a href="#intelligence" className="transition hover:text-black">Document AI</a>
          <a href="#rag" className="transition hover:text-black">RAG Assistant</a>
          <a href="#safety" className="transition hover:text-black">Human Review</a>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <Link href="/auth/login" className="rounded-full px-4 py-2 text-sm font-semibold">Sign in</Link>
          <Link href="/auth/login?demo=1" className="rounded-full bg-[#191515] px-5 py-2.5 text-sm font-semibold text-white">Open demo</Link>
        </div>
        <button className="rounded-full p-2 md:hidden" aria-label="Toggle navigation" onClick={() => setOpen((value) => !value)}>{open ? <X size={20} /> : <Menu size={20} />}</button>
      </nav>
      {open && (
        <div className="mx-auto mt-2 grid max-w-[1120px] gap-2 rounded-[24px] border border-black/5 bg-white p-4 shadow-xl md:hidden">
          <a href="#workflow" onClick={() => setOpen(false)} className="rounded-xl px-3 py-2">Workflow</a>
          <a href="#intelligence" onClick={() => setOpen(false)} className="rounded-xl px-3 py-2">Document AI</a>
          <a href="#rag" onClick={() => setOpen(false)} className="rounded-xl px-3 py-2">RAG Assistant</a>
          <Link href="/auth/login?demo=1" className="mt-2 rounded-full bg-[#191515] px-5 py-3 text-center text-sm font-semibold text-white">Open demo</Link>
        </div>
      )}
    </header>
  );
}
