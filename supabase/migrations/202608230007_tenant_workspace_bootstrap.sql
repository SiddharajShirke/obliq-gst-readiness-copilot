-- Idempotent first-login tenant workspace and one Guided Demo template.

update public.clients
set demo_scenario = 'guided_demo_template'
where id = '20000000-0000-0000-0000-000000000001'::uuid
  and demo_scenario is distinct from 'guided_demo_template';

create unique index if not exists clients_one_guided_demo_template_per_firm
  on public.clients(firm_id)
  where demo_scenario = 'guided_demo_template';

create or replace function public.bootstrap_user_workspace(
  p_user_id uuid,
  p_email text,
  p_full_name text
)
returns table(firm_id uuid, demo_client_id uuid, demo_application_id uuid)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_firm_id uuid;
  v_client_id uuid;
  v_application_id uuid;
  v_workspace_name text;
begin
  if not exists (select 1 from auth.users where id = p_user_id) then
    raise exception 'Authenticated user not found';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));

  insert into public.profiles (id, full_name, email)
  values (p_user_id, coalesce(nullif(trim(p_full_name), ''), ''), coalesce(p_email, ''))
  on conflict (id) do update
    set full_name = case
          when excluded.full_name <> '' then excluded.full_name
          else public.profiles.full_name
        end,
        email = excluded.email;

  select fm.firm_id into v_firm_id
  from public.firm_members fm
  where fm.user_id = p_user_id
  order by fm.created_at
  limit 1
  for update;

  if v_firm_id is null then
    v_workspace_name := coalesce(
      nullif(trim(p_full_name), ''),
      nullif(split_part(coalesce(p_email, ''), '@', 1), ''),
      'CA'
    ) || ' GST Workspace';
    insert into public.firms (name, slug)
    values (
      v_workspace_name,
      'workspace-' || left(replace(p_user_id::text, '-', ''), 12)
    )
    returning id into v_firm_id;

    insert into public.firm_members (firm_id, user_id, role)
    values (v_firm_id, p_user_id, 'firm_admin');
  end if;

  select c.id into v_client_id
  from public.clients c
  where c.firm_id = v_firm_id
    and c.demo_scenario = 'guided_demo_template'
  limit 1
  for update;

  if v_client_id is null then
    select c.id into v_client_id
    from public.clients c
    where c.firm_id = v_firm_id
      and c.gstin = '27RAJTR1234A1Z5'
    limit 1
    for update;
  end if;

  if v_client_id is null then
    insert into public.clients (
      firm_id, business_name, legal_name, gstin, state, business_type,
      filing_frequency, contact_name, whatsapp_phone, preferred_language,
      whatsapp_consent, assigned_preparer_id, reviewer_id, demo_scenario
    ) values (
      v_firm_id, 'Raj Traders', 'Raj Traders', '27RAJTR1234A1Z5',
      'Maharashtra', 'Retail', 'monthly', 'Raj Malhotra', '+919810000001',
      'English', true, p_user_id, p_user_id, 'guided_demo_template'
    ) returning id into v_client_id;
  else
    update public.clients
    set demo_scenario = 'guided_demo_template'
    where id = v_client_id;
  end if;

  select a.id into v_application_id
  from public.applications a
  where a.client_id = v_client_id
    and a.demo_session_id is null
  order by a.created_at
  limit 1
  for update;

  if v_application_id is null then
    insert into public.applications (
      firm_id, client_id, application_type, financial_year, period_label,
      period_start, period_end, filing_frequency, due_date, status,
      assigned_preparer_id, reviewer_id
    ) values (
      v_firm_id, v_client_id, 'gst_readiness', '2026-27', 'April 2026',
      '2026-04-01', '2026-04-30', 'monthly', '2026-05-20', 'not_started',
      p_user_id, p_user_id
    ) returning id into v_application_id;
  end if;

  insert into public.document_requirements (
    application_id, requirement_type, label, required, status
  )
  select v_application_id, values_table.requirement_type,
    values_table.label, true, 'missing'
  from (
    values
      ('sales_register', 'Sales Register'),
      ('purchase_register', 'Purchase Register'),
      ('sales_invoices', 'Sales Invoices'),
      ('purchase_expense_invoices', 'Purchase & Expense Invoices'),
      ('credit_debit_notes', 'Credit & Debit Notes'),
      ('gst_special_transactions', 'GST Special Transactions')
  ) as values_table(requirement_type, label)
  on conflict (application_id, requirement_type) do nothing;

  return query select v_firm_id, v_client_id, v_application_id;
end;
$$;

revoke execute on function public.bootstrap_user_workspace(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.bootstrap_user_workspace(uuid, text, text)
  to service_role;
