import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {SecureUploadView} from "./secure-upload-view";

describe("secure upload view", () => {
  it("shows public-safe scope, accepted formats, and intake-only states", () => {
    const html = renderToStaticMarkup(
      <SecureUploadView
        context={{
          firm: {name: "OBLIQ Demo CA"},
          client: {business_name: "Raj Traders"},
          application: {period_label: "April 2026", due_date: "2026-05-20"},
          checklist: [
            {
              id: "pending-requirement",
              label: "Sales Register",
              required: true,
              status: "missing",
              upload_status: "pending",
              processing_status: null,
            },
            {
              id: "stored-requirement",
              label: "GSTR-2B",
              required: true,
              status: "received",
              upload_status: "uploaded",
              processing_status: "awaiting_processing",
            },
          ],
          allowed_extensions: ["pdf", "csv", "xlsx", "docx", "jpg", "jpeg", "png", "json"],
          maximum_size_mb: 10,
        }}
        busyRequirementId={null}
        transientStates={{}}
        onUpload={() => undefined}
      />,
    );

    expect(html).toContain("OBLIQ Demo CA");
    expect(html).toContain("Raj Traders");
    expect(html).toContain("April 2026 GST Documents");
    expect(html).toContain("PDF");
    expect(html).toContain("DOCX");
    expect(html).toContain("10 MB");
    expect(html).toContain("Pending");
    expect(html).toContain("Uploaded");
    expect(html).toContain("Awaiting Processing");
    expect(html).not.toContain("Extraction complete");
    expect(html).not.toContain("Ready for CA review");
  });
});
