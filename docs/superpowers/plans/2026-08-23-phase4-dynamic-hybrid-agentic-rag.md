# Phase 4 Dynamic Hybrid/Agentic RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the application-scoped assistant answer dynamic analytical questions over all permitted client data and execute a small CA-controlled action set through preview, confirmation, execution, and audit.

**Architecture:** Replace fixed keyword intents with a Pydantic-validated query plan, deterministic fast-path planning, controlled application-scoped read tools, conditional pgvector/knowledge retrieval, and a bounded Groq planning/synthesis fallback. Persist write proposals separately and execute them only after the same user confirms an unexpired, unchanged proposal through existing review/correction/reconciliation services.

**Tech Stack:** FastAPI, Pydantic v2, LangGraph, Supabase/PostgreSQL, pgvector, `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions), Groq, Next.js 16, React 19, TypeScript, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-phase4-dynamic-hybrid-agentic-rag-design.md`

## Global Constraints

- Preserve Phase 1-4 Vonage, secure upload, OCR/extraction, validation, reconciliation, alert, and existing application-scoped RAG behavior.
- Every read/write derives `firm_id`, user, role, and permitted `application_id` in the backend.
- Never accept arbitrary SQL, table names, column names, Storage paths, firm IDs, or client IDs from a model or browser.
- `developer_ground_truth` never enters facts, prompts, chunks, embeddings, retrieval, citations, proposals, or execution.
- Monetary calculations use `Decimal`; null is not zero.
- Groq never grants access, mutates records, recomputes reconciliation, or decides GST/ITC treatment.
- Every mutation requires preview, explicit CA confirmation, state revalidation, execution, and audit.
- No Redis, Celery, Kafka, second vector database, autonomous loop, Phase 5 media ingestion, or production GST filing.
- Preserve unrelated dirty-worktree changes and do not modify `frontend/next-env.d.ts` or `.superpowers/` for this feature.

---

### Task 1: Typed Query Plan and Deterministic Planner

**Files:**
- Create: `backend/app/schemas/assistant_tools.py`
- Create: `backend/app/services/rag/query_planner.py`
- Create: `backend/tests/unit/test_dynamic_rag_planner.py`
- Modify: `backend/app/services/llm/providers.py`

**Interfaces:**
- Produces: `QueryPlan`, `QueryDomain`, `QueryOperation`, `QueryFilter`, `ActionType`, and `plan_question(question: str, settings: Settings) -> QueryPlan`.
- `plan_question` first returns a deterministic plan; only unresolved wording calls `complete_groq_json` with a short timeout and validates the returned plan.

- [ ] **Step 1: Write failing planner tests**

```python
def test_count_tax_invoices_is_a_transaction_count_plan():
    plan = deterministic_plan("What is count of tax invoices?")
    assert plan.domain == "transactions"
    assert plan.operation == "count"
    assert plan.filters[0].field == "record_kind"
    assert plan.filters[0].value == "tax_invoice"

def test_lowest_invoice_amount_requires_clarification_when_field_is_ambiguous():
    plan = deterministic_plan("Which tax invoice has the lowest amount?")
    assert plan.operation == "clarify"
    assert "taxable value" in plan.clarification.lower()

def test_prohibited_delete_action_is_not_plannable():
    plan = deterministic_plan("Delete the purchase register")
    assert plan.operation == "clarify"
    assert plan.action_type is None
```

- [ ] **Step 2: Run planner tests and verify RED**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/unit/test_dynamic_rag_planner.py -q`

Expected: import failure because `assistant_tools` and `query_planner` do not exist.

- [ ] **Step 3: Implement strict Pydantic plan types**

Define enum-backed fields and validators. Limit filters to 12, result limit to 100, and fields to domain allow-lists. Use filter operators `eq`, `in`, `gte`, `lte`, `contains`, `is_null`, and `not_null`. Reject unsupported combinations during validation.

```python
class QueryPlan(BaseModel):
    domain: QueryDomain
    operation: QueryOperation
    filters: list[QueryFilter] = Field(default_factory=list, max_length=12)
    metric: str | None = None
    group_by: str | None = None
    order_by: str | None = None
    order_direction: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=20, ge=1, le=100)
    needs_text_evidence: bool = False
    needs_knowledge: bool = False
    action_type: ActionType | None = None
    action_parameters: dict[str, Any] = Field(default_factory=dict)
    clarification: str | None = None
