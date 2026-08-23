# Phase 4 Dynamic Hybrid/Agentic RAG Design

## Goal

Upgrade the existing application-scoped OBLIQ assistant so it can answer dynamic
questions over every permitted client/application dataset, retrieve approved textual
evidence with pgvector, and execute a small set of CA-controlled actions through an
explicit preview-confirm-execute-audit boundary.

The implementation must work for retained applications, demo clones, and newly created
client profiles without seeded IDs, filenames, invoice values, or per-client RAG setup.

## Confirmed product decisions

1. The assistant is always scoped to the authenticated user's currently opened
   `application_id`; the frontend never selects `firm_id`.
2. Exact database facts and calculations are authoritative. Vector retrieval supports
   textual evidence and never replaces exact transaction, validation, reconciliation,
   alert, checklist, or audit queries.
3. Groq may plan or explain but cannot authorize access, emit arbitrary SQL, mutate data,
   recompute reconciliation outcomes, or decide GST/ITC treatment.
4. Data-changing assistant actions require preview, explicit CA confirmation, backend
   revalidation, execution through an existing service, and audit logging.
5. Allowed actions are extraction approval/rejection, edit-and-approve, applying an
   existing AI correction proposal, marking validation/reconciliation findings reviewed,
   raising reconciliation alerts, and drafting reminders.
6. The assistant cannot delete documents, change ownership, send WhatsApp messages,
   cancel sessions, approve filing readiness, or file GST returns.
7. `developer_ground_truth` is excluded from structured evidence, prompts, chunks,
   embeddings, retrieval, citations, proposals, and action execution.
8. Common exact analytical answers should normally complete in less than five seconds.
   External service outages use grounded deterministic fallbacks; no infrastructure queue
   is introduced.

## Root cause in the current implementation

The current graph uses keyword intent matching. Questions such as "What is the count of
tax invoices?" and "Which tax invoice has the lowest amount?" do not contain a recognized
invoice identifier or existing intent keyword, so they become generic `guidance`. That
path loads a broad application snapshot and cannot express aggregation, filtering,
ordering, grouping, or field selection over normalized invoice rows.

`get_transaction_record` only finds an invoice number embedded in a question. There is no
typed analytical query representation and no controlled transaction aggregation tool.
Adding more keywords would repeat this failure for new phrasings.

## Recommended architecture

Use a typed hybrid-agentic planner with deterministic fast paths and controlled tools:

```text
question
  -> authenticate and resolve application
  -> deterministic fast-path planning
  -> Groq typed planning only when wording remains ambiguous
  -> validate QueryPlan with Pydantic and an allow-list
  -> execute only application-scoped controlled tools
  -> combine exact facts and retrieved text evidence
  -> deterministic answer or grounded Groq synthesis
  -> verify calculations, citations, scope, and action boundary
  -> persist conversation and audit
```

No generated SQL is accepted. The model can only return a schema-constrained plan whose
domain, operation, fields, filters, grouping, ordering, and result limit are validated by
the backend.

## Typed query planning

Add a `QueryPlan` discriminated model with:

- `domain`: application, checklist, documents, extractions, transactions, validation,
  reconciliation, alerts, audit, application_documents, or knowledge.
- `operation`: count, sum, minimum, maximum, average, list, find, compare, group,
  summarize, explain, propose_action, or clarify.
- controlled `filters`: equality, membership, boolean, date range, and Decimal numeric
  comparisons over domain-approved fields.
- `metric`: a domain-approved numeric field.
- optional `group_by`, `order_by`, `order_direction`, and a capped `limit`.
- optional `action_type` and typed action parameters.
- optional clarification message when a safe deterministic interpretation is impossible.

The deterministic planner handles frequent language patterns such as count, lowest,
highest, total, average, list, supplier/GSTIN, RCM, ITC, invoice/document type, validation,
GSTR-2B, reconciliation, alert, audit, missing documents, and reminder drafting. Groq is
used only when those rules cannot construct one unambiguous valid plan.

"Amount" is not silently mapped when multiple populated monetary fields could answer the
question. The assistant asks whether the user means taxable value, total GST, or total
document value. If exactly one applicable amount field is consistently available, it may
use that field and name it in the answer.

