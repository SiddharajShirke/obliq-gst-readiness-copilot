begin;

create table if not exists public.assistant_action_proposals (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  demo_session_id uuid references public.whatsapp_demo_sessions(id) on delete cascade,
  conversation_id uuid not null,
  action_type text not null check (action_type in (
    'approve_extraction',
    'reject_extraction',
    'edit_and_approve_extraction',
    'apply_validation_correction',
    'mark_validation_reviewed',
    'mark_reconciliation_reviewed',
    'raise_reconciliation_alert',
    'draft_reminder'
  )),
  payload jsonb not null default '{}'::jsonb,
  preview jsonb not null default '{}'::jsonb,
  evidence_fingerprint text not null,
  status text not null default 'pending_confirmation' check (status in (
    'pending_confirmation', 'confirmed', 'executed', 'cancelled', 'expired', 'failed'
  )),
  expires_at timestamptz not null,
  confirmed_at timestamptz,
  executed_at timestamptz,
  result jsonb,
  error_message text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists assistant_action_proposals_scope_idx
  on public.assistant_action_proposals(
    user_id, application_id, conversation_id, status, created_at desc
  );

create trigger assistant_action_proposals_set_updated_at
before update on public.assistant_action_proposals
for each row execute function public.set_updated_at();

alter table public.assistant_action_proposals enable row level security;
revoke all on public.assistant_action_proposals from anon, authenticated;
grant select, insert, update on public.assistant_action_proposals to authenticated;
grant select, insert, update, delete on public.assistant_action_proposals to service_role;

create policy assistant_action_proposals_access
on public.assistant_action_proposals for all
using (
  user_id = auth.uid()
  and public.user_has_firm_access(firm_id)
  and exists (
    select 1 from public.applications a
    where a.id = application_id and a.firm_id = firm_id
  )
)
with check (
  user_id = auth.uid()
  and public.user_has_firm_access(firm_id)
  and exists (
    select 1 from public.applications a
    where a.id = application_id and a.firm_id = firm_id
  )
);

commit;