```

- [ ] **Step 4: Implement deterministic parsing**

Cover count, lowest/highest, total/sum, average, list/find, group, compare, explain, document/checklist, extraction, validation, GSTR-2B/reconciliation, alert, audit, and the allowed action verbs. Normalize common GST terms such as tax invoice, sales invoice, purchase invoice, credit/debit note, RCM, ITC unavailable, books-only, and GSTR-2B-only.

- [ ] **Step 5: Implement bounded Groq plan fallback**

Add optional `timeout_seconds` to the existing Groq helper or wrap the call at the planner. Send only allowed domains/operations/fields and the question. Validate with `QueryPlan.model_validate`; on timeout/schema failure return a clarification plan, never generic guidance.

- [ ] **Step 6: Run planner tests and verify GREEN**

Run the Task 1 pytest command. Expected: all tests pass.

- [ ] **Step 7: Commit Task 1**

```powershell
git add backend/app/schemas/assistant_tools.py backend/app/services/rag/query_planner.py backend/app/services/llm/providers.py backend/tests/unit/test_dynamic_rag_planner.py
git commit -m "feat: add typed assistant query planner"
```

---

### Task 2: Application-Scoped Structured Read Tools

**Files:**
- Create: `backend/app/services/rag/structured_tools.py`
- Create: `backend/tests/unit/test_dynamic_rag_tools.py`
- Modify: `backend/app/services/rag/application_context.py`

**Interfaces:**
- Consumes: validated `QueryPlan`, backend-derived `firm_id`, `application_id`, and `DataStore`.
- Produces: `ToolResult(answer_data, rows, calculation, citations, source_types, confidence)` through `execute_query_plan(...)`.

- [ ] **Step 1: Write failing exact analytics tests**

Create memory-store records for two applications and assert:

```python
result = await execute_query_plan(store, firm_id=FIRM_ID, application_id=APP_A, plan=count_plan)
assert result.calculation == {"operation": "count", "value": 3, "record_count": 3}

minimum = await execute_query_plan(store, firm_id=FIRM_ID, application_id=APP_A, plan=min_plan)
assert minimum.rows[0]["invoice_number"] == "LOW/001"
assert minimum.calculation["metric"] == "invoice_total"
assert all(row["application_id"] == APP_A for row in minimum.rows)
```

Also test sum/average with `Decimal`, null exclusion, supplier/GSTIN/date/RCM/ITC/document/review filters, deterministic ordering, and a new application created during the test.

- [ ] **Step 2: Run tool tests and verify RED**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/unit/test_dynamic_rag_tools.py -q`

Expected: import failure for `structured_tools`.

- [ ] **Step 3: Implement scoped row loaders**

Create one loader per domain. For reconciliation items, first load the latest application run and then its items. For audit, filter by `application_id`. For extractions, resolve application documents before joining extraction rows. Reject rows whose application/firm scope does not match.

- [ ] **Step 4: Implement transaction filters and aliases**

Map `record_kind=tax_invoice` to invoice-like rows while excluding credit/debit notes, GSTR-2B, and developer references. Keep `invoice_category`, `document_type`, `source_type`, and `transaction_type` available as separate exact filters. Include `review_status` in returned data.

- [ ] **Step 5: Implement Decimal analytics**

Use `Decimal(str(value))` only for non-null values. Return the selected metric, included/excluded counts, filter summary, and winning record for minimum/maximum. Do not silently interpret an unresolved `amount` metric.

- [ ] **Step 6: Implement domain citations**

Build citations from records and real provenance. For aggregates, cite a scoped normalized-portfolio summary plus up to five representative records; for a winning minimum/maximum record cite its document, page/sheet/row and record ID.

- [ ] **Step 7: Run tool tests and verify GREEN**

Run the Task 2 pytest command. Expected: all tests pass.

- [ ] **Step 8: Commit Task 2**

