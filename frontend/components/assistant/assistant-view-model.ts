import type {AssistantAnswer} from "../../lib/types";

const MONEY_METRICS = new Set([
  "taxable_value",
  "total_tax",
  "invoice_total",
  "igst",
  "cgst",
  "sgst_utgst",
  "cess",
]);

const PRIORITY_COLUMNS = [
  "invoice_number",
  "supplier_name",
  "customer_name",
  "invoice_date",
  "taxable_value",
  "total_tax",
  "invoice_total",
  "review_status",
  "match_status",
  "finding_type",
  "severity",
  "status",
  "action",
  "created_at",
];

function formatValue(value: unknown, metric?: string | null) {
  if (value === null || value === undefined || value === "") return "—";
  if (metric && MONEY_METRICS.has(metric)) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(numeric);
    }
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return "View details";
  return String(value);
}

export function buildAssistantViewModel(answer: AssistantAnswer) {
  const calculation = answer.calculation;
  const summary = calculation ? {
    label: calculation.metric
      ? calculation.metric.replaceAll("_", " ")
      : calculation.operation,
    value: formatValue(calculation.value, calculation.metric),
    caption: `${calculation.record_count} scoped record${calculation.record_count === 1 ? "" : "s"}`,
  } : null;

  const columns = answer.rows.length
    ? PRIORITY_COLUMNS.filter(column => answer.rows.some(row => column in row)).slice(0, 8)
    : [];
  const table = columns.length ? {
    columns,
    rows: answer.rows.slice(0, 50).map(row => Object.fromEntries(
      columns.map(column => [column, formatValue(row[column], column)]),
    )),
  } : null;

  const proposal = answer.proposed_action;
  const preview = proposal?.preview ?? {};
  const action = proposal ? {
    id: proposal.id,
    actionType: proposal.action_type,
    title: proposal.title,
    status: proposal.status,
    affectedCount: proposal.affected_count,
    warnings: proposal.warnings,
    expiresAt: proposal.expires_at,
    before: (preview.before as Record<string, unknown> | undefined) ?? {},
    after: (preview.after as Record<string, unknown> | undefined) ?? {},
  } : null;

  return {summary, table, clarification: answer.clarification ?? null, action};
}