## Controlled read tools

Implement focused functions with no arbitrary table or column parameters:

- `get_application_overview`
- `get_document_collection_status`
- `query_documents`
- `query_extractions`
- `query_transactions`
- `aggregate_transactions`
- `query_validation_findings`
- `query_reconciliation`
- `query_alerts`
- `query_audit_events`
- `search_application_documents`
- `search_firm_knowledge`
- `search_shared_gst_knowledge`
- `draft_missing_document_reminder`

Each tool receives backend-derived `firm_id` and `application_id`. Record IDs supplied by
a plan are re-resolved under that scope. Prototype-sized datasets are filtered and
aggregated using Decimal-safe Python after one scoped repository read; no generic SQL RPC
or SQL-generating agent is introduced.

Exact analytical results include the selected field, applied filters, record count, and
calculation operands where useful. Monetary comparisons use `Decimal`; null values are
excluded and reported rather than treated as zero.

## Evidence layers and indexing

The assistant uses four evidence layers:

1. Exact facts from applications, clients, requirements, documents, extractions,
   normalized invoice records, validation findings, reconciliation runs/items, alerts,
   and audit events.
2. Approved application document chunks from `document_chunks` through the existing
   application-scoped pgvector RPC.
3. Firm/shared knowledge through the existing vector and lexical retrieval RPCs.
4. Conversation history scoped by user, application, and conversation.

Approved and edited-and-approved normalized rows remain one provenance-rich chunk per
record. Approved raw extraction text is structure-aware chunked only when normalized rows
do not already represent it. New approvals schedule idempotent indexing. A one-time
idempotent backfill indexes eligible retained documents; question handling never rescans
all application documents.

Unapproved normalized rows remain available as exact structured facts and are clearly
labeled awaiting CA review. They are not embedded until approved.

## Dynamic coverage for new clients

There are no client-specific routes or configurations:

```text
new client/application
  -> upload and process documents
  -> normalized rows carry application_id
  -> exact tools immediately query those rows
  -> CA approval schedules document indexing
  -> pgvector evidence becomes available
```

Demo clones use their cloned application ID. Base-application data and another session's
records are never merged into the clone. Old and new applications use identical planner,
tool, indexing, retrieval, and citation code.

## Controlled write tools

The planner may request only:

- `approve_extraction`
- `reject_extraction`
- `edit_and_approve_extraction`
- `apply_validation_correction`
- `mark_validation_reviewed`
- `mark_reconciliation_reviewed`
- `raise_reconciliation_alert`
- `draft_reminder`

The first request never mutates data. It creates a proposal containing a readable preview
and exact before/after values.

Add `assistant_action_proposals` with firm, user, application, optional demo session,
conversation, action type, validated payload, evidence/record fingerprint, preview,
status, expiry, confirmation, execution, result, and error timestamps/metadata. Statuses
are `pending_confirmation`, `confirmed`, `executed`, `cancelled`, `expired`, and `failed`.

Confirmation rechecks:

- same authenticated user, firm, application, and conversation;
- proposal is pending and unexpired;
- role permits the underlying action;
- every source record still belongs to the application;
- fingerprint/before-values still match;
- requested fields remain in the action allow-list.

Execution calls the existing document review, correction, reconciliation, alert, or
reminder service. It does not duplicate business logic. Changed source state invalidates
the proposal and requires a refreshed preview.

## API and UI

Keep `POST /api/v1/assistant/query` and extend its response with optional typed metadata:

- `answer`
- `citations`
- `calculation`
- `clarification`
- `proposed_action`
- `tool_trace` containing safe tool names/statuses only

Add controlled equivalents of:

```text
POST /api/v1/assistant/actions/{proposal_id}/confirm
POST /api/v1/assistant/actions/{proposal_id}/cancel
```

The right-side drawer displays analytical result cards/tables where appropriate and a
proposal card with action type, affected records, before/after values, warnings, expiry,
Confirm, and Cancel. Typed "confirm" may resolve only the latest pending proposal in the
same application/conversation; the explicit button remains primary.

