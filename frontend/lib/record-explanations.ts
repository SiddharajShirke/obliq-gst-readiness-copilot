import {formatStatus} from "./format";
import type {AuditEvent, Finding, GSTRecord, ReconciliationItem} from "./types";

export type RowExplanation = {
  title: string;
  summary: string;
  review: string;
};

const recordPurpose: Record<string, string> = {
  sales_register: "This books-side sales record contributes to reported outward-supply totals.",
  purchase_register: "This books-side purchase record is a primary input for GSTR-2B comparison.",
  sales_invoices: "This supporting sales invoice provides transaction-level evidence for the sales register.",
  purchase_expense_invoices: "This purchase or expense invoice supports the corresponding books-side entry.",
  credit_debit_notes: "This note adjusts values from an earlier invoice or transaction.",
  gst_special_transactions: "This record captures a special GST treatment such as RCM, export, exempt supply, or correction.",
  gstr2b: "This government-side record is used only for purchase-side GSTR-2B reconciliation.",
};

export function explainGSTRecord(record: GSTRecord): RowExplanation {
  const category = record.document_type || record.invoice_category || "extracted_record";
  const identity = record.invoice_number || "an unnumbered record";
  const party = record.supplier_name || record.customer_name;
  return {
    title: `${formatStatus(category)} record`,
    summary: `${identity}${party ? ` for ${party}` : ""}. ${recordPurpose[category] || "This is normalized GST data extracted from the uploaded source document."}`,
    review: "Compare these values with the source document before approving or correcting the extraction.",
  };
}

const findingReview: Record<string, string> = {
  tax_arithmetic_mismatch: "Recalculate the visible tax components and compare them with the recorded total tax.",
  invalid_gstin: "Verify the GSTIN against the source document and the party master.",
  wrong_period: "Confirm the document date and whether it belongs to the selected GST period.",
  duplicate_invoice: "Check the referenced source records before deciding whether this is a genuine duplicate.",
  missing_invoice_number: "Check whether a readable document number exists in the original source.",
};

export function explainFinding(finding: Finding): RowExplanation {
  return {
    title: formatStatus(finding.finding_type),
    summary: finding.message || "OBLIQ detected a deterministic validation condition requiring review.",
    review: findingReview[finding.finding_type] || "Review the recorded evidence and source document before resolving or accepting this finding.",
  };
}

const moneyEvidence = new Set(["Taxable value", "IGST", "CGST", "SGST / UTGST", "Cess", "Total tax", "Document total"]);

function evidenceValue(label: string, value: unknown): string {
  if (moneyEvidence.has(label) && value != null && value !== "") {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return new Intl.NumberFormat("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 2}).format(numeric);
    }
  }
  return displayDetailValue(value);
}

export function findingEvidenceEntries(finding: Finding): Array<[string, string]> {
  const evidence = finding.evidence_context;
  if (!evidence) return Object.entries(finding.details || {}).map(([key, value]) => [formatStatus(key), displayDetailValue(value)]);
  const candidates: Array<[string, unknown]> = [
    ["Source document", evidence.document_name],
    ["Document category", evidence.document_category ? formatStatus(evidence.document_category) : null],
    ["Invoice / document number", evidence.document_number],
    ["Party", evidence.party_name],
    ["Party GSTIN", evidence.party_gstin],
    ["Invoice / document date", evidence.document_date],
    ["Selected GST period", evidence.period_label],
    ["Period start", evidence.period_start],
    ["Period end", evidence.period_end],
    ["Taxable value", evidence.taxable_value],
    ["IGST", evidence.igst],
    ["CGST", evidence.cgst],
    ["SGST / UTGST", evidence.sgst],
    ["Cess", evidence.cess],
    ["Total tax", evidence.total_tax],
    ["Document total", evidence.total_document_value],
    ["Source page", evidence.source_page],
    ["Source row", evidence.source_row],
  ];
  return candidates
    .filter(([, value]) => value != null && value !== "")
    .map(([label, value]) => [label, evidenceValue(label, value)]);
}

const reconciliationMeaning: Record<string, string> = {
  exact_match: "Books and GSTR-2B match on every available normalized comparison field.",
  value_mismatch: "The identity matched, but one or more exact field values differ.",
  invoice_number_mismatch: "A unique exact-value candidate was found with a different invoice number.",
  books_only: "This books-side record has no corresponding GSTR-2B candidate.",
  gstr2b_only: "This GSTR-2B record has no corresponding books-side candidate.",
  ambiguous_match: "More than one candidate matched the exact supporting fields, so OBLIQ did not guess.",
};

export function explainReconciliationItem(item: ReconciliationItem): RowExplanation {
  const fields = item.evidence?.difference_fields?.map(formatStatus) ?? [];
  return {
    title: formatStatus(item.match_status),
    summary: fields.length
      ? `${reconciliationMeaning[item.match_status] || "This comparison requires CA review"} Differing fields: ${fields.join(", ")}.`
      : reconciliationMeaning[item.match_status] || "This deterministic reconciliation result requires CA review.",
    review: "Use the exact Books and GSTR-2B evidence below; AI does not determine or change this outcome.",
  };
}

const auditMeaning: Record<string, string> = {
  document_uploaded: "A document was accepted into the application’s private intake workflow.",
  upload_completed: "A secure upload completed and its database metadata was recorded.",
  document_request_sent: "The reviewed document request was sent through the active WhatsApp session.",
  reminder_sent: "A reviewed reminder was sent for the requirements that were still missing.",
  reconciliation_started: "An authorized user explicitly started deterministic GSTR-2B reconciliation.",
  reconciliation_completed: "The deterministic reconciliation run completed and its findings were persisted.",
  reconciliation_alert_raised: "A CA explicitly promoted a reconciliation finding to an alert.",
};

export function explainAuditEvent(event: AuditEvent): RowExplanation {
  const entity = `${formatStatus(event.entity_type)}${event.entity_id ? ` ${event.entity_id}` : ""}`;
  return {
    title: formatStatus(event.action.replaceAll(".", "_")),
    summary: `${auditMeaning[event.action] || "OBLIQ recorded this application activity."} Affected entity: ${entity}.`,
    review: "This entry is read-only audit context. Inspect the recorded before, after, and metadata values where available.",
  };
}

export function displayDetailValue(value: unknown): string {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.map(displayDetailValue).join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nested]) => `${formatStatus(key)}: ${displayDetailValue(nested)}`)
      .join(" · ");
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}
