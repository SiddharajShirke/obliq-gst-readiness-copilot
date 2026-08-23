from __future__ import annotations

from pathlib import Path


def test_invoice_records_review_notes_migration_is_forward_only() -> None:
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "202608230005_invoice_record_review_notes.sql"
    ).read_text(encoding="utf-8").lower()

    assert "alter table public.invoice_records" in migration
    assert "add column if not exists review_notes text" in migration
    assert "notify pgrst, 'reload schema'" in migration


def test_invoice_records_review_audit_columns_are_added_forward_only() -> None:
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "202608230006_invoice_record_review_audit.sql"
    ).read_text(encoding="utf-8").lower()

    assert "alter table public.invoice_records" in migration
    assert "add column if not exists reviewed_by uuid" in migration
    assert "references auth.users(id) on delete set null" in migration
    assert "add column if not exists reviewed_at timestamptz" in migration
    assert "notify pgrst, 'reload schema'" in migration
