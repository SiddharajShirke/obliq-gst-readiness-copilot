import { ButtonHTMLAttributes } from "react";

export function Button({ className = "", variant = "primary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const variants = {
    primary: "bg-[#191515] text-white hover:bg-black",
    secondary: "bg-white text-[#191515] border border-[#d9d5d0] hover:border-[#191515]",
    ghost: "bg-transparent text-[#625d5a] hover:bg-black/5",
    danger: "bg-[#c53b3b] text-white hover:bg-[#a82e2e]",
  };
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
