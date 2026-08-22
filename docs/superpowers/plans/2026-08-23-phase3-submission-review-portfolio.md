# Phase 3 Submission and Review Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit backend-controlled document submission batches, seven extraction portfolio scopes, guarded extraction/validation correction workflows, categorized alerts, and complete light/dark/system theming.

**Architecture:** Uploaded files remain privately stored without processing until the scoped public upload token submits the current unsubmitted batch. Existing FastAPI BackgroundTasks then run the existing deterministic/NVIDIA/Groq pipeline asynchronously. Reviewed normalized rows feed deterministic validation; manual and AI corrections are proposals that require authenticated CA confirmation and preserve original extraction data.

**Tech Stack:** FastAPI, Pydantic, Supabase/PostgreSQL, existing repository abstraction, FastAPI BackgroundTasks, Next.js 16, React 19, Tailwind CSS 4, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-23-phase3-submission-review-portfolio-design.md`

## Global Constraints

- Preserve Phase 1 Vonage and Phase 2 secure upload/session isolation.
- Public submission must normally acknowledge in 5–6 seconds or less and must not wait for OCR/AI completion.
- FastAPI BackgroundTasks and existing polling remain the prototype execution/update mechanisms.
- AI can propose but cannot persist a correction without authenticated CA approval.
- Original extraction output is immutable; corrections are preserved separately with audit history.
- Ground-truth content never enters processing, validation, corrections, alerts, reconciliation, or RAG.
- Phase 4 RAG and Phase 5 Vonage media ingestion remain out of scope.
- Do not commit secrets or add production queue infrastructure.

---

### Task 1: Submission batch migration and repository parity

**Files:**
- Create: `supabase/migrations/202608230001_document_submission_batches.sql`
- Modify: `backend/app/repositories/memory.py`
- Modify: `backend/app/services/document_processing/pipeline.py`
- Test: `backend/tests/unit/test_phase3_submission_batches.py`
- Test: `backend/tests/integration/test_secure_upload_phase2.py`

**Interfaces:**
- Produces table `document_submission_batches` and document fields `submission_batch_id`, `submitted_at`.
- Produces processing state `awaiting_submission` for newly ingested business documents.
- Preserves `excluded_reference`, `needs_assignment`, and GSTR-2B routing.

- [ ] **Step 1: Write failing migration and ingestion-state tests**

```python
def test_business_upload_waits_for_explicit_submission(store, settings, context):
    document = await ingest_document(
        store, settings, context=context,
        explicit_requirement_id=context.requirements[0]["id"],
        filename="sales.csv", declared_mime_type="text/csv",
        content=b"invoice_number,taxable_value\nS-1,1000\n",
    )
    assert document["processing_status"] == "awaiting_submission"
    assert document["submission_batch_id"] is None
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest backend/tests/unit/test_phase3_submission_batches.py backend/tests/integration/test_secure_upload_phase2.py -q`

Expected: failure because the migration/table and `awaiting_submission` state do not exist.

- [ ] **Step 3: Add the forward-only migration**

Create a scoped table with firm/client/application/upload-link ownership, controlled batch statuses, counters, timestamps, indexes, and RLS/service-role grants matching existing backend-only patterns. Extend `documents_processing_status_check` to include `awaiting_submission`; add nullable `submission_batch_id` and `submitted_at`; migrate only unprocessed uploaded business documents from `awaiting_processing` to `awaiting_submission` when they have no extraction and are not already processing.

- [ ] **Step 4: Update memory-store parity and ingestion status**

Add `document_submission_batches` to memory store tables and ID generation. In `ingest_document`, map ordinary business documents to `awaiting_submission`; preserve `gstr2b`, `developer_ground_truth`, and `unknown` special states.

- [ ] **Step 5: Run focused tests**

Run: `pytest backend/tests/unit/test_phase3_submission_batches.py backend/tests/integration/test_secure_upload_phase2.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/202608230001_document_submission_batches.sql backend/app/repositories/memory.py backend/app/services/document_processing/pipeline.py backend/tests/unit/test_phase3_submission_batches.py backend/tests/integration/test_secure_upload_phase2.py
git commit -m "feat: add explicit document submission batches"
```

### Task 2: Atomic public submission API and batch progress

**Files:**
- Modify: `backend/app/api/v1/documents.py`
- Modify: `backend/app/services/document_processing/pipeline.py`
- Modify: `backend/app/services/secure_upload.py`
- Modify: `backend/app/schemas/documents.py`
- Test: `backend/tests/integration/test_phase3_submission_api.py`
- Test: `backend/tests/integration/test_phase3_bulk_ingestion.py`

**Interfaces:**
- Produces `submit_ingested_documents(store, settings, context) -> dict[str, Any]`.
- Produces `POST /api/v1/public/upload/{token}/submit` returning HTTP 202.
- Extends public upload context with `ready_to_submit_count`, `latest_submission_batch`, and per-item processing state.

- [ ] **Step 1: Write failing submission API tests**

Cover partial submission, empty repeat submission, later second batch, expired/revoked token, cross-session isolation, and no processing call during upload.

```python
response = client.post(f"/api/v1/public/upload/{token}/submit")
assert response.status_code == 202
assert response.json()["document_count"] == 2
assert response.json()["status"] == "submitted"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest backend/tests/integration/test_phase3_submission_api.py backend/tests/integration/test_phase3_bulk_ingestion.py -q`

Expected: 404 for the missing submit route and existing uploads scheduling processing too early.

- [ ] **Step 3: Remove automatic processing from upload routes**

Delete `background_tasks.add_task(process_ingested_document, ...)` from individual/folder/ZIP public upload completion. Keep upload responses at stored/awaiting-submission state.

- [ ] **Step 4: Implement atomic batch creation**

Resolve all eligible documents from the token-derived application/upload link, create one batch, update each eligible document with batch/timestamp/state, then schedule `process_ingested_document` once per bound document. If no eligible documents exist, return a controlled 409. Re-resolve documents inside each processing task and update derived batch counters after completion/failure.

- [ ] **Step 5: Extend public status context**

Return batch progress without exposing internal IDs from other application contexts. The anonymous page receives only its scoped document labels/statuses and latest batch progress.

- [ ] **Step 6: Add safe audit events**

Record `document_batch_submitted`, per-document processing completion/failure, batch ID/count, and duration. Do not record the raw token.

- [ ] **Step 7: Run focused tests and timing assertion**

Run: `pytest backend/tests/integration/test_phase3_submission_api.py backend/tests/integration/test_phase3_bulk_ingestion.py -q`

Assert the test client response is returned before a mocked slow processor completes; do not use a flaky wall-clock assertion against real external providers.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/documents.py backend/app/services/document_processing/pipeline.py backend/app/services/secure_upload.py backend/app/schemas/documents.py backend/tests/integration/test_phase3_submission_api.py backend/tests/integration/test_phase3_bulk_ingestion.py
git commit -m "feat: submit uploaded documents as processing batches"
```

