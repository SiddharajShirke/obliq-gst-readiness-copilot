-- Revised Phase 3: six-category intake, normalized GST records, exact
-- reconciliation evidence, and explicitly raised AI-assisted alerts.

alter table public.document_requirements
  drop constraint if exists document_requirements_requirement_type_check;

update public.document_requirements
set requirement_type = 'sales_invoices',
    label = 'Sales Invoices'
where requirement_type = 'sales_invoice';

update public.document_requirements
set requirement_type = 'purchase_expense_invoices',
    label = 'Purchase & Expense Invoices'
where requirement_type = 'purchase_invoice';

-- GSTR-2B is a government-side reconciliation input, never client progress.
delete from public.document_requirements
where requirement_type = 'gstr2b';

insert into public.document_requirements (
  application_id, requirement_type, label, required, status
)
select a.id, required.requirement_type, required.label, true, 'missing'
from public.applications a
cross join (
  values
    ('sales_register', 'Sales Register'),
    ('purchase_register', 'Purchase Register'),
    ('sales_invoices', 'Sales Invoices'),
    ('purchase_expense_invoices', 'Purchase & Expense Invoices'),
    ('credit_debit_notes', 'Credit & Debit Notes'),
    ('gst_special_transactions', 'GST Special Transactions')
) as required(requirement_type, label)
where not exists (
  select 1 from public.document_requirements existing
  where existing.application_id = a.id
    and existing.requirement_type = required.requirement_type
);

alter table public.document_requirements
  add constraint document_requirements_requirement_type_check check (
    requirement_type in (
      'sales_register', 'purchase_register', 'sales_invoices',
      'purchase_expense_invoices', 'credit_debit_notes',
      'gst_special_transactions'
    )
  );

alter table public.documents
  drop constraint if exists documents_document_type_check;

update public.documents set document_type = 'sales_invoices'
where document_type = 'sales_invoice';
update public.documents set document_type = 'purchase_expense_invoices'
where document_type = 'purchase_invoice';
update public.documents set processing_status = 'excluded_reference'
where document_type = 'developer_ground_truth';

alter table public.documents
  add column if not exists classification_source text,
  add column if not exists processing_error text;

alter table public.documents
  add constraint documents_document_type_check check (
    document_type is null or document_type in (
      'sales_register', 'purchase_register', 'sales_invoices',
      'purchase_expense_invoices', 'credit_debit_notes',
      'gst_special_transactions', 'gstr2b', 'developer_ground_truth',
      'filed_return', 'payment_challan', 'unknown'
    )
  );

alter table public.documents
  drop constraint if exists documents_processing_status_check;
alter table public.documents
  add constraint documents_processing_status_check check (processing_status in (
    'uploaded', 'queued', 'uploading', 'awaiting_processing', 'upload_failed',
    'processing', 'needs_assignment', 'needs_review', 'ready_for_review',
    'processing_failed', 'excluded_reference', 'processed', 'failed',
    'approved', 'rejected'
  ));

alter table public.document_extractions
  add column if not exists task_type text,
  add column if not exists started_at timestamptz,
  add column if not exists completed_at timestamptz,
  add column if not exists duration_ms integer,
  add column if not exists fallback_reason text;

alter table public.invoice_records
  add column if not exists tax_period text,
  add column if not exists document_type text,
  add column if not exists gst_rate numeric(7,4),
  add column if not exists total_tax numeric(18,2),
  add column if not exists transaction_type text,
  add column if not exists itc_status text,
  add column if not exists rcm_flag boolean,
  add column if not exists original_document_reference text,
  add column if not exists source_page integer,
  add column if not exists source_row integer,
  add column if not exists source_data jsonb not null default '{}'::jsonb;

alter table public.reconciliation_items
  drop constraint if exists reconciliation_items_match_status_check;

update public.reconciliation_items
set match_status = case match_status
  when 'matched' then 'exact_match'
  when 'purchase_only' then 'books_only'
  when 'amount_mismatch' then 'value_mismatch'
  when 'date_mismatch' then 'value_mismatch'
  when 'possible_duplicate' then 'duplicate'
  else match_status
end;

alter table public.reconciliation_items
  add constraint reconciliation_items_match_status_check check (match_status in (
    'exact_match', 'value_mismatch', 'invoice_number_mismatch',
    'books_only', 'gstr2b_only', 'ambiguous_match', 'duplicate'
  )),
  add column if not exists evidence jsonb not null default '{}'::jsonb,
  add column if not exists special_flags jsonb not null default '[]'::jsonb,
  add column if not exists review_status text not null default 'pending'
    check (review_status in ('pending', 'reviewed')),
  add column if not exists reviewed_by uuid references auth.users(id) on delete set null,
  add column if not exists reviewed_at timestamptz;

alter table public.reconciliation_runs
  add column if not exists gstr2b_document_id uuid references public.documents(id) on delete set null;

alter table public.alerts
  add column if not exists reconciliation_item_id uuid references public.reconciliation_items(id) on delete set null,
  add column if not exists evidence jsonb not null default '{}'::jsonb,
  add column if not exists ai_explanation jsonb,
  add column if not exists ai_explanation_status text not null default 'not_requested'
    check (ai_explanation_status in ('not_requested', 'pending', 'generated', 'failed')),
  add column if not exists ai_explanation_provider text,
  add column if not exists ai_explanation_model text,
  add column if not exists ai_explanation_generated_at timestamptz;

create unique index if not exists alerts_reconciliation_item_uidx
  on public.alerts(reconciliation_item_id)
  where reconciliation_item_id is not null;
create index if not exists documents_phase3_type_idx
  on public.documents(application_id, document_type, created_at desc);

-- New categories make previously complete applications partial until all six
-- client requirements are received. This applies equally to retained clones.
update public.applications a
set status = case
  when not exists (
    select 1 from public.document_requirements r
    where r.application_id = a.id and r.required and r.status <> 'received'
  ) then 'documents_complete'
  when exists (
    select 1 from public.document_requirements r
    where r.application_id = a.id and r.required and r.status = 'received'
  ) then 'partially_received'
  when a.status = 'not_started' then 'not_started'
  else 'documents_requested'
end;
