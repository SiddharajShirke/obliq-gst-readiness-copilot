# Environment-Isolated End-to-End Repair Design

## Problem

A development backend configured with `FRONTEND_URL=http://localhost:3000` used the same Supabase and live Vonage credentials as the deployed application. It created and sent a WhatsApp request whose upload token was signed with the development pepper. The deployed Vercel upload page routes public-token requests to Render, where the production pepper cannot validate that token, so the link returns 404.

The production backend and frontend are healthy. Existing upload, extraction, OCR/AI fallback, workflow-status, and review tests pass, but no test prevents a local runtime from sending a localhost upload link through live Vonage or prevents a hosted frontend from using a localhost API fallback.

## Goals

- Never send a live WhatsApp request containing a localhost, private-network, malformed, or wrong-origin upload URL.
- Fail startup when live Vonage is paired with a non-public frontend origin unless an explicit development-only override is enabled.
- Reject edited/stale approval text if its upload origin or token does not match the reminder's current upload link.
- Make hosted frontend builds fail safely if the API base is missing or points to localhost/private networking.
- Remove manual deployment drift for non-secret canonical Vercel and Render origins.
- Preserve the real six-stage workflow, tenant boundaries, secure-token storage, processing logic, and free-tier fallbacks.
- Verify the full START-to-upload-to-extraction-to-overview journey with deterministic tests.

## Non-goals

- No new GST workflow stage or Phase 5 behavior.
- No bypass of CA extraction/validation review.
- No raw token persistence or exposure in health/audit responses.
- No claim that third-party providers can never fail; failures must be safe, observable, and recoverable.

## Design

### 1. Canonical public-origin validation

Add URL helpers that normalize origins and classify loopback/private hosts. `FRONTEND_URL`, `PUBLIC_BASE_URL`, and production CORS values remain configuration-driven. Live Vonage requires an HTTPS public frontend origin by default. A narrowly named development override can allow local-only testing, but production rejects it.

### 2. Deployment configuration as code

`render.yaml` will pin the known non-secret origins:

- `FRONTEND_URL=https://obliq-gst-readiness-copilot.vercel.app`
- `BACKEND_URL=https://obliq-gst-readiness-copilot.onrender.com`
- `PUBLIC_BASE_URL=https://obliq-gst-readiness-copilot.onrender.com`
- `CORS_ORIGINS=https://obliq-gst-readiness-copilot.vercel.app`

Secrets remain `sync: false`. The supported NVIDIA small model is pinned as a non-secret model identifier.

### 3. Outbound reminder integrity

Before Vonage send, the backend will:

1. load the reminder's bound upload-link row;
2. extract exactly one `/upload/<token>` URL from the approved text;
3. require the URL origin to match canonical `FRONTEND_URL`;
4. hash the raw token with the running pepper and compare it to the bound link;
5. require the link to be unrevoked, unexpired, and bound to the same application/session/client.

Invalid messages fail with a clear 409/422 response and are never sent.

### 4. Hosted frontend fail-closed API resolution

`resolveApiBaseUrl` will accept browser-origin context. On a hosted HTTPS page it rejects a missing, localhost, loopback, or private-network API base. Localhost remains valid when the page itself is running locally. This prevents an old/misconfigured hosted bundle from silently talking to a developer machine.

### 5. Safe diagnostics

Health will expose only normalized public origins and configuration readiness flags. No tokens, API keys, phone data, or peppers will be returned.

### 6. Processing and overview continuity

The submission pipeline remains unchanged: upload storage is separate from submission; processing is serialized on the free tier; text-native PDFs skip OCR; scanned/image inputs use Tesseract; NVIDIA/Groq failures fall back deterministically; completed documents enter extraction review; overview derives live counts from persisted documents, records, findings, and reconciliation runs.

## Error handling

- Unsafe live WhatsApp configuration: startup validation error.
- Unsafe hosted API base: explicit frontend configuration error before fetch.
- Stale/wrong upload token in approval text: request rejected before provider call.
- AI provider failure: existing fallback and `fallback_reason` persistence.
- Individual processing failure: document and batch failure status remain visible.
- Render latency: background processing and overview polling continue without blocking authentication.

## Verification

- Unit tests for URL normalization and configuration rejection.
- API tests for valid link send, wrong-origin send rejection, wrong-token rejection, expired/revoked link rejection, and provider-not-called assertions.
- Frontend tests for local development acceptance and hosted localhost rejection.
- Deployment manifest tests for canonical origins and current model.
- End-to-end deterministic integration test covering session activation, link creation, token resolution, secure upload, batch submit, extraction persistence, and overview/status advancement.
- Full backend and frontend suites, lint/type/build checks, plus read-only deployed health checks after deployment.

## Rollback

The repair is isolated to configuration validation, URL integrity, diagnostics, tests, and deployment metadata. Reverting its single merge commit restores prior behavior without a database migration.
