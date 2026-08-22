# Phase 3 Submission, Review Portfolio, Validation Correction, Alerts, and Theme Design

## Purpose

Extend the existing OBLIQ Phase 3 implementation with an explicit client submission boundary, backend-controlled processing batches, an application-wide extraction portfolio, controlled validation corrections, categorized alerts, and accessible light/dark themes.

The design preserves the completed Supabase Storage intake, document metadata, OCR/NVIDIA/Groq routing, normalized GST persistence, deterministic validation, deterministic GSTR-2B reconciliation, Vonage transport, audit logging, and CA-controlled alert behavior.

## Scope

This extension implements:

- Client-controlled submission of currently uploaded documents for OCR/AI processing.
- Multiple immutable submission batches per secure upload context.
- Processing progress visible to the anonymous upload portal and authenticated CA workspace.
- Six category portfolios plus one combined GST portfolio.
- Large source-versus-extraction review workspace.
- Single-record and filtered/selected bulk extraction approval.
- Deterministic validation using approved extraction data only.
- Manual and AI-assisted correction proposals with mandatory CA approval.
- Validation alert creation with stable categories and safe AI assistance.
- Application-wide Light, Dark, and System theme modes.

This extension does not implement Phase 4 RAG, Phase 5 Vonage attachment ingestion, automatic GST treatment decisions, production job queues, or tax filing.

## Confirmed Product Decisions

1. Uploading stores documents but does not trigger OCR or AI.
2. The public Submit button processes whichever currently uploaded documents have not previously been submitted.
3. Later uploads form later submission batches.
4. Submission is controlled by one backend endpoint, not one browser request per document.
5. The submission endpoint acknowledges within a target of 1–2 seconds and must normally remain under 5–6 seconds. External OCR/AI completion is asynchronous and is not subject to that response-time target.
6. Bulk review and correction scope begins with the current category/filter and can be narrowed with checkboxes.
7. Every bulk edit or AI-assisted correction displays a before/after confirmation preview.
8. AI proposes corrections but cannot persist them without explicit CA approval.
9. Only approved extraction records participate in the validation review workflow.
10. The portfolio supports each of the six Phase 3 categories and a combined view.

## Submission Batch Architecture

### States

Newly stored business documents use `awaiting_submission`. Submission changes eligible documents to `awaiting_processing` and associates them with an immutable batch. Existing processing states remain:

```text
awaiting_submission
→ awaiting_processing
→ processing
→ ready_for_review | needs_review | processing_failed
→ approved | rejected
```

Excluded ground-truth and unassigned documents remain in their existing exclusion/review states and are never added to a processing batch.

### Data model

Add `document_submission_batches` with:

- `id`
- `firm_id`
- `client_id`
- `application_id`
- `demo_session_id` nullable
- `upload_link_id`
- `status`: `submitted`, `processing`, `partially_completed`, `completed`, `failed`
- `document_count`
- `completed_count`
- `failed_count`
- `submitted_at`
- `completed_at` nullable
- `created_at`
- `updated_at`

Extend `documents` with:

- `submission_batch_id` nullable foreign key
- `submitted_at` nullable

A document can belong to only one submission batch. A batch is immutable after creation except for derived status/counters.

### Submit endpoint

Add an equivalent of:

```text
POST /api/v1/public/upload/{token}/submit
```

The endpoint:

1. Validates the protected upload token and its application/session scope.
2. Selects business documents in `awaiting_submission` for that upload context.
3. Rejects an empty submission with a clear `409` response.
4. Creates one batch and atomically binds the eligible documents.
5. Sets the documents to `awaiting_processing`.
6. Schedules the existing processing pipeline with FastAPI `BackgroundTasks`.
7. Returns `202 Accepted` with the batch ID, submitted document count, and initial status.

The endpoint does not wait for OCR, NVIDIA, or Groq. This keeps normal acknowledgement under the 5–6 second UX boundary. Processing remains idempotent because only documents without an existing batch are eligible.

### Status endpoints

The public upload context exposes:

- count of upload-ready documents
- latest batch status
- per-document processing status
- batch completed/failed counters

The existing 2.5-second polling loop remains sufficient for this prototype. The authenticated document extraction summary returns the same batch association and progress.

### Failure behavior

- A failed document does not roll back completed documents in its batch.
- The batch becomes `partially_completed` when it contains both successful and failed documents.
- A processing failure remains retryable through the existing authenticated Process/Retry action.
- The anonymous client cannot retry AI processing or modify extracted data.
- Upload and submission audit events never contain the raw upload token.

## Public Upload Experience

The portal separates storage from processing:

```text
Upload document
→ Uploaded — Not submitted
→ Submit N Documents for Extraction
→ Submitted
→ Processing X of N
→ Ready for CA Review / Needs Attention
```

The Submit button is visible whenever at least one eligible document is awaiting submission. It submits only that current unsubmitted set. Already submitted documents are not resubmitted. Files uploaded later cause a new Submit button and a new batch.

