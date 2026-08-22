import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {DocumentPanel} from "./document-panel";

describe("Phase 3 document panel", () => {
  it("shows structured extraction review controls without raw JSON", () => {
    const html = renderToStaticMarkup(
      <DocumentPanel
        applicationId="app-1"
        checklist={[{
          id: "req-1",
          application_id: "app-1",
          requirement_type: "sales_register",
          label: "Sales Register",
          required: true,
          status: "received",
        }]}
        onChanged={() => undefined}
      />,
    );

    expect(html).toContain("Structured GST extraction");
    expect(html).toContain("Original document");
    expect(html).toContain("Combined GST Portfolio");
    expect(html).toContain("Purchase &amp; Expense Invoices");
    expect(html).toContain("Portfolio");
    expect(html).toContain("Table");
    expect(html).not.toContain("raw JSON");
  });
});
