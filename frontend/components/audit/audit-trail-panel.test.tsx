import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {AuditTrailPanel} from "./audit-trail-panel";

describe("audit trail detail panel", () => {
  it("renders real events as inspectable rows", () => {
    const html = renderToStaticMarkup(
      <AuditTrailPanel events={[{
        id: "audit-1",
        action: "document_uploaded",
        entity_type: "document",
        entity_id: "doc-7",
        created_at: "2026-08-22T10:00:00Z",
        metadata: {document_type: "sales_register"},
      }]}/>,
    );

    expect(html).toContain("Select any event to inspect its recorded context");
    expect(html).toContain("Document Uploaded");
    expect(html).toContain("doc-7");
  });
});
