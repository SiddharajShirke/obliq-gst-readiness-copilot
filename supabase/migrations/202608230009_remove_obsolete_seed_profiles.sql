-- Remove only the four obsolete fixed seed profiles. Raj Traders remains the
-- tenant Guided Demo template; user-created clients and PHASE 2 are untouched.
delete from public.clients
where (id, business_name) in (
  ('20000000-0000-0000-0000-000000000002'::uuid, 'ABC Electronics'),
  ('20000000-0000-0000-0000-000000000003'::uuid, 'Nova Services'),
  ('20000000-0000-0000-0000-000000000004'::uuid, 'City Retail'),
  ('20000000-0000-0000-0000-000000000005'::uuid, 'Mehta Consulting')
);
