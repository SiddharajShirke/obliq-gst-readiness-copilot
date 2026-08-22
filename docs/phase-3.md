# Phase 3 prototype workflow

Phase 3 adds structured GST extraction, CA review, deterministic GSTR-2B reconciliation,
and explicitly raised alerts. It preserves the Phase 1 Vonage transport and Phase 2 secure
browser upload capability.

## Runtime routes

- `POST /api/v1/public/upload/{token}` handles a selected checklist category.
- `POST /api/v1/public/upload/{token}/bulk-folder` routes browser folder files.
- `POST /api/v1/public/upload/{token}/bulk-zip` safely expands and routes a ZIP.
- `POST /api/v1/public/upload/{token}/submit` atomically submits only the
  currently unsubmitted documents and returns `202` before extraction completes.
- `GET /api/v1/public/upload/{token}/status` exposes the scoped latest-batch counters.
- `GET /api/v1/applications/{id}/documents/portfolio` serves the six category
  portfolios or the combined GST portfolio.
- `POST /api/v1/applications/{id}/extractions/bulk-review` applies an explicit
  CA approve/reject action to the selected reviewed rows.
- `GET /api/v1/applications/{id}/documents/extraction-summary` serves cards and tables.
- `POST /api/v1/applications/{id}/validation-corrections/proposals` creates a
  manual or AI-assisted, read-only correction proposal.
- `POST /api/v1/validation-corrections/{id}/apply` applies a confirmed proposal
  and reruns deterministic validation; `/reject` preserves the current data.
- `POST /api/v1/findings/{id}/raise-alert` creates a categorized validation alert
  only after an explicit CA action.
- `POST /api/v1/applications/{id}/reconciliation/gstr2b` stores and parses GSTR-2B.
- `POST /api/v1/applications/{id}/reconcile` starts exact Option A reconciliation.
- `POST /api/v1/reconciliation/items/{id}/raise-alert` explicitly creates an alert.
- `GET /api/v1/alerts` and `GET /api/v1/alerts/{id}` serve the Alerts Dashboard.

## Provider routing

Structured CSV, Excel, and JSON inputs remain deterministic. PyMuPDF and python-docx read
text documents. Tesseract is installed in the existing backend container and is used for
scanned pages before hosted model assistance. NVIDIA's hosted OpenAI-compatible/NIM endpoint
is the lightweight provider. Groq is the heavy extraction fallback. Model identifiers and
credentials are backend-only environment variables.

`NVIDIA_VISION_MODEL` is optional and must name a verified vision-capable deployment. The
runtime does not pretend a text-only model accepts images and does not fall back to Gemini.

## Boundaries

Reconciliation outcomes are deterministic and use exact normalized Decimal values. AI only
explains an alert after a CA creates it. Phase 4 document RAG and Phase 5 Vonage media intake
remain intentionally unimplemented.

## Submission and review boundary

Public uploads are permanently stored in the private Supabase bucket with
`awaiting_submission`. The user can submit the currently uploaded documents as one
immutable batch and add a later batch through the same link. FastAPI background tasks
run deterministic parsing, OCR, NVIDIA, and Groq routing after the prompt `202`
acknowledgement. The 5–6 second target applies to submission acknowledgement—not to
completion of external AI/OCR work.

Normalized rows remain review-gated. Only `approved` and `edited_and_approved` rows
enter deterministic validation. AI correction assistance creates a before/after
proposal; it cannot mutate a record until an authorized CA confirms it. Applying a
proposal preserves original extraction output and refreshes validation findings.

The frontend includes Light, Dark, and System modes, the six category portfolios plus
Combined GST Portfolio, table/card views, large record review workspaces, and scoped
validation/reconciliation alert views. These are presentation and review controls only;
they do not change the deterministic GST calculations.
