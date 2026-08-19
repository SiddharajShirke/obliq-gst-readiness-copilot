-- Tenant-aware helper functions and policies.
create or replace function public.user_has_firm_access(target_firm_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.firm_members fm
    where fm.firm_id = target_firm_id and fm.user_id = auth.uid()
  );
$$;

create or replace function public.user_has_firm_role(target_firm_id uuid, allowed_roles text[])
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.firm_members fm
    where fm.firm_id = target_firm_id
      and fm.user_id = auth.uid()
      and fm.role = any(allowed_roles)
  );
$$;

alter table public.profiles enable row level security;
alter table public.firms enable row level security;
alter table public.firm_members enable row level security;
alter table public.clients enable row level security;
alter table public.applications enable row level security;
alter table public.document_requirements enable row level security;
alter table public.upload_links enable row level security;
alter table public.documents enable row level security;
alter table public.document_extractions enable row level security;
alter table public.invoice_records enable row level security;
alter table public.validation_findings enable row level security;
alter table public.reconciliation_runs enable row level security;
alter table public.reconciliation_items enable row level security;
alter table public.reminders enable row level security;
alter table public.whatsapp_messages enable row level security;
alter table public.integration_settings enable row level security;
alter table public.knowledge_sources enable row level security;
alter table public.knowledge_chunks enable row level security;
alter table public.alerts enable row level security;
alter table public.audit_events enable row level security;
alter table public.workflow_runs enable row level security;

create policy profiles_select_self on public.profiles for select using (id = auth.uid());
create policy profiles_update_self on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());

create policy firms_select_members on public.firms for select using (public.user_has_firm_access(id));
create policy firms_update_admin on public.firms for update
using (public.user_has_firm_role(id, array['firm_admin']))
with check (public.user_has_firm_role(id, array['firm_admin']));

create policy firm_members_select_members on public.firm_members for select
using (public.user_has_firm_access(firm_id));
create policy firm_members_manage_admin on public.firm_members for all
using (public.user_has_firm_role(firm_id, array['firm_admin']))
with check (public.user_has_firm_role(firm_id, array['firm_admin']));

create policy clients_access on public.clients for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy applications_access on public.applications for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy document_requirements_access on public.document_requirements for all
using (exists (
  select 1 from public.applications a
  where a.id = application_id and public.user_has_firm_access(a.firm_id)
))
with check (exists (
  select 1 from public.applications a
  where a.id = application_id and public.user_has_firm_access(a.firm_id)
));

create policy upload_links_access on public.upload_links for all
using (exists (
  select 1 from public.applications a
  where a.id = application_id and public.user_has_firm_access(a.firm_id)
))
with check (exists (
  select 1 from public.applications a
  where a.id = application_id and public.user_has_firm_access(a.firm_id)
));

create policy documents_access on public.documents for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy document_extractions_access on public.document_extractions for all
using (exists (
  select 1 from public.documents d
  where d.id = document_id and public.user_has_firm_access(d.firm_id)
))
with check (exists (
  select 1 from public.documents d
  where d.id = document_id and public.user_has_firm_access(d.firm_id)
));

create policy invoice_records_access on public.invoice_records for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy validation_findings_access on public.validation_findings for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy reconciliation_runs_access on public.reconciliation_runs for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy reconciliation_items_access on public.reconciliation_items for all
using (exists (
  select 1 from public.reconciliation_runs r
  where r.id = reconciliation_run_id and public.user_has_firm_access(r.firm_id)
))
with check (exists (
  select 1 from public.reconciliation_runs r
  where r.id = reconciliation_run_id and public.user_has_firm_access(r.firm_id)
));

create policy reminders_access on public.reminders for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy whatsapp_messages_access on public.whatsapp_messages for all
using (firm_id is not null and public.user_has_firm_access(firm_id))
with check (firm_id is not null and public.user_has_firm_access(firm_id));

create policy integration_settings_select_admin on public.integration_settings for select
using (public.user_has_firm_access(firm_id));
create policy integration_settings_manage_admin on public.integration_settings for all
using (public.user_has_firm_role(firm_id, array['firm_admin']))
with check (public.user_has_firm_role(firm_id, array['firm_admin']));

create policy knowledge_sources_read on public.knowledge_sources for select
using (firm_id is null or public.user_has_firm_access(firm_id));
create policy knowledge_sources_manage on public.knowledge_sources for all
using (firm_id is not null and public.user_has_firm_role(firm_id, array['firm_admin']))
with check (firm_id is not null and public.user_has_firm_role(firm_id, array['firm_admin']));

create policy knowledge_chunks_read on public.knowledge_chunks for select
using (firm_id is null or public.user_has_firm_access(firm_id));
create policy knowledge_chunks_manage on public.knowledge_chunks for all
using (firm_id is not null and public.user_has_firm_role(firm_id, array['firm_admin']))
with check (firm_id is not null and public.user_has_firm_role(firm_id, array['firm_admin']));

create policy alerts_access on public.alerts for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

create policy audit_events_read on public.audit_events for select
using (public.user_has_firm_access(firm_id));
create policy audit_events_insert on public.audit_events for insert
with check (public.user_has_firm_access(firm_id));

create policy workflow_runs_access on public.workflow_runs for all
using (public.user_has_firm_access(firm_id))
with check (public.user_has_firm_access(firm_id));

insert into storage.buckets (id, name, public, file_size_limit)
values
  ('gst-documents', 'gst-documents', false, 20971520),
  ('knowledge-documents', 'knowledge-documents', false, 20971520),
  ('exports', 'exports', false, 20971520)
on conflict (id) do update set public = excluded.public, file_size_limit = excluded.file_size_limit;

create policy storage_read_firm_files on storage.objects for select to authenticated
using (
  bucket_id in ('gst-documents', 'knowledge-documents', 'exports')
  and public.user_has_firm_access(((storage.foldername(name))[1])::uuid)
);

create policy storage_insert_firm_files on storage.objects for insert to authenticated
with check (
  bucket_id in ('gst-documents', 'knowledge-documents', 'exports')
  and public.user_has_firm_access(((storage.foldername(name))[1])::uuid)
);

create policy storage_update_firm_files on storage.objects for update to authenticated
using (
  bucket_id in ('gst-documents', 'knowledge-documents', 'exports')
  and public.user_has_firm_access(((storage.foldername(name))[1])::uuid)
)
with check (
  bucket_id in ('gst-documents', 'knowledge-documents', 'exports')
  and public.user_has_firm_access(((storage.foldername(name))[1])::uuid)
);

create policy storage_delete_firm_files on storage.objects for delete to authenticated
using (
  bucket_id in ('gst-documents', 'knowledge-documents', 'exports')
  and public.user_has_firm_access(((storage.foldername(name))[1])::uuid)
);
