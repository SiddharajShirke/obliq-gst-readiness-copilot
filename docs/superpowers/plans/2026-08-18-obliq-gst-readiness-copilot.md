# OBLIQ GST Readiness Copilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a lightweight end-to-end GST document collection, extraction, validation, GSTR-2B reconciliation, RAG assistance, mock/Meta WhatsApp, Supabase, FastAPI, and Next.js prototype.

**Architecture:** A Next.js App Router frontend calls a versioned FastAPI API. FastAPI verifies Supabase JWTs, persists application data and vectors in Supabase PostgreSQL, stores files in private Supabase Storage, runs deterministic document/GST logic plus controlled LangGraph workflows, and sends through interchangeable mock or Meta WhatsApp providers.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, FastAPI, Pydantic 2, Supabase Auth/PostgreSQL/Storage, pgvector, pandas/openpyxl/PyMuPDF/Pillow, Sentence Transformers, LangGraph, ReportLab, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-obliq-gst-readiness-copilot-design.md`

## Global Constraints

- Functional prototype only; no production GST filing, payment, CI/CD, Kubernetes, microservices, or enterprise infrastructure.
- Supabase service-role and Meta credentials stay server-side.
- Hosted mode uses deterministic AI and mock WhatsApp; local mode optionally uses real Meta Cloud API and ngrok.
- CA approval is mandatory before outbound document requests/reminders and before accepting extracted data.
- Structured PostgreSQL data answers client-specific facts; RAG answers guidance questions with citations.
- Embedding dimension is fixed at 384 using `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- All demo data is synthetic.

---

### Task 1: Repository skeleton and configuration

**Files:** root config, `backend/pyproject.toml`, `frontend/package.json`, Dockerfiles, `.env.example`, docs.

**Produces:** installable backend/frontend projects and documented environment contract.

- [x] Create focused directory structure and package metadata.
- [x] Add exhaustive environment template, Docker Compose, Makefile, and gitignore.
- [x] Add initial README and architecture/deployment documents.
- [x] Verify TOML/JSON/YAML syntax and importable configuration.

### Task 2: Core domain logic using TDD

**Files:** `backend/tests/unit/*`, `backend/app/services/{validation,reconciliation,upload_tokens}.py`, RAG chunker and WhatsApp signature module.

**Produces:** tested pure functions for GSTIN/date/arithmetic/duplicate validation, reconciliation, secure token hashing, chunking, and Meta signature verification.

- [x] Write failing unit tests.
- [x] Run tests and confirm expected failures.
- [x] Implement minimal domain services.
- [x] Run tests and confirm green.

### Task 3: Supabase schema, pgvector, storage, and RLS

**Files:** `supabase/migrations/*.sql`, `supabase/seed.sql`, `supabase/config.toml`.

**Produces:** complete relational schema, indexes, helper functions, vector/lexical RPCs, RLS, and bucket creation.

- [x] Add schema and enum/check constraints.
- [x] Add pgvector/full-text indexes and search RPCs.
- [x] Add RLS helper functions and policies.
- [x] Add storage buckets and policies.
- [x] Add deterministic seed records where Auth IDs are configurable through the seed script.

### Task 4: Backend foundation and Supabase adapters

**Files:** FastAPI app/config/dependencies, repository/storage/audit modules, schemas and routers.

**Produces:** health, user, firm, client, application, checklist, audit, and signed-document APIs.

- [x] Add testable auth/token dependency and tenant context.
- [x] Add Supabase REST/storage adapters.
- [x] Add CRUD endpoints and audit writes.
- [x] Verify Python compilation and OpenAPI generation.

### Task 5: Document intake, parsing, extraction, review, and workflow

**Files:** document-processing services, Pydantic extraction schemas, LangGraph document workflow, document endpoints.

**Produces:** secure uploads from dashboard/public/mock/Meta, deterministic file routing, mock/live extraction adapters, persisted extraction, review states, and findings.

- [x] Implement secure upload token issuance/verification.
- [x] Implement CSV/XLSX/PDF/image/JSON routing and parsing.
- [x] Implement deterministic mock fixtures and live provider adapters.
- [x] Build controlled LangGraph processing graph.
- [x] Implement extraction review/update/approve/reject APIs.
- [x] Verify against generated demo documents.

### Task 6: WhatsApp providers, reminders, and webhook flow

**Files:** provider protocol, mock provider, Meta provider, webhook/reminder/integration routers.

**Produces:** hosted mock conversation and optional real outbound/inbound Meta integration.

- [x] Implement provider-neutral event/message contracts.
- [x] Implement mock transport backed by shared message tables.
- [x] Implement Meta send/template/media/webhook/signature behavior.
- [x] Implement CA-approved request/reminder flows.
- [x] Implement local credential file gate and test-connection endpoint.
- [x] Verify mock flow with API tests and Meta payload fixtures.

### Task 7: RAG ingestion, retrieval, citations, and assistant

**Files:** extractors, chunker, embedding provider, retriever, RRF, LLM answer provider, assistant router and scripts.

**Produces:** checksum-based ingestion, 384-dimensional embeddings, pgvector + FTS hybrid retrieval, citations, structured-data tools, and mock/live answers.

- [x] Implement text extraction and heading-aware chunking.
- [x] Implement lazy local embedding model plus deterministic test/mock embedder.
- [x] Implement Supabase inserts and RPC retrieval.
- [x] Implement lexical retrieval and reciprocal-rank fusion.
- [x] Implement assistant intent routing between database facts and RAG.
- [x] Add demo knowledge files and ingestion CLI.
- [x] Verify chunking/retrieval tests and mock citation output.

### Task 8: Reconciliation, readiness reports, exports, and filing evidence

**Files:** reconciliation endpoints, readiness service, ReportLab export, CSV export, filing evidence API.

**Produces:** purchase-register/GSTR-2B comparison, summary metrics, issue list, downloadable PDF/CSV, and post-filing evidence recording.

- [x] Persist reconciliation runs/items.
- [x] Compute readiness summary from structured records.
- [x] Generate PDF and CSV exports.
- [x] Add approve/return/final evidence endpoints.
- [x] Verify unit tests and export smoke tests.

### Task 9: Original responsive Next.js interface

**Files:** App Router pages/components/lib, Tailwind design system.

**Produces:** original OBLIQ-inspired landing page, auth, dashboard, clients, GST workspace tabs, secure upload, mock client, knowledge and WhatsApp settings.

- [x] Build design tokens and shared components.
- [x] Build landing/auth/protected shell.
- [x] Build dashboard and client/application flows.
- [x] Build documents/extraction/validation/reconciliation/RAG/audit tabs.
- [x] Build public upload and mock WhatsApp pages.
- [x] Build local Meta settings page.
- [x] Verify TypeScript with strict structural and AST checks; production npm lint/build commands are documented for a network-enabled environment.

### Task 10: Demo generators, seed scripts, documentation, and final verification

**Files:** `scripts/*`, `demo_data/*`, tests and docs.

**Produces:** five synthetic scenarios, generated documents, mock extraction fixtures, setup/reset commands, and verified distributable archive.

- [x] Generate synthetic PDF/image/CSV/XLSX/JSON files.
- [x] Create Supabase Auth/data seed and reset scripts.
- [x] Complete README, local/Meta/deployment/demo/limitations docs.
- [x] Run backend tests and compile checks, frontend structural checks, secret scan, and archive inspection; npm/Docker/Supabase runtime verification is documented where unavailable in the execution sandbox.
- [x] Package the repository as a ZIP without build caches, secrets, or dependencies.
