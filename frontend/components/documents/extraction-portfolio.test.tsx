import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {ExtractionPortfolio, ExtractionReviewWorkspace} from "./extraction-portfolio";
import type {ExtractionPortfolioResult, GSTRecord} from "../../lib/types";

const row: GSTRecord = {
  id: "record-1",
  document_id: "document-1",
  invoice_category: "sales_register",
  document_type: "sales_register",
  invoice_number: "INV-101",
  customer_name: "Acme Retail",
  customer_gstin: "27ABCDE1234F1Z5",
  taxable_value: "1000.00",
  total_tax: "180.00",
  invoice_total: "1180.00",
  source_row: 2,
  review_status: "pending",
};

const result: ExtractionPortfolioResult = {
  scope: "combined",
  summary: {
    record_count: 1,
    taxable_value: "1000.00",
    total_tax: "180.00",
    document_value: "1180.00",
    approved_count: 0,
    needs_review_count: 1,
    rcm_count: 0,
  },
  records: [row],
};

describe("extraction portfolio", () => {
  it("renders all six category scopes plus the combined GST portfolio from live data", () => {
    const html = renderToStaticMarkup(
      <ExtractionPortfolio
        result={result}
        mode="portfolio"
        search=""
        selectedIds={new Set()}
        onScopeChange={() => undefined}
        onModeChange={() => undefined}
        onSearchChange={() => undefined}
        onToggleSelection={() => undefined}
        onSelectVisible={() => undefined}
        onInspect={() => undefined}
        onBulkReview={() => undefined}
      />,
    );

    for (const label of [
      "Sales Register", "Purchase Register", "Sales Invoices",
      "Purchase & Expense Invoices", "Credit & Debit Notes",
      "GST Special Transactions", "Combined GST Portfolio",
    ]) expect(html).toContain(label.replaceAll("&", "&amp;"));
    expect(html).toContain("Acme Retail");
    expect(html).toContain("₹1,000");
    expect(html).toContain("Portfolio");
    expect(html).toContain("Table");
  });

  it("shows selected-set review actions with an explicit confirmation boundary", () => {
    const html = renderToStaticMarkup(
      <ExtractionPortfolio
        result={result}
        mode="table"
        search=""
        selectedIds={new Set(["record-1"])}
        onScopeChange={() => undefined}
        onModeChange={() => undefined}
        onSearchChange={() => undefined}
        onToggleSelection={() => undefined}
        onSelectVisible={() => undefined}
        onInspect={() => undefined}
        onBulkReview={() => undefined}
      />,
    );
    expect(html).toContain("1 selected for review");
    expect(html).toContain("Approve selected");
    expect(html).toContain("Reject selected");
    expect(html).toContain("A confirmation preview appears before changes are saved");
    expect(html).toContain("Select All");
  });

  it("renders a large record review workspace with evidence and guarded actions", () => {
    const html = renderToStaticMarkup(
      <ExtractionReviewWorkspace
        record={row}
        onClose={() => undefined}
        onApprove={() => undefined}
        onEdit={() => undefined}
        onReject={() => undefined}
      />,
    );
    expect(html).toContain("GST EXTRACTION REVIEW WORKSPACE");
    expect(html).toContain("INV-101");
    expect(html).toContain("Source provenance");
    expect(html).toContain("Approve Extraction");
    expect(html).toContain("Edit &amp; Approve");
    expect(html).toContain("Reject / Clarify");
    expect(html).toContain("max-w-[95vw]");
  });
});
