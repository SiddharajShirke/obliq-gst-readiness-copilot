import {Button} from "../ui/button";

type DemoRole = "admin" | "preparer" | "reviewer";

export function DemoLoginActions({
  enabled,
  busy,
  onLogin,
}: {
  enabled: boolean;
  busy: boolean;
  onLogin: (role: DemoRole) => void;
}) {
  if (!enabled) return null;
  return <>
    <div className="my-6 flex items-center gap-3 text-xs text-[#8b8581]">
      <span className="h-px flex-1 bg-[#e5e2de]"/>
      OR TRY THE GUIDED DEMO
      <span className="h-px flex-1 bg-[#e5e2de]"/>
    </div>
    <div className="grid gap-2 sm:grid-cols-3">
      <Button variant="secondary" onClick={() => onLogin("admin")} disabled={busy}>Partner</Button>
      <Button variant="secondary" onClick={() => onLogin("preparer")} disabled={busy}>Preparer</Button>
      <Button variant="secondary" onClick={() => onLogin("reviewer")} disabled={busy}>Reviewer</Button>
    </div>
  </>;
}
