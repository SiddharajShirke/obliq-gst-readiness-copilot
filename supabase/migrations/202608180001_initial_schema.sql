-- OBLIQ GST Readiness Copilot: relational schema and pgvector foundation.
create schema if not exists extensions;
create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null default '',
  email text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.firms (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.firm_members (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('firm_admin', 'gst_preparer', 'reviewer')),
  created_at timestamptz not null default timezone('utc', now()),
  unique (firm_id, user_id)
);

create table if not exists public.clients (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  business_name text not null,
  legal_name text not null,
  gstin text not null,
  state text not null,
  business_type text not null default 'business',
  filing_frequency text not null check (filing_frequency in ('monthly', 'quarterly')),
  contact_name text not null,
  whatsapp_phone text not null,
  preferred_language text not null default 'English',
  whatsapp_consent boolean not null default false,
  demo_scenario text,
  assigned_preparer_id uuid references auth.users(id) on delete set null,
  reviewer_id uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (firm_id, gstin)
);

create table if not exists public.applications (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  application_type text not null default 'gst_readiness' check (application_type = 'gst_readiness'),
  financial_year text not null,
  period_label text not null,
  period_start date not null,
  period_end date not null,
  filing_frequency text not null check (filing_frequency in ('monthly', 'quarterly')),
  due_date date,
  status text not null default 'not_started' check (status in (
    'not_started', 'documents_requested', 'partially_received', 'documents_complete',
    'processing', 'extraction_review', 'validation_review', 'reconciliation_review',
    'ready_for_ca_review', 'approved', 'ready_for_filing', 'completed'
  )),
  assigned_preparer_id uuid references auth.users(id) on delete set null,
  reviewer_id uuid references auth.users(id) on delete set null,
  filing_date date,
  arn text,
  filed_return_document_id uuid,
  payment_challan_document_id uuid,
  final_notes text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (client_id, period_start, period_end)
);

create table if not exists public.document_requirements (
  id uuid primary key default gen_random_uuid(),
  application_id uuid not null references public.applications(id) on delete cascade,
  requirement_type text not null check (requirement_type in (
    'sales_register', 'purchase_register', 'sales_invoice', 'purchase_invoice', 'gstr2b'
  )),
  label text not null,
  required boolean not null default true,
  status text not null default 'missing' check (status in (
    'missing', 'partially_received', 'received', 'processing', 'needs_review', 'approved', 'rejected'
  )),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (application_id, requirement_type)
);

