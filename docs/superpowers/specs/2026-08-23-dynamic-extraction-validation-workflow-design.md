# Dynamic Extraction-to-Validation Workflow Design

## Goal

Connect CA extraction approval to deterministic validation and render one accurate,
application-scoped workflow across the Overview, Documents & Extraction, Validation,
Reconciliation, and Audit tabs. Preserve the existing manual/AI correction previews and
explicit CA-controlled alert creation.

## Proven problems

- The workspace loads the base application for its stepper but uses the cloned session
  application for document tabs. A clone can be in `reconciliation_review` while the
  visible stepper reads `not_started` from the base application.
- Extraction approval updates records/documents but does not consistently advance the
  effective application's workflow.
- Single-document approval updates `document_extractions` without approving the
  associated normalized `invoice_records`.
- The processing graph persists validation findings before CA extraction approval.
  Consequently, the Validation tab can display pre-approval/stale findings.
- The Validation tab loads once and does not display application-scoped validation alerts.
- The top percentage is collection progress only, so it cannot describe Phase 3 progress.

## Workflow semantics

```text
document collection complete
  -> extraction processing
  -> extraction review
  -> all current records reviewed
  -> deterministic validation of approved/edited-and-approved records
  -> validation review
  -> optional explicit Raise Alert
  -> reconciliation review when validation review is complete
```

Approval does not automatically create Alerts Dashboard records. Deterministic validation
creates findings. A CA must still press **Raise Alert** for a finding to become a categorized
alert, preserving the approved human-control rule.

Rejected records count as reviewed but are excluded from deterministic validation.
Pending records prevent automatic transition out of Extraction Review. Later document
batches return the application to Extraction Review; validation is regenerated when all
current records are reviewed again.

## Backend design

### Validation workflow service

Create `backend/app/services/validation_workflow.py` with:

```python
async def run_application_validation(
    store: DataStore,
    *,
    application_id: str,
    firm_id: str,
) -> ValidationRunResult

async def advance_after_extraction_review(
    store: DataStore,
    *,
    application_id: str,
    firm_id: str,
) -> WorkflowTransitionResult
```

`run_application_validation` becomes the only path that persists `validation_findings`.
It deletes/rebuilds current findings solely from approved or edited-and-approved records,
uses the existing deterministic validation rules, updates the application to
`validation_review`, and returns counts plus rows. Existing Alerts remain immutable evidence
records even if their source finding is replaced during a later validation run.

`advance_after_extraction_review` inspects every normalized record for the application:

- pending records -> `extraction_review`, no validation run;
- all records reviewed and at least one approved record -> run deterministic validation;
- no normalized records -> remain in `extraction_review`;
- rejected records -> excluded from validation but counted as reviewed.

Bulk approve/reject, single document approve/reject, and edit-and-approve call this service
after their own persistence succeeds. Single document review also updates every associated
`invoice_records` row so the record and document review states cannot diverge.

The document-processing graph may calculate preliminary issues to choose
`ready_for_review` versus `needs_review`, but it must not persist rows in
`validation_findings` before CA approval.

### Dynamic workflow snapshot

Extend the existing document-collection response for the effective application with:

```json
{
  "workflow": {
    "current_stage": "validation_review",
    "progress_percent": 72,
    "application_status": "validation_review",
    "steps": [],
    "extraction": {
      "record_count": 24,
      "reviewed_count": 24,
      "approved_count": 24,
      "pending_count": 0,
      "rejected_count": 0
    },
    "validation": {
      "finding_count": 41,
      "open_count": 41,
      "reviewed_count": 0,
      "alert_count": 0
    },
    "reconciliation": {
      "run_count": 1,
      "review_count": 11
    }
  }
}
```

The backend derives every value from the effective cloned application. The frontend does not
combine base-application status with cloned document state. Collection progress remains a
separate `received / required` metric. Overall workflow progress is milestone- and
review-count-based, monotonic within the current database state, and never marks later filing
stages complete.

### Categorized validation portfolio

Add an application-scoped response equivalent to:

```text
GET /applications/{application_id}/validation-portfolio
```

It returns the six taxonomy categories in configured order:

1. Credit & Debit Notes
2. GST Special Transactions
3. Purchase & Expense Invoices
4. Purchase Register
5. Sales Invoices
6. Sales Register

Each category contains live requirement status, normalized-record counts, approved/pending
counts, finding totals grouped by finding type/severity/status, detailed findings, and only
explicitly raised validation alerts belonging to the application/category. Ground Truth and
GSTR-2B never appear in these six client cards.

Category labels are taxonomy configuration. No result counts, statuses, invoice values,
finding descriptions, or alerts are hard-coded in the frontend.

## Frontend design

### Workspace progress

The top card shows **Overall GST workflow progress** using the backend workflow snapshot.
It renders live step states for Documents Requested, Documents Received, Extraction Review,
Validation Review, and Reconciliation Review. Ready for CA Review and Ready for Filing stay
disabled. The Overview retains a separate Document Collection card and percentage.

### Validation tab

The Validation tab polls the validation-portfolio endpoint every 2.5 seconds and renders:

- six main category cards with Received/Missing and record/review counts;
- dynamic sub-cards for validation result groups such as wrong period, GSTIN format,
  arithmetic mismatch, missing field, duplicate, or any future backend finding type;
- live finding portfolio/table views and the existing large review workspace;
- application-scoped raised validation alerts;
- existing manual correction, AI recommendation, confirmation preview, resolve/accept, and
  explicit Raise Alert controls unchanged.

No synthetic fallback rows or hard-coded counts are allowed. Empty states explicitly say
whether records are awaiting extraction review, validation is running, or no findings were
detected.

## Polling and error behavior

Use the existing controlled polling mechanism; add no new realtime system. A validation
failure leaves approved data intact, keeps the application in Extraction Review, and exposes
a safe retry action. Alert explanation failure never blocks validation or alert persistence.

## Tests

- Effective cloned application drives workflow status and progress.
- Base application remains unchanged.
- Preliminary processing does not persist validation findings.
- Partial approval remains in Extraction Review.
- Final review automatically validates only approved records.
- Rejected records are excluded.
- Single document approval synchronizes normalized rows.
- Validation portfolio returns six live categories in order.
- Findings and raised alerts are grouped into the correct category.
- Ground Truth and GSTR-2B are excluded.
- Frontend renders category/sub-card values from API data and keeps correction/alert actions.
- Progress changes dynamically as database state changes.

## Boundaries

- No automatic Alerts Dashboard creation.
- No Phase 5 Vonage media ingestion.
- No filing-readiness transition.
- No new queue or production infrastructure.
- Preserve unrelated working-tree changes.
