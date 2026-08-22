-- Phase 3 normalized GST records preserve absent monetary fields as NULL.
-- The initial prototype schema defaulted missing amounts to zero, which can
-- incorrectly turn an unknown value into business evidence.

alter table public.invoice_records
  alter column taxable_value drop not null,
  alter column taxable_value drop default,
  alter column cgst drop not null,
  alter column cgst drop default,
  alter column sgst drop not null,
  alter column sgst drop default,
  alter column igst drop not null,
  alter column igst drop default,
  alter column cess drop not null,
  alter column cess drop default,
  alter column invoice_total drop not null,
  alter column invoice_total drop default;
