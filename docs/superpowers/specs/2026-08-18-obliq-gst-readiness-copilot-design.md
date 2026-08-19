# Role and Execution Mode

You are a senior full-stack engineer, backend engineer, AI engineer, and solution architect. Build a complete, lightweight, working prototype named:

# **OBLIQ GST Readiness Copilot**

The prototype is intended as a hiring-project submission for OBLIQ. It must demonstrate practical backend engineering, AI engineering, Retrieval-Augmented Generation, document processing, Supabase database design, authentication, WhatsApp integration, human approval workflows, and a simple but polished frontend.

Do not stop after presenting an architecture or implementation plan. Actually create the complete codebase.

When you have filesystem access, create the files directly in the repository. When you only have chat output, provide the complete directory tree and then provide every important file in separate code blocks with its exact path.

Do not ask unnecessary clarification questions. Use the decisions in this prompt as final. When a small detail is ambiguous, choose the simplest implementation that preserves the workflow.

---

# 1. Product Definition

OBLIQ is an AI-powered compliance workflow platform for Indian Chartered Accountant firms.

This prototype will focus on one complete feature instead of attempting to automate GST, TDS, ROC, and Income Tax simultaneously.

The feature is:

# **GST Document Collection, Extraction, Reconciliation, and Readiness Workflow**

The prototype should help a CA firm take one client’s GST work from incomplete document collection to a structured, reviewed, filing-ready preparation package.

The application must:

1. Allow a CA or firm employee to log in.
2. Show multiple synthetic client profiles.
3. Allow creation of new clients.
4. Store each client’s GST information and WhatsApp phone number.
5. Start a monthly or quarterly GST compliance application.
6. Generate a document checklist.
7. Draft a WhatsApp document request.
8. Require CA approval before sending the request.
9. Allow the client to upload documents through a secure link.
10. Support a browser-based mock WhatsApp client for the hosted demo.
11. Support Meta WhatsApp Cloud API for optional local testing.
12. Detect missing documents.
13. Draft reminders and require CA approval before sending them.
14. Classify uploaded documents.
15. Extract structured information from invoices, PDFs, images, CSV files, and Excel files.
16. Show the original document beside extracted data.
17. Allow the CA to approve, edit, or reject extracted information.
18. Validate GSTIN formats, dates, totals, duplicates, client ownership, and GST period.
19. Reconcile the purchase register against a simplified GSTR-2B file.
20. Provide a source-backed RAG assistant.
21. Generate a GST readiness summary.
22. Export reports.
23. Record audit events.
24. Optionally allow the CA to record the ARN and filed-return PDF after filing is completed externally.

The application must stop at:

> **Ready for CA Review / Ready for Filing**

Do not automatically file GST returns.

Do not integrate GST Portal credentials.

Do not pay GST.

Do not make final legal, tax, ITC eligibility, or filing decisions.

The CA remains the professional decision-maker.

---

# 2. Prototype Scope and Constraints

This is a functional prototype, not a production system.

## Do not implement

- Kubernetes
- Microservices
- Event-driven distributed architecture
- Complex queues or distributed workers
- Complex caching
- Autoscaling
- Distributed tracing
- Enterprise secret-management systems
- Complex retry policies
- Circuit breakers
- Full production monitoring
- Large-scale analytics
- Production GST Portal integration
- Automatic GST filing
- Tax payment workflows
- Complex workflow-rule builders
- Production WhatsApp embedded signup
- CI/CD pipelines
- GitHub Actions
- Automated deployment pipelines
- Production-grade legal or security certification
- Multi-region infrastructure

## Implement only lightweight prototype-quality foundations

- Clear modular code
- Basic validation
- Basic user-friendly error messages
- Supabase Auth
- Basic role-based authorization
- Supabase Row-Level Security
- Server-side service-role usage only where required
- Private file storage
- Expiring upload tokens
- Basic webhook verification
- Basic audit logs
- Minimal unit and integration tests
- Manual deployment instructions
- Docker support where practical
- A simple local-development setup

Do not write intentionally insecure code. Although this is not production-grade, never expose service-role keys or Meta access tokens in the browser.

---

# 3. Required Technology Stack

Use the following stack unless a package is technically incompatible.

## Frontend

- Next.js using the current App Router
- TypeScript
- Tailwind CSS
- Supabase JavaScript client
- React Hook Form
- Zod
- Motion for React or Framer Motion for subtle animation
- Lucide icons
- Native `fetch` or a simple API client
- No heavy frontend state-management framework unless genuinely necessary

## Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- Supabase Python client
- HTTPX
- PyJWT or an equivalent lightweight JWT library
- Python multipart uploads
- Pandas
- OpenPyXL
- PyMuPDF or an equivalent PDF text parser
- Pillow
- Optional Tesseract OCR support
- Sentence Transformers
- LangGraph for the controlled AI workflow
- ReportLab or another lightweight PDF-report package
- Pytest for a small number of important tests

## Database and Storage

- Supabase
- PostgreSQL
- Supabase Auth
- Supabase Storage
- `pgvector`
- PostgreSQL JSONB
- PostgreSQL full-text search for optional hybrid retrieval

## AI Providers

Use provider abstractions.

Suggested responsibilities:

- Gemini: image and scanned-document understanding
- Groq-hosted LLM: fast text generation, structured extraction from text, reminder drafting, and RAG answer generation
- OpenAI: optional fallback provider
- Sentence Transformers: local embeddings

Do not require all providers simultaneously.

The application must support:

```
AI_MODE=mock
AI_MODE=live

```

In mock mode, known demo files should return deterministic extraction results so the hosted demo remains reliable and free.

In live mode, configured LLM providers should process uploaded files.

Use one fixed local embedding model for the RAG prototype:

```
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

```

Use embedding dimension:

```
384

```

Expose the model through environment variables, but keep the database vector dimension fixed at 384 for this prototype.

---

# 4. High-Level Architecture

Implement this architecture:

```
New Original OBLIQ Landing Page
              ↓
Supabase Email/Password Authentication
              ↓
Next.js CA Dashboard
              ↓
FastAPI Backend
              ↓
Supabase PostgreSQL + pgvector
              ↓
Supabase Private Storage
              ↓
GST Workflow Agent
              ↓
Document Parsing / OCR / AI Extraction
              ↓
Deterministic Validation
              ↓
Purchase Register ↔ GSTR-2B Reconciliation
              ↓
RAG Assistant
              ↓
CA Review and Approval
              ↓
GST Readiness Report

```

WhatsApp must connect through a provider abstraction:

```
GST Workflow
      ↓
WhatsAppProvider Interface
      ↓
 ┌───────────────────────┬────────────────────────┐
 ↓                       ↓
Mock Provider            Meta Cloud API Provider
 ↓                       ↓
Hosted Client Simulator  Real WhatsApp

```

Both providers must use the same application workflow and database tables.

