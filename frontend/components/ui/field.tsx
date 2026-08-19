import { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return <label className="grid gap-1.5 text-sm font-medium text-[#292524]"><span>{label}</span>{children}{hint && <span className="text-xs font-normal text-[#77716e]">{hint}</span>}</label>;
}

const inputBase = "h-11 rounded-xl border border-[#dcd7d2] bg-white px-3.5 outline-none transition focus:border-[#72a8d4] focus:ring-4 focus:ring-[#a4c5e5]/25 disabled:cursor-not-allowed disabled:bg-[#f4f2f0]";

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${inputBase} ${className}`} {...props} />;
}

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${inputBase} ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`min-h-28 rounded-xl border border-[#dcd7d2] bg-white px-3.5 py-3 outline-none transition focus:border-[#72a8d4] focus:ring-4 focus:ring-[#a4c5e5]/25 ${className}`} {...props} />;
}
