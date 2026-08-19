export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

const acronymMap: Record<string, string> = {
  ca: "CA",
  gst: "GST",
  gstr2b: "GSTR-2B",
  itc: "ITC",
};

export function formatStatus(value?: string | null): string {
  if (!value) return "Not Started";
  const minorWords = new Set(["and", "for", "of", "to"]);
  return value
    .split("_")
    .map((word, index) => {
      const normalized = word.toLowerCase();
      if (acronymMap[normalized]) return acronymMap[normalized];
      if (index > 0 && minorWords.has(normalized)) return normalized;
      return `${word.charAt(0).toUpperCase()}${word.slice(1)}`;
    })
    .join(" ");
}

export function statusTone(value?: string | null): StatusTone {
  const status = value || "";
  if (["completed", "approved", "ready_for_filing", "ready_for_ca_review", "received", "resolved", "matched", "sent", "delivered", "read"].includes(status)) return "success";
  if (["partially_received", "documents_requested", "awaiting_approval", "purchase_only", "gstr2b_only", "date_mismatch"].includes(status)) return "warning";
  if (["failed", "rejected", "missing", "amount_mismatch", "wrong_period", "unreadable_document", "cancelled"].includes(status)) return "danger";
  if (["processing", "extraction_review", "validation_review", "reconciliation_review", "documents_complete"].includes(status)) return "info";
  return "neutral";
}

export function formatCurrency(value?: number | string | null): string {
  const number = typeof value === "string" ? Number(value) : value ?? 0;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(number) ? number : 0);
}

export function formatDate(value?: string | null, fallback = "—"): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(date);
}

export function initials(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