---

# 5. Two WhatsApp Modes

## Mode A: Hosted Deployment — Mock WhatsApp Demo

The public deployed application must run in:

```
WHATSAPP_PROVIDER=mock

```

Judges must not need:

- A Meta account
- A WhatsApp Business account
- The developer’s phone
- The developer’s WhatsApp session
- Meta access tokens
- A verified recipient number

The hosted application must include two views:

### CA View

The logged-in CA can:

- Start a GST application
- Generate a document request
- Approve the request
- View messages
- Detect missing documents
- Approve reminders
- Review uploaded files
- View extraction and reconciliation
- Use RAG
- Generate reports

### Mock Client View

Create a route such as:

```
/demo-client

```

or:

```
/demo/whatsapp

```

This page should look like a WhatsApp-style conversation, but clearly display:

> **Demo Mode — Simulated WhatsApp Client**

The judge should be able to:

- See messages sent by the CA workflow
- Click the secure upload link
- Upload documents
- Reply with text
- Upload a file directly from the simulated chat
- Receive reminders
- See confirmations

Use simple polling every few seconds or manual refresh. Do not overengineer real-time communication.

Everything after the mock transport must be real:

- Database updates
- File uploads
- Checklist updates
- Extraction
- Validation
- Reconciliation
- RAG
- Audit logs

## Mode B: Local Repository — Meta WhatsApp Cloud API

A reviewer who clones the GitHub repository should be able to use their own Meta developer credentials and verified WhatsApp recipient number.

Use:

```
WHATSAPP_PROVIDER=meta

```

The local workflow should be:

```
Local OBLIQ
      ↓
Local FastAPI
      ↓
Reviewer’s Meta Developer App
      ↓
Meta Test Business Number
      ↓
Reviewer’s Verified WhatsApp Number

```

The reviewer must never log in to the Meta test business number.

The Meta test number is controlled by the API and acts as the sender.

The reviewer receives messages on their own normal WhatsApp number.

For two-way communication:

```
Reviewer’s WhatsApp
      ↓
Meta Webhook
      ↓
Public HTTPS ngrok URL
      ↓
Local FastAPI

```

Document this using a command similar to:

```
ngrok http 8000

```

The callback URL should be:

```
https://<ngrok-domain>/api/v1/webhooks/whatsapp

```

Implement:

```
GET  /api/v1/webhooks/whatsapp
POST /api/v1/webhooks/whatsapp

```

The GET endpoint verifies the webhook.

The POST endpoint receives:

- Text messages
- Media messages
- Delivery status
- Read status
- Failure status

For media:

1. Receive the media ID.
2. Request the media URL from Meta.
3. Download the file server-side.
4. Match the sender’s phone number to a client.
5. Attach the file to the client’s active GST application.
6. Start document processing.

If multiple active applications exist for the same client, place the file in a “Needs Assignment” state.

Implement basic `X-Hub-Signature-256` verification when `META_APP_SECRET` is configured.

---

# 6. Dynamic Local Meta Integration

Create:

```
Settings → Integrations → WhatsApp

```

The page must offer:

```
Demo / Mock Mode
Meta WhatsApp Cloud API

```

In local mode, allow the reviewer to enter:

- Meta access token
- Phone Number ID
- WhatsApp Business Account ID
- App secret
- Webhook verify token
- Graph API version
- Verified test-recipient phone number
- Document-request template name
- Reminder-template name

Add:

```
Test Connection
Send Test Message
Show Webhook URL

```

The interface must explain that:

- The recipient number must first be added or verified in the reviewer’s Meta developer setup.
- A phone number alone is not enough.
- A template may be required for a business-initiated message.
- An active customer-service session may allow normal text replies.
- ngrok or another HTTPS tunnel is required for inbound local webhooks.

Do not store Meta secrets in Supabase as plain text.

For prototype local-only dynamic setup:

- Save credentials server-side to a gitignored file such as:

```
.runtime/meta_credentials.json

```

- Enable this only when:

```
ALLOW_LOCAL_CREDENTIAL_SETUP=true

```

- Disable the credential form on the public deployment.
- Add a clear warning that local file storage is prototype-only and must be replaced by a secret manager in production.

Store only non-secret integration information in Supabase, such as:

- Provider name
- Phone Number ID
- WABA ID
- Test recipient number
- Connection status
- Last successful message time
- Last webhook time

---

# 7. End-to-End Application Workflow

Implement the following exact workflow.

## Step 1: Landing Page

Create a new original landing page.

Use the existing OBLIQ website only as visual inspiration:

```
https://obliqq.framer.ai/

```

Do not clone its layout, exact text, screenshots, or proprietary assets.

Use the visual direction:

- Light blue
- Off-white
- White
- Black typography
- Warm beige accents
- Rounded cards
- Pill buttons
- Large headings
- Floating navigation
- Generous whitespace
- Subtle scroll animations
- Premium SaaS appearance

Suggested approximate design tokens:

```
Primary blue:      #A4C5E5
Soft blue:         #E8F1FA
Canvas:            #F8F7F5
Surface:           #FFFFFF
Ink:               #191515
Muted text:        #575250
Border:            #E5E2DE
Warm accent:       #F0E2D5
Success:           #16833A
Warning:           #B7791F
Danger:            #C53B3B

```

Create original messaging for the GST prototype.

Suggested content direction:

```
Badge:
AI-powered GST workflow for Indian CA firms

Headline:
Turn scattered GST documents into a review-ready filing pack.

Supporting text:
Collect documents through WhatsApp, extract invoice data,
detect missing records, reconcile GSTR-2B, and prepare every
client for CA review from one workspace.

Buttons:
Open Demo
See the Workflow

```

Landing-page sections:

1. Floating navbar
2. Hero
3. Product dashboard preview
4. GST document-collection feature
5. AI extraction feature
6. Validation feature
7. GSTR-2B reconciliation feature
8. RAG assistant feature
9. Human-review and audit section
10. Final CTA
11. Footer

Use a text-based OBLIQ wordmark if an official logo asset is not supplied. Do not extract the logo from screenshots.

## Step 2: Authentication

Use Supabase Auth with:

- Email/password registration
- Login
- Logout
- Session persistence
- Protected dashboard routes
- Password visibility toggle
- Demo-login button

Roles:

```
firm_admin
gst_preparer
reviewer

```

The frontend should obtain the Supabase session.

The FastAPI backend should accept the bearer token and verify the user.

Never expose the Supabase service-role key in the frontend.

## Step 3: Dashboard

Show:

- Total clients
- Active GST applications
- Missing documents
- Extraction jobs requiring review
- Reconciliation issues
- Applications ready for filing

Show four or five synthetic clients.

## Step 4: Create Client

The client form must include:

