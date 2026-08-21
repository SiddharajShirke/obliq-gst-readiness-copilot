# Vonage WhatsApp Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active Twilio WhatsApp Sandbox transport with a secure single-judge Vonage Messages API Sandbox transport while preserving OBLIQ's existing isolated demo-session workflow.

**Architecture:** Keep application cloning, START/dashboard tokens, protected phone binding, conversation rules, audit records, cleanup, and frontend polling provider-neutral. Add a Vonage provider that sends JSON through the existing `httpx` dependency, validates signed webhook JWTs and payload hashes before any state change, and maps Vonage JSON inbound/status events to the existing message model. Remove active Twilio provider code, dependencies, routes, settings, UI copy, scripts, and documentation; preserve historical database rows through a forward-only migration.

**Tech Stack:** FastAPI, httpx, PyJWT, Supabase/PostgreSQL, Next.js, Vitest, pytest.

**Spec:** Approved in-chat Vonage single-judge recommendation dated 2026-08-20.

## Global Constraints

- `WHATSAPP_PROVIDER=vonage` is the only non-test runtime provider.
- The sandbox uses `https://messages-sandbox.nexmo.com/v1/messages` and one allow-listed judge phone.
- Inbound and status webhooks are JSON and must be authenticated before database writes.
- Verify the HS256 webhook JWT, `iss`, `api_key`, timestamp freshness, and SHA-256 `payload_hash` over the raw request body.
- Use `message_uuid` for idempotency and message-status correlation.
- Return HTTP 200 promptly and perform outbound replies with FastAPI `BackgroundTasks`.
- Preserve Phase 1 media deferral, Supabase isolation, phone protection, RAG, extraction, document viewers, and all non-WhatsApp workflows.
- Do not commit real API keys, secrets, phone numbers, or access tokens.

---

### Task 1: Vonage provider and runtime configuration

**Files:**
- Create: `backend/app/services/whatsapp/vonage.py`
- Modify: `backend/app/services/whatsapp/base.py`, `backend/app/services/whatsapp/factory.py`, `backend/app/config.py`, `backend/pyproject.toml`, `.env.example`, `docker-compose.yml`
- Delete: `backend/app/services/whatsapp/twilio.py`
- Test: `backend/tests/unit/test_vonage_provider.py`, `backend/tests/unit/test_config.py`

**Interfaces:**
- `VonageWhatsAppProvider.send_text(recipient, text, status_callback) -> MessageSendResult`
- `VonageWhatsAppProvider.validate_webhook(raw_body, authorization, now=None) -> bool`

- [ ] Write provider/config tests proving sandbox URL, Basic authentication, normalized digits-only numbers, `webhook_url`, safe API errors, and signed webhook validation.
- [ ] Run focused tests and confirm failures are caused by the missing Vonage implementation.
- [ ] Implement the minimum provider, provider protocol, factory, and settings changes.
- [ ] Run focused tests to green and lint touched backend files.
- [ ] Remove the Twilio SDK dependency and active Twilio provider module.

### Task 2: Vonage JSON webhooks and status lifecycle

**Files:**
- Modify: `backend/app/api/v1/whatsapp.py`, `backend/app/services/whatsapp/sessions.py`, `backend/app/services/whatsapp/cleanup.py`, `backend/app/services/whatsapp/conversation.py`, `backend/app/repositories/memory.py`
- Replace: `backend/tests/integration/test_twilio_webhooks.py` with `backend/tests/integration/test_vonage_webhooks.py`
- Modify: `backend/tests/unit/test_whatsapp_demo_sessions.py`, `backend/tests/unit/test_whatsapp_conversation.py`

**Interfaces:**
- `POST /api/v1/webhooks/vonage/whatsapp`
- `POST /api/v1/webhooks/vonage/status`
- Inbound payload fields: `message_uuid`, `from`, `to`, `channel`, `message_type`, `text`, optional media fields.
- Status payload fields: `message_uuid`, `status`, optional `error`.

