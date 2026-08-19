import { Card } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";
export function StatCard({ label, value, icon: Icon, hint }: { label: string; value: string | number; icon: LucideIcon; hint?: string }) {
  return <Card className="p-5"><div className="flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.09em] text-[#77716e]">{label}</p><p className="mt-4 text-3xl font-bold tracking-[-.04em]">{value}</p>{hint&&<p className="mt-1 text-xs text-[#77716e]">{hint}</p>}</div><span className="grid h-10 w-10 place-items-center rounded-2xl bg-[#e8f1fa] text-[#477ca8]"><Icon size={19}/></span></div></Card>;
}
