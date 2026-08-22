from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608220001_secure_gst_document_intake.sql"
)
CONNECTIVITY_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608220002_phase2_connectivity.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_phase2_migration_scopes_upload_links_and_document_metadata() -> None:
    sql = _sql()

    for fragment in (
        "add column firm_id uuid",
        "add column demo_session_id uuid",
        "add column requirement_id uuid",
        "add column safe_name text",
        "add column storage_bucket text",
        "add column upload_completed_at timestamptz",
        "'awaiting_processing'",
        "documents_secure_link_sha256_uidx",
    ):
        assert fragment in sql


def test_phase2_finalize_rpc_is_service_role_only_and_checks_scope() -> None:
    sql = _sql()

    assert "create function public.complete_secure_document_upload" in sql
    assert "security definer" in sql
    assert "session_application_id = p_application_id" in sql
    assert "application_id = p_application_id" in sql
    assert "revoke execute on function public.complete_secure_document_upload" in sql
    assert "from public, anon, authenticated" in sql
    assert "grant execute on function public.complete_secure_document_upload" in sql
    assert "to service_role" in sql


def test_phase2_migration_keeps_gst_storage_private() -> None:
    sql = _sql()

    assert "update storage.buckets" in sql
    assert "set public = false" in sql
    assert "where id = 'gst-documents'" in sql
    assert "to anon" not in sql


def test_phase2_connectivity_migration_scopes_requests_to_retained_sessions() -> None:
    sql = CONNECTIVITY_MIGRATION.read_text(encoding="utf-8").lower()

    for fragment in (
        "add column base_application_id uuid",
        "add column demo_session_id uuid",
        "add column upload_link_id uuid",
        "add column provider_message_id text",
        "reminders_demo_session_created_idx",
        "reminders_provider_message_id_uidx",
    ):
        assert fragment in sql