The confirmation copy states that submission begins OCR/AI extraction and may take longer than the acknowledgement. The interface disables duplicate clicks while the backend request is in flight.

## Portfolio Information Architecture

### Seven scopes

1. Sales Register
2. Purchase Register
3. Sales Invoices
4. Purchase & Expense Invoices
5. Credit & Debit Notes
6. GST Special Transactions
7. Combined GST Portfolio

Every scope uses live normalized rows. The combined scope does not create duplicate data; it queries the same records without a category restriction.

### Portfolio modes

Each scope supports:

- Portfolio mode: summary cards and digestible record cards.
- Table mode: dense searchable and sortable rows.
- Search by invoice/document number, party name, GSTIN, and source document.
- Filters for processing status, review status, source document, date, transaction subtype, RCM, and ITC status where relevant.
- Checkboxes for exact bulk selection.
- Current-filter bulk selection with a visible selected-record count.

Category-specific cards and columns are derived from actual fields. Missing values display as unavailable and are never invented.

### Summary cards

- Sales Register: record count, taxable sales, output GST, document value, B2B/B2C.
- Purchase Register: record count, taxable purchases, input GST, RCM count, ITC unavailable count.
- Sales Invoices: invoice count, customer count, taxable value, output GST, needs review.
- Purchase & Expense Invoices: invoice count, supplier count, taxable value, input GST, needs review.
- Credit & Debit Notes: credit count, debit count, taxable adjustment, GST adjustment, linked/unlinked notes.
- GST Special Transactions: counts by subtype, transaction value, GST value, needs review.
- Combined Portfolio: total records, total taxable value, total tax, approved/pending/needs-review counts, and category distribution.

## Large Record Review Workspace

Selecting any portfolio or table row opens a responsive review workspace using approximately 90% of desktop width and most of the usable height.

Desktop layout:

```text
Original private document preview | Extracted and normalized fields
                                  | Validation context
                                  | Source page/row
                                  | Parser/provider/model/confidence
                                  | Review and correction history
```

Mobile layout uses tabs for Original, Extracted, Evidence, and History.

The workspace provides previous/next record navigation within the current filtered dataset and supports:

- Approve extraction.
- Edit and approve.
- Reject/request clarification.
- Request AI correction suggestion.

Opening a record never reruns extraction. The original structured extraction remains immutable; reviewed/corrected data remains separate.

## Extraction Approval Gates

### Record-level review

Record actions update the normalized record review state and record who reviewed it, when, and why. Document status is derived:

- `ready_for_review` while records remain pending.
- `needs_review` while unresolved extraction/validation findings remain.
- `approved` when all eligible records for the document are approved or edited-and-approved.
- `rejected` only through explicit CA/reviewer action.

### Bulk approval

Bulk actions use the current category/filter as the maximum scope. When checkboxes are selected, only checked rows are included. Before persistence, the UI displays:

- selected record count
- affected documents/categories
- fields/actions to be applied
- warnings for records already approved or containing unresolved issues

The authenticated backend revalidates firm/application scope and eligibility; it never trusts browser-provided firm/client/application identifiers.

### Application progression

The application can enter `validation_review` only after at least one approved extraction is available. Validation results are always labeled with their approved-record coverage so a partial batch is not presented as complete-application validation.

## Validation Portfolio

Validation uses approved normalized records only. It supports the same Portfolio/Table switch, category/filter scope, and checkbox selection as extraction review.

Each deterministic finding displays:

- finding type and severity
- affected field and current value
- exact deterministic rule/evidence
- source record and source document
- review status

Available actions:

1. Raise Alert: creates a categorized alert from the immutable finding evidence.
2. Manual Correction: edits one field or a selected set of records, displays before/after values, then requires explicit approval.
3. AI Correction Suggestion: sends minimal scoped evidence to the configured AI route, validates the structured proposal, displays before/after values and rationale, then requires explicit approval.

Applying a correction writes reviewed values and audit history, never overwrites the original extraction, and reruns deterministic validation only for affected records. Application-wide validation summaries refresh from the persisted findings.

## AI Correction Safety

AI correction output uses a strict Pydantic schema:

- record ID
- field name
- current value
- proposed value
- concise rationale
- evidence references
- confidence/status

The provider receives only selected records and relevant deterministic findings. It never receives the developer ground-truth document or unrelated application data.

AI cannot:

- approve its own proposal
- persist values directly
- change document classification without reviewer approval
- change reconciliation outcomes
- decide GST or ITC treatment
- resolve or close alerts

NVIDIA handles small structured correction suggestions first. Groq is a fallback for complex or schema-invalid cases. Provider failure leaves the current data unchanged and displays an unavailable/retry state.

## Alert Taxonomy and Assistance

Alerts retain client, GST period, application, source record/document, and immutable evidence.

Classification dimensions:

- workflow area: `extraction`, `validation`, `reconciliation`
- alert type: `gstin`, `period`, `arithmetic`, `duplicate`, `missing_data`, `tax_mismatch`, `gstr2b_mismatch`, `invoice_number_mismatch`, `rcm`, `itc_restriction`, `clarification`, `other_review`
- severity: existing controlled severity values
- status: existing controlled review lifecycle

