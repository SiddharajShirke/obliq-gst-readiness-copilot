# OBLIQ deployment: Render backend + Vercel frontend

This guide deploys the existing Phase 1–4 prototype without changing its runtime architecture. Phase 5 direct WhatsApp media ingestion is not included.

## A. Architecture

```text
Browser
  -> Vercel / Next.js
  -> Render / FastAPI Docker service
       -> hosted Supabase Auth + PostgreSQL + pgvector + private Storage
       -> Vonage Messages API WhatsApp Sandbox
       -> hosted NVIDIA and Groq APIs
```

Render builds [backend/Dockerfile](../../backend/Dockerfile) from GitHub. Vercel builds `frontend/` natively; the frontend Dockerfile exists only for local production-parity smoke testing. Permanent application state and private documents stay in Supabase. The container filesystem is used only for runtime caches and temporary operations.

## B. Prerequisites

- A GitHub repository containing this monorepo.
- A linked hosted Supabase project with migrations through `202608230009`.
- Existing private buckets: `gst-documents`, `knowledge-documents`, and `exports`.
- Render and Vercel accounts connected to the GitHub repository.
- Existing Vonage Sandbox, Groq, and NVIDIA credentials.
- Docker Desktop or another Compose-compatible Docker engine for the required pre-merge smoke test.

Do not use real taxpayer data in this hiring prototype.

## C. Local environment

Copy `.env.example` to `.env` and `frontend/.env.local.example` to `frontend/.env.local`. Supabase-backed local operation uses:

```env
APP_ENV=development
USE_IN_MEMORY_DB=false
AI_MODE=live
WHATSAPP_PROVIDER=vonage
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_DEMO_MODE=false
```

`PUBLIC_BASE_URL` must be the current HTTPS tunnel only while testing local Vonage webhooks. Never copy an ngrok URL to Render.

## D. Docker production smoke test

The smoke stack uses the same backend Dockerfile as Render and a standalone Next.js image:

```powershell
docker compose -f docker-compose.deploy-smoke.yml build --no-cache
docker compose -f docker-compose.deploy-smoke.yml up -d
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-WebRequest http://localhost:3000 -UseBasicParsing
docker compose -f docker-compose.deploy-smoke.yml logs backend frontend
docker compose -f docker-compose.deploy-smoke.yml down
```

The gitignored root `.env` supplies hosted Supabase, AI, security, and Vonage values. The smoke file forces Supabase/live-AI mode and does not mount a persistent disk. If live Vonage callbacks are not under test, existing valid Vonage settings are still needed by current startup validation, but ngrok does not need to be running.

Verify login, application list, secure upload, one extraction, validation, reconciliation, RAG, and Export Pack while the stack is running.

## E. Render setup

Both Render setup modes are supported. Choose one service, not both.

### Option 1: Blueprint

1. In Render, create a Blueprint from this GitHub repository.
2. Render reads the root [render.yaml](../../render.yaml).
3. Confirm service type **Web Service**, runtime **Docker**, branch **main**.
4. Confirm Dockerfile `./backend/Dockerfile`, context `.`, and health path `/api/v1/health`.
5. Enter every `sync: false` value in the Render Dashboard.
6. Do not attach a persistent disk.

### Option 2: Manual Web Service

1. In Render, choose **New -> Web Service** and connect this GitHub repository.
2. Select branch `main` and runtime **Docker**.
3. Leave **Root Directory** empty. The Dockerfile copies both `backend/` and
   `demo_data/` from the repository-root build context.
4. Set **Dockerfile Path** to `./backend/Dockerfile` and **Docker Build Context**
   to `.`.
5. Leave build and start commands empty; the Dockerfile owns both operations.
6. Set **Health Check Path** to `/api/v1/health` and enable automatic deploys.
7. Add the complete environment from section F before expecting the service to
   become healthy. A manually created Web Service does not import `render.yaml`.
8. Do not attach a persistent disk.

Render can allocate the service URL before all environment values are known. If
the first start fails, add the missing values in **Environment**, save them, and
choose **Manual Deploy -> Deploy latest commit**. Never bypass production
validation and never commit credentials merely to make the first start pass.

The container command is:

