# Architecture

## Product boundary

OBLIQ GST Readiness Copilot covers the operational workflow before filing: client creation, period checklist, approved WhatsApp requests, secure upload, extraction, review, validation, reconciliation, RAG explanation, readiness export, and optional post-filing evidence recording.

It does not perform statutory filing or make final tax decisions.

## Components

### Next.js frontend

Public routes provide the original landing page, Supabase authentication, the secure upload form, and a labelled mock WhatsApp client. Protected routes provide client and application management, extraction review, validation, reconciliation, RAG, audit logs, knowledge ingestion, and local Meta configuration.

### FastAPI backend

FastAPI exposes a versioned REST interface and Swagger. Authentication dependencies resolve either a Supabase bearer token or a synthetic demo token. Every domain operation receives a firm context.

### DataStore abstraction

- `MemoryStore`: self-contained hosted/local demo; private local files and deterministic seed data.
- `SupabaseStore`: PostgreSQL, Auth-linked profiles, private Storage and pgvector RPCs.

### Controlled agents

LangGraph coordinates deterministic nodes. It does not allow unrestricted autonomous actions.

- Document graph: load → classify → parse/extract → persist → validate → human review.
- Reminder graph: checklist → missing items → draft → approval → provider send.
- Assistant graph: classify intent → load structured facts → retrieve knowledge → cited answer.

### WhatsApp providers

Both providers implement the same interface. `MockWhatsAppProvider` writes messages to the normal message table for the browser client. `MetaWhatsAppProvider` calls Graph API and converts webhook payloads into the same internal event shape.

## Trust boundaries

- Browser receives only anon Supabase keys and user JWTs.
- Service-role, LLM and Meta secrets remain in FastAPI.
- Public clients upload through a token endpoint, not direct privileged database calls.
- Client facts come from structured rows; RAG is used for explanation and guidance.
- Human approval is mandatory before outbound reminders and final extraction acceptance.