Deterministic finding/reconciliation services choose the workflow area and alert type. The AI explanation service receives those values and exact evidence; it cannot invent or change them.

Alerts Dashboard filters by client, period, workflow area, alert type, severity, and status. Alert details display source evidence, before/after corrections when applicable, AI review assistance, and CA-controlled status actions.

## Theme System

Add a client-side theme provider with three modes:

- Light
- Dark
- System

The selection persists in local storage. System mode follows `prefers-color-scheme`. A small labeled control appears in the authenticated top bar and an accessible control appears on public/auth pages.

Semantic CSS variables cover canvas, surfaces, elevated surfaces, text, muted text, borders, primary/secondary actions, status fills, focus rings, and shadows. Existing fixed light-only colors are migrated across:

- authenticated dashboard shell and pages
- application workspace tabs
- upload portal
- authentication pages
- portfolio and review workspace
- validation and reconciliation
- alerts and audit details
- dialogs, tables, cards, badges, inputs, and toasts where supported

Both themes must meet readable contrast, preserve visible focus states, avoid color-only status communication, and reflow cleanly on mobile.

## APIs

Follow existing router conventions with equivalents of:

```text
POST /public/upload/{token}/submit
GET  /public/upload/{token}/status
GET  /applications/{application_id}/documents/portfolio
POST /applications/{application_id}/extractions/bulk-review
POST /applications/{application_id}/validation/run
POST /validation/findings/{finding_id}/raise-alert
POST /validation/corrections/propose
POST /validation/corrections/apply
```

Existing document approve/edit/reject and reconciliation alert APIs remain and are reused where their scope fits. New endpoints must enforce firm/application role access and reject cross-application record IDs.

## Audit Events

Record safe events:

- `document_batch_submitted`
- `document_processing_started`
- `document_processing_completed`
- `document_processing_failed`
- `extraction_record_approved`
- `extraction_bulk_approved`
- `extraction_edited_and_approved`
- `validation_started`
- `validation_completed`
- `validation_alert_raised`
- `validation_correction_proposed`
- `validation_correction_applied`
- `validation_correction_rejected`

Audit metadata contains IDs, counts, statuses, provider/model metadata, and safe before/after values. It excludes tokens, secrets, full signed URLs, and chain-of-thought.

## Performance and UX Targets

- Submit endpoint: target 1–2 seconds; normal upper UX boundary 5–6 seconds.
- First visible batch-status refresh: within one 2.5-second polling interval after acknowledgement.
- Portfolio filtering/view switching: client-side response under 100 ms for the prototype dataset.
- Large review workspace: opens from already-loaded row data immediately; signed source preview loads independently.
- Heavy OCR/AI work remains asynchronous and may exceed 5–6 seconds.
- External provider latency is displayed as processing progress, not hidden behind a blocking request.

No Redis, Celery, Kafka, or production queue is added.

## Security

- Public submission requires the same protected, scoped upload token as upload.
- The public submit request cannot choose firm, client, application, bucket, path, provider, or arbitrary document IDs.
- Authenticated batch review/correction endpoints re-resolve every record under the authorized application and role.
- Service-role access remains backend-only.
- Original extraction and correction history remain preserved.
- Ground-truth content remains excluded from processing, validation, correction prompts, alerts, reconciliation, and future RAG.
- Correction proposals and AI explanations never include unrelated client/application data.

## Testing Strategy

Use test-first implementation.

Backend tests cover:

- upload remains `awaiting_submission` and does not schedule processing
- partial Submit creates one batch and schedules only eligible documents
- repeated Submit is idempotent/empty-conflict safe
- later uploads create a separate batch
- token/application/session isolation
- excluded/unassigned/GSTR-2B behavior
- batch counters and partial failure
- approved-only validation coverage
- single and bulk approval authorization
- manual correction before/after preservation
- AI proposal schema and no-write behavior
- explicit correction approval and targeted revalidation
- validation alert categorization and explicit creation
- ground-truth exclusion

Frontend tests cover:

- Submit visibility/count/disabled/progress states
- seven portfolio scopes and dynamic summaries
- Portfolio/Table switch and filtered checkbox selection
- large responsive review workspace
- record and bulk approval confirmation
- validation manual/AI correction confirmation
- alert filtering/evidence/assistance
- Light/Dark/System persistence and accessible toggle
- core pages render in both theme modes without light-only text/surface regressions

Regression verification includes full backend/frontend suites, frontend production build, lint, migration tests, secret scan, and `git diff --check`.

## Prototype Boundaries

- FastAPI BackgroundTasks remain the processing mechanism.
- Polling remains the update mechanism.
- AI correction is assistance, not autonomous remediation.
- Full OCR/AI completion time depends on file complexity and external provider latency.
- No production queue, distributed locking, automatic tax decision, GST Portal submission, Phase 4 RAG, or Phase 5 Vonage media ingestion is introduced.
