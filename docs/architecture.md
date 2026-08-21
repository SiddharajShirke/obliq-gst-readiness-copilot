# Architecture

OBLIQ keeps its existing Next.js App Router frontend, FastAPI API, tenant-aware repository abstraction, Supabase PostgreSQL/Storage foundation, document processing, validation, reconciliation, RAG, reports, and audit services.

## Product and component boundaries

The Next.js application provides authentication, CA workspaces, client/application management, secure upload, extraction review, validation, reconciliation, reports, audit history, knowledge administration, and the live WhatsApp connection page. It never receives server credentials.

FastAPI exposes the versioned API and resolves a Supabase bearer token or the existing synthetic demo identity. Domain operations retain firm context and role checks. `MemoryStore` remains available for automated tests and the existing self-contained data fixtures; `SupabaseStore` remains the deployed PostgreSQL/Auth/Storage implementation.

Controlled workflows remain unchanged:

- Document graph: load, classify, parse/extract, persist, validate, human review
- Reminder graph: checklist, missing items, draft, CA approval, provider send
- Assistant graph: classify intent, load structured facts, tenant-scoped retrieval, cited answer

OBLIQ supports readiness work before filing; it does not file returns or make final tax/legal decisions.

## Vonage Phase 1 boundary

The WhatsApp provider protocol exposes only text sending and webhook validation. `VonageWhatsAppProvider` sends free-form text through the Vonage Messages API Sandbox using the existing asynchronous HTTP client stack; conversation rules remain in the conversation service.

FastAPI exposes:

- `POST /api/v1/applications/{application_id}/whatsapp-demo-sessions`
- `GET /api/v1/whatsapp-demo-sessions/{session_id}`
- `POST /api/v1/whatsapp-demo-sessions/{session_id}/cancel`
- `POST /api/v1/whatsapp-demo-sessions/{session_id}/regenerate-start-token`
- `POST /api/v1/webhooks/vonage/whatsapp`
- `POST /api/v1/webhooks/vonage/status`
- `GET /api/v1/integrations/whatsapp/status`

The creation RPC atomically creates a session, clones the selected GST application, resets workflow-result fields, clones its requirements, resets them to `missing`, and links the clone. Normal application queries filter on `demo_session_id is null`.

The binding RPC locks the START token row, verifies expiry/single-use state, cancels another active session for the same phone hash, stores protected phone fields, nulls the token hash, and activates the session.

Vonage webhooks are JSON. The backend validates the bearer JWT with the backend-only signature secret, verifies the `Vonage` issuer, configured API key, timestamp, and SHA-256 `payload_hash` over the exact raw request body. No state changes occur before validation. Vonage `message_uuid` provides idempotency.

The browser never accesses session tables directly. Status, cancellation, and regeneration require both Supabase authentication and `X-OBLIQ-Demo-Access-Token`.

Phone data is HMAC-SHA256 indexed, Fernet encrypted, masked for display, anonymized at expiry, and removed with temporary session data after retention. No raw full phone is written to ordinary logs or API responses.

Media URLs are not fetched. Phase 1 stores only media count/content-type metadata and sends a controlled response.

Existing private Storage signed URLs, OCR and document parsers, Gemini/Groq adapters, hybrid `pgvector`/full-text retrieval, firm-specific knowledge isolation, validation, reconciliation, exports, and document viewers are outside this migration and retain their existing design.
