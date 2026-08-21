# Local setup

1. Copy `.env.example` to `.env`.
2. Keep existing Supabase, auth, storage, AI, extraction, and RAG values unchanged.
3. Set all Vonage and WhatsApp security variables shown in `.env.example`.
4. Install backend and frontend dependencies.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
.\.venv\Scripts\python.exe scripts\generate_demo_documents.py
Set-Location frontend
npm.cmd install
```

Generate peppers and a Fernet key:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Start FastAPI and Next.js in separate terminals:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

```powershell
Set-Location frontend
npm.cmd run dev
```

Expose FastAPI:

```powershell
ngrok http 8000
```

Set `PUBLIC_BASE_URL=https://generated-domain.ngrok-free.app` and restart FastAPI. Configure the Vonage Sandbox inbound and status webhooks with this public origin. Webhook authentication uses Vonage signed payload JWTs rather than trusting the URL.

Run cleanup manually when needed:

```powershell
.\.venv\Scripts\python.exe scripts\cleanup_vonage_demo_sessions.py
```

There is no scheduled cleanup worker in Phase 1. Expiration also runs opportunistically during session creation, status retrieval, and inbound webhook processing.

## Local Supabase mode

Install Docker and Supabase CLI, then run:

```powershell
supabase start
supabase db reset
.\.venv\Scripts\python.exe scripts\seed_demo.py
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py
```

Copy the local Supabase values into `.env`, set `USE_IN_MEMORY_DB=false`, and keep the service-role key only in the backend environment. For direct Next.js development, copy `frontend/.env.local.example` to `frontend/.env.local`; only public Supabase values belong there.

For a hosted project, apply all migrations through the Supabase CLI or SQL Editor, including `202608200001_supabase_backend_runtime_grants.sql`, before running the seed command. If `DATABASE_URL` contains reserved characters such as `@` in its password, URL-encode them or use the exact Supabase pooler connection string; otherwise PostgreSQL clients may parse part of the password as the hostname.

When using Supabase Auth, set `NEXT_PUBLIC_DEMO_MODE=false` in both the root environment and `frontend/.env.local`. The frontend then treats the Supabase SDK session as the only authentication authority and hides fake-token role buttons.

After switching an existing browser from MemoryStore to Supabase, remove only these legacy keys in DevTools → Application → Local Storage:

```text
obliq_access_token
obliq_user
```

Do not remove the Supabase-managed `sb-<project-ref>-auth-token` key when it represents a valid session. A MemoryStore-only WhatsApp session is stored separately in Session Storage as `obliq_whatsapp_demo:<applicationId>`; the live demo page now removes that one key automatically after an authenticated 404 and creates a fresh Supabase-backed session.
