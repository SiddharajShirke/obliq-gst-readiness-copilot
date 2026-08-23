import {describe, expect, it} from "vitest";
import type {PublicUploadContext} from "./types";
import {isUploadWorkflowComplete} from "./upload-completion";

function context(overrides: Partial<PublicUploadContext> = {}): PublicUploadContext {
  return {
    firm: {name: "Firm"},
    client: {business_name: "Raj Traders"},
    application: {period_label: "May 2026"},
    checklist: [{id: "r1", label: "Sales Register", required: true, status: "received", upload_status: "uploaded", processing_status: "ready_for_review"}],
    allowed_extensions: ["pdf"],
    maximum_size_mb: 10,
    ready_to_submit_count: 0,
    latest_submission_batch: {id: "batch", status: "completed", document_count: 1, completed_count: 1, failed_count: 0},
    ...overrides,
  };
}

describe("secure upload completion", () => {
  it("redirects after every category is submitted without waiting for extraction", () => {
    expect(isUploadWorkflowComplete(context())).toBe(true);
    expect(isUploadWorkflowComplete(context({
      latest_submission_batch: {
        ...context().latest_submission_batch!,
        status: "processing",
        completed_count: 0,
      },
    }))).toBe(true);
    expect(isUploadWorkflowComplete(context({
      latest_submission_batch: {
        ...context().latest_submission_batch!,
        status: "partially_completed",
        failed_count: 1,
      },
    }))).toBe(true);
    expect(isUploadWorkflowComplete(context({ready_to_submit_count: 1}))).toBe(false);
    expect(isUploadWorkflowComplete(context({latest_submission_batch: null}))).toBe(false);
    expect(isUploadWorkflowComplete(context({
      checklist: [{...context().checklist[0], upload_status: "pending"}],
    }))).toBe(false);
  });
});