### Task 3: Public Submit UI and asynchronous progress

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/app/upload/[token]/page.tsx`
- Modify: `frontend/components/documents/secure-upload-view.tsx`
- Modify: `frontend/components/documents/secure-upload-view.test.tsx`

**Interfaces:**
- Consumes public context fields from Task 2.
- Produces `onSubmit: () => void`, `submitBusy: boolean`, and explicit storage/submission/processing UI states.

- [ ] **Step 1: Write failing frontend tests**

Test Submit visibility for one or more unsubmitted documents, hidden/disabled state at zero, “Submit N documents for extraction” copy, in-flight disabled behavior, batch progress, partial failure, and later-batch visibility.

- [ ] **Step 2: Run focused test and verify failure**

Run: `npm.cmd test -- components/documents/secure-upload-view.test.tsx`

- [ ] **Step 3: Implement page submission call**

Call `POST /public/upload/{token}/submit` without auth, set in-flight state, refresh public status, and rely on existing 2.5-second polling for progress.

- [ ] **Step 4: Implement visual batch boundary**

Show stored-not-submitted badges, a prominent confirmation area, document count, processing explanation, and progress states. Prevent duplicate button clicks while the request is pending.

- [ ] **Step 5: Run focused tests**

Run: `npm.cmd test -- components/documents/secure-upload-view.test.tsx`

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/types.ts frontend/app/upload/[token]/page.tsx frontend/components/documents/secure-upload-view.tsx frontend/components/documents/secure-upload-view.test.tsx
git commit -m "feat: submit upload batches for extraction"
```

