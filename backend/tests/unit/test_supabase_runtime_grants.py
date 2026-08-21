from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608200001_supabase_backend_runtime_grants.sql"
)


def test_backend_service_role_receives_runtime_table_and_sequence_privileges() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "grant usage on schema public to service_role" in sql
    assert "grant all privileges on all tables in schema public to service_role" in sql
    assert "grant all privileges on all sequences in schema public to service_role" in sql
    assert "alter default privileges in schema public" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
