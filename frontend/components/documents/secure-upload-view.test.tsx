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
              label: "Purchase Register",
              required: true,
              status: "received",
              upload_status: "uploaded",
              processing_status: "awaiting_processing",
            },
          ],
          allowed_extensions: ["pdf", "csv", "xlsx", "docx", "jpg", "jpeg", "png", "json"],
          maximum_size_mb: 10,
          ready_to_submit_count: 1,
          latest_submission_batch: null,
        }}
        busyRequirementId={null}
        transientStates={{}}
        onUpload={() => undefined}
        onBulkFolder={() => undefined}
        onBulkZip={() => undefined}
        bulkBusy={false}
        onSubmit={() => undefined}
        submitBusy={false}
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
    expect(html).toContain("Upload Complete Folder");
    expect(html).toContain("Upload ZIP Package");
    expect(html).toContain("Submit 1 document for extraction");
    expect(html).toContain("stored securely and will not be processed until you submit");
    expect(html).not.toContain("Extraction complete");
    expect(html).not.toContain("Ready for CA review");
  });

  it("shows submitted batch progress and prevents duplicate submission while busy", () => {
    const html = renderToStaticMarkup(
      <SecureUploadView
        context={{
          firm: {name: "OBLIQ Demo CA"},
          client: {business_name: "Raj Traders"},
          application: {period_label: "April 2026", due_date: null},
          checklist: [],
          allowed_extensions: ["pdf"],
          maximum_size_mb: 10,
          ready_to_submit_count: 2,
          latest_submission_batch: {
            id: "batch-1",
            status: "processing",
            document_count: 3,
            completed_count: 1,
            failed_count: 0,
          },
        }}
        busyRequirementId={null}
        transientStates={{}}
        onUpload={() => undefined}
        onBulkFolder={() => undefined}
        onBulkZip={() => undefined}
        bulkBusy={false}
        onSubmit={() => undefined}
        submitBusy
      />,
    );

    expect(html).toContain("Submitting\u2026");
    expect(html).toContain("1 of 3 processed");
    expect(html).toContain("disabled");
  });

  it("explains that redirect follows secure submission while extraction continues", () => {
    const html = renderToStaticMarkup(
      <SecureUploadView
        context={{
          firm: {name: "OBLIQ Demo CA"},
          client: {business_name: "Raj Traders"},
          application: {period_label: "April 2026", due_date: null},
          checklist: [{
            id: "sales-register",
            label: "Sales Register",
            required: true,
            status: "received",
            upload_status: "uploaded",
            processing_status: "processing",
          }],
          allowed_extensions: ["pdf"],
          maximum_size_mb: 10,
          ready_to_submit_count: 0,
          latest_submission_batch: {
            id: "batch-1",
            status: "processing",
            document_count: 1,
            completed_count: 0,
            failed_count: 0,
          },
        }}
        busyRequirementId={null}
        transientStates={{}}
        onUpload={() => undefined}
        onBulkFolder={() => undefined}
        onBulkZip={() => undefined}
        bulkBusy={false}
        onSubmit={() => undefined}
        submitBusy={false}
        completionRedirectSeconds={5}
      />,
    );

    expect(html).toContain("All required documents were submitted securely");
    expect(html).toContain("Extraction continues in the background");
    expect(html).not.toContain("processed successfully");
  });
});