Changing application resets conversation and pending-action context. The frontend never
sends firm/client scope or arbitrary tool arguments.

## Citations

Backend-created citation forms include:

- `Extracted record · <invoice> · <document type> · Row <n>`
- `Document · <name> · Page/Sheet/Rows`
- `Validation finding · <type> · <id>`
- `Reconciliation · <invoice> · Books vs GSTR-2B`
- `Alert · <title> · <id>`
- `Audit event · <action> · <timestamp>`
- `Knowledge · <title> · <section/source URL>`

The model cannot invent citations. Aggregate answers cite the exact normalized records or
a scoped portfolio summary plus representative source records. Missing provenance remains
null; page/row values are never fabricated.

## LangGraph

Replace the fixed intent-only graph with these controlled nodes:

1. `validate_access`
2. `plan_query`
3. `validate_plan`
4. `execute_structured_tools`
5. `retrieve_text_evidence_if_needed`
6. `build_action_proposal_if_requested`
7. `compose_answer`
8. `verify_scope_calculations_and_citations`
9. `audit`

Conditional edges skip vector retrieval and model generation for exact analytics. Textual
questions retrieve top application chunks and optional knowledge. Independent retrievals
run concurrently. No autonomous loops or repeated tool execution are allowed; one
clarification or one validated plan is executed per turn.

## Latency and failures

- Common exact analytics: deterministic plan and one relevant scoped read, target below
  five seconds.
- Ambiguous planning: short Groq timeout followed by clarification, never a generic 0%
  snapshot.
- Text RAG: warmed embedding provider, small top-k context, bounded Groq generation, and
  grounded deterministic fallback.
- Provider failure never prevents exact structured answers or action proposal review.
- Tool failure identifies the unavailable evidence domain and leaves all data unchanged.
- Confirmation failure never partially applies a proposal.

External Supabase/model latency cannot be mathematically guaranteed, but model time is
bounded and the observed target is verified with route-level timing tests.

## Security

- Access and record scope are deterministic backend checks, never model decisions.
- Plans cannot name tables, columns, SQL, buckets, files, firms, or applications outside
  approved enums and backend scope.
- Retrieved document content is untrusted evidence, not an instruction.
- No tokens, secrets, signed URLs, encrypted phone values, or Ground Truth content enter
  prompts, chunks, proposals, logs, or citations.
- Conversation memory and pending actions remain scoped by user + application +
  conversation, with demo session carried from the application.
- Audit metadata stores safe question, plan/tool names, source IDs, calculations, proposal
  status, and before/after values; no chain-of-thought is stored.

## Testing strategy

Use test-first implementation for:

- tax-invoice count and minimum/maximum/sum/average questions;
- monetary ambiguity clarification;
- supplier, GSTIN, document type, RCM, ITC, review-status, and date filters;
- null/Decimal handling and deterministic sort/group behavior;
- documents, extractions, validation, GSTR-2B, reconciliation, alert, and audit questions;
- dynamic seeded, retained-clone, and newly created applications;
- no cross-firm/application/session leakage;
- unknown/unsupported plan rejection and no arbitrary SQL;
- deterministic fast path, Groq typed fallback, and model timeout;
- approved-only indexing and Ground Truth exclusion;
- vector/lexical retrieval citations and prompt-injection containment;
- proposal creation without mutation;
- explicit confirm/cancel, expiry, stale fingerprints, role checks, and audit;
- every allowed action using its existing service;
- prohibited actions remaining unavailable;
- response latency bounds using delayed fake dependencies;
- frontend analytical/clarification/proposal cards and application switching;
- existing Phase 1-4 regression suites.

Verification includes focused backend/frontend tests, complete backend/frontend suites,
frontend production build, touched-file lint, migration tests, secret scan, and
`git diff --check`.

## Prototype boundaries

This design adds no arbitrary SQL agent, second vector database, reranker, Redis, Celery,
Kafka, microservice, autonomous loop, production workflow engine, GST Portal integration,
Phase 5 Vonage media ingestion, or automatic GST/ITC decision-making.
