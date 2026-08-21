import { formatStatus, statusTone } from "../../lib/format";

const states = {
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  danger: "bg-red-50 text-red-700 border-red-200",
  info: "bg-blue-50 text-blue-700 border-blue-200",
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
};

export function Badge({ value, label }: { value: string; label?: string }) {
  const tone = statusTone(value);
  return <span className={`inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${states[tone]}`}>{label || formatStatus(value)}</span>;
}
