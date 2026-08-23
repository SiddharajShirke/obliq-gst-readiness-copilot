"use client";

import {ArrowRight, Sparkles} from "lucide-react";
import {useRouter} from "next/navigation";
import {useState} from "react";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {apiFetch} from "@/lib/api";
import {
  guidedDemoStateFromRun,
  saveGuidedDemoState,
  saveStoredDemoSession,
  type GuidedDemoRun,
} from "@/lib/whatsapp-demo";

export function GuidedDemoLauncher({label = "Guided Demo"}: {label?: string}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function launch() {
    setBusy(true);
    try {
      const run = await apiFetch<GuidedDemoRun>("/guided-demo-runs", {method: "POST"});
      if (!run.session) throw new Error("Guided Demo session was not returned");
      saveStoredDemoSession(window.sessionStorage, run.base_application_id, {
        sessionId: run.session.session_id,
        dashboardAccessToken: run.session.dashboard_access_token,
        created: run.session,
      });
      saveGuidedDemoState(
        window.sessionStorage,
        run.base_application_id,
        guidedDemoStateFromRun(run),
      );
      toast.success(`${run.name} workspace created`);
      router.push(`/dashboard/applications/${run.base_application_id}?guided=1`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to start Guided Demo");
      setBusy(false);
    }
  }

  return <Button
    onClick={() => void launch()}
    disabled={busy}
    className="w-fit bg-[var(--obliq-action)] text-[var(--obliq-action-ink)]"
    title="Start a fresh isolated Guided Demo"
  >
    <Sparkles size={16}/>{busy ? "Creating fresh workspace…" : label}<ArrowRight size={16}/>
  </Button>;
}
