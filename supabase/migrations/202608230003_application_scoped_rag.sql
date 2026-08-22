begin;

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  demo_session_id uuid references public.whatsapp_demo_sessions(id) on delete cascade,
  document_id uuid not null references public.documents(id) on delete cascade,
  document_type text not null check (document_type <> 'developer_ground_truth'),
  chunk_index integer not null check (chunk_index >= 0),
  content text not null check (length(btrim(content)) > 0),
  page_number integer,
  sheet_name text,
  row_start integer,
  row_end integer,
  section text,
  metadata jsonb not null default '{}'::jsonb,
  checksum text not null,
  embedding extensions.vector(384) not null,
  embedding_model text not null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (document_id, checksum, chunk_index)
);

create index if not exists document_chunks_application_idx
  on public.document_chunks(application_id, document_id, chunk_index);
create index if not exists document_chunks_embedding_idx
  on public.document_chunks using hnsw (embedding extensions.vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create trigger document_chunks_set_updated_at before update on public.document_chunks
for each row execute function public.set_updated_at();

alter table public.document_chunks enable row level security;
revoke all on public.document_chunks from anon, authenticated;
grant select on public.document_chunks to authenticated;
grant select, insert, update, delete on public.document_chunks to service_role;

create policy document_chunks_read on public.document_chunks for select
using (
  public.user_has_firm_access(firm_id)
  and exists (
    select 1 from public.applications a
    where a.id = application_id and a.firm_id = firm_id
  )
);

create table if not exists public.assistant_messages (
  id uuid primary key default gen_random_uuid(),
  firm_id uuid not null references public.firms(id) on delete cascade,
  application_id uuid not null references public.applications(id) on delete cascade,
  demo_session_id uuid references public.whatsapp_demo_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  conversation_id uuid not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  citations jsonb not null default '[]'::jsonb,
  source_types jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists assistant_messages_scope_idx
  on public.assistant_messages(user_id, application_id, conversation_id, created_at);

alter table public.assistant_messages enable row level security;
revoke all on public.assistant_messages from anon, authenticated;
grant select, insert on public.assistant_messages to authenticated;
grant select, insert, update, delete on public.assistant_messages to service_role;

create policy assistant_messages_access on public.assistant_messages for all
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

create or replace function public.match_application_document_chunks(
  query_embedding extensions.vector(384),
  user_firm_id uuid,
  target_application_id uuid,
  match_count integer default 8,
  min_similarity double precision default 0.35
)
returns table (
  chunk_id uuid,
  document_id uuid,
  application_id uuid,
  document_type text,
  content text,
  metadata jsonb,
  page_number integer,
  sheet_name text,
  row_start integer,
  row_end integer,
  section text,
  similarity double precision
)
language sql
stable
security definer
set search_path = public, extensions
as $$
  select
    dc.id,
    dc.document_id,
    dc.application_id,
    dc.document_type,
    dc.content,
    dc.metadata,
    dc.page_number,
    dc.sheet_name,
    dc.row_start,
    dc.row_end,
    dc.section,
    1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  join public.applications a on a.id = dc.application_id
  where (auth.role() = 'service_role' or public.user_has_firm_access(user_firm_id))
    and a.firm_id = user_firm_id
    and dc.firm_id = user_firm_id
    and dc.application_id = target_application_id
    and dc.document_type <> 'developer_ground_truth'
    and 1 - (dc.embedding <=> query_embedding) >= min_similarity
  order by dc.embedding <=> query_embedding
  limit greatest(1, least(match_count, 50));
$$;

grant execute on function public.match_application_document_chunks to authenticated;
grant execute on function public.match_application_document_chunks to service_role;

commit;
