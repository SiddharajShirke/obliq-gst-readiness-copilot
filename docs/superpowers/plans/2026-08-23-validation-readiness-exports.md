# Validation-Gated Readiness and Export Implementation Plan

1. Add unit tests for branch-aware workflow derivation, zero-finding validation, and reconciliation review denominators.
2. Refactor workflow progress to expose main readiness, independent reconciliation availability/completion, and export gates.
3. Add API tests that reject premature main/reconciliation exports and permit the two exports independently.
4. Expand readiness aggregation and ReportLab/CSV generators with manifest, normalized GST, validation, alert, and reconciliation evidence while excluding developer ground truth.
5. Add scoped bulk validation and reconciliation review API tests and endpoints; align extraction bulk audit semantics.
6. Add frontend component tests for filter-aware Select All, selected counts, indeterminate state, and explicit bulk actions.
7. Update the application workspace, extraction, validation, and reconciliation components to consume backend progress and export eligibility.
8. Run focused backend/frontend tests, full suites where practical, frontend production build, dependency/import and Docker smoke checks, lint, secret scan, and `git diff --check`.