create table if not exists public.upload_links (
  id uuid primary key default gen_random_uuid(),
  application_id uuid not null references public.applications(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  application_id uuid references public.applications(id) on delete cascade,
  requirement_id uuid references public.document_requirements(id) on delete set null,
  source text not null check (source in (
    'dashboard', 'secure_link', 'mock_whatsapp', 'meta_whatsapp', 'seed',
    'filing_evidence', 'knowledge'
  )),
  original_name text not null,
  mime_type text not null,
  storage_path text not null,
  file_size bigint not null default 0,
  sha256 text not null,
  document_type text not null default 'unknown' check (document_type in (
    'sales_register', 'purchase_register', 'sales_invoice', 'purchase_invoice',
    'gstr2b', 'filed_return', 'payment_challan', 'unknown'
  )),
  processing_status text not null default 'uploaded' check (processing_status in (
    'uploaded', 'queued', 'processing', 'needs_assignment', 'needs_review',
    'processed', 'failed', 'approved', 'rejected'
  )),
  uploaded_by_user_id uuid references auth.users(id) on delete set null,
  uploaded_from_phone text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

alter table public.applications
  add constraint applications_filed_return_fk
  foreign key (filed_return_document_id) references public.documents(id) on delete set null;
alter table public.applications
  add constraint applications_payment_challan_fk
  foreign key (payment_challan_document_id) references public.documents(id) on delete set null;

create table if not exists public.document_extractions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null unique references public.documents(id) on delete cascade,
  document_type text not null,
  raw_text text,
  structured_data jsonb not null default '{}'::jsonb,
  field_confidences jsonb not null default '{}'::jsonb,
  overall_confidence numeric(5,4),
  provider text not null default 'mock',
  model_name text,
  review_status text not null default 'pending' check (review_status in (
    'pending', 'approved', 'edited_and_approved', 'rejected', 'clarification_requested'
  )),
  reviewed_by uuid references auth.users(id) on delete set null,
  reviewed_at timestamptz,
  review_notes text,
  original_structured_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.invoice_records (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  document_id uuid references public.documents(id) on delete set null,
  invoice_category text not null check (invoice_category in ('sales', 'purchase', 'gstr2b')),
  supplier_name text,
  supplier_gstin text,
  customer_name text,
  customer_gstin text,
  invoice_number text,
  invoice_number_normalized text,
  invoice_date date,
  place_of_supply text,
  taxable_value numeric(18,2) not null default 0,
  cgst numeric(18,2) not null default 0,
  sgst numeric(18,2) not null default 0,
  igst numeric(18,2) not null default 0,
  cess numeric(18,2) not null default 0,
  invoice_total numeric(18,2) not null default 0,
  hsn_sac text,
  line_items jsonb not null default '[]'::jsonb,
  source_type text not null,
  review_status text not null default 'pending' check (review_status in (
    'pending', 'approved', 'edited_and_approved', 'rejected'
  )),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.validation_findings (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  document_id uuid references public.documents(id) on delete cascade,
  invoice_record_id uuid references public.invoice_records(id) on delete cascade,
  finding_type text not null,
  severity text not null check (severity in ('low', 'medium', 'high')),
  message text not null,
  details jsonb not null default '{}'::jsonb,
  status text not null default 'open' check (status in ('open', 'resolved', 'accepted')),
  resolved_by uuid references auth.users(id) on delete set null,
  resolved_at timestamptz,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.reconciliation_runs (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  status text not null default 'running' check (status in ('running', 'completed', 'failed')),
  summary jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.reconciliation_items (
  id uuid primary key default gen_random_uuid(),
  reconciliation_run_id uuid not null references public.reconciliation_runs(id) on delete cascade,
  purchase_invoice_id uuid references public.invoice_records(id) on delete set null,
  gstr2b_invoice_id uuid references public.invoice_records(id) on delete set null,
  match_status text not null check (match_status in (
    'matched', 'purchase_only', 'gstr2b_only', 'amount_mismatch', 'date_mismatch', 'possible_duplicate'
  )),
  match_score numeric(5,4) not null default 0,
  differences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.reminders (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  reminder_type text not null,
  draft_message text not null,
  approved_message text,
  status text not null default 'awaiting_approval' check (status in (
    'draft', 'awaiting_approval', 'approved', 'sent', 'failed', 'cancelled'
  )),
  approved_by uuid references auth.users(id) on delete set null,
  approved_at timestamptz,
  sent_at timestamptz,
  provider text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.whatsapp_messages (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid references public.firms(id) on delete cascade,
  client_id uuid references public.clients(id) on delete cascade,
  application_id uuid references public.applications(id) on delete cascade,
  provider text not null check (provider in ('mock', 'meta')),
  direction text not null check (direction in ('inbound', 'outbound')),
  message_type text not null check (message_type in ('text', 'template', 'document', 'image', 'status')),
  content text,
  external_message_id text,
  sender_phone text,
  recipient_phone text,
  media_document_id uuid references public.documents(id) on delete set null,
  delivery_status text not null default 'queued' check (delivery_status in (
    'queued', 'sent', 'delivered', 'read', 'received', 'failed'
  )),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.integration_settings (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  provider text not null check (provider in ('mock', 'meta')),
  phone_number_id text,
  waba_id text,
  test_recipient text,
  connection_status text not null default 'not_configured' check (connection_status in (
    'not_configured', 'connected', 'error'
  )),
  last_message_at timestamptz,
  last_webhook_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (firm_id)
);

create table if not exists public.knowledge_sources (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid references public.firms(id) on delete cascade,
  source_type text not null,
  title text not null,
  description text,
  source_url text,
  storage_path text,
  document_version text,
  effective_from date,
  effective_to date,
  checksum text not null,
  status text not null default 'active' check (status in ('processing', 'active', 'failed', 'archived')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique nulls not distinct (firm_id, checksum)
);

create table if not exists public.knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.knowledge_sources(id) on delete cascade,
  firm_id uuid references public.firms(id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  search_vector tsvector generated always as (to_tsvector('english', coalesce(content, ''))) stored,
  embedding extensions.vector(384) not null,
  created_at timestamptz not null default timezone('utc', now()),
  unique (source_id, chunk_index)
);

create table if not exists public.alerts (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  application_id uuid references public.applications(id) on delete cascade,
  client_id uuid references public.clients(id) on delete cascade,
  alert_type text not null,
  title text not null,
  message text not null,
  severity text not null default 'medium' check (severity in ('low', 'medium', 'high')),
  status text not null default 'open' check (status in ('open', 'acknowledged', 'resolved')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  user_id uuid references auth.users(id) on delete set null,
  client_id uuid references public.clients(id) on delete set null,
  application_id uuid references public.applications(id) on delete set null,
  entity_type text not null,
  entity_id uuid,
  action text not null,
  before_data jsonb,
  after_data jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.workflow_runs (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  application_id uuid references public.applications(id) on delete cascade,
  workflow_type text not null,
  current_state text not null,
  state_data jsonb not null default '{}'::jsonb,
  status text not null default 'running' check (status in ('running', 'awaiting_human', 'completed', 'failed')),
  started_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists firm_members_firm_id_idx on public.firm_members(firm_id);
create index if not exists firm_members_user_id_idx on public.firm_members(user_id);
create index if not exists clients_firm_id_idx on public.clients(firm_id);
create index if not exists clients_whatsapp_phone_idx on public.clients(whatsapp_phone);
create index if not exists applications_firm_id_idx on public.applications(firm_id);
create index if not exists applications_client_id_idx on public.applications(client_id);
create index if not exists applications_status_idx on public.applications(status);
create index if not exists document_requirements_application_id_idx on public.document_requirements(application_id);
create index if not exists documents_firm_id_idx on public.documents(firm_id);
create index if not exists documents_application_id_idx on public.documents(application_id);
create index if not exists documents_sha256_idx on public.documents(sha256);
create index if not exists invoice_records_application_id_idx on public.invoice_records(application_id);
create index if not exists invoice_records_supplier_gstin_idx on public.invoice_records(supplier_gstin);
create index if not exists invoice_records_invoice_number_idx on public.invoice_records(invoice_number_normalized);
create index if not exists invoice_records_invoice_date_idx on public.invoice_records(invoice_date);
create index if not exists validation_findings_application_id_idx on public.validation_findings(application_id);
create index if not exists reconciliation_runs_application_id_idx on public.reconciliation_runs(application_id);
create index if not exists reminders_application_id_idx on public.reminders(application_id);
create index if not exists whatsapp_messages_application_id_idx on public.whatsapp_messages(application_id);
create index if not exists knowledge_chunks_firm_id_idx on public.knowledge_chunks(firm_id);
create index if not exists knowledge_chunks_search_idx on public.knowledge_chunks using gin(search_vector);
create index if not exists knowledge_chunks_embedding_idx
  on public.knowledge_chunks using hnsw (embedding extensions.vector_cosine_ops)
  with (m = 16, ef_construction = 64);
create index if not exists audit_events_application_id_idx on public.audit_events(application_id, created_at desc);

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function public.set_updated_at();
create trigger firms_set_updated_at before update on public.firms
for each row execute function public.set_updated_at();
create trigger clients_set_updated_at before update on public.clients
for each row execute function public.set_updated_at();
create trigger applications_set_updated_at before update on public.applications
for each row execute function public.set_updated_at();
create trigger document_requirements_set_updated_at before update on public.document_requirements
for each row execute function public.set_updated_at();
create trigger documents_set_updated_at before update on public.documents
for each row execute function public.set_updated_at();
create trigger document_extractions_set_updated_at before update on public.document_extractions
for each row execute function public.set_updated_at();
create trigger invoice_records_set_updated_at before update on public.invoice_records
for each row execute function public.set_updated_at();
create trigger reminders_set_updated_at before update on public.reminders
for each row execute function public.set_updated_at();
create trigger whatsapp_messages_set_updated_at before update on public.whatsapp_messages
for each row execute function public.set_updated_at();
create trigger integration_settings_set_updated_at before update on public.integration_settings
for each row execute function public.set_updated_at();
create trigger knowledge_sources_set_updated_at before update on public.knowledge_sources
for each row execute function public.set_updated_at();
create trigger alerts_set_updated_at before update on public.alerts
for each row execute function public.set_updated_at();
create trigger workflow_runs_set_updated_at before update on public.workflow_runs
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', ''),
    coalesce(new.email, '')
  )
  on conflict (id) do update
    set full_name = excluded.full_name,
        email = excluded.email,
        updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();
