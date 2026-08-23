import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import type {WorkflowProgress as WorkflowProgressValue} from "@/lib/types";
import {WorkflowProgress} from "./workflow-progress";

const workflow: WorkflowProgressValue = {
  application_id: "app-1",
  application_status: "validation_review",
  current_stage: "validation_review",
  progress_percent: 78,
  steps: [
    {key: "documents_requested", label: "Documents Requested", state: "completed", progress_percent: 100},
    {key: "documents_received", label: "Documents Received", state: "completed", progress_percent: 100},
    {key: "extraction_review", label: "Extraction Review", state: "completed", progress_percent: 100},
    {key: "validation_review", label: "Validation Review", state: "current", progress_percent: 66},
    {key: "reconciliation_review", label: "Reconciliation Review", state: "disabled", progress_percent: 0},
    {key: "ready_for_filing", label: "Ready for Filing", state: "pending", progress_percent: 0},
  ],
  extraction: {record_count: 12, reviewed_count: 12, approved_count: 12, rejected_count: 0, pending_count: 0, progress_percent: 100},
  validation: {finding_count: 3, open_count: 1, reviewed_count: 2, progress_percent: 66},
  reconciliation: {run_count: 0, item_count: 0, open_count: 0, review_required_count: 0, reviewed_count: 0, progress_percent: 0, available: false, status: "not_started", export_enabled: false},
  readiness: {ready_for_filing: false, ready_for_filing_percent: 0, main_export_enabled: false},
};

describe("WorkflowProgress", () => {
  it("renders backend progress and the independent post-validation branches", () => {
    const html = renderToStaticMarkup(<WorkflowProgress workflow={workflow} receivedCount={6} requiredCount={6}/>);

    expect(html).toContain("78%");
    expect(html).toContain("Document collection: 6/6");
    expect(html).toContain("Validation Review");
    expect(html).toContain("Reconciliation Review");
    expect(html).toContain("Ready for Filing");
    expect(html).toContain("both paths are available independently");
    expect(html).toContain("aria-current=\"step\"");
  });
});
