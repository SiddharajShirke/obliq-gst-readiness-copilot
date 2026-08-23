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