```text
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Render supplies `PORT`. The health check does not call Supabase, Vonage, Groq, or NVIDIA over the network.

## F. Render backend environment

Set these runtime values in Render. Keep secrets out of `render.yaml`.

| Variable | Required | Render value/purpose |
|---|---:|---|
| `APP_ENV` | Yes | `production` |
| `APP_DEBUG` | Yes | `false` |
| `DEMO_MODE` | Yes | `false`; tenant Guided Demo remains available through its real workflow |
| `USE_IN_MEMORY_DB` | Yes | `false` |
| `FRONTEND_URL` | Yes | Stable Vercel HTTPS origin; creates secure upload links |
| `BACKEND_URL` | Recommended | Stable Render HTTPS origin |
| `API_V1_PREFIX` | No | Default `/api/v1` |
| `CORS_ORIGINS` | Yes | Comma-separated Vercel HTTPS origins |
| `LOG_LEVEL` | No | Default `INFO` |
| `SUPABASE_URL` | Yes | Hosted project URL |
| `SUPABASE_ANON_KEY` | Recommended | Existing public/anon key; not treated as a service secret |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes, secret | Backend-only service role |
| `SUPABASE_JWT_SECRET` | No | Retained compatibility setting; current auth uses Supabase Auth `get_user` |
| `SUPABASE_JWKS_URL` | No | Retained compatibility setting |
| `DATABASE_URL` | No | Not used by the current Supabase repository |
| `SUPABASE_DOCUMENTS_BUCKET` | Yes | `gst-documents` |
| `SUPABASE_KNOWLEDGE_BUCKET` | Yes | `knowledge-documents` |
| `SUPABASE_EXPORTS_BUCKET` | Yes | `exports` |
| `AI_MODE` | Yes | `live` |
| `TEXT_LLM_PROVIDER` | Yes | `groq` |
| `VISION_LLM_PROVIDER` | Yes | `nvidia` |
| `LLM_FALLBACK_PROVIDER` | Yes | `groq` |
| `GROQ_API_KEY` | Yes, secret | Existing Groq key |
| `GROQ_MODEL` | Yes | `openai/gpt-oss-120b` in the verified environment |
| `GROQ_HEAVY_MODEL` | Yes | `openai/gpt-oss-120b` |
| `GROQ_RAG_MODEL` | Yes | `openai/gpt-oss-120b` |
| `NVIDIA_API_KEY` | Yes, secret | Existing NVIDIA key |
| `NVIDIA_BASE_URL` | Yes | `https://integrate.api.nvidia.com/v1` |
| `NVIDIA_SMALL_MODEL` | Yes | `meta/llama-3.1-8b-instruct` in the verified environment |
| `NVIDIA_VISION_MODEL` | Optional | Verified vision deployment; current configured value is `meta/llama-3.2-11b-vision-instruct` |
| `EMBEDDING_PROVIDER` | Yes | `local`; model is cached in the image |
| `EMBEDDING_MODEL` | Yes | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `EMBEDDING_DIMENSION` | Yes | `384`; must match Supabase vector columns/RPC |
| `RAG_VECTOR_TOP_K` | No | Default `12` |
| `RAG_FINAL_TOP_K` | No | Default `5` |
| `RAG_MIN_SIMILARITY` | No | Default `0.45` |
| `RAG_CHUNK_SIZE` | No | Default `900` |
| `RAG_CHUNK_OVERLAP` | No | Default `140` |
| `RAG_GENERATION_TIMEOUT_SECONDS` | No | Default `1.5` |
| `RAG_MAX_OUTPUT_TOKENS` | No | Default `800` |
| `OCR_ENABLED` | Yes | `true`; Tesseract is installed in the image |
| `TESSERACT_CMD` | No | Leave empty in Docker so PATH resolves the packaged binary |
| `MAX_UPLOAD_MB` | No | Default `20` |
| `BULK_UPLOAD_MAX_FILES` | No | Default `20` |
| `BULK_UPLOAD_MAX_TOTAL_MB` | No | Default `100` |
| `ALLOWED_UPLOAD_EXTENSIONS` | No | Existing supported extension list |
| `UPLOAD_LINK_TTL_HOURS` | No | Default `72` |
| `UPLOAD_TOKEN_PEPPER` | Yes, secret | Independent random value |
| `WHATSAPP_PROVIDER` | Yes | `vonage` |
| `VONAGE_API_KEY` | Yes, secret | Existing Sandbox API key |
| `VONAGE_API_SECRET` | Yes, secret | Existing Sandbox API secret |
| `VONAGE_SIGNATURE_SECRET` | Yes, secret | Signed webhook verification |
| `VONAGE_WHATSAPP_FROM` | Yes | Existing Sandbox sender |
| `VONAGE_SANDBOX_JOIN_MESSAGE` | Yes | Exact current allow-list message |
| `VONAGE_MESSAGES_BASE_URL` | Yes | `https://messages-sandbox.nexmo.com` |
| `PUBLIC_BASE_URL` | Yes | Stable Render HTTPS origin |
| `WHATSAPP_DEMO_TOKEN_EXPIRY_MINUTES` | No | Default `20` |
| `WHATSAPP_DEMO_SESSION_EXPIRY_MINUTES` | No | Default `120` |
| `WHATSAPP_DEMO_DATA_RETENTION_HOURS` | No | Default `24` |
| `WHATSAPP_DEMO_TOKEN_PEPPER` | Yes, secret | Independent random value |
| `WHATSAPP_PHONE_HASH_PEPPER` | Yes, secret | Independent random value |
| `WHATSAPP_PHONE_ENCRYPTION_KEY` | Yes, secret | Fernet key |

