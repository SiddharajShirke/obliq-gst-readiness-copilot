-- Persistent, user-scoped Guided Demo history over existing cloned sessions.

create table if not exists public.guided_demo_runs (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  demo_client_id uuid not null references public.clients(id) on delete cascade,
  base_application_id uuid not null references public.applications(id) on delete cascade,
  demo_session_id uuid not null unique references public.whatsapp_demo_sessions(id) on delete cascade,
  session_application_id uuid not null unique references public.applications(id) on delete cascade,
  run_number integer not null check (run_number > 0),
  name text not null,
  status text not null default 'active'
    check (status in ('active', 'completed', 'cancelled')),
  started_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz,
  cancelled_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (user_id, run_number)
);

create index if not exists guided_demo_runs_user_history_idx
  on public.guided_demo_runs(firm_id, user_id, run_number desc);

alter table public.guided_demo_runs enable row level security;
revoke all on public.guided_demo_runs from anon, authenticated;
grant select, insert, update, delete on public.guided_demo_runs to service_role;

create trigger guided_demo_runs_set_updated_at
before update on public.guided_demo_runs
for each row execute function public.set_updated_at();
