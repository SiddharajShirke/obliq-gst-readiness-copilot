# Validation-Gated Readiness and Independent Reconciliation Exports

## Goal

Make deterministic Validation Review completion the sole final gate for Ready for Filing and the main GST preparation export. GSTR-2B reconciliation becomes an independent review branch with its own completion percentage and export.

## Backend truth

`get_workflow_progress` remains the central calculation service. It derives collection, extraction, validation, reconciliation, readiness, and export eligibility from persisted records.

- Validation findings in `resolved` or `accepted` state are reviewed.
- An executed validation run with no review-required findings is complete.
- `ready_for_filing` is true exactly when validation review is 100%.
- Reconciliation completion never changes main readiness.
- Reconciliation review counts non-exact findings requiring CA review. A completed run with none is 100%.
- Application status is synchronized for compatibility, but endpoint authorization always uses freshly derived state.

## Exports

The existing private Supabase export bucket and short-lived signed URLs remain in use. ReportLab generates portable server-side PDFs; CSV generation uses the Python standard library.

The main export contains a preparatory PDF plus document manifest, normalized sales, normalized purchases, and validation CSV files. It may include the current reconciliation summary, but incomplete or absent reconciliation never blocks it.

The independent reconciliation export contains a working-report PDF and detailed evidence CSV. It is available only after all review-required items in the latest completed run are reviewed.

Developer ground-truth documents and records are excluded from every report.

## Selection and bulk review

Each review tab owns a filter-aware selection set. Select All affects only visible, eligible records and supports checked, unchecked, and indeterminate states. Changing the active filter removes hidden records from selection.

- Extraction: existing scoped bulk endpoint; pending review records only.
- Validation: new scoped bulk endpoint; open findings only; explicit Resolve or Accept action.
- Reconciliation: new scoped bulk endpoint; pending non-exact review findings only; explicit Mark Reviewed action.

All bulk endpoints verify firm, application, eligibility, and requested IDs before writing. Select All itself never writes data or raises alerts.

## UI

The workspace stepper and readiness cards render Validation and Ready for Filing as complete together. Reconciliation is displayed as a parallel branch and can remain not started or incomplete. Main and reconciliation export buttons use backend eligibility and backend endpoints enforce the same gates.

## Audit and boundaries

Transition and bulk/export events are recorded without per-checkbox noise. Readiness, percentages, and exports are deterministic; Groq and NVIDIA do not decide or generate workflow state. No filing, signing, GST Portal submission, job queue, or reporting platform is introduced.

