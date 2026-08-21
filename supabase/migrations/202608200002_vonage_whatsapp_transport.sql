-- Replace the active Twilio transport with the Vonage Messages API Sandbox.
-- Historical Twilio message rows are retained for audit continuity.

alter table public.whatsapp_demo_sessions
  rename column twilio_wa_id_hash to provider_user_id_hash;

alter table public.whatsapp_messages
  drop constraint whatsapp_messages_provider_check;
alter table public.whatsapp_messages
  add constraint whatsapp_messages_provider_check
  check (provider in ('twilio', 'vonage', 'mock'));

alter table public.integration_settings
  drop constraint integration_settings_provider_check;
alter table public.integration_settings
  add constraint integration_settings_provider_check
  check (provider in ('twilio', 'vonage', 'mock'));

drop function public.bind_whatsapp_demo_session(
  text, text, text, text, text, timestamptz
);

create function public.bind_whatsapp_demo_session(
  p_start_token_hash text,
  p_judge_phone_hash text,
  p_judge_phone_encrypted text,
  p_judge_phone_last_four text,
  p_provider_user_id_hash text,
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
      provider_user_id_hash = p_provider_user_id_hash,
      status = 'active',
      current_step = 'checklist_sent',
      connected_at = p_now,
      last_activity_at = p_now
  where id = v_session.id
  returning *;
end;
$$;

revoke execute on function public.bind_whatsapp_demo_session(
  text, text, text, text, text, timestamptz
) from public, anon, authenticated;
grant execute on function public.bind_whatsapp_demo_session(
  text, text, text, text, text, timestamptz
) to service_role;
