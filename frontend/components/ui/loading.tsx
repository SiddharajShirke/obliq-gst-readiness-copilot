export function Loading({ label = "Loading workspace…" }: { label?: string }) {
  return <div className="flex min-h-48 items-center justify-center gap-3 text-sm text-[#625d5a]"><span className="h-5 w-5 animate-spin rounded-full border-2 border-[#a4c5e5] border-t-[#191515]" />{label}</div>;
}
