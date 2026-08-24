"use client";

import {Archive, ArrowRight, Check, FileUp, FolderUp, Send, ShieldCheck} from "lucide-react";
import {Badge} from "../ui/badge";
import {Card} from "../ui/card";
import {formatDate} from "../../lib/format";
import type {PublicUploadContext, PublicUploadRequirement} from "../../lib/types";
import {ThemeToggle} from "../ui/theme-toggle";

export type UploadTransientState = "uploading" | "duplicate" | "failed";

type Props = {
  context: PublicUploadContext;
  busyRequirementId: string | null;
  transientStates: Record<string, UploadTransientState>;
  onUpload: (requirement: PublicUploadRequirement, file: File) => void;
  onBulkFolder: (files: File[]) => void;
  onBulkZip: (file: File) => void;
  bulkBusy: boolean;
  onSubmit: () => void;
  submitBusy: boolean;
  completionRedirectSeconds?: number | null;
};

function displayExtensions(extensions: string[]): string {
  return extensions.map(extension => extension.toUpperCase()).join(", ");
}

export function SecureUploadView({context, busyRequirementId, transientStates, onUpload, onBulkFolder, onBulkZip, bulkBusy, onSubmit, submitBusy, completionRedirectSeconds}: Props) {
  const complete = context.checklist.every(item => item.upload_status === "uploaded");
  const batch = context.latest_submission_batch;
  const submitCount = context.ready_to_submit_count;

  return <main className="min-h-screen bg-[#e8f1fa] p-4 sm:p-8">
    <div className="mx-auto max-w-3xl">
      <header className="flex items-center justify-between py-3">
        <span className="text-xl font-black tracking-[-.06em]">OBLIQ</span>
        <span className="flex items-center gap-2 text-xs font-semibold"><ShieldCheck size={16}/>Secure client upload <ThemeToggle compact/></span>
      </header>
      <Card className="mt-5 overflow-hidden shadow-[0_25px_80px_rgba(25,21,21,.10)]">
        <div className="bg-[#191515] p-6 text-white sm:p-8">
          <p className="text-xs font-bold tracking-[.13em] text-[#a4c5e5]">{context.firm.name}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-[-.04em]">{context.client.business_name}</h1>
          <p className="mt-2 text-sm text-white/65">{context.application.period_label} GST Documents · Due {formatDate(context.application.due_date)}</p>
        </div>
        <div className="p-5 sm:p-8">
          <p className="text-sm leading-6 text-[#625d5a]">Upload each requested category below. Original files are stored privately and made available only to the CA firm handling this GST period.</p>
          <div className="mt-4 rounded-2xl bg-[#f8f7f5] p-4 text-xs leading-5 text-[#625d5a]">
            <strong>Accepted formats:</strong> {displayExtensions(context.allowed_extensions)}<br/>
            <strong>Maximum size:</strong> {context.maximum_size_mb} MB per file
          </div>
          <section aria-label="Guided Demo upload instructions" className="mt-5 rounded-2xl border border-[var(--obliq-info-border)] bg-[var(--obliq-info-soft)] p-4 sm:p-5">
            <p className="text-[10px] font-bold tracking-[.13em] text-[var(--obliq-info-ink)]">GUIDED UPLOAD · STEP 3 OF 6</p>
            <h2 className="mt-2 text-lg font-bold text-[var(--obliq-ink)]">Upload, check, then submit</h2>
            <p className="mt-2 text-xs leading-5 text-[var(--obliq-muted)]">Storage and extraction are separate actions. Complete them in this order so the Guided Demo advances correctly.</p>
            <ol className="mt-4 grid gap-3 sm:grid-cols-2">
              {[
                ["Upload files", "Use individual uploads, a complete folder, or the supplied ZIP."],
                ["Check all six categories", "Confirm every required category displays Uploaded."],
                ["Submit the stored batch", "Press Submit documents for extraction; uploaded files do not process automatically."],
                ["Return to Overview", "After successful submission, OBLIQ redirects in five seconds. Extraction continues after you return."],
              ].map(([title, detail], index) => <li key={title} className="flex gap-3 rounded-2xl border border-[var(--obliq-info-border)] bg-[var(--obliq-surface)]/80 p-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--obliq-blue-soft)] text-xs font-bold text-[var(--obliq-info-ink)]">{index + 1}</span>
                <span><strong className="block text-sm text-[var(--obliq-ink)]">{title}</strong><span className="mt-1 block text-xs leading-5 text-[var(--obliq-muted)]">{detail}</span></span>
              </li>)}
            </ol>
            <div className="mt-4 flex items-start gap-2 rounded-xl bg-[var(--obliq-surface)]/75 p-3 text-xs leading-5 text-[var(--obliq-info-ink)]"><ArrowRight className="mt-0.5 shrink-0" size={15}/><span><strong>Next:</strong> Monitor processing, then review original-versus-extracted records in Documents & Extraction.</span></div>
          </section>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <label className="obliq-focus flex cursor-pointer items-center gap-3 rounded-2xl border border-[#d8d3ce] bg-white p-4 transition hover:bg-[#f8f7f5]">
              <FolderUp size={20}/>
              <span><strong className="block text-sm">Upload Complete Folder</strong><span className="text-xs text-[#77716e]">Route supported files to the matching categories</span></span>
              <input
                type="file"
                multiple
                className="hidden"
                disabled={bulkBusy || Boolean(busyRequirementId)}
                accept={context.allowed_extensions.map(extension => `.${extension}`).join(",")}
                ref={element => {
                  if (element) element.setAttribute("webkitdirectory", "");
                }}
                onChange={event => {
                  const files = Array.from(event.target.files ?? []);
                  if (files.length) onBulkFolder(files);
                  event.target.value = "";
                }}
              />
            </label>
            <label className="obliq-focus flex cursor-pointer items-center gap-3 rounded-2xl border border-[#d8d3ce] bg-white p-4 transition hover:bg-[#f8f7f5]">
              <Archive size={20}/>
              <span><strong className="block text-sm">Upload ZIP Package</strong><span className="text-xs text-[#77716e]">Safely unpack and route one synthetic package</span></span>
              <input
                type="file"
                className="hidden"
                disabled={bulkBusy || Boolean(busyRequirementId)}
                accept=".zip,application/zip"
                onChange={event => {
                  const file = event.target.files?.[0];
                  if (file) onBulkZip(file);
                  event.target.value = "";
                }}
              />
            </label>
          </div>
          {bulkBusy && <p className="mt-3 text-xs font-semibold text-[#477ca8]">Routing package files securely…</p>}
          <div className="mt-6 grid gap-3">
            {context.checklist.map(item => {
              const transient = transientStates[item.id];
              const uploaded = item.upload_status === "uploaded";
              const uploading = busyRequirementId === item.id;
              return <div key={item.id} className="flex flex-col justify-between gap-4 rounded-2xl border border-[#e5e2de] p-4 sm:flex-row sm:items-center">
                <div className="flex items-center gap-3">
                  <span className={`grid h-9 w-9 place-items-center rounded-full ${uploaded ? "bg-emerald-50 text-emerald-700" : "bg-[#f8f7f5] text-[#77716e]"}`}>
                    {uploaded ? <Check size={17}/> : <FileUp size={17}/>}
                  </span>
                  <div>
                    <strong className="text-sm">{item.label}</strong>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge value={uploaded ? "uploaded" : "pending"}/>
                      {item.processing_status && <Badge value={item.processing_status}/>}
                      {transient && <Badge value={transient}/>}
                    </div>
                  </div>
                </div>
                <label className={`obliq-focus cursor-pointer rounded-full px-5 py-2.5 text-center text-sm font-semibold ${uploaded ? "border border-[#dcd7d2] bg-white" : "bg-[var(--obliq-action)] text-[var(--obliq-action-ink)]"}`}>
                  {uploading ? "Uploading…" : uploaded ? "Upload another" : "Upload document"}
                  <input
                    type="file"
                    className="hidden"
                    disabled={Boolean(busyRequirementId)}
                    accept={context.allowed_extensions.map(extension => `.${extension}`).join(",")}
                    onChange={event => {
                      const file = event.target.files?.[0];
                      if (file) onUpload(item, file);
                      event.target.value = "";
                    }}
                  />
                </label>
              </div>;
            })}
          </div>
          {submitCount > 0 && <section className="mt-6 rounded-2xl border border-[#9fc6e8] bg-[#edf6ff] p-5">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="font-bold text-[#153a59]">Ready for extraction</h2>
                <p className="mt-1 max-w-xl text-xs leading-5 text-[#47708f]">
                  {submitCount} {submitCount === 1 ? "document is" : "documents are"} stored securely and will not be processed until you submit.
                </p>
              </div>
              <button
                type="button"
                disabled={submitBusy || bulkBusy || Boolean(busyRequirementId)}
                onClick={onSubmit}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-[#191515] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send size={16}/>
                {submitBusy ? "Submitting\u2026" : `Submit ${submitCount} ${submitCount === 1 ? "document" : "documents"} for extraction`}
              </button>
            </div>
          </section>}
          {batch && <section className="mt-4 rounded-2xl border border-[#e5e2de] bg-[#f8f7f5] p-4 text-sm">
            <div className="flex items-center justify-between gap-4">
              <strong>Latest extraction batch</strong>
              <Badge value={batch.status}/>
            </div>
            <p className="mt-2 text-xs text-[#625d5a]">
              {batch.completed_count} of {batch.document_count} processed
              {batch.failed_count > 0 ? ` \u00b7 ${batch.failed_count} failed` : ""}
            </p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#ddd8d3]">
              <div
                className="h-full rounded-full bg-[#477ca8] transition-all"
                style={{width: `${batch.document_count ? Math.round(((batch.completed_count + batch.failed_count) / batch.document_count) * 100) : 0}%`}}
              />
            </div>
            {batch.failed_count > 0 && <p className="mt-3 rounded-xl border border-[var(--obliq-danger-border)] bg-[var(--obliq-danger-soft)] p-3 text-xs leading-5 text-[var(--obliq-danger-ink)]">One or more documents could not be extracted. The successful documents remain available; ask the CA to retry the failed document after reviewing its processing error.</p>}
          </section>}
          {complete && <div className="mt-6 rounded-2xl bg-emerald-50 p-5 text-sm text-emerald-800">
            <div className="flex items-center gap-2 font-bold"><Check size={18}/>All required categories uploaded</div>
            <p className="mt-2 leading-6">Your files are stored securely and are awaiting processing by the OBLIQ workflow.</p>
          </div>}
          {completionRedirectSeconds != null && <div className="mt-4 rounded-2xl border border-[var(--obliq-success-border)] bg-[var(--obliq-success-soft)] p-5 text-sm text-[var(--obliq-success-ink)]"><strong className="block">All required documents were submitted securely.</strong><span className="mt-2 block">Extraction continues in the background. Returning to the OBLIQ Overview in {completionRedirectSeconds} seconds so you can continue the workflow.</span></div>}
          <p className="mt-6 text-xs leading-5 text-[#6b6562]">Upload status confirms safe storage only. It does not mean extraction or CA review is complete.</p>
        </div>
      </Card>
      <p className="mx-auto mt-5 max-w-xl text-center text-xs leading-5 text-[#6b6562]">This prototype uses synthetic demonstration information. Never upload real taxpayer data to a public demo environment.</p>
    </div>
  </main>;
}