- Business name
- Legal name
- GSTIN
- State
- Business type
- Filing frequency: monthly or quarterly
- Contact-person name
- WhatsApp phone number
- Preferred language
- WhatsApp consent status
- Assigned preparer
- Assigned reviewer

Store phone numbers in an international format such as:

```
+9198XXXXXXXX

```

Creating a client must not automatically send a WhatsApp message.

## Step 5: Start GST Application

The CA clicks:

```
Start New GST Period

```

Create an `application` or `gst_application` representing one compliance case.

Fields:

- Financial year
- GST period
- Start date
- End date
- Filing frequency
- Due date
- Assigned preparer
- Reviewer
- Status

Suggested statuses:

```
not_started
documents_requested
partially_received
documents_complete
processing
extraction_review
validation_review
reconciliation_review
ready_for_ca_review
approved
ready_for_filing
completed

```

## Step 6: Document Checklist

For the prototype, the checklist must include:

- Sales register
- Purchase register
- Sales invoices
- Purchase invoices
- GSTR-2B

Supported formats:

- PDF
- PNG
- JPEG
- CSV
- XLSX
- JSON for simplified GSTR-2B data

## Step 7: Initial WhatsApp Request

Generate a short message requesting the documents.

The CA must see:

```
Approve and Send
Edit
Cancel

```

Do not send automatically.

Create a secure upload link before sending the message.

## Step 8: Secure Upload Link

The upload link must:

- Use a cryptographically random token
- Store only a hash of the token
- Be linked to one client and one GST application
- Expire after a configurable time
- Be revocable
- Allow upload only
- Not expose internal CA notes
- Not expose other clients
- Not require a full client account

Example page:

```
Sharma & Associates
Raj Traders
April 2026 GST Documents

Sales Register         Upload
Purchase Register      Upload
Sales Invoices         Upload
Purchase Invoices      Upload
GSTR-2B                Upload

```

## Step 9: Missing-Document Detection

Compare required documents against received documents.

If a document is missing:

1. Create a CA alert.
2. Draft a reminder.
3. Require CA approval.
4. Send only after approval.

Provide:

```
Approve Reminder
Edit
Ignore

```

## Step 10: Document Processing

After upload:

1. Validate file type and size.
2. Store in a private Supabase Storage bucket.
3. Compute SHA-256 for duplicate-file detection.
4. Create a document record.
5. Classify the document.
6. Parse the content.
7. Extract structured information.
8. Save the extraction.
9. Mark it for human review.

## Step 11: Human Review

Display:

```
Original Document | Extracted Data

```

The CA can:

- Approve
- Edit and approve
- Reject
- Request client clarification

Save:

- Original extracted value
- Corrected value
- Reviewer
- Timestamp
- Reason for correction

## Step 12: Validation

Run deterministic checks:

### GSTIN

- Present
- Expected format
- Matches client GSTIN where appropriate

Do not claim that regex validation proves official GST registration status.

### Dates

- Present
- Valid
- Falls within the selected GST period
- Not an impossible future date
- Flag wrong-period invoices

### Arithmetic

Check approximately:

```
taxable_value + cgst + sgst + igst + cess ≈ invoice_total

```

Use a configurable small tolerance.

### Duplicate Detection

Use normalized combinations such as:

```
supplier_gstin
invoice_number
invoice_date
invoice_total

```

### Wrong Client

Flag documents where a customer GSTIN or business name conflicts with the selected client.

## Step 13: GSTR-2B Reconciliation

Use a simplified prototype GSTR-2B format.

Compare the purchase register with GSTR-2B using:

- Supplier GSTIN
- Normalized invoice number
- Invoice date
- Taxable value
- CGST
- SGST
- IGST
- Total tax

Statuses:

```
matched
purchase_only
gstr2b_only
amount_mismatch
date_mismatch
possible_duplicate

```

Show counts and detailed records.

Do not automatically approve or reject ITC.

Label results as:

> **Possible ITC differences requiring CA review**

## Step 14: RAG Assistant

Provide a secured assistant inside the CA dashboard.

It should answer questions such as:

- What is missing for Raj Traders?
- Why was this invoice flagged?
- What does this GSTR-2B mismatch mean?
- What should I ask the client to resend?
- Explain this finding in simple language.
- Draft a professional WhatsApp reminder.
- Show the source behind this explanation.

Use structured database tools for client facts.

Use RAG for GST guidance and firm SOP explanations.

## Step 15: GST Readiness Summary

Generate:

- Checklist status
- Documents received
- Documents reviewed
- Sales totals
- Purchase totals
- Output-tax summary
- Potential input-tax summary
- Simple estimated liability
- Validation findings
- Reconciliation counts
- Open issues
- Approval status
- Audit summary

Any liability calculation must be labelled:

> **Estimated from uploaded data and subject to CA review**

Do not present it as the final legal GST liability.

## Step 16: Approval and Export

Allow the CA to:

- Approve
- Return to preparer
- Request client clarification
- Export readiness report
- Export reconciliation CSV
- Export extracted invoice CSV
- Download supporting documents

Use ReportLab or another lightweight library to create a simple readiness PDF.

## Step 17: Record Filing Evidence

After external filing, allow the CA to enter:

- Filing date
- ARN
- Filed-return PDF
- Payment challan
- Final remarks

Then mark the application as:

```
completed

```

This is only evidence tracking. The application does not file the return itself.

---

# 8. Supabase Database Requirements

Use Supabase PostgreSQL only.

Do not use MongoDB.

Create SQL migration files under:

```
supabase/migrations/

```

Enable:

```
create extension if not exists vector;

```

Use UUID primary keys.

Add `created_at` and `updated_at` where useful.

Use a reusable updated-at trigger.

## Required tables

Implement at least the following tables.

### `profiles`

User profile linked to `auth.users`.

Suggested columns:

```
id
full_name
email
created_at
updated_at

```

### `firms`

```
id
name
slug
created_at
updated_at

```

### `firm_members`

```
id
firm_id
user_id
role
created_at

```

Roles:

```
firm_admin
gst_preparer
reviewer

```

### `clients`

```
id
firm_id
business_name
legal_name
gstin
state
business_type
filing_frequency
contact_name
whatsapp_phone
preferred_language
whatsapp_consent
assigned_preparer_id
reviewer_id
created_at
updated_at

```

### `applications`

This table satisfies the hiring requirement for “applications”.

Each row represents one GST compliance application or GST period.

```
id
firm_id
client_id
application_type
financial_year
period_label
period_start
period_end
filing_frequency
due_date
status
assigned_preparer_id
reviewer_id
filing_date
arn
final_notes
created_at
updated_at

```

Use:

```
application_type = gst_readiness

```

### `document_requirements`

```
id
application_id
requirement_type
label
required
status
created_at
updated_at

```

Requirement types:

```
sales_register
purchase_register
sales_invoice
purchase_invoice
gstr2b

```

### `upload_links`

```
id
application_id
client_id
token_hash
expires_at
revoked_at
created_at

```

