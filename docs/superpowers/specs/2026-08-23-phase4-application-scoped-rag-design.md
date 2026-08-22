# Phase 4 Application-Scoped RAG Design

## Goal

Extend OBLIQ's existing firm-knowledge RAG into an application-scoped assistant that combines exact Phase 1-3 facts, approved document evidence, reconciliation findings, raised alerts, and firm/shared GST knowledge without exposing another application.

## Architecture

Keep `knowledge_sources` and `knowledge_chunks` for firm/shared guidance. Add a separate `document_chunks` pgvector table keyed by firm, client, application, optional demo session, and source document. Exact checklist, extraction, transaction, validation, reconciliation, and alert facts remain repository queries and are never inferred from vector search.

The assistant route authenticates the user, validates the requested application, loads only that application's structured facts, retrieves only that application's document chunks, optionally retrieves firm/shared knowledge, and sends a compact evidence bundle to the existing Groq model. Citations are constructed and verified by the backend from real evidence metadata.

## Indexing

Only approved or edited-and-approved Phase 3 documents are eligible. `developer_ground_truth`, `excluded_reference`, rejected, failed, unsupported, duplicate, and unknown documents are rejected before embedding. Approved normalized rows become provenance-rich textual chunks; approved raw extraction text is chunked only when usable. Indexing is idempotent by checksum and also runs as a lazy backfill for pre-Phase-4 approvals.

## Retrieval and controlled facts

The controlled tool layer exposes document collection status, extraction summaries, transaction lookup, validation findings, latest reconciliation summary/items, explicitly raised alerts, application document search, firm/shared knowledge search, and deterministic missing-document reminder drafting. No arbitrary SQL or cross-client search is exposed.

## LangGraph

The graph has eight nodes: `validate_access`, `classify_question`, `load_structured_facts`, `retrieve_application_evidence`, `retrieve_knowledge_if_needed`, `generate_grounded_answer`, `verify_scope_and_citations`, and `audit`. Access is deterministic. Uploaded evidence is untrusted content, not instructions. Reconciliation results remain Phase 3 deterministic facts.

## Conversation and UI

Store lightweight messages by `user_id + application_id + conversation_id`. The application workspace mounts one right-side assistant drawer outside tab content. The existing RAG tab opens that drawer instead of rendering a second assistant. Changing application resets conversation scope.

## Deployment parity

Use the existing 384-dimensional local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, Supabase pgvector, LangGraph, and configured Groq model. All dependencies remain declared in `backend/pyproject.toml`; permanent vectors and messages are stored in Supabase.

## Explicit exclusions

Do not add a second vector database, reranker, arbitrary SQL agent, Phase 5 Vonage media ingestion, Ground Truth indexing, or production-scale RAG infrastructure.
