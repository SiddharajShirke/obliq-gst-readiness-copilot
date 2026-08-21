# OBLIQ GST Readiness Copilot

OBLIQ is an existing FastAPI, Next.js, and Supabase prototype for GST document collection, extraction review, validation, GSTR-2B reconciliation, RAG assistance, reports, audit logs, and controlled WhatsApp workflows.

> **Product boundary:** OBLIQ does not file GST returns, pay GST, determine final ITC eligibility, store GST Portal credentials, or replace professional judgement. Extracted fields, validation findings, reconciliation differences, and outbound reminders remain subject to CA review.

## What the prototype demonstrates

- Next.js CA dashboard and Supabase email/password authentication with demo-token fallback
- Multi-tenant PostgreSQL schema, RLS, private Storage, `pgvector`, and full-text retrieval
- Secure expiring browser upload links
- PDF/image/CSV/XLSX/JSON classification, parsing, OCR, and optional LLM extraction
- Controlled LangGraph document, reminder, and assistant workflows
- GST validation, Purchase Register to GSTR-2B reconciliation, citations, audit logs, and exports
- Real Vonage Messages API Sandbox text connectivity with isolated temporary GST demo sessions

## Phase 1 WhatsApp architecture

The active live transport is the Vonage Messages API WhatsApp Sandbox:

```text
GST application
  -> isolated application/checklist clone
  -> common Sandbox join QR + unique START QR
  -> signed Vonage JSON inbound webhook
  -> encrypted phone/session binding
  -> real checklist text + STATUS/HELP/CANCEL
  -> signed delivery callbacks
```

Each browser session receives a separate high-entropy dashboard token kept in `sessionStorage`. Each WhatsApp START token is short-lived, HMAC-hashed, single-use, and bound atomically. Judge phone numbers are HMAC-indexed, Fernet-encrypted, and displayed only in masked form.

The former browser chat simulator and active legacy provider have been removed. The mock provider exists only as an automated-test double.

## Phase 1 boundary

> The Vonage Sandbox connection, real WhatsApp delivery, inbound text webhook, session isolation, and delivery-status tracking are implemented in this phase. Direct WhatsApp document-media download, Supabase document storage, AI extraction, and dashboard document display will be implemented in the next phase.

Attachments are detected but never downloaded in Phase 1. OBLIQ stores sanitized message metadata, creates no document row, and sends a controlled phase-boundary response.

The existing RAG, OCR, Gemini/Groq extraction, document viewers, secure upload, validation, reconciliation, reports, and audit systems are unchanged by this migration.

## Repository structure

```text
backend/       FastAPI, providers, agents, parsers, RAG, and domain services
frontend/      Next.js App Router dashboard and secure upload interface
supabase/      PostgreSQL migrations, pgvector, RLS, and Storage setup
scripts/       seed, demo generation, knowledge ingestion, and cleanup commands
demo_data/     synthetic GST fixtures and knowledge
docs/          architecture, setup, deployment, walkthrough, and limitations
```

## Quick start

Requirements: Python 3.11+, Node.js 20+, npm, and optionally Supabase CLI and Docker.

```powershell
Copy-Item .env.example .env
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
.\.venv\Scripts\python.exe scripts\generate_demo_documents.py
Set-Location frontend
npm.cmd install
Set-Location ..
```

Generate secure local values:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use the first command independently for `WHATSAPP_DEMO_TOKEN_PEPPER` and `WHATSAPP_PHONE_HASH_PEPPER`; use the second for `WHATSAPP_PHONE_ENCRYPTION_KEY`.

Start the services in separate terminals:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

```powershell
Set-Location frontend
npm.cmd run dev
```

For local Vonage callbacks:

```powershell
ngrok http 8000
```

Set `PUBLIC_BASE_URL` to the HTTPS ngrok origin, restart FastAPI, and configure the two callback URLs as described in [Vonage WhatsApp setup](docs/vonage-whatsapp-setup.md).

For Supabase-backed mode, install Docker and the Supabase CLI, then apply migrations and seed the existing synthetic data:

```powershell
supabase start
supabase db reset
.\.venv\Scripts\python.exe scripts\seed_demo.py
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py
```

Set `USE_IN_MEMORY_DB=false` and retain the existing Supabase/Auth/Storage variables. Service-role credentials stay backend-only.

## Existing non-WhatsApp architecture

The document graph still performs classification, parsing/extraction, persistence, deterministic validation, and human review. The reminder graph still requires CA approval for ordinary client reminders. The assistant still combines structured application facts with tenant-isolated hybrid retrieval and cited generation.

Mock AI mode provides deterministic extraction and embeddings without paid model keys. Live AI mode continues to use the configured Groq/Gemini adapters and existing fallbacks. This Vonage phase does not route WhatsApp messages or attachments into those systems.

Main API groups remain available under `/api/v1`, including clients, applications, documents, public secure upload, validation, reconciliation, assistant queries, reports, and audit. Swagger remains at `http://localhost:8000/docs`.

## Verification

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check app tests
Set-Location ..\frontend
npm.cmd test -- --run
npm.cmd run lint
npm.cmd run build
```

Apply and verify Supabase migrations with the project CLI:

```powershell
supabase db reset
```

Manual cleanup is available because this phase adds no scheduler:

```powershell
.\.venv\Scripts\python.exe scripts\cleanup_vonage_demo_sessions.py
```

## Security notes

- Supabase service-role, Vonage, LLM, Fernet, and HMAC secrets are backend-only.
- Public upload tokens remain random, hashed, expiring, and revocable.
- Application tables retain tenant RLS; private Storage continues to use signed URLs.
- Vonage JSON webhooks are rejected before database writes unless their signed JWT, timestamp, API key, and raw-payload hash validate successfully.
- All supplied demonstration client and tax information must remain synthetic.

See [local setup](docs/local-setup.md), [deployment](docs/deployment.md), [architecture](docs/architecture.md), [demo walkthrough](docs/demo-walkthrough.md), and [limitations](docs/limitations.md).

Never commit `.env`, frontend local environment files, Vonage credentials, Supabase service-role keys, LLM keys, Fernet keys, or HMAC peppers.
