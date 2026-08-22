import { formatStatus, statusTone } from "../../lib/format";

const states = {
  success: "bg-[var(--obliq-success-soft)] text-[var(--obliq-success-ink)] border-[var(--obliq-success-border)]",
  warning: "bg-[var(--obliq-warning-soft)] text-[var(--obliq-warning-ink)] border-[var(--obliq-warning-border)]",
  danger: "bg-[var(--obliq-danger-soft)] text-[var(--obliq-danger-ink)] border-[var(--obliq-danger-border)]",
  info: "bg-[var(--obliq-info-soft)] text-[var(--obliq-info-ink)] border-[var(--obliq-info-border)]",
  neutral: "bg-[var(--obliq-neutral-soft)] text-[var(--obliq-neutral-ink)] border-[var(--obliq-neutral-border)]",
};

export function Badge({ value, label }: { value: string; label?: string }) {
  const tone = statusTone(value);
  return <span className={`inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${states[tone]}`}>{label || formatStatus(value)}</span>;
}
