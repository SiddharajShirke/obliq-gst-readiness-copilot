# Dynamic Extraction-to-Validation Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect extraction approval to approved-data validation and render accurate dynamic workflow and categorized validation portfolios for the effective application.

**Architecture:** Centralize validation persistence and post-review transitions in one backend service. Extend the effective application status response with a database-derived workflow snapshot and expose a categorized validation portfolio consumed by polling frontend components.

**Tech Stack:** FastAPI, Pydantic, Supabase/PostgreSQL, Next.js, React, TypeScript, Vitest, pytest

**Spec:** `docs/superpowers/specs/2026-08-23-dynamic-extraction-validation-workflow-design.md`

## Global Constraints

- Work on the existing `Phase-4` branch only.
- Preserve the base application and operate on the effective cloned application.
- Persist validation findings only from approved or edited-and-approved records.
- Keep Alerts Dashboard creation behind explicit CA Raise Alert action.
- Keep existing manual and AI correction confirmation workflows.
- Do not introduce static result data, Phase 5 ingestion, filing readiness, or new infrastructure.
- Preserve `frontend/next-env.d.ts` and `.superpowers/` unless separately authorized.

---

### Task 1: Central validation workflow service

**Files:**
- Create: `backend/app/services/validation_workflow.py`
- Modify: `backend/app/api/v1/compliance.py`
- Test: `backend/tests/unit/test_validation_workflow.py`

**Interfaces:**
- Consumes: existing `validate_invoice`, `detect_duplicate_groups`, and `DataStore` methods.
- Produces: `run_application_validation(store, application_id, firm_id)` and `advance_after_extraction_review(store, application_id, firm_id)`.

- [ ] **Step 1: Write failing tests for approved-only validation and transition states**

```python
result = await advance_after_extraction_review(store, application_id=APP_ID, firm_id=FIRM_ID)
assert result.current_stage == "validation_review"
assert result.eligible_record_count == 1
assert all(row["invoice_record_id"] == approved["id"] for row in result.findings)
```

- [ ] **Step 2: Run the focused tests and confirm missing-service failures**

Run: `pytest -q tests/unit/test_validation_workflow.py`
Expected: FAIL because the validation workflow service does not exist.

- [ ] **Step 3: Move deterministic application validation into the service**

Implement approved-record filtering, finding regeneration, duplicate checks, application status update, and typed result objects. Make the existing `/validate` route call the service.

- [ ] **Step 4: Run focused validation tests**

Run: `pytest -q tests/unit/test_validation_workflow.py tests/integration/test_phase3_extraction_bulk_review.py tests/integration/test_phase3_validation_corrections_api.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```text
feat(validation): centralize approved record workflow
```

### Task 2: Connect every extraction review path

**Files:**
- Modify: `backend/app/api/v1/documents.py`
- Modify: `backend/app/services/document_processing/processor.py`
- Test: `backend/tests/integration/test_phase3_extraction_bulk_review.py`
- Test: `backend/tests/integration/test_document_flow.py`

**Interfaces:**
- Consumes: `advance_after_extraction_review` from Task 1.
- Produces: synchronized document/extraction/record reviews and automatic validation after all current records are reviewed.

- [ ] **Step 1: Add failing partial/final/single-document review tests**

```python
assert partial_response.json()["workflow"]["current_stage"] == "extraction_review"
assert final_response.json()["workflow"]["current_stage"] == "validation_review"
assert all(row["review_status"] == "approved" for row in document_records)
```

- [ ] **Step 2: Verify failures show missing transitions and record synchronization**

Run: `pytest -q tests/integration/test_phase3_extraction_bulk_review.py tests/integration/test_document_flow.py`
Expected: FAIL on workflow/status assertions.

- [ ] **Step 3: Implement review transition calls and remove pre-approval finding persistence**

Bulk review, approve, reject, and edit-and-approve update associated records, then call the transition service. The processing graph keeps only an in-memory preliminary finding count for extraction review status.

- [ ] **Step 4: Run focused tests**

Run: `pytest -q tests/integration/test_phase3_extraction_bulk_review.py tests/integration/test_document_flow.py tests/unit/test_phase3_processing.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```text
feat(extraction): advance approved records to validation
```

### Task 3: Effective application workflow snapshot

**Files:**
- Create: `backend/app/services/workflow_progress.py`
- Modify: `backend/app/api/v1/applications.py`
- Modify: `frontend/lib/types.ts`
- Test: `backend/tests/unit/test_workflow_progress.py`
- Test: `backend/tests/integration/test_phase2_connectivity.py`

**Interfaces:**
- Produces: `get_workflow_progress(store, application_id)` and `DocumentCollectionStatus.workflow`.

- [ ] **Step 1: Add failing cloned-state and dynamic-progress tests**

```python
assert response["effective_application_id"] == CLONE_ID
assert response["workflow"]["application_status"] == "validation_review"
assert response["workflow"]["extraction"]["approved_count"] == 24
assert base_application["status"] == "not_started"
```

- [ ] **Step 2: Verify failures against the current collection-only response**

Run: `pytest -q tests/unit/test_workflow_progress.py tests/integration/test_phase2_connectivity.py`
Expected: FAIL because `workflow` is missing.