### `documents`

```
id
firm_id
client_id
application_id
requirement_id
source
original_name
mime_type
storage_path
file_size
sha256
document_type
processing_status
uploaded_by_user_id
uploaded_from_phone
created_at
updated_at

```

Sources:

```
dashboard
secure_link
mock_whatsapp
meta_whatsapp
seed

```

### `document_extractions`

```
id
document_id
document_type
raw_text
structured_data jsonb
field_confidences jsonb
overall_confidence
provider
model_name
review_status
reviewed_by
reviewed_at
review_notes
original_structured_data jsonb
created_at
updated_at

```

### `invoice_records`

```
id
firm_id
client_id
application_id
document_id
invoice_category
supplier_name
supplier_gstin
customer_name
customer_gstin
invoice_number
invoice_number_normalized
invoice_date
place_of_supply
taxable_value
cgst
sgst
igst
cess
invoice_total
hsn_sac
line_items jsonb
source_type
review_status
created_at
updated_at

```

### `validation_findings`

```
id
firm_id
application_id
document_id
invoice_record_id
finding_type
severity
message
details jsonb
status
resolved_by
resolved_at
created_at

```

Suggested finding types:

```
missing_gstin
invalid_gstin_format
wrong_period
invalid_date
future_date
tax_total_mismatch
duplicate_invoice
wrong_client
missing_required_field
low_confidence
unreadable_document

```

### `reconciliation_runs`

```
id
firm_id
application_id
status
summary jsonb
started_at
completed_at
created_by
created_at

```

### `reconciliation_items`

```
id
reconciliation_run_id
purchase_invoice_id
gstr2b_invoice_id
match_status
match_score
differences jsonb
created_at

```

### `reminders`

```
id
firm_id
application_id
client_id
reminder_type
draft_message
approved_message
status
approved_by
approved_at
sent_at
provider
created_at
updated_at

```

Statuses:

```
draft
awaiting_approval
approved
sent
failed
cancelled

```

### `whatsapp_messages`

```
id
firm_id
client_id
application_id
provider
direction
message_type
content
external_message_id
sender_phone
recipient_phone
media_document_id
delivery_status
metadata jsonb
created_at
updated_at

```

### `integration_settings`

Store non-secret settings only.

```
id
firm_id
provider
phone_number_id
waba_id
test_recipient
connection_status
last_message_at
last_webhook_at
created_at
updated_at

```

### `knowledge_sources`

```
id
firm_id nullable
source_type
title
description
source_url
storage_path
document_version
effective_from
effective_to
checksum
status
created_at
updated_at

```

`firm_id = null` means a shared official/demo knowledge source.

### `knowledge_chunks`

```
id
source_id
firm_id nullable
chunk_index
content
metadata jsonb
search_vector tsvector
embedding vector(384)
created_at

```

Metadata should include:

```
{
  "title": "GSTR-2B Guidance",
  "section": "Invoice Reconciliation",
  "page": 4,
  "source_type": "official_gst",
  "source_url": "https://example.com",
  "effective_from": "2026-04-01",
  "document_version": "demo-v1"
}

```

### `audit_events`

```
id
firm_id
user_id
client_id
application_id
entity_type
entity_id
action
before_data jsonb
after_data jsonb
metadata jsonb
created_at

```

### `workflow_runs`

```
id
firm_id
application_id
workflow_type
current_state
state_data jsonb
status
started_at
completed_at
created_at
updated_at

```

---

# 9. Database Indexes and Vector Search

Create normal indexes for:

- `firm_id`
- `client_id`
- `application_id`
- `status`
- `whatsapp_phone`
- `invoice_number_normalized`
- `supplier_gstin`
- `invoice_date`
- `sha256`

Create a vector cosine-similarity index on:

```
knowledge_chunks.embedding

```

Create a GIN index on:

```
knowledge_chunks.search_vector

```

Create a Supabase RPC function such as:

```
match_knowledge_chunks

```

Inputs:

- Query embedding
- User firm ID
- Optional source type
- Match count
- Minimum similarity

The function should return:

- Chunk ID
- Source ID
- Content
- Metadata
- Similarity score

Retrieval must allow:

- Shared official chunks where `firm_id is null`
- Private firm chunks belonging only to the authenticated user’s firm

---

# 10. Row-Level Security

Enable RLS on application tables.

Create helper SQL functions such as:

```
user_has_firm_access(target_firm_id)
user_has_firm_role(target_firm_id, allowed_roles)

```

Policies should ensure:

- Users can see only firms to which they belong.
- Users can see only clients belonging to their firms.
- Users can see only applications belonging to their firms.
- Users can see only documents belonging to their firms.
- Users can see only firm-specific knowledge belonging to their firms.
- Official knowledge with `firm_id is null` may be read by authenticated users.
- Only firm admins may manage firm memberships or integration settings.
- Preparers and reviewers may access assigned applications.
- Public upload links never query tables directly from the browser.
- Public upload requests go through FastAPI using the service-role client.
- Meta webhooks use the service-role client.
- The service-role key must never be sent to the browser.

Create private Supabase Storage buckets:

```
gst-documents
knowledge-documents
exports

```

Use signed URLs for document viewing and downloading.

---

# 11. Backend API

Use a versioned prefix:

```
/api/v1

```

Implement at least these endpoints.

## Health

```
GET /api/v1/health

```

## Current User

```
GET   /api/v1/users/me
PATCH /api/v1/users/me

```

Authentication itself may be handled directly through Supabase Auth from the frontend.

## Firms and Team

```
GET  /api/v1/firms/current
GET  /api/v1/firms/current/members
POST /api/v1/firms/current/members

```

## Clients

```
GET    /api/v1/clients
POST   /api/v1/clients
GET    /api/v1/clients/{client_id}
PATCH  /api/v1/clients/{client_id}
DELETE /api/v1/clients/{client_id}

```

## Applications

```
GET    /api/v1/applications
POST   /api/v1/clients/{client_id}/applications
GET    /api/v1/applications/{application_id}
PATCH  /api/v1/applications/{application_id}
GET    /api/v1/applications/{application_id}/checklist

```

## Document Request

```
POST /api/v1/applications/{application_id}/document-request/draft
POST /api/v1/applications/{application_id}/document-request/approve-send

```

## Public Upload

```
GET  /api/v1/public/upload/{token}
POST /api/v1/public/upload/{token}

```

## Documents

```
GET    /api/v1/applications/{application_id}/documents
POST   /api/v1/applications/{application_id}/documents
GET    /api/v1/documents/{document_id}
POST   /api/v1/documents/{document_id}/process
GET    /api/v1/documents/{document_id}/extraction
PATCH  /api/v1/documents/{document_id}/extraction
POST   /api/v1/documents/{document_id}/approve
POST   /api/v1/documents/{document_id}/reject

```

