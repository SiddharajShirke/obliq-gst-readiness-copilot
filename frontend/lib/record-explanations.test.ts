import {describe, expect, it} from "vitest";
import type {AuditEvent, Finding, GSTRecord, ReconciliationItem} from "./types";
import {
  explainAuditEvent,
  explainFinding,
  explainGSTRecord,
  explainReconciliationItem,
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
});
