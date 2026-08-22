# Phase 4 Application-Scoped RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an application-scoped pgvector and LangGraph assistant with exact Phase 3 facts, grounded citations, conversation isolation, and one persistent right-side workspace drawer.

**Architecture:** Preserve firm/shared `knowledge_chunks`, add application-private `document_chunks`, and keep exact numeric/status data in controlled repository queries. The backend validates application access before retrieval, Groq receives only scoped evidence, and citations are built from stored provenance rather than invented model output.

**Tech Stack:** FastAPI, Pydantic 2, Supabase PostgreSQL/pgvector, Sentence Transformers (384 dimensions), LangGraph, Groq, Next.js 16, React 19, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-23-phase4-application-scoped-rag-design.md`

## Global Constraints

- Preserve Phases 1-3 and the active Vonage transport.
- Never index, retrieve, cite, or send `developer_ground_truth` to an AI provider.
- Keep exact GST values and reconciliation outcomes deterministic.
- Use the effective cloned application for demo sessions.
- Do not add Phase 5 media ingestion or production RAG infrastructure.
- Preserve the active embedding model and `vector(384)` dimension.

---

### Task 1: Application vector schema and memory-store parity

**Files:**
- Create: `supabase/migrations/202608230003_application_scoped_rag.sql`
- Modify: `backend/app/repositories/memory.py`
- Test: `backend/tests/unit/test_phase4_application_rag.py`

**Interfaces:**
- Produces: `document_chunks`, `assistant_messages`, and `match_application_document_chunks(...)`.

- [ ] Write failing tests proving application chunk RPC results are limited to the requested firm/application and never return `developer_ground_truth`.
- [ ] Run `python -m pytest tests/unit/test_phase4_application_rag.py -q` and confirm failure because the tables/RPC do not exist.
- [ ] Add forward-only tables, RLS, HNSW index, and application-scoped RPC; mirror them in `MemoryStore`.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Approved-document indexing and Ground Truth exclusion

**Files:**
- Create: `backend/app/services/rag/document_indexing.py`
- Modify: `backend/app/services/rag/chunking.py`
- Modify: `backend/app/api/v1/documents.py`
- Test: `backend/tests/unit/test_phase4_application_rag.py`

**Interfaces:**
- Produces: `index_document(store, settings, document_id) -> list[dict]` and `sync_application_documents(store, settings, application_id) -> int`.

- [ ] Add failing tests for approved row provenance, idempotency, rejection cleanup, and Ground Truth exclusion.
- [ ] Run the tests and confirm failures are caused by the missing indexer.
- [ ] Implement provenance-rich row/text chunking with checksums and 384-dimensional embeddings.
- [ ] Trigger indexing after approve/edit-and-approve/bulk approve and remove chunks after rejection.
- [ ] Re-run tests and confirm they pass.

### Task 3: Controlled structured facts and application retrieval

**Files:**
- Create: `backend/app/services/rag/application_context.py`
- Modify: `backend/app/services/rag/retrieval.py`
- Test: `backend/tests/unit/test_phase4_application_rag.py`

**Interfaces:**
- Produces: `load_application_context(...)`, `retrieve_application_documents(...)`, and deterministic intent-specific fact loaders.

- [ ] Add failing tests for checklist facts, Purchase Register summaries, transaction lookup, reconciliation differences, alerts-vs-findings, and abstention.
- [ ] Run focused tests and verify the expected failures.
- [ ] Implement application-filtered repository functions and pgvector document retrieval while retaining existing firm/shared RRF retrieval.
- [ ] Re-run focused tests and confirm they pass.

### Task 4: Controlled LangGraph, citations, conversations, and audit

**Files:**
- Modify: `backend/app/agents/rag_assistant.py`
- Modify: `backend/app/prompts/rag.py`
- Modify: `backend/app/schemas/rag.py`
- Modify: `backend/app/api/v1/rag.py`
- Test: `backend/tests/integration/test_phase4_assistant.py`

**Interfaces:**
- Consumes: application context and retrieval services from Tasks 2-3.
- Produces: `POST /api/v1/assistant/query` with `conversation_id`, grounded answer, verified citations, and source types.

- [ ] Add failing integration tests for current-app answers, same-firm cross-app exclusion, stored Option A explanations, raised alerts only, conversation isolation, injection resistance, and RAG audit events.
- [ ] Run focused tests and confirm failures originate in the old four-node assistant.
- [ ] Implement the eight-node graph, direct Groq generation, scoped history, deterministic abstention, verified citations, and audit events.
- [ ] Re-run focused and existing assistant tests until green.

### Task 5: Persistent right-side assistant drawer

**Files:**
- Modify: `frontend/components/assistant/assistant-panel.tsx`
- Modify: `frontend/app/dashboard/applications/[applicationId]/page.tsx`
- Modify: `frontend/lib/types.ts`
- Create: `frontend/components/assistant/assistant-panel.test.tsx`

**Interfaces:**
- Produces: `RagAssistantDrawer` mounted once per application workspace and scoped to the effective application ID.

- [ ] Read the installed Next.js client-component guidance under `frontend/node_modules/next/dist/docs/`.
- [ ] Add failing Vitest tests for drawer scope, tab persistence, application reset, citations, suggestions, and error/abstention states.
- [ ] Run the focused frontend test and verify failures.
- [ ] Implement the themed fixed action, drawer, scoped conversation ID, suggestion chips, citation cards, and legacy tab-to-drawer behavior.
- [ ] Re-run focused frontend tests and confirm they pass.

### Task 6: Regression and deployment verification

**Files:**
- Modify only if a verification failure identifies a Phase 4 defect.

- [ ] Run focused backend Phase 4 and existing RAG tests.
- [ ] Run the complete backend suite.
- [ ] Run frontend tests, touched-file lint, and production build.
- [ ] Smoke-load the active 384-dimensional embedding model and verify one vector length.
- [ ] Run `git diff --check` and a tracked-file secret scan.
- [ ] Record manual/live limitations honestly; do not claim hosted Supabase or live Groq verification unless executed.