## Validation

```
POST /api/v1/applications/{application_id}/validate
GET  /api/v1/applications/{application_id}/findings
POST /api/v1/findings/{finding_id}/resolve

```

## Reconciliation

```
POST /api/v1/applications/{application_id}/reconcile
GET  /api/v1/applications/{application_id}/reconciliation

```

## Reminders

```
POST /api/v1/applications/{application_id}/reminders/draft
POST /api/v1/reminders/{reminder_id}/approve-send
POST /api/v1/reminders/{reminder_id}/cancel

```

## RAG

```
POST /api/v1/knowledge/upload
POST /api/v1/knowledge/ingest
GET  /api/v1/knowledge/sources
POST /api/v1/assistant/query

```

## Reports

```
GET  /api/v1/applications/{application_id}/readiness-summary
POST /api/v1/applications/{application_id}/export

```

## Audit

```
GET /api/v1/applications/{application_id}/audit

```

## WhatsApp

```
GET  /api/v1/webhooks/whatsapp
POST /api/v1/webhooks/whatsapp
POST /api/v1/integrations/whatsapp/test
POST /api/v1/integrations/whatsapp/save-local
GET  /api/v1/integrations/whatsapp/status

```

## Mock Client

```
GET  /api/v1/demo/messages
POST /api/v1/demo/messages
POST /api/v1/demo/upload

```

FastAPI Swagger documentation must remain enabled for easy reviewer testing.

---

# 12. Document Classification and Extraction

Do not send every file directly to an LLM.

Use deterministic parsers first.

## File Routing

```
CSV/XLSX
  → Pandas/OpenPyXL

Text PDF
  → PyMuPDF

Scanned PDF/Image
  → OCR or Gemini vision

Irregular invoice
  → LLM structured extraction

GSTR-2B JSON/XLSX
  → Deterministic parser

```

## Document Types

Support:

```
sales_register
purchase_register
sales_invoice
purchase_invoice
gstr2b
unknown

```

Classification can use:

1. Filename
2. MIME type
3. Sheet names
4. Column headers
5. Extracted text keywords
6. LLM fallback

## Invoice Extraction Schema

Create a Pydantic schema containing:

```
document_type
supplier_name
supplier_gstin
customer_name
customer_gstin
invoice_number
invoice_date
place_of_supply
taxable_value
cgst
sgst
igst
cess
invoice_total
hsn_sac
line_items
field_confidences
overall_confidence
warnings

```

Require structured JSON output from the LLM.

Validate the LLM output through Pydantic before saving it.

If parsing fails, mark:

```
needs_manual_review

```

Do not silently invent missing values.

## Register Parsing

Expected prototype columns may include aliases for:

```
invoice_no
invoice_date
supplier_gstin
customer_gstin
party_name
taxable_value
cgst
sgst
igst
cess
invoice_total

```

Create a column-alias mapper.

If required columns cannot be identified:

- Use an LLM only to map column names.
- Do not send thousands of rows to the LLM.
- Parse rows locally after the column mapping is known.

Compute:

- Invoice count
- Taxable-value total
- CGST total
- SGST total
- IGST total
- Total invoice value
- Missing GSTIN count
- Duplicate count
- Wrong-period count

## Mock Extraction Mode

Create deterministic extraction fixtures for seeded files.

When:

```
AI_MODE=mock

```

and a known demo file is uploaded, load the matching fixture from:

```
demo_data/extractions/

```

Make it clear in the UI that the hosted demo uses deterministic demo extraction for reliability.

When:

```
AI_MODE=live

```

use the configured providers.

---

# 13. Agentic Workflow

Use LangGraph, but keep the workflow controlled and deterministic.

Do not build an uncontrolled autonomous agent.

Use LLMs only where language understanding is useful.

Use normal Python logic for calculations, validation, database queries, reconciliation, permissions, and status transitions.

## Document Processing Graph

Suggested state:

```
{
    "firm_id": str,
    "client_id": str,
    "application_id": str,
    "document_id": str,
    "file_path": str,
    "document_type": str | None,
    "raw_text": str | None,
    "structured_data": dict | None,
    "findings": list,
    "confidence": float | None,
    "requires_human_review": bool,
    "status": str
}

```

Suggested nodes:

```
load_document
      ↓
classify_document
      ↓
route_parser
      ↓
parse_document
      ↓
structured_extract
      ↓
validate_extraction
      ↓
save_extraction
      ↓
create_findings
      ↓
await_human_review

```

The graph must stop before final approval.

The CA continues the workflow by using an approval endpoint.

## Reminder Workflow Graph

Suggested nodes:

```
load_application_checklist
      ↓
identify_missing_documents
      ↓
retrieve_firm_tone_and_sop
      ↓
draft_reminder
      ↓
save_as_awaiting_approval
      ↓
human_approval
      ↓
send_through_whatsapp_provider
      ↓
record_delivery_status

```

Never send a reminder before approval.

## Reconciliation Workflow

Suggested nodes:

```
load_purchase_records
      ↓
load_gstr2b_records
      ↓
normalize_invoice_numbers
      ↓
exact_match
      ↓
amount_and_date_comparison
      ↓
generate_reconciliation_items
      ↓
save_summary
      ↓
await_ca_review

```

## RAG Assistant Agent

Give the assistant controlled tools:

```
get_client
get_application_status
get_document_checklist
get_validation_findings
get_reconciliation_summary
search_knowledge_base
draft_client_message

```

The assistant should determine whether the question requires:

- Structured database data
- RAG knowledge
- Both

Examples:

```
“What document is missing?”
→ Database tool

“Why is the document required?”
→ RAG tool

“Why was invoice SD-1042 flagged?”
→ Validation database + RAG explanation

```

---

# 14. RAG Knowledge Base

Do not use client documents as the main RAG knowledge source.

Use RAG primarily for:

- Official GST guidance
- GSTR-1 guidance
- GSTR-3B guidance
- GSTR-2B guidance
- CA firm SOPs
- Document checklists
- Internal review instructions
- Reminder-writing style

Client-specific facts must remain in structured PostgreSQL tables.

Create a small seeded knowledge base in:

```
demo_data/knowledge/

```

Use short, paraphrased demo documents with source metadata.

Do not include large copyrighted documents in the repository.

Support admin upload of additional:

- PDF
- Markdown
- TXT
- HTML
- DOCX if convenient

---

# 15. RAG Ingestion Pipeline

Implement this pipeline:

```
Knowledge File
      ↓
SHA-256 Duplicate Check
      ↓
Text Extraction
      ↓
Whitespace and Header Cleanup
      ↓
Section and Page Detection
      ↓
Chunking
      ↓
Metadata Attachment
      ↓
Embedding Generation
      ↓
Supabase pgvector Storage

```

## Text Extraction

Use:

