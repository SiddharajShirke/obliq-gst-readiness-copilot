-- Complete the CA review metadata expected by invoice-record review endpoints.
alter table public.invoice_records
  add column if not exists reviewed_by uuid
    references auth.users(id) on delete set null,
  add column if not exists reviewed_at timestamptz;

comment on column public.invoice_records.reviewed_by is
  'Authenticated CA or reviewer who last reviewed the normalized record.';
comment on column public.invoice_records.reviewed_at is
  'UTC timestamp of the latest CA review decision.';

notify pgrst, 'reload schema';
