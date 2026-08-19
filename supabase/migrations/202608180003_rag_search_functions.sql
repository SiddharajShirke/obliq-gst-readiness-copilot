-- pgvector and lexical search RPCs used by the FastAPI RAG layer.
create or replace function public.match_knowledge_chunks(
  query_embedding extensions.vector(384),
  user_firm_id uuid,
  filter_source_type text default null,
  match_count integer default 12,
  min_similarity double precision default 0.45
)
returns table (
  chunk_id uuid,
  source_id uuid,
  content text,
  metadata jsonb,
  similarity double precision
)
language sql
stable
security definer
set search_path = public, extensions
as $$
  select
    kc.id as chunk_id,
    kc.source_id,
    kc.content,
    kc.metadata,
    1 - (kc.embedding <=> query_embedding) as similarity
  from public.knowledge_chunks kc
  join public.knowledge_sources ks on ks.id = kc.source_id
  where (auth.role() = 'service_role' or public.user_has_firm_access(user_firm_id))
    and (kc.firm_id is null or kc.firm_id = user_firm_id)
    and (filter_source_type is null or ks.source_type = filter_source_type)
    and (ks.effective_from is null or ks.effective_from <= current_date)
    and (ks.effective_to is null or ks.effective_to >= current_date)
    and 1 - (kc.embedding <=> query_embedding) >= min_similarity
  order by kc.embedding <=> query_embedding
  limit greatest(1, least(match_count, 50));
$$;

create or replace function public.search_knowledge_chunks_lexical(
  query_text text,
  user_firm_id uuid,
  filter_source_type text default null,
  match_count integer default 12
)
returns table (
  chunk_id uuid,
  source_id uuid,
  content text,
  metadata jsonb,
  rank real
)
language sql
stable
security definer
set search_path = public
as $$
  select
    kc.id as chunk_id,
    kc.source_id,
    kc.content,
    kc.metadata,
    ts_rank_cd(kc.search_vector, websearch_to_tsquery('english', query_text)) as rank
  from public.knowledge_chunks kc
  join public.knowledge_sources ks on ks.id = kc.source_id
  where (auth.role() = 'service_role' or public.user_has_firm_access(user_firm_id))
    and (kc.firm_id is null or kc.firm_id = user_firm_id)
    and (filter_source_type is null or ks.source_type = filter_source_type)
    and kc.search_vector @@ websearch_to_tsquery('english', query_text)
    and (ks.effective_from is null or ks.effective_from <= current_date)
    and (ks.effective_to is null or ks.effective_to >= current_date)
  order by rank desc
  limit greatest(1, least(match_count, 50));
$$;

grant execute on function public.match_knowledge_chunks to authenticated;
grant execute on function public.search_knowledge_chunks_lexical to authenticated;