- PyMuPDF for PDF
- Plain reader for TXT and Markdown
- BeautifulSoup for HTML
- `python-docx` for DOCX if implemented

OCR should be optional for scanned knowledge PDFs.

## Chunking

Write the chunking code explicitly.

Use a heading-aware strategy where possible.

Fallback strategy:

```
Target chunk size: 800–1,000 characters
Overlap: 120–150 characters

```

Requirements:

- Do not split in the middle of a word.
- Prefer paragraph boundaries.
- Preserve heading context.
- Preserve page number where available.
- Create stable chunk indexes.
- Store metadata for every chunk.
- Remove empty or extremely short chunks.
- Keep a checksum to avoid duplicate ingestion.

Create a reusable function such as:

```
chunk_document(
    text: str,
    sections: list,
    max_chars: int = 900,
    overlap_chars: int = 140
) -> list[KnowledgeChunk]

```

## Embedding Generation

Use:

```
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

```

Generate embeddings in small batches.

Normalize embeddings where appropriate.

Save vectors to:

```
knowledge_chunks.embedding vector(384)

```

Implement:

```
embed_texts(texts: list[str]) -> list[list[float]]

```

Provide a CLI script:

```
python scripts/ingest_knowledge.py

```

The script must:

1. Discover knowledge files.
2. Skip unchanged files using a checksum.
3. Extract text.
4. Chunk text.
5. Generate embeddings.
6. Insert the source.
7. Insert the chunks.
8. Print a useful summary.

---

# 16. RAG Retrieval Pipeline

Implement:

```
User Question
      ↓
Determine Firm and Intent
      ↓
Generate Query Embedding
      ↓
Metadata Filters
      ↓
Vector Retrieval
      +
PostgreSQL Full-Text Retrieval
      ↓
Simple Rank Fusion
      ↓
Top Context Chunks
      ↓
LLM Answer
      ↓
Citations

```

## Vector Retrieval

Call the Supabase RPC function.

Use configurable values:

```
RAG_VECTOR_TOP_K=12
RAG_FINAL_TOP_K=5
RAG_MIN_SIMILARITY=0.45

```

## Lexical Retrieval

Use PostgreSQL full-text search against:

```
knowledge_chunks.search_vector

```

## Rank Fusion

Implement a simple reciprocal-rank-fusion function or another small weighted merge.

Do not implement an expensive production reranking service.

## Metadata Filtering

Support filters for:

- `firm_id`
- `source_type`
- `document_version`
- `effective_from`
- `effective_to`
- `section`
- `form`, such as GSTR-2B

## RAG Answer Rules

The LLM prompt must require:

- Use only retrieved context for GST guidance.
- Cite sources.
- State when evidence is insufficient.
- Do not invent statutory deadlines.
- Do not provide final tax advice.
- Do not claim to replace the CA.
- Clearly distinguish application data from general guidance.
- Keep answers understandable.

Return structured output such as:

```
{
  "answer": "The invoice was flagged because...",
  "citations": [
    {
      "title": "GSTR-2B Guidance",
      "section": "Invoice Matching",
      "page": 4,
      "source_url": "https://..."
    }
  ],
  "used_application_data": true,
  "confidence": 0.84
}

```

---

# 17. WhatsApp Provider Interface

Create a clear interface such as:

```
class WhatsAppProvider(Protocol):
    async def send_text(...)
    async def send_template(...)
    async def parse_webhook(...)
    async def download_media(...)
    async def verify_webhook(...)

```

Implement:

```
MockWhatsAppProvider
MetaWhatsAppProvider

```

Select the provider through:

```
WHATSAPP_PROVIDER=mock
WHATSAPP_PROVIDER=meta

```

## Mock Provider

- Save outgoing messages to `whatsapp_messages`.
- Display them in the mock client UI.
- Accept incoming simulated messages and uploads.
- Create events using the same internal schema used by the Meta provider.
- Do not bypass the normal workflow.
- Use the same reminder and audit logic.

## Meta Provider

Implement:

- Text-message sending
- Template-message sending
- Test-message function
- Webhook verification
- Webhook parsing
- Media URL retrieval
- Media download
- Delivery-status updates
- Inbound-message handling
- Phone-number normalization
- Mapping sender numbers to clients

Do not hardcode Meta credentials.

---

# 18. Frontend Application Pages

Create these pages.

## Public

```
/

```

Landing page.

```
/auth/login
/auth/register

```

Authentication.

```
/upload/[token]

```

Secure client upload page.

```
/demo-client

```

Mock WhatsApp client.

## Protected CA Application

```
/dashboard

```

Overview.

```
/dashboard/clients
/dashboard/clients/new
/dashboard/clients/[clientId]

```

Client management.

```
/dashboard/applications/[applicationId]

```

Central GST workspace.

Tabs:

```
Overview
Documents
Extracted Data
Validation
Reconciliation
Assistant
Audit Trail

```

```
/dashboard/knowledge

```

Knowledge-source management.

```
/dashboard/integrations/whatsapp

```

WhatsApp setup.

```
/dashboard/settings

```

Basic firm and profile settings.

## Central GST Workspace

The top should show:

```
Client
GSTIN
GST period
Due date
Assigned preparer
Reviewer
Current status

```

Show a progress stepper:

```
Documents Requested
→ Documents Received
→ Extraction
→ CA Review
→ Validation
→ Reconciliation
→ Ready for Filing

```

---

# 19. Frontend UX Requirements

The frontend is not the primary engineering focus, but it must look polished enough for a hiring submission.

Use:

- Responsive design
- Proper empty states
- Loading states
- Success toasts
- Basic error states
- Accessible labels
- Keyboard-accessible controls
- Text labels in addition to status colors
- Mobile-friendly client cards
- Sidebar drawer on mobile
- Side-by-side document review on desktop
- Original/extracted tabs on mobile

Do not overuse animation in the dashboard.

Use animation mainly for:

- Landing-page reveals
- Button hover
- Product preview entrance
- Upload progress
- Status transitions
- Assistant drawer
- Toast messages

---

# 20. Demo Data

Create one synthetic CA firm:

```
Sharma & Associates

```

Create demo users:

```
Firm Admin / Partner
GST Preparer
Reviewer

```

Suggested accounts:

```
demo.admin@obliq.local
demo.preparer@obliq.local
demo.reviewer@obliq.local

```

Passwords must come from environment variables or a seed script.

Create five synthetic clients:

## Raj Traders

Scenario:

- Purchase register missing
- Initial reminder workflow

## ABC Electronics

Scenario:

- Duplicate invoice
- Wrong-period invoice

## Nova Services

Scenario:

- All documents present
- Ready for review

## City Retail

Scenario:

- GSTR-2B reconciliation mismatch

## Mehta Consulting

Scenario:

- Low-confidence scanned invoice
- Requires manual correction

Use only synthetic GSTINs and synthetic documents.

Generate demo files using scripts instead of requiring binary files in the response.

