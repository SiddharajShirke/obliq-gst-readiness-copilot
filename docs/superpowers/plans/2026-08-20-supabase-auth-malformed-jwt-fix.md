# Supabase Authentication and Stale Session Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure Supabase-backed OBLIQ uses real Supabase access-token JWTs, rejects malformed tokens with 401, and discards only stale MemoryStore WhatsApp session state.

**Architecture:** Supabase Auth becomes the sole browser session authority whenever public Supabase configuration exists. Legacy demo tokens remain available only when the frontend has no Supabase client and intentionally runs demo mode; the backend also accepts them only through `MemoryStore`. FastAPI performs a Supabase-only JWT shape guard, while `SupabaseStore` converts only expected Auth API failures into an unauthenticated result.

**Tech Stack:** Next.js 16, React 19, Supabase JS/Python SDKs, FastAPI, pytest, Vitest.

**Spec:** User-provided task “Diagnose and Fix OBLIQ Supabase Authentication / Malformed JWT Issue”.

## Global Constraints

- Do not weaken JWT validation, RLS, firm/application access checks, Twilio signature validation, or the WhatsApp dashboard access token.
- Do not expose or log Supabase/Twilio secrets or access/refresh tokens.
- Do not change RAG, document processing, reconciliation, reporting, or Twilio transport behavior.
- Preserve MemoryStore fake tokens for automated tests only.

---

### Task 1: Backend authentication boundary

**Files:**
- Modify: `backend/app/dependencies.py`
- Modify: `backend/app/repositories/supabase.py`
- Create: `backend/tests/unit/test_authentication.py`

**Interfaces:**
- Consumes: `DataStore.name`, `DataStore.get_user_from_token(token)`
- Produces: malformed Supabase bearer tokens and expected Supabase Auth failures resolve to HTTP 401 without swallowing unexpected repository errors.

- [ ] Write tests for missing token, malformed `demo-admin-token`, valid three-segment token, `AuthApiError`, and an unexpected runtime failure.
- [ ] Run the tests and confirm malformed/Auth API cases fail with the current unhandled behavior.
- [ ] Add a Supabase-store-only three-segment structural guard in `current_user`.
- [ ] Catch only `supabase_auth.errors.AuthApiError` inside `SupabaseStore.get_user_from_token` and return `None`.
- [ ] Run focused authentication and existing API access tests.

### Task 2: Real Supabase browser session authority

**Files:**
- Modify: `frontend/lib/supabase.ts`
- Modify: `frontend/lib/auth.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/auth/login/page.tsx`
- Create: `frontend/lib/auth-session.ts`
- Create: `frontend/lib/auth-session.test.ts`
- Create: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces: `isSupabaseAuthConfigured()`, `isMemoryDemoAuthEnabled()`, `resolveAccessToken()`, and one bounded 401 refresh attempt.

- [ ] Write tests proving Supabase mode removes only legacy auth keys, ignores fake demo tokens, returns the SDK session JWT, omits Authorization without a session, and retries a 401 at most once after refresh.
- [ ] Run the tests and confirm current localStorage-first behavior fails them.
- [ ] Make Supabase SDK session state authoritative whenever public Supabase configuration exists.
- [ ] Subscribe to `onAuthStateChange` so refreshed sessions update the displayed user without manually caching tokens.
- [ ] Hide/disable fake demo role login when Supabase is configured; retain it only for intentionally unconfigured MemoryStore test/demo mode.
- [ ] Clear stale `obliq_access_token` and `obliq_user` without signing out a valid Supabase session.
- [ ] Run focused frontend auth/API tests.

### Task 3: Stale WhatsApp browser session recovery

**Files:**
- Modify: `frontend/lib/whatsapp-demo.ts`
- Modify: `frontend/lib/whatsapp-demo.test.ts`
- Modify: `frontend/app/dashboard/applications/[applicationId]/whatsapp-demo/page.tsx`

**Interfaces:**
- Produces: `removeStoredDemoSession(storage, applicationId)` and 404-only stale-session recovery.

- [ ] Write tests proving only the application-specific `obliq_whatsapp_demo:<applicationId>` key is removed and authentication keys remain intact.
- [ ] Run the test and confirm the removal API is missing.
- [ ] On an authenticated 404 while restoring a saved demo session, clear that session key and create a fresh Supabase-backed session; propagate 401 and other failures.
- [ ] Run focused WhatsApp frontend and backend regression tests.

### Task 4: Configuration guidance and verification

**Files:**
- Modify: `.env.example`
- Modify: `frontend/.env.local.example`
- Modify: `docs/local-setup.md`

- [ ] Document `NEXT_PUBLIC_DEMO_MODE=false` for Supabase runtime and the exact two legacy browser keys plus application-specific WhatsApp session key.
- [ ] Run complete backend/frontend tests, production build, focused lint, removal/secret searches, and `git diff --check`.
- [ ] Where credentials and local Supabase tooling are available, sign in with a real seeded Auth user, create a new session, and verify its session/application/checklist rows. Otherwise report the manual verification gap without claiming it passed.
