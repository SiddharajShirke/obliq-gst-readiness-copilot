import { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return <label className="grid gap-1.5 text-sm font-medium text-[#292524]"><span>{label}</span>{children}{hint && <span className="text-xs font-normal text-[#77716e]">{hint}</span>}</label>;
}

const inputBase = "h-11 rounded-xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-3.5 text-[var(--obliq-ink)] outline-none transition focus:border-[var(--obliq-focus)] focus:ring-4 focus:ring-[var(--obliq-focus-ring)] disabled:cursor-not-allowed disabled:bg-[var(--obliq-disabled)]";

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${inputBase} ${className}`} {...props} />;
}

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${inputBase} ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`min-h-28 rounded-xl border border-[var(--obliq-border)] bg-[var(--obliq-surface)] px-3.5 py-3 text-[var(--obliq-ink)] outline-none transition focus:border-[var(--obliq-focus)] focus:ring-4 focus:ring-[var(--obliq-focus-ring)] ${className}`} {...props} />;
}