```powershell
git add backend/app/services/rag/structured_tools.py backend/app/services/rag/application_context.py backend/tests/unit/test_dynamic_rag_tools.py
git commit -m "feat: add scoped rag analytics tools"
```

---

### Task 3: Conditional LangGraph Planner and Hybrid Retrieval

**Files:**
- Modify: `backend/app/agents/rag_assistant.py`
- Modify: `backend/app/schemas/rag.py`
- Modify: `backend/app/prompts/rag.py`
- Modify: `backend/app/services/rag/retrieval.py`
- Modify: `backend/tests/unit/test_phase4_application_rag.py`
- Create: `backend/tests/integration/test_dynamic_agentic_rag.py`

**Interfaces:**
- Consumes: `QueryPlan` and `ToolResult` from Tasks 1-2.
- Produces: existing `AssistantAnswer` plus optional `calculation`, `clarification`, `proposed_action`, and safe `tool_trace`.

- [ ] **Step 1: Write failing route tests for the reported questions**

```python
count = client.post("/api/v1/assistant/query", json={
    "application_id": app_id,
    "question": "What is count of tax invoices?",
})
assert count.status_code == 200
assert count.json()["calculation"]["operation"] == "count"
assert "application review snapshot" not in count.json()["answer"].lower()

lowest = client.post("/api/v1/assistant/query", json={
    "application_id": app_id,
    "question": "Which tax invoice has the lowest total invoice value?",
})
assert lowest.json()["calculation"]["operation"] == "minimum"
assert lowest.json()["citations"][0]["source_type"] == "structured_fact"
```

Add tests for validation, reconciliation, GSTR-2B-only, raised alerts versus findings, audit history, cross-application denial, and prompt-injection content.

- [ ] **Step 2: Run dynamic integration tests and verify RED**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/integration/test_dynamic_agentic_rag.py -q`

Expected: current snapshot response lacks `calculation` and fails exact assertions.

- [ ] **Step 3: Replace fixed graph nodes**

Implement nodes `validate_access`, `plan_query`, `validate_plan`, `execute_structured_tools`, `retrieve_text_evidence_if_needed`, `build_action_proposal_if_requested`, `compose_answer`, `verify_scope_calculations_and_citations`, and `audit`. Keep `_FallbackGraph` behavior equivalent when LangGraph is unavailable.

- [ ] **Step 4: Add conditional graph edges**

Skip embeddings and Groq for exact analytics. Run application-document and knowledge retrieval concurrently only when the validated plan requests them. Keep top-k bounded by existing settings.

- [ ] **Step 5: Extend response schemas safely**

Add typed `CalculationResult`, `ToolTraceItem`, and optional fields with defaults so existing frontend/API clients remain compatible. Backend citations remain authoritative.

- [ ] **Step 6: Implement grounded composition**

Use deterministic templates for counts, numeric extrema, sums, averages, lists, and clarification. Use Groq only to synthesize retrieved text/tool evidence, with current timeout and structured-output validation. On failure, render `ToolResult` rather than the old 0% message.

- [ ] **Step 7: Run focused Phase 4 tests and verify GREEN**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_phase4_application_rag.py tests/unit/test_rag_pipeline.py tests/integration/test_phase4_assistant.py tests/integration/test_dynamic_agentic_rag.py -q
```

- [ ] **Step 8: Commit Task 3**

```powershell
git add backend/app/agents/rag_assistant.py backend/app/schemas/rag.py backend/app/prompts/rag.py backend/app/services/rag/retrieval.py backend/tests/unit/test_phase4_application_rag.py backend/tests/integration/test_dynamic_agentic_rag.py
git commit -m "feat: route assistant through controlled langgraph tools"
```

---

### Task 4: Assistant Action Proposal Migration and Store Support

**Files:**
- Create: `supabase/migrations/202608230004_dynamic_agentic_rag.sql`
- Modify: `backend/app/repositories/memory.py`
- Create: `backend/tests/unit/test_dynamic_rag_migration.py`
- Create: `backend/tests/unit/test_assistant_action_proposals.py`

**Interfaces:**
- Produces: `assistant_action_proposals` persistence with one pending/executed lifecycle and RLS.

- [ ] **Step 1: Write failing migration assertions**

