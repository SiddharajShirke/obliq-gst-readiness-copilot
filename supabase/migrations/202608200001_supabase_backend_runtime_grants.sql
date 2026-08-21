-- Permit the backend-only Supabase service role to use the public schema.
-- RLS remains enabled for browser roles; no anon/authenticated grants are added.

grant usage on schema public to service_role;
grant all privileges on all tables in schema public to service_role;
grant all privileges on all sequences in schema public to service_role;
grant execute on all routines in schema public to service_role;

alter default privileges in schema public
  grant all privileges on tables to service_role;
alter default privileges in schema public
  grant all privileges on sequences to service_role;
alter default privileges in schema public
  grant execute on routines to service_role;
