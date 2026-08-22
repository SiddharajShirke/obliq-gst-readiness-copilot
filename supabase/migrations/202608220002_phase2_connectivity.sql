-- Connect human-approved document requests/reminders to retained Vonage demo sessions.

alter table public.reminders
  add column base_application_id uuid references public.applications(id) on delete cascade,
  add column demo_session_id uuid references public.whatsapp_demo_sessions(id) on delete set null,
  add column upload_link_id uuid references public.upload_links(id) on delete set null,
  add column provider_message_id text;

update public.reminders
set base_application_id = application_id
where base_application_id is null;

alter table public.reminders
  alter column base_application_id set not null;

create index reminders_base_application_created_idx
  on public.reminders(base_application_id, created_at desc);

create index reminders_demo_session_created_idx
  on public.reminders(demo_session_id, created_at desc)
  where demo_session_id is not null;

create unique index reminders_provider_message_id_uidx
  on public.reminders(provider, provider_message_id)
  where provider_message_id is not null;
