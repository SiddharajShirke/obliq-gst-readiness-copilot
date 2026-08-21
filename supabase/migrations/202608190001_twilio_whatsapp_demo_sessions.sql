-- Replace the Meta/browser simulator transport with isolated Twilio Sandbox sessions.

create table public.whatsapp_demo_sessions (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  base_client_id uuid not null references public.clients(id) on delete cascade,
  base_application_id uuid not null references public.applications(id) on delete cascade,
  session_application_id uuid null references public.applications(id) on delete set null,
  created_by_user_id uuid not null references auth.users(id) on delete restrict,
  start_token_hash text null,
  dashboard_access_token_hash text not null,
  judge_phone_hash text null,
  judge_phone_encrypted text null,
  judge_phone_last_four text null,
  twilio_wa_id_hash text null,
  status text not null check (status in (
    'waiting_for_start', 'active', 'expired', 'cancelled', 'completed'
  )),
  current_step text null,
  token_expires_at timestamptz not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default timezone('utc', now()),
  connected_at timestamptz null,
  last_activity_at timestamptz null,
  completed_at timestamptz null,
  cancelled_at timestamptz null,
  anonymized_at timestamptz null,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default timezone('utc', now())
);

create unique index whatsapp_demo_sessions_start_token_hash_uidx
  on public.whatsapp_demo_sessions(start_token_hash)
  where start_token_hash is not null;
create index whatsapp_demo_sessions_phone_hash_idx
  on public.whatsapp_demo_sessions(judge_phone_hash)
  where judge_phone_hash is not null;
create index whatsapp_demo_sessions_expiry_idx
  on public.whatsapp_demo_sessions(status, expires_at);
create index whatsapp_demo_sessions_base_application_idx
  on public.whatsapp_demo_sessions(base_application_id, created_at desc);

create trigger whatsapp_demo_sessions_set_updated_at
before update on public.whatsapp_demo_sessions
for each row execute function public.set_updated_at();

alter table public.applications
  add column demo_session_id uuid null
  references public.whatsapp_demo_sessions(id) on delete restrict;

alter table public.applications
  drop constraint applications_client_id_period_start_period_end_key;

create unique index applications_normal_period_uidx
  on public.applications(client_id, period_start, period_end)
  where demo_session_id is null;
create index applications_demo_session_id_idx
  on public.applications(demo_session_id)
  where demo_session_id is not null;

alter table public.whatsapp_messages
  rename column external_message_id to provider_message_id;
alter table public.whatsapp_messages
  add column demo_session_id uuid null
    references public.whatsapp_demo_sessions(id) on delete cascade,
  add column error_code text null,
  add column error_message text null,
  add column sender_phone_encrypted text null,
  add column recipient_phone_encrypted text null,
  add column sender_phone_last_four text null,
  add column recipient_phone_last_four text null,
  add column queued_at timestamptz null,
  add column sent_at timestamptz null,
  add column delivered_at timestamptz null,
  add column read_at timestamptz null,
  add column failed_at timestamptz null;

delete from public.whatsapp_messages where provider not in ('twilio', 'mock');
alter table public.whatsapp_messages drop constraint whatsapp_messages_provider_check;
alter table public.whatsapp_messages
  add constraint whatsapp_messages_provider_check check (provider in ('twilio', 'mock'));
alter table public.whatsapp_messages drop constraint whatsapp_messages_message_type_check;
alter table public.whatsapp_messages
  add constraint whatsapp_messages_message_type_check check (
    message_type in ('text', 'media', 'status', 'template', 'document', 'image')
  );
alter table public.whatsapp_messages drop constraint whatsapp_messages_delivery_status_check;
alter table public.whatsapp_messages
  add constraint whatsapp_messages_delivery_status_check check (
    delivery_status in (
      'queued', 'sending', 'sent', 'delivered', 'read', 'received', 'failed', 'undelivered'
    )
  );
alter table public.whatsapp_messages drop column sender_phone;
alter table public.whatsapp_messages drop column recipient_phone;

create unique index whatsapp_messages_provider_message_id_uidx
  on public.whatsapp_messages(provider, provider_message_id)
  where provider_message_id is not null;
create index whatsapp_messages_demo_session_id_idx
  on public.whatsapp_messages(demo_session_id, created_at);

alter table public.audit_events
  add column demo_session_id uuid null
  references public.whatsapp_demo_sessions(id) on delete set null;
create index audit_events_demo_session_id_idx
  on public.audit_events(demo_session_id, created_at desc);

delete from public.integration_settings where provider not in ('twilio', 'mock');
alter table public.integration_settings drop column phone_number_id;
alter table public.integration_settings drop column waba_id;
alter table public.integration_settings drop column test_recipient;
alter table public.integration_settings drop constraint integration_settings_provider_check;
alter table public.integration_settings
  add constraint integration_settings_provider_check check (provider in ('twilio', 'mock'));