Read the migration and assert it contains the table, foreign keys, status/expiry checks, application/user/conversation index, RLS, authenticated policy, and service-role grants.

- [ ] **Step 2: Write failing memory-store proposal test**

Assert `get_store().tables["assistant_action_proposals"]` exists and isolates reset state.

- [ ] **Step 3: Run migration/proposal tests and verify RED**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/unit/test_dynamic_rag_migration.py tests/unit/test_assistant_action_proposals.py -q`

- [ ] **Step 4: Add forward-only SQL migration**

Create UUID primary key and columns for firm, user, application, optional demo session, conversation, action type, payload JSONB, preview JSONB, evidence fingerprint, status, expiry, confirmation, execution, result, error, and timestamps. Restrict statuses to `pending_confirmation`, `confirmed`, `executed`, `cancelled`, `expired`, and `failed`. RLS requires `user_id = auth.uid()`, firm access, and an application in that firm.

- [ ] **Step 5: Add memory table**

Add `assistant_action_proposals` to the deterministic table dictionary without changing seeded clients/applications.

- [ ] **Step 6: Run tests and verify GREEN**

Run the Task 4 pytest command.

- [ ] **Step 7: Apply hosted migration**

Run from repository root using the existing linked Supabase project:

```powershell
npx supabase db push
```

Verify the applied migration list with `npx supabase migration list` and do not recreate/reset Supabase.

- [ ] **Step 8: Commit Task 4**

```powershell
git add supabase/migrations/202608230004_dynamic_agentic_rag.sql backend/app/repositories/memory.py backend/tests/unit/test_dynamic_rag_migration.py backend/tests/unit/test_assistant_action_proposals.py
git commit -m "feat: persist assistant action proposals"
```

---

### Task 5: Reusable Review/Correction/Reconciliation Action Services

**Files:**
- Create: `backend/app/services/assistant_actions.py`
- Modify: `backend/app/api/v1/documents.py`
- Modify: `backend/app/api/v1/compliance.py`
- Modify: `backend/app/services/validation_corrections.py`
- Create: `backend/tests/unit/test_assistant_action_execution.py`

**Interfaces:**
- Produces: `create_action_proposal(...)`, `confirm_action_proposal(...)`, and `cancel_action_proposal(...)`.
- Reuses existing document indexing, correction, reconciliation alert explanation, audit, and validation services.

- [ ] **Step 1: Write failing no-mutation proposal tests**

For every allowed action, assert proposal creation changes only `assistant_action_proposals`. Assert extraction/reconciliation/finding/alert rows are unchanged before confirmation.

- [ ] **Step 2: Write failing confirmation safety tests**

Test same user/application/conversation, role, expiry, cancelled/executed proposal, stale fingerprint, cross-application record, and prohibited action. Assert failures leave source rows unchanged.

- [ ] **Step 3: Run action tests and verify RED**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/unit/test_assistant_action_execution.py -q`

- [ ] **Step 4: Implement proposal creation**

Resolve every target row, capture allowed before-values, hash canonical JSON with SHA-256, produce a human-readable preview, set a 15-minute expiry, and record `assistant_action_proposed` without secrets or source-document content.

- [ ] **Step 5: Extract reusable mutation helpers**

Move the existing route-level approve/reject/edit, finding resolution, reconciliation review, and reconciliation alert creation logic into service functions. Keep route status codes and payload behavior unchanged by calling those services from the existing routes.

- [ ] **Step 6: Implement confirmation execution**

Re-resolve records, compare fingerprint, update proposal to confirmed, execute exactly one service action, persist result/executed state, and record `assistant_action_confirmed` plus `assistant_action_executed`. On failure persist `failed` and safe error metadata.

- [ ] **Step 7: Reuse correction proposals**

For `apply_validation_correction`, require an existing `validation_correction_proposals` row scoped to the same application and call `apply_correction_proposal`. Preserve its own before/after data and rerun deterministic validation through the existing validation function.

