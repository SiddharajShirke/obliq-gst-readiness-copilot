import type {PublicUploadContext} from "./types";

export function isUploadWorkflowComplete(context: PublicUploadContext): boolean {
  return context.checklist.length > 0
    && context.checklist.every(item => item.upload_status === "uploaded")
    && context.ready_to_submit_count === 0
    && context.latest_submission_batch != null;
}