### Task 4: Seven-scope portfolio API and deterministic summaries

**Files:**
- Create: `backend/app/services/document_processing/portfolio.py`
- Modify: `backend/app/api/v1/documents.py`
- Modify: `backend/app/schemas/documents.py`
- Test: `backend/tests/unit/test_phase3_portfolio.py`
- Test: `backend/tests/integration/test_phase3_portfolio_api.py`

**Interfaces:**
- Produces `build_portfolio(records, scope) -> PortfolioResult`.
- Produces `GET /applications/{application_id}/documents/portfolio?scope=<scope>`.
- Valid scopes are six business categories plus `combined`.

- [ ] **Step 1: Write failing category-summary tests**

Create independent fixtures for sales, purchases, invoices, notes, special transactions, and combined totals. Assert Decimal-derived values, null preservation, counts/subtypes, review coverage, and no duplicated combined rows.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest backend/tests/unit/test_phase3_portfolio.py backend/tests/integration/test_phase3_portfolio_api.py -q`

- [ ] **Step 3: Implement portfolio service**

Query normalized records once per application/scope, calculate category-specific summaries with Decimal, return source provenance and extraction/provider metadata, and never inspect developer ground truth.

- [ ] **Step 4: Add authorized API endpoint**

Enforce firm/application access through existing dependency helpers. Reject unsupported scopes with 422. Return live records and summaries only for the selected application.

- [ ] **Step 5: Run focused tests**

Run: `pytest backend/tests/unit/test_phase3_portfolio.py backend/tests/integration/test_phase3_portfolio_api.py -q`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/document_processing/portfolio.py backend/app/api/v1/documents.py backend/app/schemas/documents.py backend/tests/unit/test_phase3_portfolio.py backend/tests/integration/test_phase3_portfolio_api.py
git commit -m "feat: expose dynamic GST extraction portfolios"
```

### Task 5: Attractive portfolio UI and large review workspace

**Files:**
- Create: `frontend/components/documents/extraction-portfolio.tsx`
- Create: `frontend/components/documents/extraction-summary-cards.tsx`
- Create: `frontend/components/documents/extraction-review-workspace.tsx`
- Create: `frontend/components/documents/portfolio-filters.tsx`
- Modify: `frontend/components/documents/document-panel.tsx`
- Modify: `frontend/lib/types.ts`
- Test: `frontend/components/documents/extraction-portfolio.test.tsx`
- Test: `frontend/components/documents/extraction-review-workspace.test.tsx`
- Test: `frontend/components/documents/document-panel.test.tsx`

**Interfaces:**
- Consumes Task 4 portfolio response.
- Produces category/combined scope navigation, portfolio/table modes, filter/selection state, and a 90%-width review dialog.

- [ ] **Step 1: Write failing UI tests**

Assert all seven scopes, category-specific summaries, no hard-coded values, Portfolio/Table mode switch, selected/filter counts, source provenance, previous/next navigation, and large dialog actions.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `npm.cmd test -- components/documents/extraction-portfolio.test.tsx components/documents/extraction-review-workspace.test.tsx components/documents/document-panel.test.tsx`

- [ ] **Step 3: Build portfolio components**

Split responsibilities so filters, summaries, rows/cards, and review workspace remain independently testable. Use actual row data for party/invoice/money/status/provenance. Missing values render as unavailable.

- [ ] **Step 4: Build large responsive review workspace**

Desktop uses source preview and extracted fields side-by-side; mobile uses semantic tabs. Opening loads a signed document URL independently and never triggers processing. Include provider/model/confidence, source row/page, history, and actions.