- [ ] **Step 8: Run action and existing endpoint tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_assistant_action_execution.py tests/integration/test_phase3_extraction_bulk_review.py tests/integration/test_phase3_validation_corrections_api.py tests/integration/test_phase3_alerts.py -q
```

- [ ] **Step 9: Commit Task 5**

```powershell
git add backend/app/services/assistant_actions.py backend/app/api/v1/documents.py backend/app/api/v1/compliance.py backend/app/services/validation_corrections.py backend/tests/unit/test_assistant_action_execution.py
git commit -m "feat: execute confirmed assistant actions"
```

---

### Task 6: Assistant Action API and Conversation Integration

**Files:**
- Modify: `backend/app/api/v1/rag.py`
- Modify: `backend/app/schemas/rag.py`
- Modify: `backend/app/agents/rag_assistant.py`
- Create: `backend/tests/integration/test_assistant_actions_api.py`

**Interfaces:**
- Produces: `POST /api/v1/assistant/actions/{proposal_id}/confirm` and `/cancel`.
- Extends `/assistant/query` to return a proposal preview without executing it.

- [ ] **Step 1: Write failing API tests**

Assert an action question returns `pending_confirmation`; source data remains unchanged; confirm executes; cancel does not; a second confirmation returns `409`; another user/application receives `404`; and a prohibited action returns a safe refusal.

- [ ] **Step 2: Run API tests and verify RED**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/integration/test_assistant_actions_api.py -q`

- [ ] **Step 3: Implement action proposal response**

Add `ProposedAction` with ID, action type, title, preview, affected count, warnings, expiry, and status. Never return raw fingerprints or unrestricted payloads.

- [ ] **Step 4: Implement confirm/cancel routes**

Use `require_roles("firm_admin", "reviewer")`, except reminder drafting may also permit `gst_preparer`. Resolve proposal ownership inside the service and pass FastAPI `BackgroundTasks` for indexing or alert explanation.

- [ ] **Step 5: Audit conversation/tool metadata**

Record safe plan domain/operation, controlled tool names, source IDs, calculation, proposal ID/status, model, and latency. Do not store hidden reasoning.

- [ ] **Step 6: Run API tests and verify GREEN**

Run the Task 6 pytest command.

- [ ] **Step 7: Commit Task 6**

```powershell
git add backend/app/api/v1/rag.py backend/app/schemas/rag.py backend/app/agents/rag_assistant.py backend/tests/integration/test_assistant_actions_api.py
git commit -m "feat: add confirmed assistant action api"
```

---

### Task 7: Dynamic Assistant Drawer Results and Confirmation UI

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/assistant/assistant-panel.tsx`
- Create: `frontend/components/assistant/assistant-view-model.ts`
- Create: `frontend/components/assistant/assistant-view-model.test.ts`

**Interfaces:**
- Consumes: extended `AssistantAnswer` and action confirm/cancel APIs.
- Produces: accessible calculation, result-table, clarification, and proposal cards inside the persistent drawer.

- [ ] **Step 1: Write failing view-model tests**

Test formatting for count, currency minimum, null-aware totals, citations, clarification, pending proposal, executed proposal, and error state. Assert no raw JSON is presented.

- [ ] **Step 2: Run frontend test and verify RED**

Run: `cd frontend && npm test -- assistant-view-model.test.ts`

Expected: module does not exist.

- [ ] **Step 3: Extend frontend types**

Add optional calculation, rows, clarification, proposed action, and safe tool-trace types while preserving existing `AssistantAnswer` fields.

- [ ] **Step 4: Implement pure view models**

Format INR values with `Intl.NumberFormat("en-IN", {style: "currency", currency: "INR"})`, dates without fabrication, count labels, filters, result rows, proposal before/after fields, and statuses.

- [ ] **Step 5: Render dynamic response cards**

Add compact summary cards for count/sum/average/min/max, a scrollable result table for list/group answers, clarification chips, and citations. Keep text answers for narrative responses.

- [ ] **Step 6: Render proposal confirmation**

Show action, affected records, warnings, before/after preview, expiry, Confirm, and Cancel. Disable both buttons during request; update the message from the API result; never infer execution from optimistic UI state.

- [ ] **Step 7: Run frontend test, lint, and build**

```powershell
cd frontend
npm test -- assistant-view-model.test.ts
npm run lint
npm run build
```

- [ ] **Step 8: Commit Task 7**

```powershell
git add frontend/lib/types.ts frontend/components/assistant/assistant-panel.tsx frontend/components/assistant/assistant-view-model.ts frontend/components/assistant/assistant-view-model.test.ts
git commit -m "feat: show dynamic rag results and action previews"
```

---

### Task 8: Eligible-Document Backfill and New-Client Verification

**Files:**
- Create: `backend/scripts/backfill_application_rag.py`
- Create: `backend/tests/unit/test_rag_backfill.py`
- Modify: `docs/deployment.md`

**Interfaces:**
- Produces: idempotent CLI that indexes approved eligible documents for one application or all accessible service-role applications.

- [ ] **Step 1: Write failing backfill tests**

Seed old approved, pending, rejected, Ground Truth, and new-client documents. Assert only approved eligible documents are indexed, rerun is idempotent, and every chunk retains the source application.

- [ ] **Step 2: Run test and verify RED**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/unit/test_rag_backfill.py -q`

