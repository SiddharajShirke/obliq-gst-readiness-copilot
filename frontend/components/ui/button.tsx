import { ButtonHTMLAttributes } from "react";

export function Button({ className = "", variant = "primary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const variants = {
    primary: "bg-[var(--obliq-action)] text-[var(--obliq-action-ink)] hover:opacity-90 dark:hover:bg-[var(--obliq-action-hover)] dark:hover:opacity-100",
    secondary: "bg-[var(--obliq-surface)] text-[var(--obliq-ink)] border border-[var(--obliq-border)] hover:border-[var(--obliq-muted)] dark:hover:bg-[var(--obliq-interactive-hover)]",
    ghost: "bg-transparent text-[var(--obliq-muted)] hover:bg-black/5 dark:hover:bg-[var(--obliq-interactive-hover)] dark:hover:text-[var(--obliq-ink)]",
    danger: "bg-[#c53b3b] text-white hover:bg-[#a82e2e]",
  };
  return (
    <button
      className={`obliq-focus inline-flex min-h-10 items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
