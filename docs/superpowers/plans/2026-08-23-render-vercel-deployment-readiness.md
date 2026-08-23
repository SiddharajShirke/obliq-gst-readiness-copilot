# Render + Vercel Deployment Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Phase-4 OBLIQ monorepo reproducibly deployable to Render and Vercel without changing its Supabase, Vonage, AI, RAG, or reporting architecture.

**Architecture:** Render builds the existing FastAPI Docker image from Git and Vercel builds the existing Next.js application from `frontend/`. Hosted Supabase remains the only persistent database, Auth, vector, and private-file store; Groq, NVIDIA, and Vonage remain hosted integrations configured only by environment.

**Tech Stack:** FastAPI, Uvicorn, Python 3.11 container, Next.js 16, Node 22, Supabase, pgvector, Groq, NVIDIA, Vonage, Tesseract, ReportLab, Render Blueprint, Vercel.

**Spec:** User-approved “OBLIQ — Final Deployment Readiness” requirements in the active Phase-4 task.

## Global Constraints

- Preserve Phase 1–4 behavior and all existing user changes.
- Do not implement Phase 5 direct WhatsApp media ingestion.
- Do not commit secrets, signed URLs, private keys, or local environment files.
- Use Supabase for permanent state; local disk is temporary or MemoryStore-only.
- Render must honor the `PORT` environment variable; Vercel must build `frontend/` natively.
- Production must use `USE_IN_MEMORY_DB=false`, `AI_MODE=live`, and `WHATSAPP_PROVIDER=vonage`.
- No Redis, Celery, Kafka, Kubernetes, or redundant deployment workflow.

---

### Task 1: Preserve workflow UX while removing extraction-gated redirect

**Files:**
- Modify: `frontend/lib/upload-completion.ts`
- Modify: `frontend/lib/upload-completion.test.ts`
- Modify: `frontend/components/documents/secure-upload-view.tsx`
- Modify: `frontend/components/documents/secure-upload-view.test.tsx`

**Interfaces:**
- Consumes: `PublicUploadContext`
- Produces: secure-submission completion gate independent of OCR/AI/RAG status

- [x] Write and run failing tests proving a processing batch is sufficient after all files are submitted.
- [x] Update the completion predicate and user-facing message.
- [x] Run focused tests and confirm redirect remains blocked before explicit submission.

### Task 2: Restore dynamic Alerts navigation and refine the landing experience

**Files:**
- Modify: `frontend/components/dashboard/app-shell.tsx`
- Modify: `frontend/components/dashboard/app-shell.test.tsx`
- Modify: `frontend/components/alerts/alerts-dashboard.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/landing/`
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Consumes: existing `/alerts` API and semantic theme tokens
- Produces: visible Alerts workspace, responsive product storytelling, reduced-motion-safe animation

- [x] Write and run failing navigation, landing, and theme tests.
- [x] Restore Alerts without restoring Knowledge Base or WhatsApp destinations.
- [x] Add theme-safe visual motion and responsive Phase 1–4 capability presentation.
- [x] Run focused frontend tests.

### Task 3: Harden production configuration and backend container

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/unit/test_config.py`
- Modify: `backend/Dockerfile`
- Create: `.dockerignore`
- Create: `render.yaml`

**Interfaces:**
- Consumes: exact current backend environment variables
- Produces: validated production settings, PORT-aware Uvicorn container, Render health check

- [x] Add failing tests for unsafe production settings.
- [x] Implement production validation and safe startup logging.
- [x] Make Docker use the Render PORT and install only active native dependencies.
- [x] Add secret-safe build context exclusions and a main-branch Render Blueprint.
- [x] Run config tests and backend import smoke.

### Task 4: Add Vercel and full-stack deployment smoke configuration

**Files:**
- Modify: `frontend/Dockerfile`
- Modify: `frontend/.env.local.example`
- Modify: `.env.example`
- Create: `docker-compose.deploy-smoke.yml`

**Interfaces:**
- Consumes: `NEXT_PUBLIC_API_BASE_URL`, public Supabase values, backend environment
- Produces: native Vercel build guidance and optional local container-parity smoke stack

- [x] Use lockfile-clean installs in the smoke image.
- [x] Ensure frontend public variables contain no backend secret.
- [x] Add a compose smoke topology using hosted external services.
- [x] Validate Compose YAML syntax independently; Docker execution remains blocked until Docker is installed.

### Task 5: Document exact platform configuration

**Files:**
- Create: `docs/deployment/render-vercel.md`
- Modify: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Produces: exact local/Render/Vercel environment matrix and first-deployment sequence

- [x] Document architecture, prerequisites, platform variables, Supabase Auth URLs, Vonage webhooks, main auto-deploy, post-deploy checks, and troubleshooting.
- [x] Document the Render free-tier cold-start limitation.
- [x] Document that Phase 5 variables and providers are not required.

### Task 6: Verify and commit Phase-4 atomically

**Files:**
- Verify: complete repository

**Interfaces:**
- Produces: evidence-backed pre-merge status and coherent Phase-4 commits

- [x] Run full backend tests and Ruff.
- [x] Run frontend tests, lint, and production build.
- [x] Run migration status, `git diff --check`, and secret scan.
- [ ] Run backend/full-stack Docker builds and health smoke (blocked: Docker is not installed on this workstation).
- [ ] Commit workflow/UI, deployment configuration, and deployment documentation coherently.
- [ ] Do not merge or push `main`.