- [ ] **Step 3: Implement database-derived milestones and percentage**

Calculate requested, received, extraction review ratio, validation review ratio, and reconciliation state from the effective application and related rows. Never consult the base status after effective scope resolution.

- [ ] **Step 4: Run focused tests**

Run: `pytest -q tests/unit/test_workflow_progress.py tests/integration/test_phase2_connectivity.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```text
feat(workflow): derive effective application progress
```

### Task 4: Categorized validation portfolio API

**Files:**
- Create: `backend/app/services/validation_portfolio.py`
- Modify: `backend/app/api/v1/compliance.py`
- Modify: `backend/app/schemas/documents.py`
- Test: `backend/tests/integration/test_validation_portfolio_api.py`

**Interfaces:**
- Produces: `GET /applications/{application_id}/validation-portfolio` with summary and six category objects.

- [ ] **Step 1: Write failing category, grouping, alert, and exclusion tests**

```python
assert [row["type"] for row in payload["categories"]] == EXPECTED_SIX_TYPES
assert payload["categories"][0]["requirement_status"] == "received"
assert ground_truth_id not in str(payload)
assert gstr2b_id not in str(payload)
assert category["alerts"][0]["workflow_area"] == "validation"
```

- [ ] **Step 2: Run and verify the missing-route failure**

Run: `pytest -q tests/integration/test_validation_portfolio_api.py`
Expected: FAIL with 404.

- [ ] **Step 3: Implement application-scoped category assembly**

Join requirements, normalized records, current findings, and explicitly raised validation alerts in service code. Group result sub-cards from live finding types; do not hard-code result values.

- [ ] **Step 4: Run focused API tests**

Run: `pytest -q tests/integration/test_validation_portfolio_api.py tests/integration/test_phase3_alerts.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```text
feat(validation): expose categorized live portfolio
```

### Task 5: Dynamic workspace progress UI

**Files:**
- Modify: `frontend/app/dashboard/applications/[applicationId]/page.tsx`
- Modify: `frontend/lib/types.ts`
- Create: `frontend/components/workflow/workflow-progress.tsx`
- Create: `frontend/components/workflow/workflow-progress.test.tsx`

**Interfaces:**
- Consumes: `DocumentCollectionStatus.workflow` from Task 3.
- Produces: dynamic overall workflow bar and steps while retaining separate collection progress.

- [ ] **Step 1: Write failing effective-workflow rendering tests**

```tsx
expect(rendered).toContain("Validation Review")
expect(rendered).toContain("72%")
expect(rendered).not.toContain("Ready for Filing ✓")
```

- [ ] **Step 2: Run and verify failure**

Run: `npm.cmd test -- components/workflow/workflow-progress.test.tsx`
Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the workflow component and replace base-status calculations**

Render backend-provided percentage and step states. Keep the Overview collection card driven by `received_count`, `missing_count`, and collection `progress_percent`.

- [ ] **Step 4: Run focused frontend tests**

Run: `npm.cmd test -- components/workflow/workflow-progress.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```text
feat(workflow): render dynamic application progress
```

### Task 6: Six-category dynamic Validation UI

**Files:**
- Modify: `frontend/components/documents/findings-panel.tsx`
- Modify: `frontend/components/documents/findings-panel.test.tsx`
- Modify: `frontend/lib/types.ts`

**Interfaces:**
- Consumes: validation portfolio from Task 4.
- Preserves: correction proposal dialog, resolve/accept, and explicit Raise Alert API calls.

- [ ] **Step 1: Add failing six-category/sub-card/live-alert tests**

```tsx
expect(html).toContain("Credit & Debit Notes")
expect(html).toContain("GST Special Transactions")
expect(html).toContain("Wrong Period")
expect(html).toContain("Raised validation alerts")
expect(html).not.toContain("Synthetic finding")
```

- [ ] **Step 2: Verify current component fails the portfolio expectations**

Run: `npm.cmd test -- components/documents/findings-panel.test.tsx`
Expected: FAIL because it fetches only a flat findings list.

- [ ] **Step 3: Implement polling category cards and dynamic sub-cards**

Poll every 2.5 seconds, render requirement status and live counts, and retain existing finding review/correction controls. Display raised validation alerts from the application-scoped response.

- [ ] **Step 4: Run focused frontend tests**

Run: `npm.cmd test -- components/documents/findings-panel.test.tsx components/documents/correction-preview-dialog.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```text
feat(validation): render categorized live review portfolio
```

### Task 7: Full verification

**Files:**
- Verify only; no unrelated fixes.

- [ ] **Step 1: Run backend suites**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Run frontend suites and build**

Run: `npm.cmd test`
Run: `npm.cmd run lint`
Run: `npm.cmd run build`
Expected: tests/build pass; no new lint errors.

- [ ] **Step 3: Verify hosted Raj Traders state**

Approve a fresh/pending extracted record, verify the effective clone advances, validation is regenerated from approved records, category cards update, and no Alert is created until explicit Raise Alert.

- [ ] **Step 4: Run repository checks**

Run: `git diff --check`
Run: secret scan over the task diff.
Expected: no whitespace errors or committed secrets.

- [ ] **Step 5: Commit verification-only fixes if necessary**

Do not commit `frontend/next-env.d.ts` or `.superpowers/`.
