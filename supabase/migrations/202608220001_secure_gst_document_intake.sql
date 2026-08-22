-- Phase 2: secure browser intake into private Supabase Storage.

alter table public.upload_links
  add column firm_id uuid references public.firms(id) on delete cascade,
  add column demo_session_id uuid references public.whatsapp_demo_sessions(id) on delete cascade,
  add column requirement_id uuid references public.document_requirements(id) on delete cascade,
  add column created_by_user_id uuid references auth.users(id) on delete set null;

update public.upload_links ul
set firm_id = a.firm_id,
    demo_session_id = a.demo_session_id
from public.applications a
where a.id = ul.application_id;

alter table public.upload_links
  alter column firm_id set not null;

-- Old rows used a non-domain-separated SHA-256 construction. Make the
-- HMAC transition explicit instead of leaving apparently valid legacy links.
update public.upload_links
set revoked_at = timezone('utc', now())
where revoked_at is null;

create index upload_links_demo_session_id_idx
  on public.upload_links(demo_session_id, created_at desc)
  where demo_session_id is not null;
create index upload_links_application_expiry_idx
  on public.upload_links(application_id, expires_at)
  where revoked_at is null;

alter table public.documents
  add column demo_session_id uuid references public.whatsapp_demo_sessions(id) on delete cascade,
  add column safe_name text,
  add column storage_bucket text not null default 'gst-documents',
  add column upload_completed_at timestamptz;

alter table public.documents
  alter column document_type drop not null;

alter table public.documents
  drop constraint documents_processing_status_check;
alter table public.documents
  add constraint documents_processing_status_check check (processing_status in (
    'uploaded', 'queued', 'uploading', 'awaiting_processing', 'upload_failed',
    'processing', 'needs_assignment', 'needs_review', 'processed', 'failed',
    'approved', 'rejected'
  ));

create index documents_demo_session_id_idx
  on public.documents(demo_session_id, created_at desc)
  where demo_session_id is not null;
create index documents_requirement_id_idx
  on public.documents(requirement_id, created_at desc)
  where requirement_id is not null;
create unique index documents_secure_link_sha256_uidx
  on public.documents(application_id, sha256)
  where source = 'secure_link'
    and upload_completed_at is not null
    and processing_status <> 'upload_failed';

create function public.complete_secure_document_upload(
  p_document_id uuid,
  p_firm_id uuid,
  p_client_id uuid,
  p_application_id uuid,
  p_demo_session_id uuid,
  p_requirement_id uuid,
  p_original_name text,
  p_safe_name text,
  p_mime_type text,
  p_file_size bigint,
  p_sha256 text,
  p_storage_bucket text,
  p_storage_path text,
  p_completed_at timestamptz
)
returns setof public.documents
language plpgsql
security definer
set search_path = public
as $$
declare
  v_application public.applications%rowtype;
  v_requirement public.document_requirements%rowtype;
  v_session public.whatsapp_demo_sessions%rowtype;
begin
  select * into v_application
  from public.applications
  where id = p_application_id
    and firm_id = p_firm_id
    and client_id = p_client_id
  for update;

  if not found or v_application.demo_session_id is distinct from p_demo_session_id then
    raise exception 'Secure upload application scope mismatch';
  end if;

  select * into v_requirement
  from public.document_requirements
  where id = p_requirement_id
    and application_id = p_application_id
  for update;

  if not found then
    raise exception 'Secure upload requirement scope mismatch';
  end if;

  if p_demo_session_id is not null then
    select * into v_session
    from public.whatsapp_demo_sessions
    where id = p_demo_session_id
      and session_application_id = p_application_id
      and firm_id = p_firm_id
      and base_client_id = p_client_id
      and status = 'active'
      and expires_at > p_completed_at
    for update;

    if not found then
      raise exception 'Secure upload demo session scope mismatch';
    end if;
  end if;

  if exists (
    select 1
    from public.documents
    where application_id = p_application_id
      and sha256 = p_sha256
      and source = 'secure_link'
      and upload_completed_at is not null
      and processing_status <> 'upload_failed'
  ) then
    raise exception using errcode = '23505', message = 'Duplicate secure upload';
  end if;

  insert into public.documents (
    id, firm_id, client_id, application_id, demo_session_id, requirement_id,
    source, original_name, safe_name, mime_type, storage_bucket, storage_path,
    file_size, sha256, document_type, processing_status, uploaded_by_user_id,
    uploaded_from_phone, upload_completed_at
  ) values (
    p_document_id, p_firm_id, p_client_id, p_application_id, p_demo_session_id,
    p_requirement_id, 'secure_link', p_original_name, p_safe_name, p_mime_type,
    p_storage_bucket, p_storage_path, p_file_size, p_sha256, null,
    'awaiting_processing', null, null, p_completed_at
  );

  update public.document_requirements
  set status = 'received'
  where id = p_requirement_id;

  update public.applications
  set status = case
    when exists (
      select 1 from public.document_requirements
      where application_id = p_application_id
        and required
        and status = 'missing'
    ) then 'partially_received'
    else 'documents_complete'
  end
  where id = p_application_id;

  if p_demo_session_id is not null then
    update public.whatsapp_demo_sessions
    set current_step = case
          when exists (
            select 1 from public.document_requirements
            where application_id = p_application_id
              and required
              and status = 'missing'
          ) then 'documents_received'
          else 'documents_complete'
        end,
        last_activity_at = p_completed_at
    where id = p_demo_session_id;
  end if;

  return query
  select * from public.documents where id = p_document_id;
end;
$$;

revoke execute on function public.complete_secure_document_upload(
  uuid, uuid, uuid, uuid, uuid, uuid, text, text, text, bigint,
  text, text, text, timestamptz
) from public, anon, authenticated;
grant execute on function public.complete_secure_document_upload(
  uuid, uuid, uuid, uuid, uuid, uuid, text, text, text, bigint,
  text, text, text, timestamptz
) to service_role;

update storage.buckets
set public = false
where id = 'gst-documents';
