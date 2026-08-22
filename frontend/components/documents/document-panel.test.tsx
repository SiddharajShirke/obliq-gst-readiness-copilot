import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {DocumentPanel} from "./document-panel";

describe("Phase 2 document panel", () => {
  it("shows storage intake state without Phase 3 processing controls", () => {
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

    expect(html).toContain("Uploaded documents");
    expect(html).toContain("Awaiting processing");
    expect(html).not.toContain(">Process<");
    expect(html).not.toContain(">Reprocess<");
    expect(html).not.toContain("Original and extracted data");
    expect(html).not.toContain("Review extracted fields");
  });
});
