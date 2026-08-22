import type { HTMLAttributes } from "react";

export function Card({ children, className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-[22px] border border-[var(--obliq-border)] bg-[var(--obliq-surface)] text-[var(--obliq-ink)] ${className}`} {...props}>{children}</div>;
}
