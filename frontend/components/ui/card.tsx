import type { HTMLAttributes } from "react";

export function Card({ children, className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-[22px] border border-[#e5e2de] bg-white ${className}`} {...props}>{children}</div>;
}