Create:

```
scripts/generate_demo_documents.py

```

It should generate:

- Sales register CSV
- Purchase register XLSX
- Simplified GSTR-2B XLSX or JSON
- Purchase-invoice PDF
- Sales-invoice PDF
- Invoice image
- One duplicate invoice
- One wrong-period invoice
- One arithmetic-mismatch invoice
- One low-quality image
- Matching mock extraction fixtures

---

# 21. Suggested Project Structure

Create a structure similar to:

```
obliq-gst-readiness-copilot/
│
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── auth/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── upload/[token]/page.tsx
│   │   ├── demo-client/page.tsx
│   │   └── dashboard/
│   │       ├── layout.tsx
│   │       ├── page.tsx
│   │       ├── clients/
│   │       ├── applications/
│   │       ├── knowledge/
│   │       ├── integrations/
│   │       └── settings/
│   ├── components/
│   │   ├── landing/
│   │   ├── dashboard/
│   │   ├── documents/
│   │   ├── reconciliation/
│   │   ├── assistant/
│   │   └── ui/
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   ├── supabase.ts
│   │   ├── types.ts
│   │   └── validation.ts
│   ├── public/
│   ├── package.json
│   └── Dockerfile
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── supabase.py
│   │   │   ├── storage.py
│   │   │   ├── audit.py
│   │   │   ├── validation.py
│   │   │   ├── reconciliation.py
│   │   │   ├── reports.py
│   │   │   ├── document_processing/
│   │   │   ├── rag/
│   │   │   ├── llm/
│   │   │   └── whatsapp/
│   │   ├── agents/
│   │   │   ├── document_workflow.py
│   │   │   ├── reminder_workflow.py
│   │   │   └── rag_assistant.py
│   │   └── prompts/
│   │       ├── extraction.py
│   │       ├── reminder.py
│   │       └── rag.py
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── supabase/
│   ├── config.toml
│   ├── migrations/
│   └── seed.sql
│
├── scripts/
│   ├── seed_demo.py
│   ├── reset_demo.py
│   ├── ingest_knowledge.py
│   ├── generate_demo_documents.py
│   └── verify_meta_setup.py
│
├── demo_data/
│   ├── knowledge/
│   ├── documents/
│   └── extractions/
│
└── docs/
    ├── architecture.md
    ├── local-setup.md
    ├── meta-whatsapp-setup.md
    ├── deployment.md
    ├── demo-walkthrough.md
    └── limitations.md

```

You may simplify this structure when it genuinely improves readability, but preserve a clear separation between frontend, backend, Supabase migrations, AI services, WhatsApp providers, and demo data.

---

# 22. Environment Variables

Create one exhaustive `.env.example` with comments.

Include at least:

## Application

```
APP_NAME=OBLIQ GST Readiness Copilot
APP_ENV=development
APP_DEBUG=true
DEMO_MODE=true
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
API_V1_PREFIX=/api/v1
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO

```

## Frontend

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_DEMO_MODE=true

```

## Supabase

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=
SUPABASE_JWKS_URL=
DATABASE_URL=

SUPABASE_DOCUMENTS_BUCKET=gst-documents
SUPABASE_KNOWLEDGE_BUCKET=knowledge-documents
SUPABASE_EXPORTS_BUCKET=exports

```

## AI Mode

```
AI_MODE=mock
TEXT_LLM_PROVIDER=groq
VISION_LLM_PROVIDER=gemini
LLM_FALLBACK_PROVIDER=openai

```

## Groq

```
GROQ_API_KEY=
GROQ_MODEL=

```

## Gemini

```
GEMINI_API_KEY=
GEMINI_TEXT_MODEL=
GEMINI_VISION_MODEL=

```

## OpenAI Optional Fallback

```
OPENAI_API_KEY=
OPENAI_TEXT_MODEL=
OPENAI_VISION_MODEL=

```

## Embeddings and RAG

```
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384

RAG_VECTOR_TOP_K=12
RAG_FINAL_TOP_K=5
RAG_MIN_SIMILARITY=0.45
RAG_CHUNK_SIZE=900
RAG_CHUNK_OVERLAP=140

```

## OCR

```
OCR_ENABLED=true
TESSERACT_CMD=

```

## Uploads

```
MAX_UPLOAD_MB=20
ALLOWED_UPLOAD_EXTENSIONS=pdf,png,jpg,jpeg,csv,xlsx,json
UPLOAD_LINK_TTL_HOURS=72

```

## WhatsApp

```
WHATSAPP_PROVIDER=mock

META_ACCESS_TOKEN=
META_PHONE_NUMBER_ID=
META_WABA_ID=
META_APP_SECRET=
META_WEBHOOK_VERIFY_TOKEN=
META_GRAPH_API_VERSION=
META_TEST_RECIPIENT_NUMBER=
META_DOCUMENT_REQUEST_TEMPLATE=
META_REMINDER_TEMPLATE=

ALLOW_LOCAL_CREDENTIAL_SETUP=false
LOCAL_META_CREDENTIALS_FILE=.runtime/meta_credentials.json
PUBLIC_WEBHOOK_BASE_URL=

```

## ngrok Optional

```
NGROK_AUTHTOKEN=
NGROK_DOMAIN=

```

## Demo Accounts

```
DEMO_ADMIN_EMAIL=demo.admin@obliq.local
DEMO_ADMIN_PASSWORD=ChangeMe123!

DEMO_PREPARER_EMAIL=demo.preparer@obliq.local
DEMO_PREPARER_PASSWORD=ChangeMe123!

DEMO_REVIEWER_EMAIL=demo.reviewer@obliq.local
DEMO_REVIEWER_PASSWORD=ChangeMe123!

```

## Demo Reset

```
DEMO_RESET_ON_START=false
DEMO_SEED_DATA=true

```

Do not include real credentials.

---

# 23. Local Execution Guide

The README must provide exact steps.

## Prerequisites

- Node.js
- Python
- Docker
- Supabase CLI
- Optional Tesseract
- Optional ngrok
- Optional Meta developer account

## Basic Demo Mode

Expected flow:

```
git clone <repository-url>
cd obliq-gst-readiness-copilot
cp .env.example .env
supabase start
supabase db reset
python scripts/generate_demo_documents.py
python scripts/seed_demo.py
python scripts/ingest_knowledge.py
docker compose up --build

```

Or provide equivalent `Makefile` commands:

```
make setup
make seed
make ingest
make dev

```

Document the URLs:

```
Frontend: http://localhost:3000
Backend: http://localhost:8000
Swagger: http://localhost:8000/docs
Supabase Studio: local Supabase Studio URL

```

## Real Meta Outbound Test

Document:

1. Create Meta developer app.
2. Add WhatsApp product.
3. Copy test-number credentials.
4. Add and verify a test-recipient phone.
5. Set Meta environment variables.
6. Set:

