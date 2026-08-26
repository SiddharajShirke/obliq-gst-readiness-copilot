# Environment-Isolated End-to-End Repair Implementation Plan

> Execute test-first. Do not change the six-stage GST business workflow.

## Task 1: Add failing backend configuration and URL-integrity tests

**Files:**

- Modify `backend/tests/unit/test_config.py`
- Modify `backend/tests/integration/test_phase2_connectivity.py`
- Modify `backend/tests/unit/test_free_tier_deployment.py`

**Steps:**

1. Assert live Vonage rejects localhost/private `FRONTEND_URL` by default.
2. Assert test/mock runtime remains usable.
3. Assert approval rejects a wrong upload origin and a token not bound to the reminder.
4. Assert the provider is not called on rejection.
5. Assert `render.yaml` pins canonical non-secret origins and a supported NVIDIA model.
6. Run the focused tests and confirm they fail for the intended reasons.

## Task 2: Implement backend origin and reminder-integrity safeguards

**Files:**

- Modify `backend/app/config.py`
- Modify `backend/app/services/secure_upload.py`
- Modify `backend/app/api/v1/whatsapp.py`
- Modify `backend/app/api/v1/health.py`

**Steps:**

1. Add normalized-origin and unsafe-host helpers.
2. Harden live Vonage and production settings validation.
3. Add a secure upload-message verifier tied to the stored link.
4. Invoke verification immediately before provider send.
5. Expose safe origin/readiness diagnostics.
6. Run focused backend tests to green.

## Task 3: Add failing frontend hosted-origin tests

**Files:**

- Modify `frontend/lib/api.test.ts`

**Steps:**

1. Assert local pages may use local API defaults.
2. Assert hosted HTTPS pages reject missing/local/private API bases.
3. Assert the canonical Render API is accepted and normalized.
4. Run the focused test and confirm failure.

## Task 4: Implement hosted frontend fail-closed behavior

**Files:**

- Modify `frontend/lib/api.ts`

**Steps:**

1. Add optional runtime-origin input for pure testability.
2. Reject unsafe API hosts only when the page origin is hosted.
3. Preserve local development behavior.
4. Run frontend API and workflow tests to green.

## Task 5: Pin deployment origins and update configuration guidance

**Files:**

- Modify `render.yaml`
- Modify `.env.example`
- Modify `frontend/.env.local.example`
- Modify `README.md` only within the isolated worktree if needed

**Steps:**

1. Pin public non-secret deployment origins.
2. Pin the supported NVIDIA small-model identifier.
3. Document environment isolation and invalid-link recovery.
4. Preserve all existing highlighted reviewer/deployment sections.
5. Run deployment and config tests.

## Task 6: Add deterministic end-to-end workflow regression

**Files:**

- Add or modify a focused file under `backend/tests/integration/`

**Steps:**

1. Create and activate an isolated WhatsApp demo session.
2. Draft and send a request through the mock provider.
3. Resolve its public token.
4. Upload a representative supported document and submit the batch.
5. Execute background processing deterministically.
6. Assert extraction rows, invoice records, batch status, collection status, workflow progress, and audit events.
7. Add a scanned/image parser unit case if existing coverage does not prove OCR routing.

## Task 7: Verify and prepare production handoff

**Steps:**

1. Run focused backend tests.
2. Run the full backend suite.
3. Run frontend tests, lint, and production build.
4. Run Ruff checks.
5. Review `git diff`, ensure no secrets/tokens and no unrelated README changes.
6. Commit the isolated branch.
7. Report required Render/Vercel redeploy actions and a safe smoke-test checklist.
