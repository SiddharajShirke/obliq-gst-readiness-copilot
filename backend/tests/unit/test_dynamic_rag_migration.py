from __future__ import annotations

from pathlib import Path


def test_dynamic_rag_migration_has_scoped_action_proposals_and_rls() -> None:
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "202608230004_dynamic_agentic_rag.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create table if not exists public.assistant_action_proposals" in migration
    assert "references public.applications" in migration
    assert "references auth.users" in migration
    assert "pending_confirmation" in migration
    assert "executed" in migration
    assert "expires_at" in migration
    assert "enable row level security" in migration
    assert "auth.uid()" in migration
    assert "service_role" in migration

