"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Eye, EyeOff, FileCheck2, MessageCircleMore, ScanText } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, loginDemo, user } = useAuth();
  const router=useRouter();
  const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [show,setShow]=useState(false); const [busy,setBusy]=useState(false);
  useEffect(()=>{if(user) router.replace("/dashboard");},[user,router]);
  useEffect(()=>{if(typeof window!=="undefined"&&new URLSearchParams(window.location.search).get("demo")==="1"&&!user){loginDemo().then(()=>router.replace("/dashboard"));}},[user,loginDemo,router]);
  async function submit(event:FormEvent){event.preventDefault();setBusy(true);try{await login(email,password);router.push("/dashboard");}catch(error){toast.error(error instanceof Error?error.message:"Login failed");}finally{setBusy(false)}}
  async function demo(role:"admin"|"preparer"|"reviewer"="admin"){setBusy(true);await loginDemo(role);router.push("/dashboard");}
  return <main className="min-h-screen bg-[#f8f7f5] p-3 sm:p-6"><div className="mx-auto grid min-h-[calc(100vh-48px)] max-w-[1180px] overflow-hidden rounded-[32px] border border-[#e5e2de] bg-white shadow-[0_28px_90px_rgba(25,21,21,.10)] lg:grid-cols-[1.05fr_.95fr]">
    <section className="relative hidden overflow-hidden bg-[#a4c5e5] p-12 lg:block"><Link href="/" className="text-2xl font-black tracking-[-.06em]">OBLIQ</Link><h1 className="mt-20 max-w-lg text-5xl font-bold leading-[1.02] tracking-[-.05em]">GST preparation begins before the filing portal.</h1><p className="mt-5 max-w-md leading-7 text-[#413d3a]">Collect, extract, reconcile and review every client in one controlled workspace.</p><div className="absolute inset-x-8 bottom-8 grid gap-3 sm:grid-cols-3">{[{icon:MessageCircleMore,label:"Collect"},{icon:ScanText,label:"Extract"},{icon:FileCheck2,label:"Review"}].map(({icon:Icon,label})=><div key={label} className="rounded-[20px] border border-white/50 bg-white/55 p-4 backdrop-blur"><Icon size={20}/><p className="mt-6 text-sm font-semibold">{label}</p></div>)}</div></section>
    <section className="flex items-center justify-center p-6 sm:p-12"><div className="w-full max-w-md"><Link href="/" className="text-xl font-black tracking-[-.06em] lg:hidden">OBLIQ</Link><p className="mt-12 text-xs font-bold tracking-[.15em] text-[#477ca8] lg:mt-0">WELCOME BACK</p><h2 className="mt-3 text-4xl font-bold tracking-[-.045em]">Sign in to your CA workspace.</h2><p className="mt-3 text-sm leading-6 text-[#6b6562]">Use Supabase email/password authentication or enter the self-contained demo.</p>
      <form onSubmit={submit} className="mt-8 grid gap-5"><Field label="Email address"><Input value={email} onChange={e=>setEmail(e.target.value)} type="email" placeholder="ca@firm.in" required/></Field><Field label="Password"><div className="relative"><Input value={password} onChange={e=>setPassword(e.target.value)} type={show?"text":"password"} className="w-full pr-12" required/><button type="button" onClick={()=>setShow(!show)} className="absolute right-3 top-2.5 rounded-lg p-1 text-[#77716e]">{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></Field><Button disabled={busy} className="mt-1 w-full">{busy?"Signing in…":"Sign in"}</Button></form>
      <div className="my-6 flex items-center gap-3 text-xs text-[#8b8581]"><span className="h-px flex-1 bg-[#e5e2de]"/>OR TRY THE GUIDED DEMO<span className="h-px flex-1 bg-[#e5e2de]"/></div>
      <div className="grid gap-2 sm:grid-cols-3"><Button variant="secondary" onClick={()=>demo("admin")} disabled={busy}>Partner</Button><Button variant="secondary" onClick={()=>demo("preparer")} disabled={busy}>Preparer</Button><Button variant="secondary" onClick={()=>demo("reviewer")} disabled={busy}>Reviewer</Button></div>
      <p className="mt-8 text-center text-sm text-[#6b6562]">New to the prototype? <Link href="/auth/register" className="font-semibold text-[#191515]">Create an account</Link></p><p className="mt-4 rounded-xl bg-[#f8f7f5] p-3 text-xs leading-5 text-[#77716e]">Demo mode uses synthetic clients, deterministic AI outputs and a browser WhatsApp simulator.</p>
    </div></section>
  </div></main>;
}
