-- Explicit client submission boundary for Phase 3 processing.

alter table public.documents
  add column if not exists upload_link_id uuid references public.upload_links(id) on delete set null,
  add column if not exists submission_batch_id uuid,
  add column if not exists submitted_at timestamptz;

alter table public.documents drop constraint if exists documents_processing_status_check;
alter table public.documents add constraint documents_processing_status_check check (processing_status in (
  'uploaded', 'queued', 'uploading', 'awaiting_submission', 'awaiting_processing',
  'upload_failed', 'processing', 'needs_assignment', 'needs_review',
  'ready_for_review', 'processing_failed', 'excluded_reference', 'processed',
  'failed', 'approved', 'rejected'
));

create table if not exists public.document_submission_batches (
  id uuid primary key,
  firm_id uuid not null references public.firms(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  demo_session_id uuid references public.whatsapp_demo_sessions(id) on delete set null,
  upload_link_id uuid not null references public.upload_links(id) on delete cascade,
  status text not null default 'submitted' check (
    status in ('submitted', 'processing', 'partially_completed', 'completed', 'failed')
  ),
  document_count integer not null check (document_count > 0),
  completed_count integer not null default 0 check (completed_count >= 0),
  failed_count integer not null default 0 check (failed_count >= 0),
  submitted_at timestamptz not null,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.documents
  add constraint documents_submission_batch_id_fkey
  foreign key (submission_batch_id) references public.document_submission_batches(id) on delete set null;

create index if not exists document_submission_batches_application_idx
  on public.document_submission_batches(application_id, submitted_at desc);
create index if not exists documents_submission_batch_idx
  on public.documents(submission_batch_id) where submission_batch_id is not null;
create index if not exists documents_upload_link_submission_idx
  on public.documents(upload_link_id, processing_status) where upload_link_id is not null;

alter table public.document_submission_batches enable row level security;
revoke all on public.document_submission_batches from anon, authenticated;
grant select, insert, update, delete on public.document_submission_batches to service_role;

create or replace function public.submit_document_batch(
  p_upload_link_id uuid,
  p_batch_id uuid,
  p_now timestamptz
)
returns setof public.document_submission_batches
language plpgsql
security definer
set search_path = public
as $$
declare
  v_link public.upload_links%rowtype;
  v_application public.applications%rowtype;
  v_count integer;
begin
  select * into v_link from public.upload_links
  where id = p_upload_link_id and revoked_at is null and expires_at > p_now
  for update;
  if not found then return; end if;

  select * into v_application from public.applications
  where id = v_link.application_id and firm_id = v_link.firm_id and client_id = v_link.client_id;
  if not found then return; end if;

  select count(*) into v_count from public.documents
  where upload_link_id = v_link.id
    and application_id = v_link.application_id
    and processing_status = 'awaiting_submission'
    and submission_batch_id is null
    and document_type not in ('developer_ground_truth', 'unknown');
  if v_count = 0 then return; end if;

  insert into public.document_submission_batches (
    id, firm_id, client_id, application_id, demo_session_id, upload_link_id,
    status, document_count, submitted_at
  ) values (
    p_batch_id, v_link.firm_id, v_link.client_id, v_link.application_id,
    v_link.demo_session_id, v_link.id, 'submitted', v_count, p_now
  );

  update public.documents set
    submission_batch_id = p_batch_id,
    submitted_at = p_now,
    processing_status = 'awaiting_processing',
    updated_at = p_now
  where upload_link_id = v_link.id
    and application_id = v_link.application_id
    and processing_status = 'awaiting_submission'
    and submission_batch_id is null
    and document_type not in ('developer_ground_truth', 'unknown');

  return query select * from public.document_submission_batches where id = p_batch_id;
end;
$$;

revoke all on function public.submit_document_batch(uuid, uuid, timestamptz) from public;
grant execute on function public.submit_document_batch(uuid, uuid, timestamptz) to service_role;