- [ ] **Step 5: Run focused tests**

Run the Task 5 focused command and expect all tests to pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/documents/extraction-portfolio.tsx frontend/components/documents/extraction-summary-cards.tsx frontend/components/documents/extraction-review-workspace.tsx frontend/components/documents/portfolio-filters.tsx frontend/components/documents/document-panel.tsx frontend/lib/types.ts frontend/components/documents/*.test.tsx
git commit -m "feat: add seven-scope extraction review portfolio"
```

### Task 6: Record and bulk extraction review gates

**Files:**
- Modify: `backend/app/api/v1/documents.py`
- Modify: `backend/app/schemas/documents.py`
- Modify: `backend/app/services/document_processing/processor.py`
- Modify: `frontend/components/documents/extraction-review-workspace.tsx`
- Modify: `frontend/components/documents/extraction-portfolio.tsx`
- Test: `backend/tests/integration/test_phase3_extraction_bulk_review.py`
- Test: `frontend/components/documents/extraction-portfolio.test.tsx`

**Interfaces:**
- Produces `POST /applications/{application_id}/extractions/bulk-review`.
- Request includes controlled action, current filter scope, explicit record IDs, and optional reviewed values/notes.
- Backend record IDs are always re-resolved within the authorized application.

- [ ] **Step 1: Write failing authorization and state tests**

Test single approval, filtered/selected bulk approval, cross-application rejection, unsupported role, already-approved handling, document derived status, original extraction preservation, and audit events.

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest backend/tests/integration/test_phase3_extraction_bulk_review.py -q`

- [ ] **Step 3: Implement bulk review service/endpoint**

Resolve target rows, validate action eligibility, persist reviewed values separately, derive parent document state, and move application to validation review only when approved coverage exists.

- [ ] **Step 4: Add confirmation preview UI**

Show affected count/categories/documents and exact actions. When checkboxes exist, only checked IDs are submitted; otherwise submit current filtered record IDs. Require a final explicit confirmation.

- [ ] **Step 5: Run backend and frontend focused tests**

Run Task 6 test files and expect all tests to pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/documents.py backend/app/schemas/documents.py backend/app/services/document_processing/processor.py backend/tests/integration/test_phase3_extraction_bulk_review.py frontend/components/documents/extraction-review-workspace.tsx frontend/components/documents/extraction-portfolio.tsx frontend/components/documents/extraction-portfolio.test.tsx
git commit -m "feat: gate validation behind extraction approval"
```

### Task 7: Guarded validation correction proposals and targeted revalidation

**Files:**
- Create: `supabase/migrations/202608230002_validation_corrections_and_alert_categories.sql`
- Create: `backend/app/services/validation_corrections.py`
- Create: `backend/app/prompts/validation_corrections.py`
- Modify: `backend/app/api/v1/compliance.py`
- Modify: `backend/app/schemas/documents.py`
- Modify: `backend/app/services/validation.py`
- Modify: `backend/app/repositories/memory.py`
- Test: `backend/tests/unit/test_phase3_validation_corrections.py`
- Test: `backend/tests/integration/test_phase3_validation_corrections_api.py`

**Interfaces:**
- Produces `validation_correction_proposals` preserving proposed/approved/rejected state and before/after values.
- Produces proposal and apply endpoints scoped to application/record IDs.
- AI proposal uses NVIDIA first and Groq once as schema-validation/provider fallback.

- [ ] **Step 1: Write failing safety tests**

Assert approved-only validation, manual proposal no-write behavior, AI proposal no-write behavior, strict output schema, ground-truth exclusion, cross-application rejection, explicit apply, before/after preservation, rejected proposal no mutation, and affected-record revalidation.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest backend/tests/unit/test_phase3_validation_corrections.py backend/tests/integration/test_phase3_validation_corrections_api.py -q`

- [ ] **Step 3: Add forward-only migration and memory parity**

Create lightweight proposal storage with application/record/finding linkage, controlled statuses, proposal type/provider/model, changes JSONB, rationale, proposer/approver/timestamps, and indexes/RLS matching current backend service-role access.

- [ ] **Step 4: Implement manual and AI proposal services**

Build minimal evidence payloads from selected approved records/findings. Validate AI JSON through Pydantic. Never pass write-capable objects to provider adapters. Return a normalized before/after preview.

- [ ] **Step 5: Implement explicit apply/reject endpoints**

On approval, copy reviewed values into corrected normalized rows, preserve original structured output, write audit events, and rerun deterministic validation only for affected records. On rejection, mark the proposal rejected without mutation.

- [ ] **Step 6: Run focused tests**

Run Task 7 focused command and expect all tests to pass.

- [ ] **Step 7: Commit**

```bash
git add supabase/migrations/202608230002_validation_corrections_and_alert_categories.sql backend/app/services/validation_corrections.py backend/app/prompts/validation_corrections.py backend/app/api/v1/compliance.py backend/app/schemas/documents.py backend/app/services/validation.py backend/app/repositories/memory.py backend/tests/unit/test_phase3_validation_corrections.py backend/tests/integration/test_phase3_validation_corrections_api.py
git commit -m "feat: add CA-approved validation corrections"
```

### Task 8: Validation portfolio, correction UI, and validation alerts

**Files:**
- Create: `frontend/components/documents/validation-portfolio.tsx`
- Create: `frontend/components/documents/correction-preview-dialog.tsx`
- Modify: `frontend/components/documents/findings-panel.tsx`
- Modify: `frontend/lib/types.ts`
- Modify: `backend/app/api/v1/alerts.py`
- Modify: `backend/app/schemas/alerts.py`
- Modify: `frontend/components/alerts/alerts-dashboard.tsx`
- Test: `frontend/components/documents/validation-portfolio.test.tsx`
- Test: `frontend/components/documents/correction-preview-dialog.test.tsx`
- Test: `backend/tests/integration/test_phase3_validation_alerts.py`
- Test: `frontend/components/alerts/alerts-dashboard.test.tsx`

**Interfaces:**
- Consumes Task 7 correction endpoints and approved validation coverage.
- Produces validation Portfolio/Table modes and explicit Raise Alert/manual/AI correction actions.
- Extends alerts with workflow area and controlled alert type.

- [ ] **Step 1: Write failing validation UI and alert tests**

Test coverage labels, filters/checkbox scope, one-field and selected-set preview, AI unavailable behavior, approve/reject proposal controls, explicit alert creation, alert categories, and no automatic alert.

- [ ] **Step 2: Run focused tests and verify failure**

Run backend and frontend Task 8 test files.

- [ ] **Step 3: Implement validation portfolio UI**

Reuse portfolio/table/filter patterns without duplicating extraction state. Display deterministic evidence, current reviewed values, finding status, and category coverage.

- [ ] **Step 4: Implement correction preview dialog**

Display every affected record/field with before and proposed value, rationale, provider metadata for AI suggestions, and explicit Apply/Reject. Disable Apply while mutation is pending.

- [ ] **Step 5: Extend categorized alerts**

The deterministic backend maps finding types to workflow area/alert type. The Alerts Dashboard filters and renders those categories with client/period/source evidence and existing AI explanation safeguards.

- [ ] **Step 6: Run focused tests**

Run Task 8 commands and expect all tests to pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/documents/validation-portfolio.tsx frontend/components/documents/correction-preview-dialog.tsx frontend/components/documents/findings-panel.tsx frontend/lib/types.ts backend/app/api/v1/alerts.py backend/app/schemas/alerts.py frontend/components/alerts/alerts-dashboard.tsx frontend/components/documents/*.test.tsx backend/tests/integration/test_phase3_validation_alerts.py frontend/components/alerts/alerts-dashboard.test.tsx
git commit -m "feat: add validation correction and alert review UI"
```

### Task 9: Application-wide Light/Dark/System theme

**Files:**
- Create: `frontend/lib/theme.tsx`
- Create: `frontend/components/ui/theme-toggle.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/components/dashboard/app-shell.tsx`
- Modify: `frontend/components/ui/card.tsx`
- Modify: `frontend/components/ui/button.tsx`
- Modify: `frontend/components/ui/badge.tsx`
- Modify: relevant files under `frontend/app/` and `frontend/components/` containing fixed light-only colors
- Test: `frontend/lib/theme.test.tsx`
- Test: `frontend/components/ui/theme-toggle.test.tsx`
- Test: existing frontend component tests

**Interfaces:**
- Produces `ThemeProvider`, `useTheme()`, and `ThemeToggle` with `light | dark | system`.
- Persists only the theme preference key and follows `prefers-color-scheme` in system mode.

- [ ] **Step 1: Write failing theme tests**

Test stored preference load, system fallback, document root class updates, toggle labels/accessibility, and server-safe initialization.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `npm.cmd test -- lib/theme.test.tsx components/ui/theme-toggle.test.tsx`

- [ ] **Step 3: Implement provider and no-flash initialization**

Add a small inline initialization script or server-safe pre-hydration strategy that reads only the theme preference and applies the correct root class before paint. Wrap the app in `ThemeProvider`.

- [ ] **Step 4: Define semantic tokens and migrate fixed colors**

Add light/dark CSS variables for canvas, surfaces, elevated surfaces, text, muted text, borders, focus, actions, statuses, and shadows. Replace light-only literals across auth, upload, dashboard, application, documents, validation, reconciliation, alerts, and audit UI with semantic classes/tokens.

- [ ] **Step 5: Add top-bar and public/auth toggles**

Place the labeled control in the authenticated header; public/auth layouts receive a compact accessible control. Preserve mobile navigation and focus visibility.

- [ ] **Step 6: Run full frontend tests and build**

Run: `npm.cmd test`

Run: `npm.cmd run lint`

Run: `npm.cmd run build`

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/theme.tsx frontend/components/ui/theme-toggle.tsx frontend/app/layout.tsx frontend/app/globals.css frontend/components frontend/app frontend/lib/theme.test.tsx
git commit -m "feat: add accessible light and dark themes"
```

### Task 10: Full regression, migration, security, and manual verification

**Files:**
- Modify: `.env.example` only if a new non-secret setting is necessary
- Modify: `README.md`
- Modify: `docs/phase-3.md`
- Test: complete backend and frontend suites

**Interfaces:**
- Documents exact workflow, migration commands, runtime limitations, and manual test evidence.

- [ ] **Step 1: Apply migrations to the authorized Supabase project**

Run the repository’s established Supabase link/push workflow. Confirm both new migrations are recorded without rewriting older migrations.

- [ ] **Step 2: Run backend verification**

Run: `cd backend; ..\.venv\Scripts\python.exe -m pytest -q`

Run the repository’s configured backend lint/import smoke commands.

- [ ] **Step 3: Run frontend verification**

Run: `cd frontend; npm.cmd test`

Run: `cd frontend; npm.cmd run lint`

Run: `cd frontend; npm.cmd run build`

- [ ] **Step 4: Run repository checks**

Run: `git diff --check`

Run a tracked-file secret-pattern scan excluding local `.env` files and dependencies. Inspect every match before reporting.

- [ ] **Step 5: Perform manual end-to-end test with synthetic files**

Verify partial upload, explicit Submit acknowledgement, asynchronous status, later second batch, every category portfolio, combined portfolio, large review workspace, approval gate, deterministic validation, manual correction, AI proposal/confirmation, validation alert creation, and both themes. Do not claim real NVIDIA/Groq success unless live provider calls were observed.

- [ ] **Step 6: Update documentation with observed results**

Record actual commands/results, response timing, provider/model routing, migrations, limitations, and manual verification status.

- [ ] **Step 7: Final atomic commit**

```bash
git add .env.example README.md docs/phase-3.md
git commit -m "docs: describe submission and review workflow"
```

- [ ] **Step 8: Report repository state**

Run: `git diff --stat`

Run: `git status --short`

Report existing unrelated dirty changes separately from this plan’s commits.