```
WHATSAPP_PROVIDER=meta

```

7. Restart backend.
8. Open WhatsApp integration settings.
9. Click Test Connection.
10. Send test message.

## Full Two-Way Meta Test

Document:

1. Start backend.
2. Start ngrok:

```
ngrok http 8000

```

3. Copy HTTPS URL.
4. Configure Meta callback:

```
https://<ngrok-domain>/api/v1/webhooks/whatsapp

```

5. Use the configured verify token.
6. Subscribe to message events.
7. Send a message or media file from the verified recipient.
8. Confirm the webhook event appears in OBLIQ.

Explain that the reviewer’s own Meta account and test recipient are required.

---

# 24. Manual Deployment Guide

Do not create CI/CD.

Provide manual deployment instructions.

Suggested deployment:

```
Frontend: Vercel
Backend: Render or Railway
Database/Auth/Storage: Hosted Supabase

```

Public deployment configuration:

```
DEMO_MODE=true
WHATSAPP_PROVIDER=mock
ALLOW_LOCAL_CREDENTIAL_SETUP=false

```

The public deployment must not expose Meta credentials.

The public deployment should provide:

- Demo login button
- Seeded clients
- Mock WhatsApp client
- Seeded documents
- Deterministic demo extraction
- Working RAG knowledge base
- Resettable synthetic data

Provide manual steps for:

- Creating a Supabase project
- Running migrations
- Creating storage buckets
- Seeding demo users
- Deploying backend
- Deploying frontend
- Setting environment variables
- Updating CORS
- Verifying the health endpoint

---

# 25. Minimal Tests

Do not build an extensive test suite.

Include a few useful tests:

- JWT-protected endpoint rejects unauthenticated user
- User cannot access another firm’s client
- Mock WhatsApp provider stores an outgoing message
- Secure upload token expires correctly
- Invoice arithmetic validation flags mismatch
- Duplicate invoice detection works
- Reconciliation identifies matched and unmatched records
- Chunking creates overlapping chunks
- RAG retrieval returns firm-specific and official chunks
- Meta webhook verification works

Do not add CI/CD.

---

# 26. README Requirements

Create a complete README containing:

1. Product overview
2. Problem being solved
3. Prototype scope
4. Architecture diagram in Mermaid
5. Technology stack
6. Feature walkthrough
7. Hosted mock-mode explanation
8. Local Meta-mode explanation
9. Local setup
10. Environment variables
11. Demo credentials
12. RAG architecture
13. Database design
14. API documentation link
15. Manual deployment guide
16. Limitations
17. Security notes
18. Future production improvements

Clearly state:

> The hosted demo simulates WhatsApp transport through a browser client. The same workflow supports Meta WhatsApp Cloud API through the local provider configuration.

Also state:

> This prototype prepares GST data for CA review. It does not file returns, pay GST, determine final ITC eligibility, or replace professional judgement.

---

# 27. Required Deliverables

Produce all of the following:

- Complete directory structure
- Complete frontend code
- Complete FastAPI backend code
- Supabase SQL migrations
- RLS policies
- Storage setup
- pgvector setup
- Vector-search RPC function
- RAG ingestion code
- Chunking code
- Embedding-generation code
- Retrieval code
- Hybrid-search code
- Citation-based answer generation
- LangGraph workflow code
- Document-processing code
- Invoice extraction schemas
- Excel/CSV parsing
- Simplified GSTR-2B parsing
- Validation logic
- Reconciliation logic
- Mock WhatsApp provider
- Meta WhatsApp provider
- Webhook endpoints
- ngrok setup guide
- Secure upload-link flow
- Demo client simulator
- CA dashboard
- Auth pages
- Landing page
- Seed data
- Demo-document generator
- Demo-extraction fixtures
- GST readiness report export
- Audit logging
- `.env.example`
- Docker configuration
- Makefile or clear run commands
- Minimal tests
- Local setup guide
- Manual deployment guide
- Demo walkthrough

Do not provide only pseudo-code.

Do not leave core features as TODOs.

Small non-core items may be marked as future enhancements, but the central workflow must be functional.

---

# 28. Acceptance Criteria

The implementation is complete when all of the following work.

## Hosted Mock Mode

1. Judge opens the landing page.
2. Judge signs in with a demo CA account.
3. Judge sees five synthetic clients.
4. Judge opens Raj Traders.
5. Judge starts an April GST application.
6. Judge generates a document checklist.
7. Judge approves the WhatsApp request.
8. The message appears in the mock client interface.
9. Judge uploads only four of five document categories.
10. CA dashboard detects that the purchase register is missing.
11. The system drafts a reminder.
12. Judge approves it.
13. The reminder appears in the client simulator.
14. Judge uploads the missing purchase register.
15. Checklist becomes complete.
16. AI/mock extraction processes files.
17. Judge reviews and corrects one extracted field.
18. Validation finds one duplicate or wrong-period invoice.
19. Reconciliation compares purchase register and GSTR-2B.
20. RAG assistant explains one finding with citations.
21. GST readiness summary is generated.
22. Judge downloads the readiness report.
23. Audit trail shows the important actions.

## Local Meta Mode

1. Reviewer clones the repository.
2. Reviewer runs mock mode without external credentials.
3. Reviewer adds their own Meta credentials.
4. Reviewer chooses their verified recipient number.
5. Test Connection succeeds.
6. A real WhatsApp test message reaches their phone.
7. Reviewer starts ngrok.
8. Meta verifies the webhook.
9. A reply or media message reaches local FastAPI.
10. The document appears in the correct GST application.
11. The same extraction and readiness workflow continues.

---

# 29. Final Implementation Rules

- Build a lightweight prototype.
- Keep code understandable for a beginner reviewing the repository.
- Add comments around complex AI, RAG, webhook, and Supabase logic.
- Use type hints.
- Use Pydantic schemas.
- Avoid unnecessary abstractions.
- Use provider interfaces only where they provide clear value.
- Use synthetic data only.
- Never commit secrets.
- Never expose service-role keys to the frontend.
- Never expose Meta tokens to the frontend.
- Never claim automatic GST filing.
- Never claim final ITC eligibility.
- Never present AI outputs as professional tax advice.
- Always require human review for extracted data.
- Always require human approval before sending document requests or reminders.
- Use structured database data for client facts.
- Use RAG for knowledge explanations.
- Display sources with RAG answers.
- Ensure mock mode works without paid services.
- Ensure real Meta mode is optional.
- Do not implement CI/CD.
- Do not stop after creating an implementation plan.
- Create the actual working codebase and documentation.

At the end, provide:

1. A short implementation summary.
2. The final directory tree.
3. Exact local run commands.
4. Demo credentials.
5. Exact steps to run mock WhatsApp mode.
6. Exact steps to run Meta WhatsApp mode with ngrok.
7. Any known prototype limitations.