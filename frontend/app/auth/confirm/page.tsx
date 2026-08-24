"use client";

import {CheckCircle2, MailWarning, RefreshCw} from "lucide-react";
import Link from "next/link";
import {useRouter} from "next/navigation";
import {FormEvent, useEffect, useState, useSyncExternalStore} from "react";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {Field, Input} from "@/components/ui/field";
import {useAuth} from "@/lib/auth";
import {parseAuthConfirmationError} from "@/lib/supabase";

export default function AuthConfirmationPage() {
  const {user, loading, resendConfirmation} = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const browserHash = useSyncExternalStore(
    () => () => undefined,
    () => window.location.hash,
    () => "",
  );
  const checkedRedirect = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );
  const error = parseAuthConfirmationError(browserHash);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [router, user]);

  async function resend(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await resendConfirmation(email.trim());
      toast.success("A new confirmation email has been sent. Use only the newest link.");
    } catch (resendError) {
      toast.error(resendError instanceof Error ? resendError.message : "Unable to resend confirmation email");
    } finally {
      setBusy(false);
    }
  }

  const failed = Boolean(error?.code || error?.description);
  return <main className="grid min-h-screen place-items-center bg-[var(--obliq-bg)] p-4">
    <section className="w-full max-w-lg rounded-[30px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)] p-7 shadow-xl sm:p-10">
      <Link href="/" className="text-xl font-black tracking-[-.06em]">OBLIQ</Link>
      {loading || !checkedRedirect ? <>
        <span className="mt-10 grid h-12 w-12 place-items-center rounded-full bg-[var(--obliq-info-soft)] text-[var(--obliq-info-ink)]"><RefreshCw className="animate-spin" size={22}/></span>
        <h1 className="mt-5 text-3xl font-bold">Confirming your email</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--obliq-muted)]">OBLIQ is validating the Supabase confirmation and preparing your workspace.</p>
      </> : <>
        <span className="mt-10 grid h-12 w-12 place-items-center rounded-full bg-[var(--obliq-warning-soft)] text-[var(--obliq-warning-ink)]"><MailWarning size={22}/></span>
        <p className="mt-5 text-xs font-bold tracking-[.13em] text-[var(--obliq-warning-ink)]">EMAIL CONFIRMATION REQUIRED</p>
        <h1 className="mt-2 text-3xl font-bold">{error?.expired ? "Confirmation link expired" : failed ? "Email could not be confirmed" : "Confirm your email"}</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--obliq-muted)]">{error?.description ?? "Request a fresh confirmation email below."} Use only the newest link you receive.</p>
        <form className="mt-6 grid gap-4" onSubmit={resend}>
          <Field label="Account email"><Input type="email" value={email} onChange={event => setEmail(event.target.value)} required/></Field>
          <Button disabled={busy || !email.trim()}>{busy ? "Sending..." : "Resend confirmation email"}</Button>
        </form>
        <div className="mt-5 flex items-center gap-2 rounded-2xl bg-[var(--obliq-success-soft)] p-4 text-xs leading-5 text-[var(--obliq-success-ink)]"><CheckCircle2 size={17}/><span>Your original registration is retained; confirming the email activates access.</span></div>
        <p className="mt-6 text-center text-sm text-[var(--obliq-muted)]"><Link href="/auth/login" className="font-semibold text-[var(--obliq-ink)]">Return to sign in</Link></p>
      </>}
    </section>
  </main>;
}
