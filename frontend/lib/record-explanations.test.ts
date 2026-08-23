import {describe, expect, it} from "vitest";
import type {AuditEvent, Finding, GSTRecord, ReconciliationItem} from "./types";
import {
  explainAuditEvent,
  explainFinding,
  explainGSTRecord,
  explainReconciliationItem,
  findingEvidenceEntries,
} from "./record-explanations";

describe("dynamic row explanations", () => {
  it("explains extracted GST records using their actual category", () => {
    const record = {
      document_type: "purchase_register",
      invoice_number: "INV-44",
      supplier_name: "Dynamic Supplier",
    } as GSTRecord;

    const explanation = explainGSTRecord(record);

    expect(explanation.title).toContain("Purchase Register");
    expect(explanation.summary).toContain("INV-44");
    expect(explanation.summary).toContain("Dynamic Supplier");
  });

  it("explains validation, reconciliation, and audit rows without raw JSON", () => {
    const finding = {
      id: "finding-1",
      finding_type: "tax_arithmetic_mismatch",
      severity: "medium",
      message: "Tax components do not equal total tax",
      details: {expected_total: "180.00", actual_total: "170.00"},
      status: "open",
    } satisfies Finding;
    const reconciliation = {
      match_status: "value_mismatch",
      evidence: {difference_fields: ["taxable_value", "cgst"]},
    } as ReconciliationItem;
    const audit = {
      action: "document_uploaded",
      entity_type: "document",
      entity_id: "doc-7",
    } as AuditEvent;

    expect(explainFinding(finding).summary).toContain("Tax components");
    expect(explainReconciliationItem(reconciliation).summary.toLowerCase()).toContain("taxable value");
    expect(explainAuditEvent(audit).summary).toContain("doc-7");
  });

  it("presents meaningful validation evidence before technical identifiers", () => {
    const finding = {
      id: "finding-1",
      finding_type: "wrong_period",
      severity: "medium",
      message: "Invoice does not belong to the selected GST period.",
      status: "open",
      document_id: "opaque-document-id",
      invoice_record_id: "opaque-record-id",
      evidence_context: {
        issue_summary: "Invoice dated 02-08-2026 is outside May 2026.",
        document_name: "01_Purchase_Register.pdf",
        document_number: "INV-44",
        party_name: "Dynamic Supplier",
        party_gstin: "27ABCDE1234F1Z5",
        document_date: "2026-08-02",
        period_label: "May 2026",
        taxable_value: "90000.00",
      },
    } satisfies Finding;

    expect(findingEvidenceEntries(finding)).toEqual(expect.arrayContaining([
      ["Source document", "01_Purchase_Register.pdf"],
      ["Invoice / document number", "INV-44"],
      ["Party", "Dynamic Supplier"],
      ["Selected GST period", "May 2026"],
    ]));
    expect(findingEvidenceEntries(finding).flat()).not.toContain("opaque-document-id");
  });
});