`LOCAL_UPLOAD_DIR`, `LOCAL_EXPORT_DIR`, and seed-account variables are MemoryStore/local-only. Gemini, Twilio, Meta, and Phase-5 secure-media credentials are not required.

## G. Vercel setup

1. Import the same GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Keep framework preset **Next.js** and the existing `npm run build`.
4. Set **Production Branch** to `main`.
5. Do not configure a custom output directory or static export.
6. Add the four public variables below to Production (and Preview only when previews are intentionally tested).

## H. Vercel frontend environment

| Variable | Required | Vercel value/purpose |
|---|---:|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | `https://<render-service>.onrender.com/api/v1` |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Hosted Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase browser-safe anon key |
| `NEXT_PUBLIC_DEMO_MODE` | Yes | `false` |

Never add the Supabase service role, Groq/NVIDIA/Vonage secrets, Fernet key, or HMAC peppers to Vercel.

## I. Complete environment matrix

| Variable | Local backend | Render backend | Local frontend | Vercel frontend | Public/secret | Purpose |
|---|---|---|---|---|---|---|
| `FRONTEND_URL` | `http://localhost:3000` | Vercel HTTPS origin | — | — | Public config | Secure upload-link origin |
| `BACKEND_URL` | `http://localhost:8000` | Render HTTPS origin | — | — | Public config | Backend canonical origin |
| `PUBLIC_BASE_URL` | Current ngrok HTTPS | Render HTTPS origin | — | — | Public config | Vonage callback/status origin |
| `CORS_ORIGINS` | Local frontend | Vercel HTTPS origin(s) | — | — | Public config | Browser origin allow-list |
| `SUPABASE_URL` | Hosted URL | Hosted URL | — | — | Public identifier | Backend Supabase endpoint |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret | Secret | Never | Never | Secret | Privileged backend data/storage access |
| `SUPABASE_ANON_KEY` | Optional | Optional | — | — | Public | Backend compatibility |
| `GROQ_API_KEY` | Secret | Secret | Never | Never | Secret | Groq generation |
| `NVIDIA_API_KEY` | Secret | Secret | Never | Never | Secret | NVIDIA assistance |
| `VONAGE_API_SECRET` / `VONAGE_SIGNATURE_SECRET` | Secret | Secret | Never | Never | Secret | Sending and webhook validation |
| HMAC peppers / Fernet key | Secret | Secret | Never | Never | Secret | Upload/session/phone protection |
| `NEXT_PUBLIC_API_BASE_URL` | — | — | Local API `/api/v1` | Render API `/api/v1` | Public | Central frontend API base |
| `NEXT_PUBLIC_SUPABASE_URL` | — | — | Hosted URL | Hosted URL | Public | Browser Auth endpoint |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | — | — | Anon key | Anon key | Public | Browser Auth |
| `NEXT_PUBLIC_DEMO_MODE` | — | — | `false` | `false` | Public | Disables MemoryStore token UI |

All other backend-only values use the exact names in section F and never move into `NEXT_PUBLIC_*`.

## J. Supabase URL and migration configuration

Before cloud deployment:

```powershell
.\node_modules\@supabase\cli-windows-x64\bin\supabase.exe migration list --linked
.\node_modules\@supabase\cli-windows-x64\bin\supabase.exe db push --linked --dry-run
```

Apply only reviewed forward migrations with `supabase db push --linked`. Never run `supabase db reset` against the hosted project.

In **Authentication → URL Configuration**:

- Site URL: stable Vercel production URL.
- Redirect URLs: stable Vercel production URL and the existing localhost URLs.
- Add a Vercel preview wildcard only if preview authentication is intentionally enabled.

