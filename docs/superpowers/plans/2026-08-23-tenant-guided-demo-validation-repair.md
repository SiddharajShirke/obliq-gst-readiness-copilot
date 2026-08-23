# Tenant Guided Demo, Validation, and Extraction Reliability Plan

**Goal:** Deliver the approved Phase 4 tenant onboarding, persistent Guided Demo,
validation UX, dynamic progress, theme, upload-completion, and extraction reliability
repairs without regressing Phase 1-4.

**Spec:** `docs/superpowers/specs/2026-08-23-tenant-guided-demo-validation-repair-design.md`

## Task 1: Repair failed extraction at the schema boundary

1. Add failing schema/processor tests for non-numeric AI provenance and safe detailed
   processing errors.
2. Verify the tests fail for the observed `source_row = "A"` response.
3. Add narrow provenance normalization and preserve raw provider output.
4. Retry the failed hosted document through the existing processor and verify the
   seven-document batch becomes complete.
5. Run Phase 3 routing, normalization, submission, and processing tests.

## Task 2: Add idempotent tenant onboarding

1. Add failing backend tests for an authenticated Supabase user without membership,
   repeated bootstrap, exactly one Raj Traders template, and unlimited normal clients.
2. Add a forward-only RPC migration and onboarding API/service.
3. Add frontend auth tests for session bootstrap and implement the bootstrap call.
4. Update demo seeding/memory fixtures so user-facing defaults expose only Raj Traders.
5. Run authentication, clients, schema, and migration tests.

## Task 3: Persist numbered Guided Demo runs

1. Add failing backend and frontend tests for first run, completion persistence,
   explicit profile navigation, and monotonically numbered restart.
2. Add `guided_demo_runs` migration, service, schemas, and scoped endpoints.
3. Replace sessionStorage-only lifecycle with backend state while retaining local UI
   continuity during navigation.
4. Render completed/current runs on Overview and add explicit Restart.
5. Run Guided Demo and WhatsApp session regression tests.

## Task 4: Enrich validation evidence and AI review guidance

1. Add failing portfolio tests for human-readable evidence and correction tests that
   include selected findings.
2. Enrich portfolio findings without exposing unrelated application data.
3. Pass deterministic finding evidence into NVIDIA/Groq correction prompts.
4. Render detailed issue/evidence cards and useful no-safe-change guidance.
5. Preserve explicit preview/confirmation and existing correction audit behavior.

## Task 5: Derive accurate application list status

1. Add failing backend tests for derived application display status.
2. Enrich the application list from the central workflow service.
3. Update Overview, Clients, and GST Works to use derived state.
4. Add focused frontend status rendering tests.

## Task 6: Complete upload handoff and light-theme repairs

1. Add failing frontend tests for terminal-batch countdown/redirect and non-terminal
   behavior.
2. Add the five-second completion notice, Go now action, and authenticated Overview
   target.
3. Add failing token/component tests for light-mode action/selected states.
4. Update only light semantic action/active tokens and remove remaining hard-coded
   black action buttons in touched views.

## Task 7: Apply approved hosted-data cleanup

1. Produce a read-only dependency and Storage-object dry run for the four exact seeded
   client IDs.
2. Delete their private Storage objects, then their client rows and cascaded data.
3. Verify Raj Traders, PHASE 2, and all non-seeded records remain.
4. Record the cleanup result without exposing secrets or personal data.

## Task 8: Verification

1. Run focused backend and frontend tests after each TDD cycle.
2. Run the complete backend suite and complete frontend suite.
3. Run backend lint, frontend lint, frontend production build, Docker build, migration
   checks, `git diff --check`, and secret scan.
4. Inspect the final diff/status and report manual/live checks separately from mocks.

