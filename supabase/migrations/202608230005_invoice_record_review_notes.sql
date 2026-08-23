-- Preserve CA review notes on normalized invoice records.
-- Phase 3 review endpoints already persist this field, but the original
-- invoice_records migration omitted the nullable column.
alter table public.invoice_records
  add column if not exists review_notes text;

comment on column public.invoice_records.review_notes is
  'Optional CA notes recorded while approving, editing, or rejecting extraction records.';

notify pgrst, 'reload schema';