## K. Vonage Sandbox webhook update

After Render is healthy, configure the exact existing routes:

```text
Inbound: https://<render-service>.onrender.com/api/v1/webhooks/vonage/whatsapp
Status:  https://<render-service>.onrender.com/api/v1/webhooks/vonage/status
```

Set `PUBLIC_BASE_URL=https://<render-service>.onrender.com` and restart/redeploy the backend. Secure document links are separately generated from `FRONTEND_URL=https://<vercel-domain>`.

## L. Main-branch auto-deployment

`render.yaml` sets `branch: main` and `autoDeployTrigger: commit`. Vercel must set Production Branch to `main`. Phase-4 branch commits do not become production releases; merging or pushing the resulting commit to `main` triggers both native Git deployments. No deploy-hook GitHub Action is required.

## M. First deployment sequence

1. Verify/apply hosted Supabase migrations.
2. Merge the verified Phase-4 branch into `main`.
3. Create/sync the Render Blueprint from `main`.
4. Configure Render secrets.
5. Obtain the stable Render backend URL.
6. Verify Render `/api/v1/health`.
7. Import the same repository into Vercel.
8. Set Root Directory to `frontend`.
9. Set Production Branch to `main`.
10. Set `NEXT_PUBLIC_API_BASE_URL` to the Render URL plus `/api/v1`.
11. Add public Supabase variables and deploy.
12. Obtain the stable Vercel production URL.
13. Set Render `FRONTEND_URL` and `CORS_ORIGINS` to that Vercel URL.
14. Redeploy Render.
15. Update Supabase Auth Site URL/redirects.
16. Update Vonage inbound/status webhooks.
17. Confirm `PUBLIC_BASE_URL` is the Render origin.
18. Confirm a new WhatsApp request contains the Vercel secure upload URL.
19. Run the end-to-end judge test.

## N. Post-deployment end-to-end test

Test registration/login, tenant Guided Demo, client creation, Draft Request, both Vonage QR steps, signed inbound/status callbacks, secure Vercel upload, private Storage, submit-and-return behavior, extraction, CA review, validation, readiness, Export Pack, GSTR-2B reconciliation, alert + AI explanation, reconciliation export, application-scoped RAG citations, and Audit Trail.

Direct WhatsApp attachments are not part of this test.

## O. Troubleshooting

- **No open ports followed by a `Settings` validation error:** this is not a
  Docker port problem. FastAPI exited before Uvicorn could bind the Render
  `PORT`. For a manual Web Service, add every required value from section F in
  the Render **Environment** page, then redeploy. In particular, the Vonage
  provider requires `VONAGE_API_KEY`, `VONAGE_API_SECRET`,
  `VONAGE_SIGNATURE_SECRET`, `VONAGE_WHATSAPP_FROM`,
  `VONAGE_SANDBOX_JOIN_MESSAGE`, `PUBLIC_BASE_URL`,
  `WHATSAPP_DEMO_TOKEN_PEPPER`, `WHATSAPP_PHONE_HASH_PEPPER`, and
  `WHATSAPP_PHONE_ENCRYPTION_KEY`. Reuse the existing encryption key and
  peppers so retained session data remains readable.
- **Render fails at startup:** inspect the first Pydantic error; production intentionally rejects MemoryStore, mock AI, debug mode, HTTP public URLs, non-HTTPS CORS, missing Supabase service role, or a non-384 embedding dimension.
- **Render build is slow:** the image pre-caches the multilingual Sentence Transformer and installs Tesseract. This avoids a first-request model download but increases build time/image size.
- **Render Free cold start:** the first request may be delayed. Do not add artificial keep-alive infrastructure.
- **Browser CORS failure:** `CORS_ORIGINS` must contain the exact Vercel origin without a path.
- **Secure link points locally:** correct `FRONTEND_URL`, then redeploy/restart FastAPI and create a fresh request/link.
- **Vonage callbacks fail:** confirm `PUBLIC_BASE_URL`, the two exact routes, HTTPS, signature secret, and Sandbox sender.
- **RAG model error:** keep `EMBEDDING_DIMENSION=384`; changing dimension requires a deliberate database migration and is outside deployment readiness.
- **OCR failure:** leave `TESSERACT_CMD` empty in Render; the Docker image installs the binary in PATH.
- **Export failure:** verify the private `exports` bucket exists and the service role can upload; URLs are short-lived signed URLs by design.