delete from public.documents where source in ('mock_whatsapp', 'meta_whatsapp');
alter table public.documents drop constraint documents_source_check;
alter table public.documents
  add constraint documents_source_check check (source in (
    'dashboard', 'secure_link', 'seed', 'filing_evidence', 'knowledge'
  ));

alter table public.whatsapp_demo_sessions enable row level security;

create or replace function public.create_whatsapp_demo_session(
  p_firm_id uuid,
  p_base_application_id uuid,
  p_created_by_user_id uuid,
  p_start_token_hash text,
  p_dashboard_access_token_hash text,
  p_token_expires_at timestamptz,
  p_expires_at timestamptz
)
returns table(session_id uuid, session_application_id uuid, base_client_id uuid)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_base public.applications%rowtype;
  v_session_id uuid := gen_random_uuid();
  v_application_id uuid := gen_random_uuid();
begin
  select * into v_base
  from public.applications
  where id = p_base_application_id
    and firm_id = p_firm_id
    and demo_session_id is null
  for share;

  if not found then
    raise exception 'Base GST application not found';
  end if;

  insert into public.whatsapp_demo_sessions (
    id, firm_id, base_client_id, base_application_id, created_by_user_id,
    start_token_hash, dashboard_access_token_hash, status, current_step,
    token_expires_at, expires_at
  ) values (
    v_session_id, v_base.firm_id, v_base.client_id, v_base.id, p_created_by_user_id,
    p_start_token_hash, p_dashboard_access_token_hash, 'waiting_for_start',
    'scan_start_qr', p_token_expires_at, p_expires_at
  );

  insert into public.applications (
    id, firm_id, client_id, application_type, financial_year, period_label,
    period_start, period_end, filing_frequency, due_date, status,
    assigned_preparer_id, reviewer_id, filing_date, arn,
    filed_return_document_id, payment_challan_document_id, final_notes,
    demo_session_id
  ) values (
    v_application_id, v_base.firm_id, v_base.client_id, v_base.application_type,
    v_base.financial_year, v_base.period_label, v_base.period_start, v_base.period_end,
    v_base.filing_frequency, v_base.due_date, 'not_started',
    v_base.assigned_preparer_id, v_base.reviewer_id, null, null, null, null, null,
    v_session_id
  );

  insert into public.document_requirements (
    application_id, requirement_type, label, required, status
  )
  select v_application_id, requirement_type, label, required, 'missing'
  from public.document_requirements
  where application_id = v_base.id;

  update public.whatsapp_demo_sessions
  set session_application_id = v_application_id
  where id = v_session_id;

  return query select v_session_id, v_application_id, v_base.client_id;
end;
$$;

create or replace function public.bind_whatsapp_demo_session(
  p_start_token_hash text,
  p_judge_phone_hash text,
  p_judge_phone_encrypted text,
  p_judge_phone_last_four text,
  p_twilio_wa_id_hash text,
  p_now timestamptz
)
returns setof public.whatsapp_demo_sessions
language plpgsql
security definer
set search_path = public
as $$
declare
  v_session public.whatsapp_demo_sessions%rowtype;
begin
  select * into v_session
  from public.whatsapp_demo_sessions
  where start_token_hash = p_start_token_hash
    and status = 'waiting_for_start'
    and token_expires_at > p_now
    and expires_at > p_now
  for update;

  if not found then
    return;
  end if;

  update public.whatsapp_demo_sessions
  set status = 'cancelled',
      cancelled_at = p_now,
      last_activity_at = p_now
  where id <> v_session.id
    and judge_phone_hash = p_judge_phone_hash
    and status = 'active';

  return query
  update public.whatsapp_demo_sessions
  set start_token_hash = null,
      judge_phone_hash = p_judge_phone_hash,
      judge_phone_encrypted = p_judge_phone_encrypted,
      judge_phone_last_four = p_judge_phone_last_four,
      twilio_wa_id_hash = p_twilio_wa_id_hash,
      status = 'active',
      current_step = 'checklist_sent',
      connected_at = p_now,
      last_activity_at = p_now
  where id = v_session.id
  returning *;
end;
$$;

revoke execute on function public.create_whatsapp_demo_session(
  uuid, uuid, uuid, text, text, timestamptz, timestamptz
) from public, anon, authenticated;
revoke execute on function public.bind_whatsapp_demo_session(
  text, text, text, text, text, timestamptz
) from public, anon, authenticated;
grant execute on function public.create_whatsapp_demo_session(
  uuid, uuid, uuid, text, text, timestamptz, timestamptz
) to service_role;
grant execute on function public.bind_whatsapp_demo_session(
  text, text, text, text, text, timestamptz
) to service_role;