- [ ] **Step 3: Implement backfill CLI**

Support `--application-id <uuid>` and `--all`. Load settings/store normally, call existing `index_document`, print only counts/IDs, and never print extraction text, tokens, keys, or signed URLs.

- [ ] **Step 4: Document deployment-safe execution**

Add commands using the declared backend environment. State that new approvals index automatically and backfill is needed only for retained pre-feature approvals.

- [ ] **Step 5: Run test and a dry local memory backfill**

Run the Task 8 pytest command and then the script against memory configuration with a test application ID. Expected: eligible/indexed/skipped counts and exit code 0.

- [ ] **Step 6: Commit Task 8**

```powershell
git add backend/scripts/backfill_application_rag.py backend/tests/unit/test_rag_backfill.py docs/deployment.md
git commit -m "feat: backfill eligible application rag evidence"
```

---

### Task 9: End-to-End Verification and Latency Guardrails

**Files:**
- Modify only if a failing verification proves a scoped fix is necessary.

**Interfaces:**
- Verifies the complete approved design; introduces no new feature scope.

- [ ] **Step 1: Run focused backend suites**

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/unit/test_dynamic_rag_planner.py tests/unit/test_dynamic_rag_tools.py tests/unit/test_assistant_action_proposals.py tests/unit/test_assistant_action_execution.py tests/integration/test_dynamic_agentic_rag.py tests/integration/test_assistant_actions_api.py -q
```

- [ ] **Step 2: Run full backend suite and lint**

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check app tests
```

- [ ] **Step 3: Run frontend verification**

```powershell
cd frontend
npm test
npm run lint
npm run build
```

- [ ] **Step 4: Run migration and repository checks**

```powershell
npx supabase migration list
git diff --check
git status --short
```

- [ ] **Step 5: Run secret scan over tracked changes**

Scan `git diff`/commits for Supabase keys, Groq/NVIDIA keys, Vonage secrets, encryption keys, tokens, and signed URLs. Do not read or print `.env` values.

- [ ] **Step 6: Run live application tests**

Against Raj Traders and one newly created client, ask:

```text
What is the count of tax invoices?
Which tax invoice has the lowest total invoice value?
Show RCM purchase records above ₹50,000.
Which records failed period validation?
Which invoices are only in GSTR-2B?
Which reconciliation findings were raised as alerts?
Who approved the latest extraction?
```

Verify exact values directly against scoped Supabase rows and real citations. Ask an ambiguous amount question and verify clarification. Ask about another client and verify refusal/no leakage.

- [ ] **Step 7: Verify controlled action flow manually**

Propose one harmless review action, verify no mutation before confirmation, cancel it, then create a fresh proposal and confirm it. Verify before/after data and audit events. Do not send WhatsApp or change filing readiness.

- [ ] **Step 8: Measure route latency**

Measure at least five warmed exact analytical requests. Report p50 and maximum; target each common exact request below five seconds. Separately report Groq/text-RAG latency and any external-service timeout fallback.

- [ ] **Step 9: Final atomic verification commit if needed**

Commit only verification-driven code/document fixes with a scoped message. Do not commit `.env`, `.superpowers/`, runtime files, or unrelated `frontend/next-env.d.ts` changes.
