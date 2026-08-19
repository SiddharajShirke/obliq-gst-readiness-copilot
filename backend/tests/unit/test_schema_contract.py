from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "supabase" / "migrations" / "202608180001_initial_schema.sql"


def _schema_sql() -> str:
    return SCHEMA.read_text(encoding="utf-8").lower()


def test_clients_schema_supports_seeded_demo_scenario() -> None:
    sql = _schema_sql()

    clients_start = sql.index("create table if not exists public.clients")
    clients_end = sql.index("create table if not exists public.applications")
    clients_block = sql[clients_start:clients_end]

    assert "demo_scenario text" in clients_block


def test_auth_user_creation_populates_profiles() -> None:
    sql = _schema_sql()

    assert sql.count("create or replace function public.handle_new_user()") == 1
    assert "on conflict (id) do update" in sql
    assert "after insert on auth.users" in sql
    assert "execute function public.handle_new_user()" in sql
