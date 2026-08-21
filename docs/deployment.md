# Deployment

Deploy FastAPI on a directly reachable HTTPS domain and Next.js separately or through the existing Docker Compose configuration.

For hosted Supabase, apply migrations in order, verify the existing private Storage buckets, configure Auth, and seed synthetic data from a trusted backend environment. Keep `USE_IN_MEMORY_DB=false` in that deployment.

For Render or Railway, use the existing backend Dockerfile, expose port 8000, and retain `/api/v1/health` as the health check. For Vercel, use `frontend` as the project root and set `NEXT_PUBLIC_API_BASE_URL` to the public FastAPI `/api/v1` origin. Public frontend variables may contain only Supabase URL/anon values and existing demo flags.

Set backend-only variables in the FastAPI service, including Vonage credentials and signature secret, `PUBLIC_BASE_URL`, both HMAC peppers, and the Fernet key. Never expose these as `NEXT_PUBLIC_*` values. Keep the Supabase service-role key and LLM keys backend-only as before.

Example:

```env
WHATSAPP_PROVIDER=vonage
PUBLIC_BASE_URL=https://api.obliq.example
VONAGE_WHATSAPP_FROM=<sandbox-number-digits>
VONAGE_MESSAGES_BASE_URL=https://messages-sandbox.nexmo.com
```

Configure Vonage Sandbox endpoints exactly:

```text
Inbound POST: https://api.obliq.example/api/v1/webhooks/vonage/whatsapp
Status POST:  https://api.obliq.example/api/v1/webhooks/vonage/status
```

Restart FastAPI after changing `PUBLIC_BASE_URL`. Do not place a proxy-only internal hostname, Docker service name, localhost, or HTTP origin in that variable.

Run the Supabase migration before enabling traffic:

```powershell
supabase db reset
```

For an existing deployed database, use the project’s normal migration deployment command instead of resetting production data.

No scheduler is claimed in Phase 1. Invoke `scripts/cleanup_vonage_demo_sessions.py` manually or configure an external platform scheduler explicitly.