- [ ] Write failing integration tests for signature-before-write, START binding, duplicate `message_uuid`, commands, media deferral, safe failures, and status updates.
- [ ] Run focused webhook tests and confirm the expected route/behavior failures.
- [ ] Implement raw-body validation, JSON parsing, provider-neutral persistence, HTTP 200 acknowledgements, and Vonage status mapping.
- [ ] Run focused integration and related session/conversation tests to green.
- [ ] Verify outbound failures update the existing row without leaking secrets or full phone numbers.

### Task 3: Forward-only database compatibility migration

**Files:**
- Create: `supabase/migrations/202608200002_vonage_whatsapp_transport.sql`
- Replace: `backend/tests/unit/test_twilio_migration.py` with `backend/tests/unit/test_vonage_migration.py`

**Interfaces:**
- Active providers: `vonage`, `mock`; historical `twilio` message/settings rows remain readable.
- Session provider identity column: `provider_user_id_hash`; legacy `twilio_wa_id_hash` is migrated without data loss.
- `bind_whatsapp_demo_session(..., p_provider_user_id_hash text)` remains service-role only.

- [ ] Write failing migration contract tests for constraints, historical preservation, provider identity migration, and RPC permissions.
- [ ] Run the migration test and confirm failure against the absent migration.
- [ ] Add a forward-only migration that changes constraints and RPC parameters without rewriting applied migrations.
- [ ] Update MemoryStore RPC parity and session cleanup.
- [ ] Run migration/session tests to green.

### Task 4: Single-judge frontend and runtime-status copy

**Files:**
- Modify: `frontend/app/dashboard/applications/[applicationId]/whatsapp-demo/page.tsx`, `frontend/app/dashboard/integrations/whatsapp/page.tsx`, `frontend/components/whatsapp/whatsapp-runtime-status.tsx`, `frontend/lib/whatsapp-demo.ts`
- Test: existing `frontend/lib/whatsapp-demo.test.ts` and WhatsApp component tests; add focused copy/status assertions where needed.

**Interfaces:**
- Existing session API response fields remain stable: `sandbox_join_message`, `sandbox_join_whatsapp_url`, `start_message`, `start_whatsapp_url`.
- UI identifies Vonage Sandbox, one judge, 100 messages/month, and 1 message/second.

- [ ] Write failing frontend assertions that Twilio branding is absent and Vonage single-judge instructions are present.
- [ ] Run focused Vitest tests with `npm.cmd` and confirm expected failures.
- [ ] Update connection/status UI without adding chat simulation or changing the route.
- [ ] Run focused tests, lint, and production build.

### Task 5: Documentation, scripts, searches, and full verification

**Files:**
- Create: `docs/vonage-whatsapp-setup.md`, `scripts/cleanup_vonage_demo_sessions.py`
- Modify: `README.md`, `docs/architecture.md`, `docs/local-setup.md`, `docs/deployment.md`, `docs/demo-walkthrough.md`, `docs/limitations.md`, `Makefile`
- Delete: `docs/twilio-whatsapp-setup.md`, `scripts/cleanup_twilio_demo_sessions.py`, Twilio-specific tests.

**Interfaces:**
- Sandbox webhooks: `/api/v1/webhooks/vonage/whatsapp` and `/api/v1/webhooks/vonage/status`.
- Manual cleanup command: `python scripts/cleanup_vonage_demo_sessions.py`.

- [ ] Replace Twilio setup and operational instructions with exact Vonage sandbox onboarding, allow-list QR, webhook URLs, ngrok, security, quota, and Phase 1 limitations.
- [ ] Run active-Twilio and simulator-removal searches and explain any unavoidable historical migration references.
- [ ] Run complete backend tests, Ruff, frontend tests/lint/build, migration checks available locally, secret scan, and `git diff --check`.
- [ ] Record `git diff --stat`, `git status --short`, and whether a real allow-listed WhatsApp device was tested.
