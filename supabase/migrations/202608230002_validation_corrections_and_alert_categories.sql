begin;

create table if not exists public.validation_correction_proposals (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  proposal_type text not null check (proposal_type in ('manual', 'ai')),
  status text not null default 'proposed' check (status in ('proposed', 'applied', 'rejected')),
  record_ids jsonb not null default '[]'::jsonb,
  changes jsonb not null default '[]'::jsonb,
  rationale text,
  provider text,
  model text,
  proposed_by uuid references auth.users(id) on delete set null,
  decided_by uuid references auth.users(id) on delete set null,
  proposed_at timestamptz not null default now(),
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists validation_correction_proposals_application_idx
  on public.validation_correction_proposals(application_id, created_at desc);

alter table public.validation_correction_proposals enable row level security;
revoke all on public.validation_correction_proposals from anon, authenticated;
grant select, insert, update, delete on public.validation_correction_proposals to service_role;

alter table public.alerts add column if not exists workflow_area text;
alter table public.alerts add column if not exists alert_category text;
alter table public.alerts add column if not exists validation_finding_id uuid
  references public.validation_findings(id) on delete set null;
create unique index if not exists alerts_validation_finding_unique
  on public.alerts(validation_finding_id) where validation_finding_id is not null;

commit;
