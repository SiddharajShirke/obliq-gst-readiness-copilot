# Tenant Guided Demo, Validation, and Extraction Reliability Design

## Scope

This Phase 4 repair preserves the existing Phase 1-4 architecture. It adds
idempotent tenant onboarding, persistent Guided Demo runs, richer validation
evidence, safer AI correction assistance, accurate application summaries, and a
deployment-portable extraction boundary. Phase 5 media ingestion remains excluded.

## Tenant onboarding

After Supabase authentication, the frontend calls one idempotent backend bootstrap
endpoint. The endpoint validates the Supabase user without requiring an existing
firm membership, then atomically ensures one personal firm, one firm-admin
membership, one tenant-scoped Raj Traders Guided Demo client, one base GST
application, and the six required checklist rows. Repeated calls return the same
workspace. Users may create any number of additional client profiles and GST
applications through the existing APIs.

The Raj Traders row is distinguished by `demo_scenario = guided_demo_template`.
No user-created client is inferred from its name. A forward-only database RPC is
used so concurrent first-login requests cannot create duplicate workspaces.

## Guided Demo runs

`guided_demo_runs` stores user-, firm-, and application-scoped run history. Starting
or restarting a run reuses the existing WhatsApp session-cloning service and never
mutates the template application. Runs are numbered monotonically per user as
`Guided Demo 1`, `Guided Demo 2`, and so on. Completion is persisted only after a
successful Export Pack response. Completed runs remain visible on Overview.

The completion modal waits for an explicit user action. It offers an Open Client
Profile action and does not automatically navigate. Restart explicitly creates the
next run.

## Extraction reliability

AI output remains schema constrained. Provider output is retained before
normalization. Provenance values such as source page/row accept only positive
integer representations; invalid values become unknown rather than invalidating an
otherwise valid GST record. Monetary, tax, GSTIN, and date fields remain strictly
validated. Stored processing errors contain a safe diagnostic code and concise
message, never secrets or provider payloads.

Deterministic parsing remains first. Tesseract remains a supported OCR route because
the backend Docker image installs it. `TESSERACT_CMD` is a local override only; a
deployed container uses the binary from PATH. NVIDIA/Groq remain hosted,
environment-configured providers. Provider failure may use the existing bounded
fallback once; it cannot mark a document complete without validated normalized data.

## Validation evidence and AI assistance

The validation portfolio enriches each finding with client-facing evidence derived
from its application, document, and extracted record: filename/category, invoice or
document number, party, GSTIN, transaction date, period, taxable/tax totals, and
source page/row where available. Technical UUIDs remain secondary traceability
details.

AI correction requests include only the selected scoped findings, exact
deterministic evidence, and relevant extracted/source context. AI remains read-only.
When evidence cannot support a safe field replacement, the response gives a useful
CA review recommendation rather than fabricating a value. Persistence still requires
the existing before/after preview and explicit confirmation.

## Dynamic workflow state

The backend workflow-progress service remains the source of truth. Application list
responses expose a derived display status/workflow snapshot. Overview, Clients, and
GST Works render that derived state rather than stale `applications.status` values.

## Upload completion

The public upload page redirects only after all six required categories are stored,
all currently uploaded files have been submitted, and the latest extraction batch is
terminal. It shows a five-second completion notice and a Go to Overview action. The
redirect target is `/dashboard`; unauthenticated browsers are handled by the existing
auth guard.

## Theme

Light-mode semantic action tokens use the OBLIQ blue palette rather than pure black.
Selected surfaces use a soft blue background with dark blue text. Dark-mode tokens
remain unchanged. Icons continue to inherit `currentColor`.

## Seed cleanup

The active hosted tenant retains Raj Traders, PHASE 2, and every non-seeded
user-created record. The four verified fixed seeded clients (ABC Electronics, Nova
Services, City Retail, Mehta Consulting) and their dependent database rows/private
Storage objects are removed by exact IDs after a dry run. Future seed tooling creates
only the Raj Traders template. Cleanup never matches arbitrary client names.
