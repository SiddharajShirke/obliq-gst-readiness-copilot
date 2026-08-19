# Manual Deployment

No CI/CD is included because this hiring artifact is intentionally a lightweight prototype.

## Hosted Supabase

1. Create a Supabase project.
2. Apply the SQL files in `supabase/migrations/` in order.
3. Verify the three private Storage buckets.
4. Set service-role credentials only on the backend.
5. Run `USE_IN_MEMORY_DB=false python scripts/seed_demo.py` from a trusted machine.

## Backend on Render or Railway

- Root/build context: repository root
- Dockerfile: `backend/Dockerfile`
- Port: `8000`
- Health: `/api/v1/health`
- Set backend and Supabase environment variables.
- For the public hiring demo use mock AI/WhatsApp and disable local credential entry.

## Frontend on Vercel

- Root directory: `frontend`
- Framework: Next.js
- Set `NEXT_PUBLIC_API_BASE_URL` to the deployed FastAPI `/api/v1` URL.
- Set Supabase public URL and anon key if using real Auth.
- Set `NEXT_PUBLIC_DEMO_MODE=true` for the hiring demo.

## Public-demo settings

```env
DEMO_MODE=true
AI_MODE=mock
WHATSAPP_PROVIDER=mock
ALLOW_LOCAL_CREDENTIAL_SETUP=false
```

Never place `SUPABASE_SERVICE_ROLE_KEY`, Meta tokens, LLM keys or `META_APP_SECRET` in Vercel public variables.
