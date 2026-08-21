from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE_MIGRATION = (
    ROOT / "supabase" / "migrations" / "202608190001_twilio_whatsapp_demo_sessions.sql"
)
VONAGE_MIGRATION = (
    ROOT / "supabase" / "migrations" / "202608200002_vonage_whatsapp_transport.sql"
)


def test_original_session_migration_still_protects_isolated_demo_data() -> None:
    sql = BASE_MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table public.whatsapp_demo_sessions" in sql
    assert "judge_phone_hash text" in sql
    assert "judge_phone_encrypted text" in sql
    assert "judge_phone_last_four text" in sql
    assert "add column demo_session_id uuid" in sql
    assert "where demo_session_id is null" in sql
    assert "create unique index whatsapp_messages_provider_message_id_uidx" in sql
    assert "(provider, provider_message_id)" in sql


def test_vonage_migration_preserves_history_and_generalizes_provider_identity() -> None:
    sql = VONAGE_MIGRATION.read_text(encoding="utf-8").lower()

    assert "rename column twilio_wa_id_hash to provider_user_id_hash" in sql
    assert "provider in ('twilio', 'vonage', 'mock')" in sql
    assert "delete from public.whatsapp_messages" not in sql
    assert "delete from public.integration_settings" not in sql
    assert "p_provider_user_id_hash text" in sql
    assert "provider_user_id_hash = p_provider_user_id_hash" in sql


def test_vonage_binding_rpc_remains_service_role_only() -> None:
    sql = VONAGE_MIGRATION.read_text(encoding="utf-8").lower()

    signature = "text, text, text, text, text, timestamptz"
    assert f"revoke execute on function public.bind_whatsapp_demo_session(\n  {signature}" in sql
    assert f"grant execute on function public.bind_whatsapp_demo_session(\n  {signature}" in sql
    assert ") from public, anon, authenticated" in sql
    assert ") to service_role" in sql
    assert "security definer" in sql
